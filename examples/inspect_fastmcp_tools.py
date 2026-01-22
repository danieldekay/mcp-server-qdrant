#!/usr/bin/env python3
"""
Inspect what FastMCP actually sees when the server is instantiated.

This directly imports the mcp server instance and checks its tool registration.

Usage:
    uv run python examples/inspect_fastmcp_tools.py
"""

import inspect
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def main():
    print("=" * 80)
    print("FastMCP Tool Registration Inspection")
    print("=" * 80)
    print()

    # Import the actual server instance
    print("1. Importing server instance...")
    print("-" * 80)
    try:
        from mcp_server_qdrant.server import mcp

        print("   ✅ Server imported successfully")
    except Exception as e:
        print(f"   ❌ Failed to import server: {e}")
        import traceback

        traceback.print_exc()
        return 1
    print()

    # Check if it's a FastMCP instance
    print("2. Server Instance Type:")
    print("-" * 80)
    print(f"   Type: {type(mcp)}")
    print(f"   Class: {mcp.__class__.__name__}")
    print()

    # Try to inspect registered tools
    print("3. Registered Tools:")
    print("-" * 80)

    # FastMCP stores tools in _tool_manager
    if hasattr(mcp, "_tool_manager"):
        tool_manager = mcp._tool_manager
        print(f"   Tool manager type: {type(tool_manager)}")

        if hasattr(tool_manager, "tools"):
            tools = tool_manager.tools
            print(f"   Number of tools: {len(tools)}")
            print()

            for tool_name, tool in tools.items():
                print(f"   Tool: {tool_name}")
                print(f"      Type: {type(tool)}")

                # Check if tool has a function
                if hasattr(tool, "fn"):
                    fn = tool.fn
                    print(f"      Function: {fn.__name__}")

                    # Inspect signature
                    sig = inspect.signature(fn)
                    params = list(sig.parameters.keys())
                    print(f"      Parameters: {params}")

                    # Check for PDF filter params
                    expected_filters = [
                        "document_id",
                        "physical_page_index",
                        "page_label",
                    ]
                    found_filters = [p for p in expected_filters if p in params]
                    missing_filters = [p for p in expected_filters if p not in params]

                    if tool_name == "qdrant-find":
                        print(f"      Found filter params: {found_filters or '(none)'}")
                        if missing_filters:
                            print(f"      ❌ Missing filter params: {missing_filters}")
                        else:
                            print(f"      ✅ All filter params present!")

                # Check if tool has schema
                if hasattr(tool, "input_schema") or hasattr(tool, "inputSchema"):
                    schema = getattr(tool, "input_schema", None) or getattr(
                        tool, "inputSchema", None
                    )
                    if schema:
                        print(f"      Input Schema Type: {type(schema)}")
                        if hasattr(schema, "model_json_schema"):
                            json_schema = schema.model_json_schema()
                            if "properties" in json_schema:
                                schema_params = list(json_schema["properties"].keys())
                                print(f"      Schema parameters: {schema_params}")

                                if tool_name == "qdrant-find":
                                    found = [
                                        p
                                        for p in expected_filters
                                        if p in schema_params
                                    ]
                                    missing = [
                                        p
                                        for p in expected_filters
                                        if p not in schema_params
                                    ]
                                    print(
                                        f"      Schema has filter params: {found or '(none)'}"
                                    )
                                    if missing:
                                        print(f"      ❌ Schema missing: {missing}")
                                    else:
                                        print(f"      ✅ Schema has all filter params!")

                print()
        else:
            print("   ⚠️ Tool manager has no 'tools' attribute")
    else:
        print("   ⚠️ Server has no '_tool_manager' attribute")
        # Try alternative attributes
        for attr in dir(mcp):
            if "tool" in attr.lower():
                print(f"   Found attribute: {attr}")

    print()
    print("=" * 80)
    print("Inspection Complete")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
