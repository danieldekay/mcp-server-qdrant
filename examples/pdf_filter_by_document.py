#!/usr/bin/env python
"""Example: Filter Qdrant search by document_id using MCP tool schema.

Run:
uv run python examples/pdf_filter_by_document.py
"""

import asyncio
from mcp_server_qdrant.server import mcp


async def main():
    # Use the internal tool invocation pattern: FastMCP provides a run_tool helper
    # We'll look up the qdrant-find tool and invoke it programmatically
    tools = await mcp.get_tools()
    find_tool = (
        tools.get("qdrant-find")
        if isinstance(tools, dict)
        else next((t for t in tools if getattr(t, "name", None) == "qdrant-find"), None)
    )
    if not find_tool:
        print("qdrant-find tool not found")
        return

    args = {"query": "test", "collection_name": None, "document_id": "example.pdf"}

    # The FunctionTool exposes a 'run' method which accepts kwargs
    result = await find_tool.run(**args)
    print("Result:", result)


if __name__ == "__main__":
    asyncio.run(main())
