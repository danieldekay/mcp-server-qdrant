#!/usr/bin/env python
"""Verification script to check if PDF filter parameters are exposed in MCP tool schema."""

import sys
from mcp_server_qdrant.server import mcp
import json


def main():
    # Get the tool list
    tools = list(mcp.list_tools())
    print("Available tools:")
    for tool in tools:
        print(f"  - {tool.name}")

    # Find qdrant-find tool
    find_tool = next((t for t in tools if t.name == "qdrant-find"), None)
    if not find_tool:
        print("ERROR: qdrant-find tool not found!")
        sys.exit(1)

    print(f"\n{'=' * 60}")
    print("qdrant-find Tool Schema")
    print("=" * 60)
    print(f"\nDescription: {find_tool.description[:100]}...")

    print(f"\nInput Schema Properties:")
    props = find_tool.inputSchema.get("properties", {})

    for param in sorted(props.keys()):
        schema = props[param]
        ptype = schema.get("type", schema.get("anyOf", "unknown"))
        desc = schema.get("description", "No description")
        required = param in find_tool.inputSchema.get("required", [])
        req_marker = "[REQUIRED]" if required else "[OPTIONAL]"
        print(f"\n  {req_marker} {param}:")
        print(f"    Type: {ptype}")
        print(f"    Description: {desc[:80]}")

    print(f"\n{'=' * 60}")
    print(f"Total parameters: {len(props)}")
    print(f"Required parameters: {find_tool.inputSchema.get('required', [])}")

    # Check for PDF filter parameters
    pdf_filters = ["document_id", "physical_page_index", "page_label"]
    print(f"\n{'=' * 60}")
    print("PDF Filter Parameters Status:")
    print("=" * 60)

    all_present = True
    for pf in pdf_filters:
        if pf in props:
            print(f"  ✓ {pf} - PRESENT")
        else:
            print(f"  ✗ {pf} - MISSING")
            all_present = False

    print(f"\n{'=' * 60}")
    if all_present:
        print("✅ SUCCESS: All PDF filter parameters are present!")
        return 0
    else:
        print("❌ FAILURE: Some PDF filter parameters are missing!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
