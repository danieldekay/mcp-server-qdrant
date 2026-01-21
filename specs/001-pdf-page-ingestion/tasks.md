---
description: "Task list for PDF page-by-page ingestion implementation"
---

# Tasks: PDF Page-by-Page Ingestion

**Input**: Design documents from `/specs/001-pdf-page-ingestion/`
**Prerequisites**: plan.md (complete), spec.md (complete), research.md (complete)

**Tests**: Tests are NOT requested in the specification, so test tasks are OMITTED

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and dependency management

- [x] T001 Add pypdf>=5.1.0 dependency to pyproject.toml in [dependencies] section
- [x] T002 Add markitdown dependency to pyproject.toml for future multi-format support
- [x] T003 [P] Update .github/copilot-instructions.md with pypdf library context and async wrapper patterns
- [x] T004 [P] Create test fixtures directory tests/fixtures/pdfs/ for PDF test files

**Checkpoint**: Dependencies installed and project structure ready

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core PDF extraction infrastructure that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Create src/mcp_server_qdrant/pdf_extractor.py with PDFPageExtractor class
- [x] T006 Implement async extract_page_content() method using asyncio.to_thread() wrapper
- [x] T007 Implement async extract_page_label() method for pypdf page_labels API
- [x] T008 Implement graceful fallback to "Page N" format when page labels unavailable
- [x] T009 Add PdfIngestionSettings class to src/mcp_server_qdrant/settings.py with enable_pdf_ingestion flag
- [x] T010 [P] Create test fixtures: tests/fixtures/pdfs/academic_paper.pdf (Roman numerals)
- [x] T011 [P] Create test fixtures: tests/fixtures/pdfs/book_chapter.pdf (custom page start)
- [x] T012 [P] Create test fixtures: tests/fixtures/pdfs/no_labels.pdf (standard numbering)

**Checkpoint**: Foundation ready - PDF extraction module complete, user story implementation can begin

---

## Phase 3: User Story 1 - Ingest PDF with Page-Level Granularity (Priority: P1) 🎯 MVP

**Goal**: Enable basic PDF page-by-page ingestion where each page is stored as a separate Qdrant entry with page number metadata

**Independent Test**: Ingest a sample PDF file via CLI and verify that each page is stored as a separate vector entry with correct metadata in Qdrant

### Implementation for User Story 1

- [x] T013 [P] [US1] Add PDFPageEntry Pydantic model to src/mcp_server_qdrant/qdrant.py with fields: content, physical_page_index, page_label, document_id, total_pages
- [x] T014 [US1] Extend cli_ingest.py SUPPORTED_EXTENSIONS to include '.pdf' file extension
- [x] T015 [US1] Implement async ingest_pdf_file() function in cli_ingest.py using PDFPageExtractor
- [x] T016 [US1] Add per-page loop in ingest_pdf_file() to call extract_page_content() and extract_page_label()
- [x] T017 [US1] Create PDFPageEntry instance for each page with metadata (document_id, physical_page_index, page_label)
- [x] T018 [US1] Call QdrantConnector.store() for each PDFPageEntry with --enable-chunking awareness
- [x] T019 [US1] Add error handling for corrupted PDFs with logging (skip page, continue ingestion)
- [x] T020 [US1] Add progress logging for multi-page PDF ingestion (e.g., "Processing page 5/100")

**Checkpoint**: User Story 1 complete - Can ingest PDFs page-by-page via CLI with basic metadata

---

## Phase 4: User Story 4 - Handle Custom PDF Page Numbering (Priority: P2)

**Goal**: Preserve both physical page position AND PDF's internal page labels (Roman numerals, chapter numbers, etc.) for accurate citation

**Independent Test**: Ingest a PDF with custom page numbering (book chapter starting at page 45) and verify metadata includes both physical_page_index and page_label

**Note**: US4 is implemented before US2/US3 because it extends US1's data model - must be done before search features depend on metadata schema

### Implementation for User Story 4

- [x] T021 [US4] Update PDFPageEntry model to ensure physical_page_index (int) and page_label (Optional[str]) are distinct fields
- [x] T022 [US4] Verify extract_page_label() handles all pypdf page label types: /D (decimal), /r /R (roman), /a /A (letters)
- [x] T023 [US4] Add format_page_label() helper function for mixed numbering schemes (e.g., "Chapter 1-5")
- [x] T024 [US4] Update CLI output to display both physical position and page label: "Page 2 (label: xlv)"
- [x] T025 [US4] Add metadata validation to ensure both fields are always populated (page_label may be None, use fallback)

**Checkpoint**: User Story 4 complete - Custom page numbering fully supported with dual metadata

---

## Phase 5: User Story 2 - Search and Retrieve by Page Reference (Priority: P2)

**Goal**: Enable search results to display page numbers alongside content for easy source location

**Independent Test**: After ingesting PDFs, perform semantic searches and verify results show page numbers in formatted output

### Implementation for User Story 2

- [x] T026 [US2] Update format_entry() method in src/mcp_server_qdrant/mcp_server.py to include page metadata in search results
- [x] T027 [US2] Format output as: "<entry><content>...</content><page>Document: {document_id}, Page: {page_label} ({physical_page_index})</page></entry>"
- [x] T028 [US2] Ensure qdrant-find MCP tool returns page metadata in response for LLM context
- [x] T029 [US2] Test search results with multi-page PDF to verify all matching pages returned with distinct metadata

**Checkpoint**: User Story 2 complete - Search results now include actionable page references

---

## Phase 6: User Story 3 - Filter by Document and Page Range (Priority: P3)

**Goal**: Enable advanced filtering by document name and page range using existing FilterableField system

**Independent Test**: Perform searches with metadata filters for specific documents or page ranges and verify only matching pages returned

### Implementation for User Story 3

- [x] T030 [P] [US3] Add 'document_id' FilterableField to QdrantSettings in settings.py (type: keyword, condition: ==)
- [x] T031 [P] [US3] Add 'physical_page_index' FilterableField to QdrantSettings (type: integer, condition: >=/<=/==)
- [x] T032 [P] [US3] Add 'page_label' FilterableField to QdrantSettings (type: keyword, condition: ==)
- [x] T033 [US3] Verify wrap_filters() in common/wrap_filters.py auto-generates filter parameters for new fields
- [x] T034 [US3] Verify make_indexes() in common/filters.py creates payload indexes for new FilterableFields
- [x] T035 [US3] Update tool_find_description in settings.py to document available PDF filters
- [x] T036 [US3] Test combined filters: document_id="paper.pdf" AND physical_page_index>=10 AND physical_page_index<=20

**Checkpoint**: User Story 3 complete - Advanced filtering by document and page range fully functional

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, validation, and final improvements

- [x] T037 [P] Create docs/PDF_INGESTION.md with usage examples and CLI commands
- [x] T038 [P] Update main README.md to list PDF ingestion in supported file types
- [x] T039 [P] Add PDF ingestion examples to examples/ directory with sample output
- [x] T040 [P] Update CHANGELOG.md with feature summary and breaking changes (if any)
- [x] T041 Run full CI pipeline (Python 3.10-3.13) to verify no regressions
- [x] T042 Validate constitution compliance: async-first, environment config, backward compatibility
- [x] T043 Performance testing: Ingest 100-page PDF and verify completion time <5 minutes
- [x] T044 [P] Add troubleshooting section to docs for common PDF issues (encrypted, corrupted, no text)

**Checkpoint**: Feature complete, documented, and validated

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup (Phase 1) - BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational (Phase 2) - MVP, no other story dependencies
- **US4 (Phase 4)**: Depends on US1 (Phase 3) - Extends data model, must complete before US2/US3 rely on schema
- **US2 (Phase 5)**: Depends on US1 + US4 (Phase 3-4) - Needs complete metadata schema for display
- **US3 (Phase 6)**: Depends on US1 + US4 (Phase 3-4) - Needs complete metadata schema for filtering
- **Polish (Phase 7)**: Depends on all user stories (Phase 3-6)

### User Story Dependencies

```
Setup (Phase 1)
    ↓
Foundational (Phase 2) ← CRITICAL BLOCKER
    ↓
US1: Basic Ingestion (Phase 3) ← MVP
    ↓
US4: Custom Page Numbers (Phase 4) ← Data model extension
    ↓
    ├── US2: Search Display (Phase 5) ← Can start in parallel ──┐
    └── US3: Filtering (Phase 6)      ← Can start in parallel ──┤
                                                                   ↓
                                              Polish (Phase 7)
```

### Within Each User Story

- Models before services
- Core extraction before CLI integration
- Error handling after happy path
- Logging after core functionality
- Story complete before moving to next priority

### Parallel Opportunities

**Phase 1 (Setup)**: T003 and T004 can run in parallel
**Phase 2 (Foundational)**: T010, T011, T012 (fixture creation) can run in parallel
**Phase 3 (US1)**: T013 (model creation) can start immediately, independent of other US1 tasks initially
**Phase 4 (US4)**: Most tasks sequential (extends existing model)
**Phase 6 (US3)**: T030, T031, T032 (FilterableField additions) can run in parallel
**Phase 7 (Polish)**: T037, T038, T039, T040, T044 (documentation) can run in parallel

**After Foundational Phase completes**: US1 (Phase 3) can start immediately
**After US1 + US4 complete**: US2 (Phase 5) and US3 (Phase 6) can proceed in parallel if team capacity allows

---

## Parallel Example: Phase 6 (User Story 3)

```bash
# Launch all FilterableField additions in parallel (different files initially):
Task: "Add 'document_id' FilterableField to settings.py"
Task: "Add 'physical_page_index' FilterableField to settings.py"
Task: "Add 'page_label' FilterableField to settings.py"

# Note: These will eventually merge into the same file but can be developed
# and tested independently in branches before integration
```

---

## Implementation Strategy

### MVP First (User Story 1 + User Story 4 Only)

1. **Complete Phase 1**: Setup → Dependencies installed
2. **Complete Phase 2**: Foundational → PDF extraction ready (CRITICAL)
3. **Complete Phase 3**: User Story 1 → Basic page-by-page ingestion working
4. **Complete Phase 4**: User Story 4 → Custom page numbering supported
5. **STOP and VALIDATE**: Test with academic paper (Roman numerals) and book chapter
6. **Deploy/demo if ready**: MVP delivers page-level PDF ingestion with proper citation support

### Incremental Delivery

1. **Setup + Foundational** → Foundation ready (Phases 1-2)
2. **Add US1** → Test independently → Basic PDF ingestion working (Phase 3)
3. **Add US4** → Test independently → Custom numbering supported (Phase 4) → **MVP COMPLETE** 🎯
4. **Add US2** → Test independently → Search results show page numbers (Phase 5)
5. **Add US3** → Test independently → Advanced filtering available (Phase 6)
6. **Polish** → Documentation and validation (Phase 7)

Each increment adds value without breaking previous functionality.

### Parallel Team Strategy

With multiple developers:

1. **Team completes Setup + Foundational together** (Phases 1-2)
2. **Once Foundational is done**:
   - Developer A: User Story 1 (Phase 3)
3. **After US1 complete**:
   - Developer A: User Story 4 (Phase 4)
4. **After US1 + US4 complete**:
   - Developer A: User Story 2 (Phase 5)
   - Developer B: User Story 3 (Phase 6) ← Can run in parallel
5. **Team completes Polish together** (Phase 7)

---

## MVP Scope (Recommended for First Release)

**Include**:

- ✅ Phase 1: Setup
- ✅ Phase 2: Foundational
- ✅ Phase 3: User Story 1 (P1 - Core ingestion)
- ✅ Phase 4: User Story 4 (P2 - Custom page numbering - essential for citations)

**Defer to v2**:

- ⏭️ Phase 5: User Story 2 (P2 - Search display enhancement)
- ⏭️ Phase 6: User Story 3 (P3 - Advanced filtering)

**Rationale**: US1 + US4 deliver complete page-level ingestion with accurate citation support. US2/US3 are search enhancements that add value but aren't required for the core ingestion capability to be useful.

---

## Task Count Summary

- **Total Tasks**: 44
- **Phase 1 (Setup)**: 4 tasks
- **Phase 2 (Foundational)**: 8 tasks
- **Phase 3 (US1 - P1)**: 8 tasks
- **Phase 4 (US4 - P2)**: 5 tasks
- **Phase 5 (US2 - P2)**: 4 tasks
- **Phase 6 (US3 - P3)**: 7 tasks
- **Phase 7 (Polish)**: 8 tasks

**Parallel Opportunities**: 11 tasks marked [P] can run in parallel within their phases

**MVP Task Count** (Phases 1-4): 25 tasks

---

## Notes

- **[P] tasks**: Different files, no dependencies - can be parallelized
- **[Story] label**: Maps task to specific user story for traceability
- **No tests included**: Specification doesn't request test tasks (can add later if needed)
- **US4 before US2/US3**: Data model must be stable before search features depend on it
- **Constitution compliance**: All async patterns, environment config, backward compatibility maintained
- **File paths**: Absolute paths from repository root for clarity
- **Commit strategy**: Commit after each task or logical group for easy rollback
- **Stop at any checkpoint**: Validate story independently before proceeding
