"""
Sprint MCP server — standalone entry point.

Run:
    PYTHONPATH=. python -m sprint_mcp.main          # default port 8001
    PYTHONPATH=. python -m sprint_mcp.main --port 8001

In Cloud Shell:
    PYTHONPATH=. uvicorn sprint_mcp.main:asgi_app --host 0.0.0.0 --port 8001
"""

from __future__ import annotations

import argparse
import logging

from sprint_mcp.mcp_connector import mcp_app

logger = logging.getLogger(__name__)

# ASGI app — used when mounting in FastAPI (Phase 2) or running via uvicorn directly.
asgi_app = mcp_app.streamable_http_app()


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="Sprint MCP server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--log-level", default="info")
    args = parser.parse_args()

    logging.basicConfig(level=args.log_level.upper())
    logger.info("Starting Sprint MCP server on %s:%s", args.host, args.port)
    uvicorn.run(asgi_app, host=args.host, port=args.port, log_level=args.log_level)


if __name__ == "__main__":
    main()
