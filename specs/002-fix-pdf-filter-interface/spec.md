# Feature Specification: Fix PDF Filter Parameter Exposure in MCP Tool Interface

**Feature Branch**: `002-fix-pdf-filter-interface`
**Created**: January 21, 2026
**Status**: Draft
**Input**: User description: "The PDF page numbering infrastructure is implemented and storing data correctly, but the filtering feature needs debugging in how it exposes parameters through the MCP tool interface. The data is there with proper metadata — we just can't filter by it through the current tool signature."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Filter Search Results by Document ID (Priority: P1)

An MCP client user wants to search for content within a specific PDF document by providing the document identifier in their search query, limiting results to only that document.

**Why this priority**: This is the most fundamental filtering capability - being able to search within a single document. Without this working through the MCP interface, users cannot leverage the page-level PDF data that's already stored correctly.

**Independent Test**: Can be fully tested by connecting an MCP client (Claude Desktop, Cursor, etc.), calling the qdrant-find tool with a document_id parameter, and verifying that only results from that specific document are returned. This demonstrates the filter is exposed and functional.

**Acceptance Scenarios**:

1. **Given** an MCP client is connected to the server and multiple PDF documents are stored, **When** the user calls qdrant-find with a document_id filter, **Then** only pages from that specific document appear in results
2. **Given** an MCP client inspects the qdrant-find tool signature, **When** viewing the available parameters, **Then** document_id is visible and documented as a filter option
3. **Given** a user provides an invalid or non-existent document_id, **When** the search executes, **Then** no results are returned (empty result set) without errors

---

### User Story 2 - Filter by Physical Page Index (Priority: P2)

An MCP client user wants to retrieve content from a specific page position within a document by specifying the physical page index (0-based sequential position).

**Why this priority**: Enables users to jump directly to a specific page by its position in the document, which is essential for workflows that track page numbers sequentially (e.g., "show me page 5").

**Independent Test**: Connect an MCP client, call qdrant-find with both document_id and physical_page_index parameters, verify that only the requested page is returned.

**Acceptance Scenarios**:

1. **Given** an MCP client has stored a 10-page PDF, **When** the user calls qdrant-find with physical_page_index=5, **Then** only content from the 6th physical page (0-indexed) is returned
2. **Given** a user combines document_id and physical_page_index filters, **When** the search executes, **Then** results match both criteria (specific page from specific document)
3. **Given** a user requests a physical_page_index that doesn't exist, **When** the search executes, **Then** an empty result set is returned

---

### User Story 3 - Filter by Page Label (Priority: P2)

An MCP client user wants to search for content on a page using its original document page label (e.g., "iv", "45") rather than physical position, enabling citation-accurate searching.

**Why this priority**: Critical for academic and professional use cases where users reference original page numbers from source documents. Complements physical page index filtering for different use cases.

**Independent Test**: Ingest a PDF with custom numbering, call qdrant-find with page_label parameter (e.g., page_label="45"), verify that only the page with that label is returned.

**Acceptance Scenarios**:

1. **Given** a PDF chapter with pages labeled 45-60 is ingested, **When** a user calls qdrant-find with page_label="47", **Then** only content from the page labeled "47" is returned
2. **Given** a PDF with Roman numeral pages (i, ii, iii), **When** a user filters by page_label="ii", **Then** only the second page's content appears in results
3. **Given** multiple documents with the same page label, **When** filtering by page_label alone, **Then** all matching pages across documents are returned unless combined with document_id filter

---

### User Story 4 - Combine Multiple Filters in One Query (Priority: P3)

An MCP client user wants to apply multiple filters simultaneously (e.g., search within document X for pages 10-20 with specific content) to perform precise, targeted searches.

**Why this priority**: Enables power users to perform complex queries, but basic single-filter searches (P1-P2) already provide substantial value.

**Independent Test**: Call qdrant-find with multiple filter parameters (document_id + physical_page_index + search query), verify all filters are applied correctly.

**Acceptance Scenarios**:

1. **Given** a user provides document_id and physical_page_index together, **When** the search executes, **Then** results must match both filter criteria
2. **Given** a user provides conflicting filters (e.g., page_label and physical_page_index for different pages), **When** the search executes, **Then** results respect both constraints (possibly returning empty results if no match)
3. **Given** a user combines semantic search query text with metadata filters, **When** the search executes, **Then** results match both the semantic content and the metadata constraints

---

### Edge Cases

- What happens when a user provides a filter parameter with an invalid data type (e.g., string for physical_page_index)?
- How does the system handle special characters in page_label filters (e.g., "A-1", "Appendix B")?
- What happens when no documents match the filter criteria?
- How does the tool signature handle optional vs required filter parameters?
- What happens when a filter parameter name conflicts with existing query parameters?
- How are case sensitivity differences handled in document_id and page_label matching?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The qdrant-find MCP tool MUST expose document_id as a filterable parameter in its signature
- **FR-002**: The qdrant-find MCP tool MUST expose physical_page_index as a filterable parameter in its signature
- **FR-003**: The qdrant-find MCP tool MUST expose page_label as a filterable parameter in its signature
- **FR-004**: System MUST map the exposed filter parameters to the correct Qdrant metadata fields (metadata.document_id, metadata.physical_page_index, metadata.page_label)
- **FR-005**: System MUST apply filters as conditions in the Qdrant query to restrict results based on provided parameters
- **FR-006**: Tool parameters MUST include descriptions that clearly explain the purpose and expected format of each filter
- **FR-007**: System MUST validate filter parameter data types before executing queries (integer for physical_page_index, string for document_id and page_label)
- **FR-008**: System MUST handle optional filter parameters - filters should only be applied when explicitly provided by the user
- **FR-009**: System MUST support combining multiple filter parameters in a single query without conflicts
- **FR-010**: System MUST maintain backward compatibility with existing qdrant-find queries that don't use filters
- **FR-011**: Filter parameters MUST be visible to MCP clients through standard tool introspection (e.g., FastMCP tool schema generation)
- **FR-012**: System MUST use exact match filtering for document_id and page_label (not partial/fuzzy matching)
- **FR-013**: System MUST use equality comparison for physical_page_index filtering

### Key Entities *(include if feature involves data)*

- **MCP Tool Signature**: Defines the parameters available to MCP clients, including filter fields (document_id, physical_page_index, page_label)
- **FilterableField Configuration**: Settings that define which metadata fields should be exposed as filters, including field type, condition, and description
- **Qdrant Query Filter**: The translated filter condition object passed to Qdrant based on provided parameter values

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: MCP clients can successfully filter searches by document_id and receive only results from the specified document (100% accuracy)
- **SC-002**: MCP clients can successfully filter searches by physical_page_index and receive only results from the specified page position (100% accuracy)
- **SC-003**: MCP clients can successfully filter searches by page_label and receive only results with the matching label (100% accuracy)
- **SC-004**: Tool parameter documentation in MCP client interfaces clearly shows all three filter parameters with descriptions
- **SC-005**: Combining multiple filters (e.g., document_id + physical_page_index) returns results that match all provided criteria (100% accuracy)
- **SC-006**: Queries without filter parameters continue to work as before, returning unfiltered results
- **SC-007**: Invalid filter values (wrong type, non-existent IDs) return empty results without causing errors or crashes
