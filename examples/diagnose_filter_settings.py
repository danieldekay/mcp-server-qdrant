#!/usr/bin/env python3
"""
Diagnostic script to verify filterable_fields settings initialization.

This script helps identify why PDF metadata filter parameters might not be
exposed in the MCP tool signature.

Usage:
    uv run python examples/diagnose_filter_settings.py
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcp_server_qdrant.constants import PDFMetadataKeys
from mcp_server_qdrant.settings import QdrantSettings, FilterableField


def main():
    print("=" * 80)
    print("PDF Metadata Filter Settings Diagnostic")
    print("=" * 80)
    print()

    # Check environment variables
    print("1. Environment Variables:")
    print("-" * 80)
    env_vars = {
        "QDRANT_URL": os.getenv("QDRANT_URL"),
        "COLLECTION_NAME": os.getenv("COLLECTION_NAME"),
        "QDRANT_ALLOW_ARBITRARY_FILTER": os.getenv("QDRANT_ALLOW_ARBITRARY_FILTER"),
    }
    for key, value in env_vars.items():
        print(f"   {key}: {value or '(not set)'}")
    print()

    # Check for any filterable_fields related env vars
    print("2. Filter-Related Environment Variables:")
    print("-" * 80)
    for key, value in os.environ.items():
        if "FILTER" in key.upper() or "FILTERABLE" in key.upper():
            print(f"   {key}: {value}")
    if not any(
        "FILTER" in k.upper() or "FILTERABLE" in k.upper() for k in os.environ.keys()
    ):
        print("   (none found)")
    print()

    # Initialize settings
    print("3. QdrantSettings Initialization:")
    print("-" * 80)
    try:
        settings = QdrantSettings()
        print("   ✅ Settings initialized successfully")
    except Exception as e:
        print(f"   ❌ Failed to initialize settings: {e}")
        return 1
    print()

    # Check filterable_fields
    print("4. filterable_fields Value:")
    print("-" * 80)
    if settings.filterable_fields is None:
        print("   ❌ filterable_fields is None")
        print("   This is the ROOT CAUSE - defaults not applied!")
        print()
        print("   Expected: List of 3 FilterableField objects")
        print("   Actual: None")
    elif not settings.filterable_fields:
        print("   ❌ filterable_fields is empty list")
        print("   Expected: List of 3 FilterableField objects")
        print("   Actual: []")
    else:
        print(f"   ✅ filterable_fields has {len(settings.filterable_fields)} fields")
        for i, field in enumerate(settings.filterable_fields, 1):
            print(f"      {i}. {field.name}")
            print(f"         - Type: {field.field_type}")
            print(f"         - Condition: {field.condition}")
            print(f"         - Required: {field.required}")
            print(f"         - Description: {field.description[:50]}...")
    print()

    # Check PDF metadata fields specifically
    print("5. PDF Metadata Fields Check:")
    print("-" * 80)
    expected_fields = [
        PDFMetadataKeys.DOCUMENT_ID,
        PDFMetadataKeys.PHYSICAL_PAGE_INDEX,
        PDFMetadataKeys.PAGE_LABEL,
    ]

    if settings.filterable_fields:
        field_names = {f.name for f in settings.filterable_fields}
        for expected in expected_fields:
            if expected in field_names:
                field = next(
                    f for f in settings.filterable_fields if f.name == expected
                )
                status = "✅" if field.condition else "⚠️"
                print(f"   {status} {expected}: condition='{field.condition}'")
            else:
                print(f"   ❌ {expected}: NOT FOUND")
    else:
        print("   ❌ Cannot check - filterable_fields is None or empty")
    print()

    # Check filterable_fields_dict_with_conditions
    print("6. filterable_fields_dict_with_conditions():")
    print("-" * 80)
    conditions = settings.filterable_fields_dict_with_conditions()
    print(f"   Fields with conditions: {len(conditions)}")

    if len(conditions) == 0:
        print("   ❌ PROBLEM: No fields with conditions!")
        print("   This means wrap_filters() will NOT be applied")
        print("   Expected: 3 fields (document_id, physical_page_index, page_label)")
    else:
        print("   ✅ Fields with conditions found:")
        for name, field in conditions.items():
            print(f"      - {name} ({field.field_type}, condition='{field.condition}')")
    print()

    # Check if wrap_filters would be applied
    print("7. Tool Registration Simulation:")
    print("-" * 80)
    if len(conditions) > 0:
        print("   ✅ wrap_filters() WOULD BE APPLIED")
        print(f"   Filter parameters would be exposed: {list(conditions.keys())}")
    else:
        if settings.allow_arbitrary_filter:
            print("   ⚠️ wrap_filters() NOT applied (no conditions)")
            print("   query_filter parameter exposed as ArbitraryFilter")
        else:
            print("   ❌ wrap_filters() NOT applied (no conditions)")
            print("   query_filter parameter removed (set to None)")
    print()

    # Final diagnosis
    print("8. Final Diagnosis:")
    print("-" * 80)

    if settings.filterable_fields is None:
        print("   🔴 ISSUE IDENTIFIED: filterable_fields is None")
        print()
        print("   Root Cause:")
        print("   - Pydantic BaseSettings did not apply default value")
        print("   - Likely due to environment variable override or Pydantic quirk")
        print()
        print("   Solution:")
        print("   - Use default_factory instead of default=")
        print("   - Add field_validator to ensure non-None value")
        print()
        return 1

    elif len(conditions) == 0:
        print("   🔴 ISSUE IDENTIFIED: No fields have conditions defined")
        print()
        print("   Root Cause:")
        print("   - filterable_fields exist but conditions are None")
        print()
        print("   Solution:")
        print("   - Verify FilterableField definitions include condition parameter")
        print()
        return 1

    elif len(conditions) < 3:
        print("   🟡 PARTIAL ISSUE: Some fields missing")
        print(f"   - Expected 3 fields, found {len(conditions)}")
        print(f"   - Missing: {set(expected_fields) - set(conditions.keys())}")
        print()
        return 1

    else:
        print("   🟢 ALL CHECKS PASSED")
        print("   - filterable_fields is properly initialized")
        print("   - All 3 PDF metadata fields have conditions")
        print("   - wrap_filters() will be applied correctly")
        print()
        print("   If parameters still not exposed, check:")
        print("   - FastMCP tool introspection")
        print("   - MCP protocol serialization")
        print("   - make_partial_function() interaction")
        print()
        return 0


if __name__ == "__main__":
    sys.exit(main())
