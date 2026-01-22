# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added - Schema Inspection Tool (2026-01-22)

- **New `qdrant-get-schema` Tool** (`src/mcp_server_qdrant/mcp_server.py`)
  - Runtime configuration inspection tool for MCP clients
  - Returns JSON with collection name, storage mode, embedding provider details, filterable fields, and RAG settings
  - Enables agents to dynamically discover available filters without guessing
  - Zero-argument tool that always returns current server state
  - Prevents hallucinations by providing ground truth about server capabilities

- **Updated Agent Skill Documentation** (`.github/skills/qdrant-mcp/SKILL.md`)
  - Added comprehensive usage guide for `qdrant-get-schema` tool
  - Updated skill description with schema inspection keywords
  - Emphasized workflow of calling get-schema before find operations
  - Enhanced tool reference section with JSON response examples

- **Example Script** (`examples/test_get_schema.py`)
  - Demonstration of programmatic schema inspection
  - Validates schema structure and required fields
  - Shows how to parse and display filter information

### Added - PDF Page-by-Page Ingestion (2026-01-21)

- **PDF Page-Level Extraction** (`src/mcp_server_qdrant/pdf_extractor.py`)
  - Intelligent PDF text extraction using `pypdf` library
  - Dual page numbering system: preserves both physical position and document labels (Roman numerals, chapters, etc.)
  - Async-first implementation wrapping synchronous extraction in thread pools
  - Graceful fallback to sequential numbering when PDF labels are missing

- **Enhanced CLI Ingestion** (`src/mcp_server_qdrant/cli_ingest.py`)
  - Integrated PDF support into `qdrant-ingest` tool
  - Automatic page-by-page decomposition during ingestion
  - Per-page metadata tagging (document_id, physical_index, page_label)

- **PDF metadata filtering**
  - New filterable fields: `document_id`, `physical_page_index`, `page_label`
  - Deep-link support for search results referencing specific pages

### Added - RAG Features Integration (2026-01-04)

**Integrated comprehensive RAG capabilities from [mahmoudimus/mcp-server-qdrant](https://github.com/mahmoudimus/mcp-server-qdrant)**

- **Document Chunking System** (`src/mcp_server_qdrant/chunking.py`)
  - Three intelligent chunking strategies: semantic, sentence-based, and fixed-size
  - Configurable chunk size, overlap, and strategy via environment variables
  - Optional NLTK and tiktoken dependencies with graceful fallback
  - Automatic chunk metadata tracking (`chunk_index`, `total_chunks`, `is_chunk`)
  - Smart overlap handling to preserve context across chunks

- **Bulk Document Ingest CLI** (`src/mcp_server_qdrant/cli_ingest.py`)
  - New `qdrant-ingest` command-line tool for bulk document ingestion
  - Support for 25+ file types (Python, JavaScript, TypeScript, Go, Rust, Java, C++, Markdown, JSON, YAML, HTML, CSS, etc.)
  - Regex-based file filtering with `--include` and `--exclude` patterns
  - Metadata tagging for knowledge base organization
  - Automatic integration with document chunking

- **Set-Based Filtering** (`src/mcp_server_qdrant/sets.py`)
  - Organize documents into logical knowledge base groups
  - Semantic matching for natural language queries to document sets
  - Configuration via `.qdrant_sets.json` file
  - Fuzzy string matching with configurable threshold (30% similarity)
  - Enable with `QDRANT_ENABLE_SEMANTIC_SET_MATCHING` environment variable

- **New Embedding Providers**
  - Model2Vec: Fast, lightweight static embeddings (`model2vec==0.6.0`)
  - Google Gemini: Gemini embedding models support (`google-generativeai>=0.8.3`)
  - OpenAI-compatible: Generic endpoint support for OpenAI-compatible APIs

- **Multiple Collections Support**
  - Configure multiple collections via `COLLECTION_NAMES` environment variable
  - Dynamic `collection_name` parameter added to all tools when multiple collections configured

- **Hybrid Search Support**
  - Dense + sparse vector search for improved accuracy
  - Support for RRF (Reciprocal Rank Fusion) and DBSF (Distribution-Based Score Fusion)
  - Configure with `SPARSE_EMBEDDING_MODEL` environment variable
  - New `qdrant-hybrid-find` tool with `TOOL_HYBRID_FIND_DESCRIPTION` configuration

- **New Environment Variables**
  - `COLLECTION_NAMES`: List of collection names for multiple collections
  - `QDRANT_READ_ONLY`: Enable read-only mode (disables write operations)
  - `USE_UNNAMED_VECTORS`: Use Qdrant's unnamed vector field instead of named vectors
  - `SPARSE_EMBEDDING_MODEL`: Sparse embedding model for hybrid search
  - `OAI_COMPAT_ENDPOINT`: OpenAI-compatible API endpoint URL
  - `OAI_COMPAT_API_KEY`: API key for OpenAI-compatible endpoint
  - `OAI_COMPAT_VEC_SIZE`: Vector size override for OpenAI-compatible embeddings
  - `GEMINI_API_KEY`: API key for Google Gemini embeddings
  - `ENABLE_CHUNKING`: Enable automatic document chunking
  - `MAX_CHUNK_SIZE`: Maximum chunk size in tokens/characters (default: 512)
  - `CHUNK_OVERLAP`: Overlap between consecutive chunks (default: 50)
  - `CHUNK_STRATEGY`: Chunking strategy - "semantic", "sentence", or "fixed" (default: semantic)
  - `QDRANT_ENABLE_SEMANTIC_SET_MATCHING`: Enable set-based document filtering
  - `QDRANT_SETS_CONFIG`: Path to document sets configuration file (default: .qdrant_sets.json)
  - `TOOL_HYBRID_FIND_DESCRIPTION`: Custom description for hybrid find tool

- **New Dependencies**
  - `nltk>=3.8.1`: Sentence tokenization for chunking (optional)
  - `tiktoken>=0.5.0`: Token counting for chunking (optional)
  - `model2vec==0.6.0`: Model2Vec embeddings
  - `google-generativeai>=0.8.3`: Google Gemini embeddings
  - Updated `openai>=1.109.1` (from >=1.0.0)

- **Documentation**
  - Added `RAG_ATTRIBUTION.md`: Comprehensive attribution for RAG features
  - Added `INTEGRATION_SUMMARY.md`: Complete integration documentation
  - Added `.github/copilot-instructions.md`: Developer guide and architecture overview
  - Updated `README.md`: Merged environment variables and added RAG features documentation

### Added - OpenAI Provider Support (2025-12)

- **OpenAI Embedding Provider** (`src/mcp_server_qdrant/embeddings/openai.py`)
  - Support for OpenAI embedding models: `text-embedding-3-small`, `text-embedding-3-large`, `text-embedding-ada-002`
  - Compatible with both single vector and named vector collections
  - Handles API key from environment variable `OPENAI_API_KEY`
  - Backward compatibility with existing OpenAI-based Qdrant databases

- **Enhanced Qdrant Connector**
  - Graceful fallback for missing named vectors in existing databases
  - Support for both legacy format (single vectors with `text` payload) and new format (named vectors with `document` payload)
  - Dual payload structure handling for maximum compatibility

- **Environment Variables**
  - `EMBEDDING_PROVIDER`: Now supports "openai" value
  - `OPENAI_API_KEY`: API key for OpenAI embeddings

- **Dependencies**
  - Added `python-dotenv>=1.1.0` for environment variable management

- **Documentation**
  - Added `OPENAI_IMPLEMENTATION.md`: Complete OpenAI integration documentation
  - Added VS Code MCP configuration examples

### Changed

- **Embedding Provider Type Enum** (`src/mcp_server_qdrant/embeddings/types.py`)
  - Extended to include: `OPENAI`, `MODEL2VEC`, `OAI_COMPAT`, `GEMINI`

- **Settings System** (`src/mcp_server_qdrant/settings.py`)
  - Added `ChunkingSettings` class for RAG configuration
  - Extended `QdrantSettings` with set-based filtering options
  - Updated `EmbeddingProviderSettings` to support new providers

- **QdrantConnector** (`src/mcp_server_qdrant/qdrant.py`)
  - Integrated document chunking in `store()` method
  - Added `_store_single()` helper for individual chunk storage
  - Enhanced `search()` method with fallback for missing named vectors

- **QdrantMCPServer** (`src/mcp_server_qdrant/mcp_server.py`)
  - Added chunking settings support
  - Enhanced tool registration with dynamic collection names

- **Server Initialization** (`src/mcp_server_qdrant/server.py`)
  - Initialize `ChunkingSettings` alongside other settings

### Fixed

- **Vector Name Fallback**: Fixed issue where queries would fail if named vector not found in collection; now gracefully falls back to single-vector query
- **Payload Structure Compatibility**: Enhanced handling of different payload structures (text vs document fields)

## Attribution

### RAG Features

- **Source:** [mahmoudimus/mcp-server-qdrant](https://github.com/mahmoudimus/mcp-server-qdrant)
- **Commit:** [5af3f72](https://github.com/mahmoudimus/mcp-server-qdrant/commit/5af3f72f1afd1afa8dce39976cd29191ddb69887)
- **Author:** Mahmoud Rusty Abdelkader ([@mahmoudimus](https://github.com/mahmoudimus))
- **Date:** November 17, 2025
- **License:** Apache-2.0

### Co-authors

- Claude (Anthropic) - Co-author of RAG features
- Original inspiration from avidspartan1/mcp-server-qdrant-rag fork

## Migration Guide

### Upgrading to RAG Features

The RAG features are **fully backward compatible** and disabled by default. To enable:

1. **Install optional dependencies** (if using chunking):

   ```bash
   uv sync
   # Optional: For enhanced chunking
   pip install nltk tiktoken
   ```

2. **Enable chunking** (optional):

   ```bash
   export ENABLE_CHUNKING=true
   export CHUNK_STRATEGY=semantic  # or "sentence" or "fixed"
   export MAX_CHUNK_SIZE=512
   export CHUNK_OVERLAP=50
   ```

3. **Use bulk ingest** (optional):

   ```bash
   qdrant-ingest ingest /path/to/documents \
     --collection my-collection \
     --knowledge-base my-kb \
     --enable-chunking
   ```

### Using OpenAI Embeddings

To use OpenAI embeddings with existing databases:

1. **Set environment variables**:

   ```bash
   export EMBEDDING_PROVIDER=openai
   export EMBEDDING_MODEL=text-embedding-3-small
   export OPENAI_API_KEY=your-api-key
   ```

2. **Update configuration**: No code changes required; the connector automatically detects and handles different payload structures.

### Breaking Changes

None. All new features are opt-in via environment variables.

---

For detailed information, see:

- [docs/RAG_ATTRIBUTION.md](docs/RAG_ATTRIBUTION.md) - RAG features documentation
- [docs/OPENAI_IMPLEMENTATION.md](docs/OPENAI_IMPLEMENTATION.md) - OpenAI provider documentation
- [docs/development/INTEGRATION_SUMMARY.md](docs/development/INTEGRATION_SUMMARY.md) - Integration process documentation
