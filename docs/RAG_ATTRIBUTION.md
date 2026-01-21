# RAG Features Attribution

## Source

The comprehensive RAG (Retrieval-Augmented Generation) capabilities in this repository were integrated from:

**Repository:** [mahmoudimus/mcp-server-qdrant](https://github.com/mahmoudimus/mcp-server-qdrant)
**Commit:** [5af3f72f1afd1afa8dce39976cd29191ddb69887](https://github.com/mahmoudimus/mcp-server-qdrant/commit/5af3f72f1afd1afa8dce39976cd29191ddb69887)
**Author:** Mahmoud Rusty Abdelkader ([@mahmoudimus](https://github.com/mahmoudimus))
**Date:** November 17, 2025
**License:** Apache-2.0 (same as this project)

## Features Added

The following RAG features were integrated from the upstream fork:

### 1. Document Chunking (`src/mcp_server_qdrant/chunking.py`)

- **Three intelligent chunking strategies:**
  - **Semantic:** Splits at natural boundaries (paragraphs, sentences)
  - **Sentence:** Preserves structural integrity at sentence boundaries
  - **Fixed:** Predictable token/character-based splitting
- **Configurable parameters:** `ENABLE_CHUNKING`, `MAX_CHUNK_SIZE`, `CHUNK_OVERLAP`, `CHUNK_STRATEGY`
- **Automatic chunk metadata:** `chunk_index`, `total_chunks`, `is_chunk`
- **Optional dependencies:** NLTK and tiktoken for enhanced processing
- **Smart overlap handling** to preserve context across chunks

### 2. Document Ingest CLI (`src/mcp_server_qdrant/cli_ingest.py`)

- **New `qdrant-ingest` command-line tool** for bulk document ingestion
- **Commands:**
  - `ingest`: Process files/directories with 25+ supported file types
  - `list`: Display all available collections
- **Supported file types:**
  - Code: `.py`, `.js`, `.ts`, `.go`, `.rs`, `.java`, `.cpp`, etc.
  - Documents: `.txt`, `.md`
  - Config: `.json`, `.yaml`, `.toml`
  - Web: `.html`, `.css`
- **Regex-based file filtering** (`--include`, `--exclude` patterns)
- **Metadata tagging** (knowledge_base, doc_type)
- **Automatic chunking integration**

### 3. Set-Based Filtering (`src/mcp_server_qdrant/sets.py`)

- **Organize documents into logical knowledge base groups**
- **Semantic matching** for natural language queries to document sets
- **Configuration via `.qdrant_sets.json` file**
- **Each set has:** slug (unique ID), description, aliases
- **Fuzzy string matching** with configurable threshold (30% similarity)
- **Enable with:** `QDRANT_ENABLE_SEMANTIC_SET_MATCHING`

### 4. Core Integration Updates

- **Modified files:**
  - `src/mcp_server_qdrant/mcp_server.py`: Added chunking settings support
  - `src/mcp_server_qdrant/qdrant.py`: Integrated chunking logic in store operations
  - `src/mcp_server_qdrant/server.py`: Initialize ChunkingSettings
  - `src/mcp_server_qdrant/settings.py`: New ChunkingSettings class and set-based filtering config

### 5. New Dependencies

- `nltk>=3.8.1` - Sentence tokenization (optional, with fallback)
- `tiktoken>=0.5.0` - Token counting (optional, with fallback)
- `model2vec==0.6.0` - Fast, lightweight static embeddings
- `google-generativeai>=0.8.3` - Google Gemini embeddings support

## Integration Notes

### Merged with Existing Features

This integration was carefully merged with our existing work:

- **OpenAI Provider:** Our custom OpenAI embedding provider (`src/mcp_server_qdrant/embeddings/openai.py`) was preserved
- **Dependencies:** Combined both dependency sets in `pyproject.toml`
- **Documentation:** Merged environment variables table in `README.md` to include both feature sets
- **Embedding providers:** Added "openai" to the list of supported providers alongside the new ones

### Compatibility

- All features are **fully backward compatible**
- Optional dependencies disable cleanly when not installed
- Graceful degradation for NLTK/tiktoken when unavailable
- Chunking is disabled by default (`ENABLE_CHUNKING=false`)

## Changes Made During Integration

1. **Dependencies merge:** Combined `openai>=1.109.1` with our `python-dotenv>=1.1.0`
2. **README update:** Added "openai" to the list of embedding providers
3. **No code conflicts:** The RAG features integrate cleanly with our OpenAI provider implementation

## Acknowledgments

Special thanks to:

- **Mahmoud Rusty Abdelkader** ([@mahmoudimus](https://github.com/mahmoudimus)) for implementing these comprehensive RAG features
- **Claude** (co-author) for assistance in the original implementation
- Original inspiration from **avidspartan1/mcp-server-qdrant-rag** fork

## Related Documentation

- **Original commit message:** See commit `d5cadba` in this repository
- **Upstream repository:** <https://github.com/mahmoudimus/mcp-server-qdrant>
- **Our OpenAI implementation:** See [OPENAI_IMPLEMENTATION.md](OPENAI_IMPLEMENTATION.md) for our custom OpenAI provider details
