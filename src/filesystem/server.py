"""Filesystem MCP Server with Streamable HTTP support."""

import argparse
import logging
from pathlib import Path

import uvicorn
from fastmcp import FastMCP

from . import tools, utils

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")

mcp = FastMCP(
    name="filesystem",
)

tools.register_tools(mcp)


def main() -> None:
    """Run the filesystem MCP server."""
    parser = argparse.ArgumentParser(description="Filesystem MCP Server with Streamable HTTP support")
    parser.add_argument(
        "--port",
        type=int,
        default=8123,
        help="Port to listen on (default: 8123)",
    )
    parser.add_argument(
        "--allowed-root",
        type=str,
        default=".",
        help="Root directory for filesystem operations (default: current directory)",
    )
    args = parser.parse_args()

    utils.ALLOWED_ROOT = Path(args.allowed_root).resolve()

    if not utils.ALLOWED_ROOT.exists():
        logger.error("Allowed root directory does not exist: %s", utils.ALLOWED_ROOT)
        exit(1)

    if not utils.ALLOWED_ROOT.is_dir():
        logger.error("Allowed root is not a directory: %s", utils.ALLOWED_ROOT)
        exit(1)

    logger.info("Starting Filesystem MCP Server")
    logger.info("Allowed root: %s", utils.ALLOWED_ROOT)
    logger.info("Listening on: http://0.0.0.0:%s/mcp", args.port)

    app = mcp.http_app(
        transport="streamable-http",
    )

    # Run with uvicorn - this properly manages the FastMCP lifespan
    uvicorn.run(app, host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
