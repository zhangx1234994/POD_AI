// Minimal static file server with a built-in /api reverse proxy.
// - No external deps (works on any Node >= 18).
// - SPA fallback to index.html.
// - Avoids "VITE_API_BASE_URL drift" by keeping API calls same-origin: /api/*
//
// Usage:
//   node scripts/node_static_proxy.mjs --root podi-admin-web/dist --port 8199 --api http://127.0.0.1:8099
//
import http from 'node:http';
import https from 'node:https';
import { createReadStream, promises as fsp } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function parseArgs(argv) {
  const out = {};
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith('--')) continue;
    const key = a.slice(2);
    const next = argv[i + 1];
    if (next && !next.startsWith('--')) {
      out[key] = next;
      i++;
    } else {
      out[key] = true;
    }
  }
  return out;
}

function guessContentType(p) {
  const ext = path.extname(p).toLowerCase();
  switch (ext) {
    case '.html':
      return 'text/html; charset=utf-8';
    case '.js':
      return 'application/javascript; charset=utf-8';
    case '.css':
      return 'text/css; charset=utf-8';
    case '.json':
      return 'application/json; charset=utf-8';
    case '.svg':
      return 'image/svg+xml';
    case '.png':
      return 'image/png';
    case '.jpg':
    case '.jpeg':
      return 'image/jpeg';
    case '.webp':
      return 'image/webp';
    case '.ico':
      return 'image/x-icon';
    case '.woff':
      return 'font/woff';
    case '.woff2':
      return 'font/woff2';
    default:
      return 'application/octet-stream';
  }
}

function send(res, status, headers, body) {
  res.writeHead(status, headers);
  res.end(body);
}

const args = parseArgs(process.argv);
const root = path.resolve(__dirname, '..', String(args.root || 'dist'));
const port = Number(args.port || 8199);
const apiBase = String(args.api || 'http://127.0.0.1:8099');

const apiUrl = new URL(apiBase);
const apiClient = apiUrl.protocol === 'https:' ? https : http;

const server = http.createServer(async (req, res) => {
  try {
    const method = req.method || 'GET';
    const url = new URL(req.url || '/', `http://${req.headers.host || 'localhost'}`);
    const pathname = decodeURIComponent(url.pathname);

    // API reverse proxy (same-origin /api/*).
    if (pathname.startsWith('/api/')) {
      const upstreamPath = pathname + url.search;
      const options = {
        protocol: apiUrl.protocol,
        hostname: apiUrl.hostname,
        port: apiUrl.port || (apiUrl.protocol === 'https:' ? 443 : 80),
        method,
        path: upstreamPath,
        headers: {
          ...req.headers,
          host: apiUrl.host,
        },
      };
      const upstreamReq = apiClient.request(options, (upstreamRes) => {
        res.writeHead(upstreamRes.statusCode || 502, upstreamRes.headers);
        upstreamRes.pipe(res);
      });
      upstreamReq.on('error', (e) => {
        send(res, 502, { 'content-type': 'application/json' }, JSON.stringify({ detail: String(e?.message || e) }));
      });
      req.pipe(upstreamReq);
      return;
    }

    // Static files (SPA fallback).
    const safePath = pathname.replace(/\0/g, '');
    const rel = safePath.startsWith('/') ? safePath.slice(1) : safePath;
    const filePath = path.join(root, rel);

    async function serveFile(p) {
      const stat = await fsp.stat(p);
      if (!stat.isFile()) throw new Error('not a file');
      const headers = {
        'content-type': guessContentType(p),
      };
      // Cache policy: index.html no-store; hashed assets immutable.
      if (p.endsWith('/index.html') || p.endsWith(path.sep + 'index.html')) {
        headers['cache-control'] = 'no-store';
      } else if (p.includes(`${path.sep}assets${path.sep}`)) {
        headers['cache-control'] = 'public, max-age=31536000, immutable';
      } else {
        headers['cache-control'] = 'public, max-age=60';
      }
      res.writeHead(200, headers);
      createReadStream(p).pipe(res);
    }

    // Direct file hit.
    try {
      await serveFile(filePath);
      return;
    } catch {}

    // SPA fallback to index.html (only for GET/HEAD).
    if (method === 'GET' || method === 'HEAD') {
      await serveFile(path.join(root, 'index.html'));
      return;
    }

    send(res, 404, { 'content-type': 'application/json' }, JSON.stringify({ detail: 'Not Found' }));
  } catch (e) {
    send(res, 500, { 'content-type': 'application/json' }, JSON.stringify({ detail: String(e?.message || e) }));
  }
});

server.listen(port, '0.0.0.0', () => {
  // eslint-disable-next-line no-console
  console.log(`[static-proxy] root=${root} port=${port} api=${apiBase}`);
});

