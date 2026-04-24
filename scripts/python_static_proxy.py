#!/usr/bin/env python3
"""Small static file server with a same-origin /api reverse proxy.

This is the no-Node runtime companion to scripts/node_static_proxy.mjs. It is
intended for production-like static hosting of built Vite apps on small hosts.
"""

from __future__ import annotations

import argparse
import http.client
import json
import mimetypes
import os
import posixpath
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar


HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


class StaticProxyHandler(BaseHTTPRequestHandler):
    root: ClassVar[Path]
    api_base: ClassVar[urllib.parse.ParseResult]

    server_version = "PODIStaticProxy/1.0"

    def do_GET(self) -> None:
        self._handle()

    def do_HEAD(self) -> None:
        self._handle(head_only=True)

    def do_POST(self) -> None:
        self._handle()

    def do_PUT(self) -> None:
        self._handle()

    def do_PATCH(self) -> None:
        self._handle()

    def do_DELETE(self) -> None:
        self._handle()

    def _handle(self, *, head_only: bool = False) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path.startswith("/api/"):
            self._proxy_api(parsed, head_only=head_only)
            return
        self._serve_static(parsed.path, head_only=head_only)

    def _proxy_api(self, parsed: urllib.parse.SplitResult, *, head_only: bool) -> None:
        upstream_path = urllib.parse.urlunsplit(("", "", parsed.path, parsed.query, ""))
        body_len = int(self.headers.get("content-length") or "0")
        body = self.rfile.read(body_len) if body_len > 0 else None
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in HOP_BY_HOP_HEADERS and key.lower() != "host"
        }
        headers["Host"] = self.api_base.netloc
        conn_class = http.client.HTTPSConnection if self.api_base.scheme == "https" else http.client.HTTPConnection
        try:
            conn = conn_class(self.api_base.hostname, self.api_base.port, timeout=120)
            conn.request(self.command, upstream_path, body=body, headers=headers)
            resp = conn.getresponse()
            resp_body = resp.read()
        except Exception as exc:
            self._send_json(502, {"detail": str(exc)}, head_only=head_only)
            return
        finally:
            try:
                conn.close()
            except Exception:
                pass

        self.send_response(resp.status)
        for key, value in resp.getheaders():
            if key.lower() not in HOP_BY_HOP_HEADERS:
                self.send_header(key, value)
        self.end_headers()
        if not head_only:
            self.wfile.write(resp_body)

    def _serve_static(self, raw_path: str, *, head_only: bool) -> None:
        rel = posixpath.normpath(urllib.parse.unquote(raw_path)).lstrip("/")
        if rel == ".":
            rel = ""
        candidate = (self.root / rel).resolve()
        root_resolved = self.root.resolve()
        if root_resolved not in candidate.parents and candidate != root_resolved:
            self._send_json(403, {"detail": "Forbidden"}, head_only=head_only)
            return

        if candidate.is_dir():
            candidate = candidate / "index.html"
        if not candidate.is_file():
            candidate = root_resolved / "index.html"
        if not candidate.is_file():
            self._send_json(404, {"detail": "Not Found"}, head_only=head_only)
            return

        content_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        if candidate.name == "index.html":
            self.send_header("Cache-Control", "no-store")
        elif "assets" in candidate.parts:
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        else:
            self.send_header("Cache-Control", "public, max-age=60")
        self.send_header("Content-Length", str(candidate.stat().st_size))
        self.end_headers()
        if not head_only:
            with candidate.open("rb") as fh:
                self.wfile.write(fh.read())

    def _send_json(self, status: int, payload: dict[str, object], *, head_only: bool) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head_only:
            self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), fmt % args))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--api", default="http://127.0.0.1:8099")
    args = parser.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        raise SystemExit(f"static root not found: {root}")

    api_base = urllib.parse.urlparse(args.api)
    if api_base.scheme not in {"http", "https"} or not api_base.hostname:
        raise SystemExit(f"invalid api base: {args.api}")

    StaticProxyHandler.root = root
    StaticProxyHandler.api_base = api_base
    mimetypes.add_type("application/javascript; charset=utf-8", ".js")
    mimetypes.add_type("text/css; charset=utf-8", ".css")
    server = ThreadingHTTPServer(("0.0.0.0", args.port), StaticProxyHandler)
    print(f"[static-proxy] pid={os.getpid()} root={root} port={args.port} api={args.api}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
