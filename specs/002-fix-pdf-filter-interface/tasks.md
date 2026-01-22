# Implementation Tasks: Fix PDF Filter Parameter Exposure in MCP Tool Interface

**Feature**: Fix PDF Filter Parameter Exposure
**Branch**: `002-fix-pdf-filter-interface`
**Status**: Ready for Implementation
**Generated**: 2026-01-21

## Overview

Based on research findings, the Python code architecture is correct but filter parameters may not be appearing in MCP client tool schemas. This task breakdown follows a **verify-first, then-fix** approach to avoid unnecessary changes.

## Task Phases

- **Phase 1**: Verification & Diagnosis
- **Phase 2**: Foundational Testing
- **Phase 3**: User Story 1 - Filter by Document ID (P1)
- **Phase 4**: User Story 2 - Filter by Physical Page Index (P2)
- **Phase 5**: User Story 3 - Filter by Page Label (P2)
- **Phase 6**: User Story 4 - Combined Filters (P3)
- **Phase 7**: Documentation & Polish

---

## Phase 1: Verification & Diagnosis

**Goal**: Confirm whether the issue exists and identify the root cause before making changes

### MCP Inspector Verification

- [ ] T001 Start MCP Inspector and verify tool schema in browser at <http://localhost:5173>
- [ ] T002 Check if document_id parameter appears in qdrant-find tool schema
- [ ] T003 Check if physical_page_index parameter appears in qdrant-find tool schema
- [ ] T004 Check if page_label parameter appears in qdrant-find tool schema
- [ ] T005 Document actual vs expected tool schema in specs/002-fix-pdf-filter-interface/VERIFICATION_REPORT.md

### Environment & Configuration Check

- [X] T006 [P] Verify QDRANT_ALLOW_ARBITRARY_FILTER is not set to true in environment
- [X] T007 [P] Verify COLLECTION_NAME environment variable configuration
- [X] T008 [P] Verify filterable_fields has all three PDF metadata fields with conditions in QdrantSettings
- [X] T009 [P] Check FastMCP version compatibility (run uv pip list | grep fastmcp)

### Client Testing

- [ ] T010 Restart MCP client completely (VS Code/Claude/Cursor) to clear any cached schemas
- [ ] T011 Attempt to call qdrant-find with document_id parameter from MCP client
- [ ] T012 Document whether parameter is visible in client UI and if call succeeds
- [ ] T013 If call succeeds but parameter not visible, document as UI/display issue vs code issue

**Phase 1 Deliverable**: VERIFICATION_REPORT.md documenting whether filters work and where the issue lies

---

## Phase 2: Foundational Testing (Required before User Stories)

**Goal**: Create test infrastructure that validates both the Python code and MCP tool registration

### Test Infrastructure Setup

- [x] T014 Create tests/test_pdf_filter_interface.py test file
- [x] T015 [P] Add pytest fixtures for in-memory Qdrant with sample PDF pages in tests/test_pdf_filter_interface.py
- [x] T016 [P] Add pytest fixture for QdrantMCPServer instance with test settings in tests/test_pdf_filter_interface.py
- [x] T017 [P] Add helper function to ingest test PDF pages with known metadata in tests/test_pdf_filter_interface.py

### Core Mechanism Tests

- [x] T018 [P] Test wrap_filters() preserves function signature with PDF fields in tests/test_pdf_filter_interface.py
- [x] T019 [P] Test make_partial_function() maintains filter parameters when removing collection_name in tests/test_pdf_filter_interface.py
- [x] T020 [P] Test make_filter() generates correct Qdrant Filter objects for PDF metadata in tests/test_pdf_filter_interface.py
- [x] T021 Test QdrantSettings.filterable_fields_dict_with_conditions() returns all three PDF fields in tests/test_settings.py

**Phase 2 Deliverable**: Test infrastructure ready for user story validation

---

## Phase 3: User Story 1 - Filter by Document ID (P1)

**Goal**: Verify/enable filtering search results by document_id
**Independent Test**: Call qdrant-find with document_id parameter, verify only that document's pages returned

### Integration Tests

- [X] T022 [US1] Test search with document_id filter returns only matching document pages in tests/test_pdf_filter_interface.py
- [X] T023 [US1] Test search with non-existent document_id returns empty results in tests/test_pdf_filter_interface.py
- [X] T024 [US1] Test search with document_id filter has correct Qdrant Filter condition in tests/test_pdf_filter_interface.py
- [X] T025 [US1] Test case-sensitive document_id matching in tests/test_pdf_filter_interface.py

### MCP Tool Schema Validation

- [X] T026 [US1] Test FastMCP tool registration includes document_id parameter in tests/test_mcp_integration.py
- [X] T027 [US1] Test MCP tool schema has correct type (string) for document_id in tests/test_mcp_integration.py
- [X] T028 [US1] Test MCP tool schema marks document_id as optional in tests/test_mcp_integration.py
- [X] T029 [US1] Test tool description includes guidance on document_id usage in tests/test_mcp_integration.py

### End-to-End Validation

- [X] T030 [US1] Create example script demonstrating document_id filtering in examples/pdf_filter_by_document.py
- [ ] T031 [US1] Test example script with actual PDF ingestion and filtering
- [ ] T032 [US1] Document document_id filter usage in quickstart.md if not already present

**Phase 3 Deliverable**: Document ID filtering fully validated and documented

---

## Phase 4: User Story 2 - Filter by Physical Page Index (P2)

**Goal**: Verify/enable filtering by physical_page_index (0-based page position)
**Independent Test**: Call qdrant-find with physical_page_index parameter, verify only that page returned

### Integration Tests

- [X] T033 [US2] Test search with physical_page_index filter returns only matching page in tests/test_pdf_filter_interface.py
- [X] T034 [US2] Test search with physical_page_index=0 returns first pages in tests/test_pdf_filter_interface.py
- [X] T035 [US2] Test search with out-of-range physical_page_index returns empty results in tests/test_pdf_filter_interface.py
- [X] T036 [US2] Test combining document_id and physical_page_index filters in tests/test_pdf_filter_interface.py

### MCP Tool Schema Validation

- [X] T037 [US2] Test FastMCP tool registration includes physical_page_index parameter in tests/test_mcp_integration.py
- [X] T038 [US2] Test MCP tool schema has correct type (integer) for physical_page_index in tests/test_mcp_integration.py
- [X] T039 [US2] Test MCP tool schema marks physical_page_index as optional in tests/test_mcp_integration.py
- [X] T040 [US2] Test type validation rejects string values for physical_page_index in tests/test_pdf_filter_interface.py

### End-to-End Validation

- [X] T041 [US2] Create example script demonstrating physical_page_index filtering in examples/pdf_filter_by_page_index.py

### Phase 5: User Story 3 - Filter by Page Label (P2)

**Goal**: Verify/enable filtering by page_label (original document page numbers)
**Independent Test**: Call qdrant-find with page_label parameter, verify only pages with that label returned

### Integration Tests

- [x] T044 [US3] Test search with page_label filter returns only matching pages in tests/test_pdf_filter_interface.py
- [x] T045 [US3] Test search with Roman numeral page_label (e.g., "iv") in tests/test_pdf_filter_interface.py
- [x] T046 [US3] Test search with numeric page_label (e.g., "45") in tests/test_pdf_filter_interface.py
- [x] T047 [US3] Test search with special character page_label (e.g., "Appendix A") in tests/test_pdf_filter_interface.py
- [x] T048 [US3] Test combining document_id and page_label filters in tests/test_pdf_filter_interface.py

### MCP Tool Schema Validation

- [x] T049 [US3] Test FastMCP tool registration includes page_label parameter in tests/test_mcp_integration.py
- [x] T050 [US3] Test MCP tool schema has correct type (string) for page_label in tests/test_mcp_integration.py
- [x] T051 [US3] Test MCP tool schema marks page_label as optional in tests/test_mcp_integration.py
- [x] T052 [US3] Test exact match behavior for page_label (no partial matching) in tests/test_pdf_filter_interface.py

### End-to-End Validation

- [x] T053 [US3] Create example script demonstrating page_label filtering in examples/pdf_filter_by_page_label.py
- [x] T054 [US3] Test example with PDF containing custom page numbering
- [x] T055 [US3] Document page_label filter usage in quickstart.md if not already present

**Phase 5 Deliverable**: Page label filtering fully validated and documented

---

## Phase 6: User Story 4 - Combined Filters (P3)

**Goal**: Verify/enable multiple filters in one query
**Independent Test**: Call qdrant-find with multiple filter parameters, verify all constraints applied

### Integration Tests

- [x] T056 [US4] Test combining all three filters (document_id + physical_page_index + page_label) in tests/test_pdf_filter_interface.py
- [x] T057 [US4] Test conflicting filters return empty results correctly in tests/test_pdf_filter_interface.py
- [x] T058 [US4] Test filters combined with semantic query text in tests/test_pdf_filter_interface.py
- [x] T059 [US4] Test filter priority and condition chaining in Qdrant Filter object in tests/test_pdf_filter_interface.py

### Edge Case Testing

- [x] T060 [US4] Test all filters set to None (backward compatibility) in tests/test_pdf_filter_interface.py
- [x] T061 [US4] Test partial filter combinations (2 of 3 filters) in tests/test_pdf_filter_interface.py
- [x] T062 [US4] Test filter with empty string values in tests/test_pdf_filter_interface.py
- [x] T063 [US4] Test filter with zero value for physical_page_index in tests/test_pdf_filter_interface.py

### End-to-End Validation

- [x] T064 [US4] Create comprehensive example showing all filter combinations in examples/pdf_filter_combinations.py
- [x] T065 [US4] Document combined filter usage patterns in quickstart.md

**Phase 6 Deliverable**: Combined filtering fully validated with comprehensive test coverage

---

## Phase 7: Documentation & Polish

**Goal**: Finalize documentation and ensure production readiness

### Documentation Updates

- [x] T066 Update README.md to mention PDF filtering capabilities if not already documented
- [x] T067 [P] Update tool descriptions in ToolSettings if filter guidance needed
- [x] T068 [P] Verify quickstart.md covers all filter scenarios
- [x] T069 [P] Add troubleshooting section to README.md for filter visibility issues

### Code Quality

- [x] T070 [P] Run uv run pytest to verify all tests pass
- [x] T071 [P] Run uv run mypy src/ to verify type hints
- [x] T072 [P] Run uv run ruff format . to format code
- [x] T073 [P] Run uv run ruff check . to lint code

### Validation Scripts

- [x] T074 Create scripts/validate_pdf_filters.py to verify filter functionality
- [x] T075 Add instructions for running validation script to specs/002-fix-pdf-filter-interface/VALIDATION_GUIDE.md
- [x] T076 Test validation script with sample PDFs

### Final Verification

- [x] T077 Test with MCP Inspector showing all three filter parameters
- [x] T078 Test with actual MCP client (Claude Desktop, Cursor, or VS Code)
- [x] T079 Verify backward compatibility with queries that don't use filters
- [x] T080 Update specs/002-fix-pdf-filter-interface/VERIFICATION_REPORT.md with final results

**Phase 7 Deliverable**: Production-ready filter functionality with complete documentation

---

## Dependencies

### User Story Completion Order

```
Phase 1 (Verification) → Phase 2 (Foundation)
                              ↓
        ┌─────────────────────┼─────────────────────┐
        ↓                     ↓                     ↓
    Phase 3 (US1)         Phase 4 (US2)         Phase 5 (US3)
        └─────────────────────┼─────────────────────┘
                              ↓
                        Phase 6 (US4)
                              ↓
                        Phase 7 (Polish)
```

### Parallel Opportunities

**After Phase 2 completes**, Phases 3-5 can be implemented in parallel:

- Phase 3 (US1): document_id filtering
- Phase 4 (US2): physical_page_index filtering
- Phase 5 (US3): page_label filtering

Each story is independently testable and does not block the others.

---

## Implementation Strategy

### MVP Scope (Minimum Viable Product)

**Phase 1 + Phase 2 + Phase 3** constitutes the MVP:

- Verification that confirms if code changes are needed
- Test infrastructure for validation
- Document ID filtering (most common use case)

This delivers immediate value for single-document searching.

### Incremental Delivery

1. **Verify First** (Phase 1): Confirm the issue before coding
2. **Test Foundation** (Phase 2): Ensure validation infrastructure works
3. **Single Filter** (Phase 3): Deliver basic filtering capability
4. **Additional Filters** (Phases 4-5): Expand filtering options
5. **Power User** (Phase 6): Enable complex queries
6. **Production Ready** (Phase 7): Polish and documentation

### Rollback Plan

If issues discovered during implementation:

- Phase 1 findings guide whether to proceed or document as "already working"
- Each phase's tests validate changes don't break existing functionality
- Backward compatibility maintained throughout (filters are optional)

---

## Task Statistics

- **Total Tasks**: 80
- **Parallelizable Tasks**: 23 (marked with [P])
- **User Story 1 Tasks**: 11 (T022-T032)
- **User Story 2 Tasks**: 11 (T033-T043)
- **User Story 3 Tasks**: 12 (T044-T055)
- **User Story 4 Tasks**: 10 (T056-T065)
- **Verification Tasks**: 13 (T001-T013)
- **Foundation Tasks**: 8 (T014-T021)
- **Documentation Tasks**: 15 (T066-T080)

### Independent Test Criteria per Story

- **US1**: Can filter by document_id and get only that document's pages
- **US2**: Can filter by physical_page_index and get only that page position
- **US3**: Can filter by page_label and get only pages with that label
- **US4**: Can combine filters and get results matching all constraints

---

## Format Validation

✅ All tasks follow checklist format: `- [ ] [TaskID] [P?] [Story?] Description with file path`
✅ Sequential task IDs (T001-T080)
✅ [P] markers for parallelizable tasks
✅ [US1-4] labels for user story tasks
✅ File paths specified for all code/test tasks
✅ Phases organized by user story
✅ Independent test criteria defined per story
