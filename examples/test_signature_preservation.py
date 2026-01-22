#!/usr/bin/env python3
"""
Test script to verify that wrap_filters + make_partial_function preserves signatures.

This tests the actual wrapping mechanism used in mcp_server.py.

Usage:
    uv run python examples/test_signature_preservation.py
"""

import inspect
import sys
from pathlib import Path
from typing import Annotated

from pydantic import Field

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcp_server_qdrant.common.wrap_filters import wrap_filters
from mcp_server_qdrant.common.func_tools import make_partial_function
from mcp_server_qdrant.settings import FilterableField


def test_original_function():
    """Original find function signature."""

    def find(
        query: Annotated[str, Field(description="What to search for")],
        collection_name: Annotated[
            str, Field(description="The collection to search in")
        ],
        query_filter: dict | None = None,
    ) -> list[str]:
        return [f"query={query}, collection={collection_name}, filter={query_filter}"]

    return find


def main():
    print("=" * 80)
    print("Signature Preservation Test")
    print("=" * 80)
    print()

    # Define filterable fields (same as in settings.py)
    filterable_fields = {
        "document_id": FilterableField(
            name="document_id",
            description="The unique identifier of the document",
            field_type="keyword",
            condition="==",
        ),
        "physical_page_index": FilterableField(
            name="physical_page_index",
            description="The 0-based physical index of the page",
            field_type="integer",
            condition="==",
        ),
        "page_label": FilterableField(
            name="page_label",
            description="The original page numbering label",
            field_type="keyword",
            condition="==",
        ),
    }

    # Step 1: Original function
    print("1. Original Function Signature:")
    print("-" * 80)
    find_original = test_original_function()
    sig = inspect.signature(find_original)
    print(f"   Parameters: {list(sig.parameters.keys())}")
    print(f"   Signature: {sig}")
    print()

    # Step 2: After wrap_filters
    print("2. After wrap_filters():")
    print("-" * 80)
    find_wrapped = wrap_filters(find_original, filterable_fields)
    sig = inspect.signature(find_wrapped)
    params = list(sig.parameters.keys())
    print(f"   Parameters: {params}")
    print(f"   Signature: {sig}")
    print()

    # Check if filter params are added
    expected_params = [
        "query",
        "collection_name",
        "document_id",
        "physical_page_index",
        "page_label",
    ]
    missing = set(expected_params) - set(params)
    extra = set(params) - set(expected_params)

    if missing:
        print(f"   ❌ Missing parameters: {missing}")
    if extra:
        print(f"   ⚠️ Extra parameters: {extra}")
    if not missing and not extra:
        print("   ✅ All expected parameters present!")
    print()

    # Step 3: After make_partial_function (collection_name fixed)
    print("3. After make_partial_function(collection_name='test-collection'):")
    print("-" * 80)
    find_partial = make_partial_function(
        find_wrapped, {"collection_name": "test-collection"}
    )
    sig = inspect.signature(find_partial)
    params = list(sig.parameters.keys())
    print(f"   Parameters: {params}")
    print(f"   Signature: {sig}")
    print()

    # Check if filter params are still there
    expected_params_partial = [
        "query",
        "document_id",
        "physical_page_index",
        "page_label",
    ]
    missing = set(expected_params_partial) - set(params)
    extra = set(params) - set(expected_params_partial)

    if missing:
        print(f"   ❌ PROBLEM: Missing parameters: {missing}")
        print("   This is why filters aren't exposed!")
        return 1
    if extra:
        print(f"   ⚠️ Extra parameters: {extra}")
    if not missing and not extra:
        print("   ✅ All expected parameters still present!")
    print()

    # Step 4: Test actual function call
    print("4. Function Call Test:")
    print("-" * 80)
    try:
        result = find_partial(
            query="test query",
            document_id="doc123",
            physical_page_index=5,
            page_label="vi",
        )
        print(f"   ✅ Call succeeded: {result}")
        print()
        return 0
    except Exception as e:
        print(f"   ❌ Call failed: {e}")
        import traceback

        traceback.print_exc()
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
