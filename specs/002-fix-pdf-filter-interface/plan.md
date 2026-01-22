# Implementation Plan: Fix PDF Filter Parameter Exposure in MCP Tool Interface

**Branch**: `002-fix-pdf-filter-interface` | **Date**: 2026-01-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-fix-pdf-filter-interface/spec.md`

## Summary

**STATUS UPDATE (2026-01-21):** Research completed. Python code is verified correct - issue is in FastMCP tool registration.

The PDF page-by-page ingestion infrastructure (feature 001) correctly stores metadata (`document_id`, `physical_page_index`, `page_label`) in Qdrant. The filter parameter exposure mechanism is **fully functional** at the Python level - `wrap_filters()` correctly transforms the function signature, and `make_partial_function()` preserves it. However, these filter parameters are not appearing in the MCP tool schema sent to clients.

**Root Cause**: FastMCP's `self.tool()` registration does not properly introspect dynamically modified function signatures (`__signature__` and `__annotations__`), or the MCP protocol serialization drops the dynamically added parameters.

**Evidence**:

- ✅ Diagnostic script confirms all 3 PDF fields have conditions defined
- ✅ Signature preservation test confirms `wrap_filters()` + `make_partial_function()` chain works perfectly
- ✅ Function calls with filter parameters succeed and construct correct Qdrant filters

**Next Investigation**: Use MCP Inspector to examine actual tool schema, then investigate FastMCP's tool registration internals.

## Technical Context

**Language/Version**: Python 3.10+ (CI tests against 3.10, 3.11, 3.12, 3.13)
**Primary Dependencies**: FastMCP (MCP server framework), Qdrant AsyncQdrantClient, Pydantic (settings)
**Storage**: Qdrant vector database (supports in-memory `:memory:` and persistent local/remote)
**Testing**: pytest with `@pytest.mark.asyncio`, in-memory Qdrant for isolation
**Target Platform**: Cross-platform (Linux, macOS, Windows) - MCP server runs via stdio/SSE transport
**Project Type**: Single Python package (`mcp-server-qdrant`)
**Performance Goals**: No specific latency requirements for filtering (metadata filters have negligible overhead)
**Constraints**: Must maintain async-first architecture, backward compatibility with non-filtered queries
**Scale/Scope**: Fix affects 3 filter parameters, 1 settings class, 1 MCP tool, requires integration tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### ✅ Core Principles Compliance

- **I. Environment-First Configuration**: ✅ PASS
  - Filter fields are defined in `QdrantSettings.filterable_fields` using Pydantic Field defaults
  - No CLI arguments needed for this fix (filter configuration via env vars or defaults)

- **II. Async-First Architecture**: ✅ PASS
  - Fix does not introduce any synchronous operations
  - `wrap_filters()` is a synchronous decorator wrapping async tool functions (correct pattern)
  - Qdrant queries remain async via `AsyncQdrantClient`

- **III. Backward Compatibility**: ✅ PASS
  - Filters are optional parameters (default None)
  - Queries without filters continue to work unchanged
  - No changes to payload structure or vector format

- **IV. Provider Abstraction**: ✅ PASS
  - No changes to embedding provider interface or implementations
  - Filter logic is orthogonal to embedding operations

- **V. Test Coverage**: ✅ PASS
  - Will add integration tests for filtered queries
  - Tests use in-memory Qdrant with random collection names
  - All async patterns follow existing test conventions

- **VI. Graceful Degradation**: ✅ PASS
  - No optional dependencies involved in filtering
  - Filters work with all existing embedding providers

- **VII. Type Safety & Documentation**: ✅ PASS
  - All functions maintain type hints
  - Docstrings will document filter parameters
  - Follows PEP 8 and project naming conventions

### Technical Standards Compliance

- **FastMCP Integration**: ✅ PASS
  - Uses `@self.tool()` decorator (existing pattern)
  - Type hints with `Annotated[type, Field(description="...")]` for parameter schema generation
  - `wrap_filters()` preserves FastMCP signature introspection via `__signature__` and `__annotations__`

- **Collection Management**: ✅ PASS
  - No changes to collection creation or indexing
  - Existing payload indexes for `metadata.document_id`, `metadata.physical_page_index`, `metadata.page_label` already created by feature 001

- **Error Handling**: ✅ PASS
  - Invalid filter values return empty results (Qdrant behavior)
  - Type validation handled by FastMCP/Pydantic parameter coercion

**GATE RESULT**: ✅ ALL CHECKS PASSED - Proceed to Phase 0

## Project Structure

### Documentation (this feature)

```text
specs/002-fix-pdf-filter-interface/
├── plan.md              # This file
├── research.md          # Phase 0: Investigation of wrap_filters behavior and PDF metadata field configuration
├── data-model.md        # Phase 1: Filter parameter data structures and Qdrant filter conditions
├── quickstart.md        # Phase 1: How to use PDF filters in MCP clients
├── contracts/           # Phase 1: MCP tool schema showing filter parameters
│   └── qdrant-find-tool-schema.json
└── tasks.md             # Phase 2: Implementation checklist (created by /speckit.tasks, not this command)
```

### Source Code (repository root)

```text
src/mcp_server_qdrant/
├── constants.py         # EXISTING: PDFMetadataKeys definitions (document_id, physical_page_index, page_label)
├── settings.py          # MODIFY: Ensure filterable_fields default includes PDF fields with conditions
├── mcp_server.py        # VERIFY/FIX: Ensure wrap_filters() is applied correctly to find() tool
├── common/
│   ├── wrap_filters.py  # EXISTING: Dynamic filter parameter generation (no changes needed)
│   └── filters.py       # EXISTING: make_filter() for condition translation (no changes needed)
└── qdrant.py            # EXISTING: No changes (metadata storage and filtering already functional)

tests/
├── test_pdf_filter_interface.py  # NEW: Integration tests for PDF metadata filtering via MCP tool
├── test_settings.py               # MODIFY: Add tests for PDF filterable fields configuration
└── test_mcp_integration.py        # MODIFY: Add tests for filtered queries through MCP server

examples/
└── pdf_filter_demo.py   # NEW: Demonstrate filtering PDFs by document_id, page_index, page_label
```

**Structure Decision**: Single Python package structure (Option 1). All source code under `src/mcp_server_qdrant/`. This is a debugging/fix feature - no new components, only configuration verification and integration testing.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations detected. This feature maintains all constitutional principles.

---

## Phase 0: Research Complete ✅

**Status**: Investigation completed
**Output**: [research.md](research.md)

**Key Findings**:

- Python code architecture is 100% correct
- All three PDF metadata fields properly configured with `condition="=="`
- `wrap_filters()` successfully modifies function signatures
- `make_filter()` correctly translates to Qdrant conditions
- Potential issue in FastMCP tool registration or MCP client caching

**Recommendation**: Verify with MCP Inspector before making code changes. Issue may be client-side caching or environment configuration.

## Phase 1: Design & Contracts Complete ✅

**Status**: Design documentation completed
**Outputs**:

- [data-model.md](data-model.md) - Filter parameter data structures
- [contracts/qdrant-find-tool-schema.json](contracts/qdrant-find-tool-schema.json) - Expected MCP tool schema
- [quickstart.md](quickstart.md) - User guide for PDF filtering

**Constitution Check (Post-Design)**: ✅ ALL CHECKS PASSED

No design decisions violate constitutional principles. The fix maintains:

- Async-first architecture (no blocking operations)
- Backward compatibility (filters are optional)
- Type safety (proper type hints and validation)
- Test coverage (integration tests planned)
- Environment-first configuration (no new CLI args)

**Agent Context Updated**: ✅ GitHub Copilot context file updated with current technology stack

---

## Next Steps

This completes the `/speckit.plan` command output. To proceed with implementation:

1. **Verify the issue**: Use MCP Inspector to confirm parameters are actually missing
2. **Run `/speckit.tasks`**: Generate detailed implementation checklist
3. **Execute tasks**: Follow Phase 2 task breakdown for implementation
4. **Test thoroughly**: Run integration tests for all filter combinations

**Branch**: `002-fix-pdf-filter-interface` ready for implementation phase.
