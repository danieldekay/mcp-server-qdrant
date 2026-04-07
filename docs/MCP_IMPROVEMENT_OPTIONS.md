## MCP Improvement Options

This document summarizes the current functionality of the Qdrant MCP server
and proposes 10 improvement areas. Each item is split into S, M, and L
versions so it can be used as a roadmap rather than a flat backlog.

## Current Functionality

The MCP server already supports a solid retrieval workflow:

- Semantic storage and search via `qdrant-store` and `qdrant-find`
- Runtime schema inspection via `qdrant-get-schema`
- Cross-collection search via `qdrant-find-all`
- PDF page-by-page ingestion via `qdrant-ingest-pdf`
- Document inventory via `qdrant-list-documents`
- Exact text lookup via `qdrant-keyword-search`
- Chapter and table-of-contents discovery via `qdrant-list-chapters`
- Multiple embedding providers including FastEmbed, OpenAI, Gemini,
  and OpenRouter
- Collection statistics, chunking support, and teaching-specific metadata

The strongest next step is to improve ranking quality, lifecycle management,
ingestion reliability, and operational control.

## Proposed Improvements

### 1. Global Ranked Search Across Collections

**Why it matters:** `qdrant-find-all` searches every collection, but it does
not yet behave like a single ranked retrieval surface.

- **S**: Sort all cross-collection hits by score and always show the source
  collection in the result metadata.
- **M**: Deduplicate near-identical hits and merge semantic and keyword
  results into one ranked response.
- **L**: Add an optional reranking stage using a cross-encoder or external
  rerank provider.

### 2. Document Lifecycle Management

**Why it matters:** The MCP can ingest and search documents, but there is no
complete tool surface for update, delete, replace, or reindex operations.

- **S**: Add delete-by-document-id and delete-by-filter tools.
- **M**: Add replace-document and metadata-update tools.
- **L**: Add versioned documents with soft deletion, rollback, and reindex
  history.

### 3. Answer-Oriented Retrieval

**Why it matters:** The current tools return chunks and metadata, which is
good infrastructure but still low-level for many clients.

- **S**: Standardize citation formatting so every result clearly shows
  document, page, chapter, and score.
- **M**: Add a `qdrant-answer` tool that generates short grounded answers
  using retrieved passages only.
- **L**: Add teaching-oriented answer modes such as explain, compare,
  summarize, and quiz.

### 4. Async Ingestion Jobs

**Why it matters:** Large PDF ingests are synchronous today, which makes them
harder to monitor, resume, or cancel.

- **S**: Return richer ingestion summaries with processed, skipped, and failed
  page counts.
- **M**: Add `start-job`, `get-job-status`, and `cancel-job` tools for long
  ingest runs.
- **L**: Build a resumable queue-backed ingestion pipeline with retries and
  checkpoints.

### 5. Collection Administration Tools

**Why it matters:** The MCP can inspect collections, but it cannot fully
manage them from the tool layer.

- **S**: Add list, create, and delete collection tools.
- **M**: Add clone, alias, and migration helpers for switching embedding
  models or schemas.
- **L**: Add an admin plane for quotas, retention, lifecycle policies, and
  schema migration workflows.

### 6. Retrieval Planning and Filter UX

**Why it matters:** The server exposes useful filters, but clients still need
to know how to combine semantic search, keyword search, and document filters
effectively.

- **S**: Extend `qdrant-get-schema` with example queries for common filter
  combinations.
- **M**: Add preset query modes such as course-wide, document-only,
  chapter-only, or exact-term-plus-semantic-expansion.
- **L**: Add a planner tool that converts natural language search intent into
  the appropriate search strategy and filters.

### 7. Payload and Index Consistency

**Why it matters:** The server still carries compatibility logic for legacy and
new payload shapes, which increases complexity and can weaken exact-search
behavior.

- **S**: Normalize all ingested content to one canonical text field.
- **M**: Add a migration tool for legacy collections.
- **L**: Add an automatic compatibility repair pass that detects and fixes
  mixed payload formats.

### 8. Retrieval Evaluation and Regression Testing

**Why it matters:** Functional correctness is well-tested, but retrieval
quality is not yet measured as a first-class concern.

- **S**: Add a golden query set with expected document and page matches.
- **M**: Compare provider quality across FastEmbed, OpenAI, Gemini, and
  OpenRouter on the same sample corpus.
- **L**: Build a repeatable evaluation suite for recall, ranking quality,
  latency, and cost.

### 9. Performance and Cost Controls

**Why it matters:** Ingestion and search work today, but repeated embedding and
reindexing will become expensive as collections grow.

- **S**: Add content hashing to skip duplicate re-embeds.
- **M**: Add embedding caches and idempotent upsert behavior.
- **L**: Support server-side inference, bulk indexing optimization, and
  background compaction workflows.

### 10. Security, Tenancy, and Auditability

**Why it matters:** The server has some safety checks, but shared deployments
need stronger write controls, isolation, and observability.

- **S**: Add stricter path allowlists and collection allowlists for writable
  tools.
- **M**: Add per-collection read/write policies and audit logging.
- **L**: Add real tenant isolation with scoped access, authenticated sessions,
  and administrative audit trails.

## Recommended Priority

If only three improvements should move forward first, these provide the best
product leverage:

1. Global ranked search across collections
2. Document lifecycle management
3. Async ingestion jobs

These three upgrades move the MCP from a good retrieval backend toward a more
complete and production-ready knowledge operations interface.