#!/usr/bin/env python3
"""
Deep inspection of FastMCP's tool registration internals.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def main():
    from mcp_server_qdrant.server import mcp

    print("FastMCP ToolManager Attributes:")
    print("=" * 80)

    tm = mcp._tool_manager

    for attr in sorted(dir(tm)):
        if not attr.startswith("_"):
            value = getattr(tm, attr, None)
            print(f"{attr}: {type(value).__name__}")

            if attr == "list_tools" and callable(value):
                # Try calling it
                try:
                    result = value()
                    print(f"  → Returns: {type(result)}")
                    if hasattr(result, "__iter__"):
                        print(f"  → Length: {len(list(result))}")
                except Exception as e:
                    print(f"  → Error: {e}")

    print()
    print("Trying to get tools list:")
    print("-" * 80)

    # Try different methods to get tools
    methods = ["list_tools", "get_tools", "tools", "_tools"]

    for method_name in methods:
        if hasattr(tm, method_name):
            attr = getattr(tm, method_name)
            print(f"\n{method_name}:")

            if callable(attr):
                try:
                    result = attr()
                    print(f"  Type: {type(result)}")

                    if isinstance(result, list):
                        print(f"  Count: {len(result)}")
                        for tool in result:
                            print(f"  - {tool}")
                            if hasattr(tool, "name"):
                                print(f"    Name: {tool.name}")
                            if hasattr(tool, "inputSchema"):
                                schema = tool.inputSchema
                                if hasattr(schema, "properties"):
                                    print(
                                        f"    Properties: {list(schema.properties.keys())}"
                                    )
                except Exception as e:
                    print(f"  Error: {e}")
            else:
                print(f"  Value: {attr}")
                if isinstance(attr, dict):
                    print(f"  Keys: {list(attr.keys())}")


if __name__ == "__main__":
    main()
