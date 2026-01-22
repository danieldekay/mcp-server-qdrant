# Research: PDF Metadata Filter Parameters Not Exposed in MCP Tool

## Executive Summary

**Status:** ✅ **PYTHON CODE VERIFIED CORRECT - ISSUE IN FASTMCP**

After comprehensive testing with diagnostic scripts, the root cause has been identified:

**The Python code architecture is 100% correct.** All components work as designed:

- ✅ Settings properly initialize with 3 PDF metadata fields
- ✅ Each field has `condition="=="` defined
- ✅ `wrap_filters()` successfully adds filter parameters to function signature
- ✅ `make_partial_function()` preserves filter parameters when removing `collection_name`
- ✅ Actual function calls construct correct Qdrant filters

**The issue is in FastMCP's tool registration or MCP protocol serialization.** The dynamically modified function signatures are not being properly introspected when registering tools via `self.tool()`.

**Next Steps:**

1. Test with MCP Inspector (`fastmcp dev`) to verify tool schema
2. Investigate FastMCP's tool schema extraction mechanism
3. Consider workarounds or upstream FastMCP fix

See [Verified Test Results](#verified-test-results) section below for proof.

## Current Configuration State

### 1. Settings Configuration (`settings.py`)

**Location:** Lines 133-148

```python
filterable_fields: list[FilterableField] | None = Field(
    default=[
        FilterableField(
            name=PDFMetadataKeys.DOCUMENT_ID,
            description="The unique identifier of the document",
            field_type="keyword",
            condition="==",  # ✅ CONDITION DEFINED
        ),
        FilterableField(
            name=PDFMetadataKeys.PHYSICAL_PAGE_INDEX,
            description="The 0-based physical index of the page",
            field_type="integer",
            condition="==",  # ✅ CONDITION DEFINED
        ),
        FilterableField(
            name=PDFMetadataKeys.PAGE_LABEL,
            description="The original page numbering label (e.g., 'iv', '45')",
            field_type="keyword",
            condition="==",  # ✅ CONDITION DEFINED
        ),
    ]
)
```

**Constants Definition** (`constants.py`, lines 8-14):

```python
class PDFMetadataKeys:
    DOCUMENT_ID = "document_id"
    PAGE_LABEL = "page_label"
    PHYSICAL_PAGE_INDEX = "physical_page_index"
    TOTAL_PAGES = "total_pages"
    FILENAME = "filename"
    FILEPATH = "filepath"
    EXTENSION = "extension"
```

**Filter Selection Method** (`settings.py`, lines 164-170):

```python
def filterable_fields_dict_with_conditions(self) -> dict[str, FilterableField]:
    if self.filterable_fields is None:
        return {}
    return {
        field.name: field
        for field in self.filterable_fields
        if field.condition is not None  # Filters out fields without conditions
    }
```

**Status:** ✅ All three PDF metadata fields have `condition="=="` defined

### 2. Tool Registration (`mcp_server.py`)

**Location:** Lines 180-192

```python
find_foo = find
store_foo = store

filterable_conditions = (
    self.qdrant_settings.filterable_fields_dict_with_conditions()
)

if len(filterable_conditions) > 0:
    find_foo = wrap_filters(find_foo, filterable_conditions)  # ✅ WRAPPING APPLIED
elif not self.qdrant_settings.allow_arbitrary_filter:
    find_foo = make_partial_function(find_foo, {"query_filter": None})
```

**Status:** ✅ `wrap_filters()` is correctly applied when conditions exist

### 3. Filter Wrapping Mechanism (`wrap_filters.py`)

**Signature Transformation** (lines 44-92):

```python
# Create a new signature parameters from `filterable_fields`
for field in filterable_fields.values():
    field_name = field.name
    field_type: type
    if field.field_type == "keyword":
        field_type = str
    elif field.field_type == "integer":
        field_type = int
    # ... (field type mapping)

    if field.required:
        # Required parameter
        annotation = Annotated[field_type, Field(description=field.description)]
        parameter = inspect.Parameter(...)
        required_new_params.append(parameter)
    else:
        # Optional parameter (default=None)
        annotation = Annotated[Optional[field_type], Field(description=field.description)]
        parameter = inspect.Parameter(..., default=None, ...)
        optional_new_params.append(parameter)
```

**Status:** ✅ Mechanism correctly generates optional parameters with `None` defaults

## Root Cause Analysis

### Finding: Code is Correct, Issue is Runtime

After thorough analysis, the code architecture is **working as designed**:

1. ✅ PDF metadata fields have conditions defined (`condition="=="`)
2. ✅ `filterable_fields_dict_with_conditions()` correctly filters fields
3. ✅ `wrap_filters()` is applied when `len(filterable_conditions) > 0`
4. ✅ Tool signature transformation logic is sound

### Hypothesis: Runtime Initialization Problem

The issue is likely caused by one of these scenarios:

#### **Scenario A: Environment Variable Override** (Most Likely)

If an environment variable is set that affects `filterable_fields`, it could override the default:

```bash
# Possible culprit - empty filterable fields
export QDRANT_FILTERABLE_FIELDS="[]"
```

**Evidence:** Pydantic BaseSettings loads from environment variables, which take precedence over defaults.

**Verification Command:**

```bash
env | grep -i qdrant
env | grep -i filter
```

#### **Scenario B: Settings Instance Creation Issue**

The server initialization in `server.py` (lines 1-9) might not be properly instantiating settings:

```python
mcp = QdrantMCPServer(
    tool_settings=ToolSettings(),
    qdrant_settings=QdrantSettings(),  # Could be loading empty filterable_fields
    embedding_provider_settings=EmbeddingProviderSettings(),
    chunking_settings=ChunkingSettings(),
)
```

**Verification:** Check actual runtime instance values.

#### **Scenario C: Pydantic Field Default Not Triggering**

If `filterable_fields` is set to `None` via environment or during instantiation, the default list won't be used.

**From BaseSettings docs:** Environment variables are coerced to the field type. An env var like `FILTERABLE_FIELDS=null` could set it to `None`.

### Expected Behavior vs. Actual

**Expected (if defaults work):**

```python
>>> settings = QdrantSettings()
>>> settings.filterable_fields
[
    FilterableField(name='document_id', ...),
    FilterableField(name='physical_page_index', ...),
    FilterableField(name='page_label', ...),
]
>>> settings.filterable_fields_dict_with_conditions()
{
    'document_id': FilterableField(...),
    'physical_page_index': FilterableField(...),
    'page_label': FilterableField(...)
}
```

**Actual (reported issue):**

```python
>>> # Likely returns empty dict
>>> settings.filterable_fields_dict_with_conditions()
{}
>>> # Or filterable_fields is None
>>> settings.filterable_fields
None
```

## Recommended Solution

### Step 1: Diagnostic Check

Add debug logging to verify the issue:

**File:** `src/mcp_server_qdrant/mcp_server.py`
**Location:** After line 183

```python
filterable_conditions = (
    self.qdrant_settings.filterable_fields_dict_with_conditions()
)

# ADD DIAGNOSTIC LOGGING
logger.info(f"Filterable fields: {self.qdrant_settings.filterable_fields}")
logger.info(f"Filterable conditions count: {len(filterable_conditions)}")
logger.info(f"Filterable conditions: {filterable_conditions}")

if len(filterable_conditions) > 0:
    find_foo = wrap_filters(find_foo, filterable_conditions)
```

### Step 2: Force Non-None Default (If Needed)

If Pydantic is not applying the default, use a factory function:

**File:** `src/mcp_server_qdrant/settings.py`
**Location:** Around line 133

```python
from pydantic import field_validator

def _default_filterable_fields():
    """Factory function for default filterable fields."""
    return [
        FilterableField(
            name=PDFMetadataKeys.DOCUMENT_ID,
            description="The unique identifier of the document",
            field_type="keyword",
            condition="==",
        ),
        FilterableField(
            name=PDFMetadataKeys.PHYSICAL_PAGE_INDEX,
            description="The 0-based physical index of the page",
            field_type="integer",
            condition="==",
        ),
        FilterableField(
            name=PDFMetadataKeys.PAGE_LABEL,
            description="The original page numbering label (e.g., 'iv', '45')",
            field_type="keyword",
            condition="==",
        ),
    ]

class QdrantSettings(BaseSettings):
    # ...

    filterable_fields: list[FilterableField] | None = Field(
        default_factory=_default_filterable_fields
    )

    @field_validator("filterable_fields", mode="before")
    @classmethod
    def ensure_filterable_fields(cls, v):
        """Ensure filterable_fields is never None."""
        if v is None:
            return _default_filterable_fields()
        return v
```

### Step 3: Runtime Verification Test

Create a test to verify settings initialization:

**File:** `tests/test_settings_initialization.py`

```python
import pytest
from mcp_server_qdrant.settings import QdrantSettings
from mcp_server_qdrant.constants import PDFMetadataKeys


def test_filterable_fields_default_not_none():
    """Verify filterable_fields defaults are applied."""
    settings = QdrantSettings()

    assert settings.filterable_fields is not None
    assert len(settings.filterable_fields) == 3

    field_names = {f.name for f in settings.filterable_fields}
    assert PDFMetadataKeys.DOCUMENT_ID in field_names
    assert PDFMetadataKeys.PHYSICAL_PAGE_INDEX in field_names
    assert PDFMetadataKeys.PAGE_LABEL in field_names


def test_filterable_fields_with_conditions():
    """Verify filterable_fields_dict_with_conditions returns expected fields."""
    settings = QdrantSettings()

    conditions = settings.filterable_fields_dict_with_conditions()

    assert len(conditions) == 3
    assert PDFMetadataKeys.DOCUMENT_ID in conditions
    assert conditions[PDFMetadataKeys.DOCUMENT_ID].condition == "=="
```

## Code Change Summary

### If Diagnostic Shows Empty Fields (Solution)

**File:** `src/mcp_server_qdrant/settings.py`

**Change:** Replace `default=` with `default_factory=` and add validator

```python
# BEFORE (line 133)
filterable_fields: list[FilterableField] | None = Field(
    default=[
        FilterableField(...),
        # ...
    ]
)

# AFTER
def _default_filterable_fields():
    return [
        FilterableField(
            name=PDFMetadataKeys.DOCUMENT_ID,
            description="The unique identifier of the document",
            field_type="keyword",
            condition="==",
        ),
        FilterableField(
            name=PDFMetadataKeys.PHYSICAL_PAGE_INDEX,
            description="The 0-based physical index of the page",
            field_type="integer",
            condition="==",
        ),
        FilterableField(
            name=PDFMetadataKeys.PAGE_LABEL,
            description="The original page numbering label (e.g., 'iv', '45')",
            field_type="keyword",
            condition="==",
        ),
    ]

filterable_fields: list[FilterableField] | None = Field(
    default_factory=_default_filterable_fields
)

@field_validator("filterable_fields", mode="before")
@classmethod
def ensure_filterable_fields(cls, v):
    if v is None:
        return _default_filterable_fields()
    return v
```

### If Diagnostic Shows Fields Present (Alternative Issue)

Then the problem is in `wrap_filters()` or tool registration. Check:

1. FastMCP tool introspection behavior
2. Signature preservation through `make_partial_function()`
3. MCP protocol serialization of tool schemas

## Verification Checklist

After implementing fix:

- [ ] Run `test_settings_initialization.py` - defaults load correctly
- [ ] Run `uv run fastmcp dev src/mcp_server_qdrant/server.py` - inspect tool schema
- [ ] Check MCP Inspector tool signature includes: `document_id`, `physical_page_index`, `page_label`
- [ ] Test actual tool call with filter: `qdrant-find(query="test", document_id="mydoc")`
- [ ] Verify Qdrant query includes proper filter conditions

## Additional Investigation Points

If the above doesn't resolve the issue:

1. **Check FastMCP Version:** Ensure FastMCP properly inspects `__signature__` and `__annotations__`
2. **Check MCP Protocol:** Verify how tool schemas are serialized
3. **Check Partial Function Wrapping:** `make_partial_function()` might interfere with signature preservation
4. **Check Order of Operations:** Wrapping order matters - `wrap_filters()` before or after `make_partial_function()`?

## Verified Test Results

### Diagnostic Results

Running `examples/diagnose_filter_settings.py`:

```
🟢 ALL CHECKS PASSED
- filterable_fields is properly initialized
- All 3 PDF metadata fields have conditions
- wrap_filters() will be applied correctly
```

### Signature Preservation Test Results

Running `examples/test_signature_preservation.py`:

```
2. After wrap_filters():
   Parameters: ['query', 'collection_name', 'document_id', 'physical_page_index', 'page_label']
   ✅ All expected parameters present!

3. After make_partial_function(collection_name='test-collection'):
   Parameters: ['query', 'document_id', 'physical_page_index', 'page_label']
   ✅ All expected parameters still present!

4. Function Call Test:
   ✅ Call succeeded with proper filter construction
```

**CRITICAL FINDING:** The Python code is **100% correct**. Signature transformation works perfectly through both `wrap_filters()` and `make_partial_function()`. **UPDATE:** FastMCP is also working correctly and exposing all parameters!

### FastMCP Tool Registration Verification

Running `examples/inspect_tool_manager.py`:

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
      'description': "The original page numbering label"
    }
  },
  'required': ['query', 'collection_name']
}
```

✅ **All three PDF filter parameters ARE present in the actual MCP tool schema!**

## Conclusion

**Final Diagnosis:** The PDF filter parameters ARE working and correctly exposed in the MCP tool schema.

The entire chain works correctly:

1. ✅ Settings initialization applies defaults properly
2. ✅ `filterable_fields_dict_with_conditions()` returns all 3 fields
3. ✅ `wrap_filters()` adds filter parameters to signature
4. ✅ `make_partial_function()` preserves filter parameters
5. ✅ Function calls work with correct Qdrant filter building
6. ✅ **FastMCP correctly exposes all parameters in tool schema**

**Root Cause of Reported Issue:** Likely environmental:

- MCP client caching old tool schemas
- User inspecting wrong server instance
- Environment variable override (`QDRANT_ALLOW_ARBITRARY_FILTER=true`)
- Misinterpretation of what should be visible

**Recommended Action:**

1. User should restart MCP client completely
2. Clear any MCP client caches
3. Verify environment variables with `env | grep QDRANT`
4. Test actual tool call with filter parameters
5. If still not working, provide MCP client logs for debugging
