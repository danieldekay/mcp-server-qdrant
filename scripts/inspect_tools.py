#!/usr/bin/env python

import asyncio
from mcp_server_qdrant.server import mcp


async def main():
    tools_getter = getattr(mcp, "list_tools", None) or getattr(mcp, "get_tools", None)
    tools = await tools_getter()
    print("tools repr:", repr(tools))
    # If tools is a dict, inspect the FunctionTool object
    if isinstance(tools, dict):
        ft = tools.get("qdrant-find")
        print("FunctionTool repr:", repr(ft))
        if ft is not None:
            print("FunctionTool dir:", [a for a in dir(ft) if not a.startswith("_")])
            # Try to access known attributes
            for attr in (
                "name",
                "description",
                "description_template",
                "inputSchema",
                "input_schema",
                "schema",
                "get_schema",
                "parameters",
            ):
                try:
                    val = getattr(ft, attr)
                    if callable(val):
                        val = val()
                    print(
                        f"  {attr}:",
                        type(val),
                        (list(val.keys()) if hasattr(val, "keys") else val),
                    )
                except Exception as e:
                    print(f"  {attr}: <error calling attribute: {e}>")

    for t in tools:
        print("tool repr:", repr(t), "type", type(t))
        print("  dir:", [a for a in dir(t) if not a.startswith("_")])
        try:
            print("  name:", getattr(t, "name", None))
        except Exception:
            pass
        # Try common attributes that may contain schema info
        for attr in ("input_schema", "schema", "inputSchema", "get_schema"):
            if hasattr(t, attr):
                print(f"  has {attr}:", getattr(t, attr))


if __name__ == "__main__":
    asyncio.run(main())
