import argparse
import io
import sys


def _force_utf8_stdio() -> None:
    """Ensure stdout/stderr use UTF-8 on Windows (CP1252 default breaks MCP stdio)."""
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def main():
    """
    Main entry point for the mcp-server-qdrant script defined
    in pyproject.toml. It runs the MCP server with a specific transport
    protocol.
    """
    _force_utf8_stdio()

    # Parse the command-line arguments to determine the transport protocol.
    parser = argparse.ArgumentParser(description="mcp-server-qdrant")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
    )
    args = parser.parse_args()

    # Import is done here to make sure environment variables are loaded
    # only after we make the changes.
    from mcp_server_qdrant.server import mcp

    mcp.run(transport=args.transport)
