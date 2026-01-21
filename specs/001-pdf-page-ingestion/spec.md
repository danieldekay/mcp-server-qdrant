# Feature Specification: PDF Page-by-Page Ingestion

**Feature Branch**: `001-pdf-page-ingestion`
**Created**: January 21, 2026
**Status**: Draft
**Input**: User description: "Add PDF page-by-page ingestion with metadata for page numbers"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ingest PDF with Page-Level Granularity (Priority: P1)

A user has a PDF document (e.g., a research paper, technical manual, or book) and wants to store each page as a separate searchable entry in Qdrant. Each page should include metadata indicating its page number, allowing for precise retrieval and citation.

**Why this priority**: This is the core functionality that delivers immediate value - enabling page-level semantic search across PDF documents. Without this, users cannot leverage the existing ingestion pipeline for PDF content at page granularity.

**Independent Test**: Can be fully tested by providing a sample PDF file, ingesting it via the CLI tool, and verifying that each page is stored as a separate vector entry with correct page number metadata. Delivers the ability to search and retrieve specific pages from PDFs.

**Acceptance Scenarios**:

1. **Given** a user has a 10-page PDF document, **When** they ingest it using the ingestion tool, **Then** the system creates 10 separate entries in Qdrant, each containing the text content of one page
2. **Given** a user ingests a PDF, **When** they query the database, **Then** each result includes metadata with the original PDF filename and page number
3. **Given** a user ingests a multi-page PDF, **When** they search for content that appears on page 5, **Then** the search results identify page 5 as the source
4. **Given** a user has already ingested some PDFs, **When** they ingest another PDF with the same filename, **Then** the system handles this appropriately without creating duplicate entries

---

### User Story 2 - Search and Retrieve by Page Reference (Priority: P2)

A user searches for content across their PDF collection and wants to see results that reference specific pages, enabling them to locate exact sources within documents.

**Why this priority**: Enhances the core ingestion capability by making search results actionable - users can immediately identify which page in which document contains relevant information.

**Independent Test**: After ingesting PDFs (from P1), perform semantic searches and verify that results display page numbers alongside content, allowing users to jump directly to the relevant page in the source document.

**Acceptance Scenarios**:

1. **Given** a user has ingested multiple PDFs, **When** they search for "machine learning algorithms", **Then** results show which document and page number contains the matching content
2. **Given** search results include page metadata, **When** a user views the results, **Then** they can easily identify the source (filename + page number) for each match
3. **Given** a user searches for content present on multiple pages across documents, **When** viewing results, **Then** all matching pages are returned with distinct page number metadata

---

### User Story 3 - Filter by Document and Page Range (Priority: P3)

A user wants to search within a specific PDF document or limit results to certain page ranges, enabling focused searches within large document collections.

**Why this priority**: Provides advanced search capabilities for power users with large PDF collections, but basic search (P2) already delivers value without this filtering.

**Independent Test**: Ingest PDFs, then test search queries with metadata filters for specific documents or page ranges, verifying that only matching pages are returned.

**Acceptance Scenarios**:

1. **Given** a user has ingested multiple PDFs, **When** they search with a filter for a specific document name, **Then** only pages from that document are returned
2. **Given** a user searches with a page range filter (e.g., pages 1-20), **When** the query executes, **Then** only results from within that page range are returned
3. **Given** a user combines document and page range filters, **When** searching, **Then** results match both criteria

---

### User Story 4 - Handle Custom PDF Page Numbering (Priority: P2)

A user ingests a PDF that has custom page numbering (e.g., a book chapter starting at page 45, or an academic paper with Roman numerals for the preface), and wants both the physical page position and the document's internal page number preserved for accurate citation.

**Why this priority**: Essential for academic and professional use cases where proper citation requires the actual page number from the source document, not just the sequential position. Common in book chapters, research papers, and multi-part documents.

**Independent Test**: Ingest a PDF with custom page numbering (e.g., chapter starting at page 45), verify that metadata includes both the physical page index (0-based or 1-based position) and the PDF's internal page label, allowing users to cite the correct page number.

**Acceptance Scenarios**:

1. **Given** a user ingests a PDF chapter where page numbering starts at 45, **When** the second physical page is stored, **Then** metadata includes both physical_page=2 and page_label="45" (or page_number=46)
2. **Given** a user ingests a PDF with Roman numeral page numbers (i, ii, iii), **When** pages are stored, **Then** metadata preserves the Roman numeral labels alongside physical positions
3. **Given** a user searches for content from a document with custom numbering, **When** results are displayed, **Then** the original page number from the document is shown for proper citation
4. **Given** a PDF has mixed numbering schemes (Roman numerals then Arabic), **When** all pages are ingested, **Then** each page's metadata reflects its specific numbering style

---

### Edge Cases

- What happens when a PDF page contains no extractable text (e.g., scanned images without OCR)?
- How does the system handle PDFs with non-standard page numbering (e.g., Roman numerals in front matter)?
- What happens when a PDF is password-protected or encrypted?
- How does the system handle extremely large PDFs (e.g., 1000+ pages)?
- What happens when PDF extraction fails mid-document (e.g., corrupted page)?
- How are multi-column layouts or complex page structures handled during text extraction?
- What happens when the same PDF is ingested multiple times?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST extract text content from each page of a PDF document independently
- **FR-002**: System MUST store each page as a separate entry in the Qdrant collection
- **FR-003**: System MUST include metadata with each stored page containing at minimum: source filename and page number
- **FR-004**: System MUST support the existing ingestion CLI tool (`qdrant-ingest`) for PDF processing
- **FR-005**: System MUST maintain the original page order information in metadata for sequential navigation
- **FR-006**: System MUST handle PDFs with varying page counts (from single-page to multi-hundred page documents)
- **FR-007**: System MUST skip pages with no extractable text and log a warning, rather than failing the entire ingestion
- **FR-008**: System MUST include PDF file extension (`.pdf`) in the list of supported file types for ingestion
- **FR-009**: System MUST allow users to specify whether to use the existing chunking feature per page or treat each page as a single unit
- **FR-010**: Users MUST be able to search for content and receive results that include page number metadata
- **FR-011**: Users MUST be able to filter search results by document name and page number using the existing filterable fields system
- **FR-012**: System MUST provide clear error messages when PDF processing fails (e.g., corrupted file, password protection)
- **FR-013**: System MUST extract and preserve PDF internal page labels/numbers when available (e.g., custom page numbering, Roman numerals)
- **FR-014**: System MUST store both physical page position (sequential index) and original page label/number in metadata for accurate citation

### Key Entities

- **PDF Page Entry**: Represents a single page from a PDF document stored in Qdrant
  - Text content extracted from the page
  - Physical page index (0-based or 1-based sequential position in document)
  - Page label/number (original page numbering from PDF, may be custom/non-sequential)
  - Source filename
  - Document title (if available from PDF metadata)
  - Total page count of source document
  - File path of original PDF
  - Optional: PDF metadata (author, creation date, etc.)
  - Optional: chunk_index and total_chunks (if per-page chunking is enabled)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can ingest a 100-page PDF document and successfully store all 100 pages as separate searchable entries within 5 minutes
- **SC-002**: Search queries return results with accurate page number metadata 100% of the time
- **SC-003**: Users can locate specific content and identify the exact page number in the source document within 3 search attempts
- **SC-004**: System successfully processes PDFs with varying characteristics (different sizes, page counts, layouts) with a success rate of 95% or higher
- **SC-005**: Page-level granularity improves search precision by reducing average result size to single pages instead of entire documents
- **SC-006**: Users ingesting PDF collections report reduced time to locate specific information compared to document-level ingestion

## Assumptions *(optional)*

- Users have PDF files accessible on their local filesystem or network storage
- PDF text extraction will use standard Python libraries (e.g., PyPDF2, pdfplumber, or pymupdf)
- The existing chunking feature can optionally be applied to pages that exceed reasonable size limits
- Users are working with primarily text-based PDFs; OCR for scanned documents is out of scope for initial implementation
- PDFs may have custom page numbering (starting at arbitrary numbers, Roman numerals, or mixed schemes)
- Most PDF libraries provide access to page labels/numbers through their metadata APIs
- The existing metadata filtering system will be extended to support document name and page number filters

## Dependencies *(optional)*

- Requires a PDF text extraction library to be added as a dependency (e.g., `pymupdf>=1.23.0`, `PyPDF2>=3.0.0`, or `pdfplumber>=0.10.0`)
- Depends on existing `cli_ingest.py` bulk ingestion tool
- Depends on existing `FilterableField` system for metadata filtering
- Depends on existing `QdrantConnector` for storing entries
- Depends on existing embedding provider infrastructure

## Out of Scope *(optional)*

- OCR (Optical Character Recognition) for scanned PDF images
- PDF form field extraction
- Extraction of images, tables, or charts from PDFs
- PDF editing or modification capabilities
- PDF generation or creation
- Handling of PDF annotations or comments
- Interactive PDF features (e.g., hyperlinks, JavaScript)
- Non-PDF document formats (Word, PowerPoint, etc.) - though these could be future enhancements
