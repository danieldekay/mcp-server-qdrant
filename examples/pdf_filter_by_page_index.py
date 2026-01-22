#!/usr/bin/env python
"""Example: Filter Qdrant search by physical_page_index (0-based).

Run:
uv run python examples/pdf_filter_by_page_index.py
"""

import asyncio
from mcp_server_qdrant.server import mcp


async def main():
    tools = await mcp.get_tools()
    find_tool = (
        tools.get("qdrant-find")
        if isinstance(tools, dict)
        else next((t for t in tools if getattr(t, "name", None) == "qdrant-find"), None)
    )
    if not find_tool:
        print("qdrant-find tool not found")
        return

    args = {
        "query": "introduction",
        "collection_name": None,
        "physical_page_index": 0,
    }

    result = await find_tool.run(args)
    print("Result:", result)


if __name__ == "__main__":
    asyncio.run(main())
