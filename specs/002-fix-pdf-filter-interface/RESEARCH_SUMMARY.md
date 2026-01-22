# Research Summary: PDF Filter Parameter Investigation

**Date**: 2026-01-21
**Task**: Investigate why PDF metadata filter parameters aren't exposed in qdrant-find tool
**Status**: ✅ **COMPLETE - PARAMETERS ARE WORKING!**

---

## Quick Summary

**THE FEATURE IS ALREADY WORKING!** PDF filter parameters ARE exposed in the MCP tool schema.

The user's reported issue may be due to:

1. MCP client caching old tool schemas
2. Looking at wrong tool instance
3. Environment configuration affecting initialization

---

## Critical Discovery

Inspection of the actual FastMCP tool registration reveals:

```python
qdrant-find tool parameters:
{
    'query': {...},
    'collection_name': {...},
    'document_id': {...},           # ✅ PRESENT!
    'physical_page_index': {...},  # ✅ PRESENT!
    'page_label': {...}             # ✅ PRESENT!
}
```

**All three PDF metadata filter parameters are correctly exposed in the tool schema.**

---

## What Was Investigated

### Files Analyzed

1. `settings.py` - Verified `filterable_fields` configuration
2. `mcp_server.py` - Verified `wrap_filters()` application
3. `wrap_filters.py` - Verified signature transformation logic
4. `func_tools.py` - Verified `make_partial_function()` behavior

### Tests Created

1. **`examples/diagnose_filter_settings.py`** - Settings initialization diagnostic
2. **`examples/test_signature_preservation.py`** - Signature transformation test

---

## Key Findings

### ✅ Settings Configuration (CORRECT)

**File**: `settings.py` lines 133-148

All 3 PDF metadata fields are properly configured with `condition="=="`:

```python
filterable_fields: list[FilterableField] | None = Field(
    default=[
        FilterableField(name="document_id", condition="==", ...),
        FilterableField(name="physical_page_index", condition="==", ...),
        FilterableField(name="page_label", condition="==", ...),
    ]
)
```

**Test Result**: `diagnose_filter_settings.py` confirms all checks pass.

### ✅ Filter Wrapping (CORRECT)

**File**: `mcp_server.py` lines 183-188

`wrap_filters()` is correctly applied when conditions exist:

```python
filterable_conditions = self.qdrant_settings.filterable_fields_dict_with_conditions()
if len(filterable_conditions) > 0:
    find_foo = wrap_filters(find_foo, filterable_conditions)
```

### ✅ Signature Preservation (CORRECT)

**File**: `common/wrap_filters.py` + `common/func_tools.py`

The entire transformation chain works perfectly:

1. **Original**: `find(query, collection_name, query_filter=None)`
2. **After wrap_filters**: `find(query, collection_name, document_id=None, physical_page_index=None, page_label=None)`
3. **After make_partial_function**: `find(query, document_id=None, physical_page_index=None, page_label=None)`

**Test Result**: `test_signature_preservation.py` confirms:

- ✅ Parameters added correctly
- ✅ Parameters preserved through chaining
- ✅ Function calls work with proper filter construction

---

## Root Cause (UPDATED)

**There is no bug in the code.** The PDF filter parameters are correctly exposed.

**Possible explanations for the reported issue:**

1. **MCP Client Cache**: Client may be using cached tool schema from before the parameters were added
2. **Wrong Server Instance**: User may be inspecting a different server or outdated deployment
3. **Environment Override**: `QDRANT_ALLOW_ARBITRARY_FILTER=true` would prevent `wrap_filters()` application
4. **Misinterpretation**: User may have been looking at function signature in code, not MCP tool schema

**Verification Required**: User should:

1. Restart their MCP client completely (clear any caches)
2. Re-import or reload the server connection
3. Check actual tool call to verify parameters are accepted

---

## Evidence

### Tool Registration Inspection

```bash
uv run python examples/inspect_tool_manager.py
```

**Output:**

```
qdrant-find tool parameters:
{
  'properties': {
    'query': {...},
    'collection_name': {...},
    'document_id': {
      'anyOf': [{'type': 'string'}, {'type': 'null'}],
      'default': None,
      'description': 'The unique identifier of the document'
    },
    'physical_page_index': {
      'anyOf': [{'type': 'integer'}, {'type': 'null'}],
      'default': None,
      'description': 'The 0-based physical index of the page'
    },
    'page_label': {
      'anyOf': [{'type': 'string'}, {'type': 'null'}],
      'default': None,
      'description': "The original page numbering label (e.g., 'iv', '45')"
    }
  },
  'required': ['query', 'collection_name']
}
```

✅ **All three filter parameters are present and correctly typed!**

### Settings Diagnostic

```bash
# Settings diagnostic
$ uv run python examples/diagnose_filter_settings.py
🟢 ALL CHECKS PASSED
   - filterable_fields is properly initialized
   - All 3 PDF metadata fields have conditions
   - wrap_filters() will be applied correctly
```

### Signature Preservation Test

```bash
# Signature test
$ uv run python examples/test_signature_preservation.py
✅ After wrap_filters: ['query', 'collection_name', 'document_id', 'physical_page_index', 'page_label']
✅ After make_partial_function: ['query', 'document_id', 'physical_page_index', 'page_label']
✅ Function call succeeded with correct filter construction
```

---

## Next Steps

### For User: Verify in Their Environment

1. **Restart MCP Client**: Completely restart VS Code / Cursor / Claude Desktop
2. **Clear Caches**: Check for any MCP client cache files
3. **Verify Environment**: Check `env | grep QDRANT` for unexpected overrides
4. **Test Tool Call**: Actually call the tool with filter parameters:

   ```python
   qdrant-find(
       query="test",
       collection_name="my-collection",
       document_id="my-doc",
       physical_page_index=5
   )
   ```

5. **Check MCP Inspector**: Run `fastmcp dev` and visually inspect the tool schema

### For Us: Documentation

Since the feature is working, update documentation to:

1. Show example filter usage in README
2. Document all filterable fields in API docs
3. Add troubleshooting section for "parameters not showing" issues

### No Code Changes Needed

The implementation is correct and working. This was a verification task that confirmed functionality.

---

## Technical Details

### How wrap_filters() Works

```python
def wrap_filters(original_func, filterable_fields):
    # 1. Get original signature
    sig = inspect.signature(original_func)

    # 2. Create wrapper that transforms filter params → query_filter dict
    def wrapper(*args, **kwargs):
        filter_values = {k: kwargs.pop(k) for k in filterable_fields}
        query_filter = make_filter(filterable_fields, filter_values)
        return original_func(**kwargs, query_filter=query_filter)

    # 3. Build new signature with filter params
    new_params = []
    for field in filterable_fields.values():
        param = inspect.Parameter(
            name=field.name,
            annotation=Annotated[Optional[type], Field(...)],
            default=None
        )
        new_params.append(param)

    # 4. Set new signature on wrapper
    wrapper.__signature__ = sig.replace(parameters=new_params)
    wrapper.__annotations__ = {...}

    return wrapper
```

This creates a valid Python function with proper introspection attributes. The issue is **FastMCP doesn't check these attributes when extracting tool schemas**.

---

## Files Created

- **research.md** - Detailed investigation report with code snippets
- **examples/diagnose_filter_settings.py** - Settings initialization diagnostic (39 lines)
- **examples/test_signature_preservation.py** - Signature transformation test (121 lines)

---

## Conclusion

✅ **PDF filter parameters ARE working and exposed correctly.**
✅ **All code is functioning as designed.**
📋 **This is a verification success, not a bug fix.**

The reported issue is likely environmental (cached schemas, wrong server instance, etc.), not a code defect. No changes needed to `settings.py`, `mcp_server.py`, `wrap_filters.py`, or `func_tools.py`.
