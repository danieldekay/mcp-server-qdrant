# Implementation Plan: PDF Page-by-Page Ingestion

**Branch**: `001-pdf-page-ingestion` | **Date**: 2026-01-23 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-pdf-page-ingestion/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Implement PDF page-by-page ingestion capability where each PDF page is stored as a separate Qdrant entry with comprehensive metadata. **Technical approach**: Extend existing `cli_ingest.py` bulk ingestion tool with PDF-specific processing using **pypdf library** for page label extraction. Implement async wrappers using `asyncio.to_thread()` pattern to maintain constitution compliance. Store dual page numbering (physical_page_index + page_label) to support academic/professional PDFs with custom numbering schemes (Roman numerals, chapter numbers, etc.).

## Technical Context

**Language/Version**: Python >=3.10 (project supports 3.10-3.13)
**Primary Dependencies**:

- FastMCP 2.7.0+ (MCP server framework)
- Qdrant Client 1.12.0+ (vector database client, AsyncQdrantClient)
- Pydantic 2.10.6+ (settings and validation)
- **pypdf 5.1.0+** (NEW - PDF text extraction and page label metadata)
- Optional: NLTK, tiktoken (for chunking, graceful degradation required)

**Storage**: Qdrant vector database (local or remote, :memory: for tests)
**Testing**: pytest with pytest-asyncio (asyncio_mode = "auto"), Python 3.10-3.13 matrix in CI
**Target Platform**: Cross-platform (macOS, Linux, Windows) - MCP server + CLI tool
**Project Type**: Single project - Python package with CLI scripts

**Performance Goals**:

- Async I/O throughout (non-negotiable per constitution)
- PDF parsing: Acceptable performance for typical documents (<1000 pages)
- No performance regression for existing non-PDF ingestion

**Constraints**:

- **Async-first architecture**: ALL I/O operations must be async (constitution principle II)
- **Environment-first config**: No CLI args except --transport (constitution principle I)
- **Backward compatibility**: Must not break existing ingestion workflows (constitution principle III)
- **Graceful degradation**: Handle PDFs without page labels (constitution principle VI)
- **Type safety**: Full type hints, Pydantic models (constitution principle VII)

**Scale/Scope**:

- Target: Academic papers, books, technical documentation (10-1000 pages typical)
- Page label formats: Roman numerals, Arabic, chapter prefixes, appendices
- Bulk ingestion: Multiple PDFs in directory tree
- Search: Filter by document_id, page_range, page_label pattern

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Design Evaluation

✅ **I. Environment-First Configuration**

- Feature uses existing Pydantic BaseSettings pattern
- New `PdfIngestionSettings` class for PDF-specific config
- No new CLI arguments except feature flags (--enable-pdf-ingestion)
- Compliant with "no CLI args except --transport" rule

✅ **II. Async-First Architecture**

- **Strategy**: Wrap pypdf sync operations with `asyncio.to_thread()`
- Pattern: `async def extract_page_label() -> str: return await asyncio.to_thread(_sync_extract)`
- Maintains async API contract throughout codebase
- No blocking I/O in main event loop

✅ **III. Backward Compatibility**

- New feature, no breaking changes to existing functionality
- Extends `cli_ingest.py` with new `--pdf` flag
- Existing document ingestion workflows unaffected
- New FilterableFields (physical_page_index, page_label) are additive

✅ **IV. Provider Abstraction**

- PDF extraction isolated in new `pdf_extractor.py` module
- Future: Could support multiple PDF backends if needed
- Follows existing embedding provider pattern

✅ **V. Test Coverage**

- Unit tests: page label extraction, async wrappers, error handling
- Integration tests: full PDF ingestion pipeline
- Test fixtures: Various PDF numbering schemes
- CI: Python 3.10-3.13 matrix

✅ **VI. Graceful Degradation**

- **Fallback**: If PDF has no page labels, use `Page N` format
- **Pattern**: `label = reader.page_labels.get(index) or f"Page {index + 1}"`
- Similar to NLTK/tiktoken optional dependency handling

✅ **VII. Type Safety**

- New Pydantic models: `PDFPageEntry`, `PdfIngestionSettings`
- Full type hints: `async def extract_page_label(pdf_path: str, index: int) -> Optional[str]`
- Comprehensive docstrings with parameter types

### Post-Design Re-Evaluation (Phase 1)

*[To be completed after data model and contracts are designed]*

## Project Structure

### Documentation (this feature)

```text
specs/001-pdf-page-ingestion/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command) - COMPLETE
├── data-model.md        # Phase 1 output (/speckit.plan command) - PENDING
├── quickstart.md        # Phase 1 output (/speckit.plan command) - PENDING
├── contracts/           # Phase 1 output (/speckit.plan command) - PENDING
│   ├── cli-interface.yaml     # CLI tool extensions
│   └── metadata-schema.yaml   # PDF page metadata structure
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/mcp_server_qdrant/
├── pdf_extractor.py     # NEW - PDF text and metadata extraction
├── cli_ingest.py        # MODIFIED - Add PDF ingestion support
├── settings.py          # MODIFIED - Add PdfIngestionSettings
├── qdrant.py            # MODIFIED - Handle PDF page entries
├── chunking.py          # EXISTING - May be used for large PDF pages
├── common/
│   └── filters.py       # MODIFIED - Add page_label, physical_page_index fields
└── embeddings/          # EXISTING - Unchanged

tests/
├── test_pdf_extractor.py           # NEW - PDF extraction unit tests
├── test_pdf_ingestion_integration.py # NEW - Full pipeline integration tests
├── test_settings.py                # MODIFIED - Add PDF settings tests
└── fixtures/
    ├── academic_paper.pdf          # NEW - Roman numeral front matter
    ├── book_chapters.pdf           # NEW - Chapter-based numbering
    └── no_labels.pdf               # NEW - PDF without custom labels
```

└── [platform-specific structure: feature modules, UI flows, platform tests]

```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

**No violations.** All constitution principles are satisfied:
- Async-first achieved via `asyncio.to_thread()` wrapper pattern
- Environment-first config maintained (new Pydantic settings only)
- Backward compatibility preserved (additive changes only)
- Graceful degradation for PDFs without page labels
