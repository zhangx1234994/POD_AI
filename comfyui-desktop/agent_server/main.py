"""Entrypoint for desktop agent HTTP server."""

from __future__ import annotations

import uvicorn

from agent_core.config import load_config


def main() -> None:
    cfg = load_config()
    uvicorn.run("agent_server.app:app", host="0.0.0.0", port=int(cfg.agent_port or 18079), reload=False)


if __name__ == "__main__":
    main()
