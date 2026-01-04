# mcp-server-qdrant Developer Guide

## Architecture Overview

This is a **Model Context Protocol (MCP) server** that bridges LLM applications with Qdrant vector database for semantic memory/search. Built on **FastMCP framework** (similar to FastAPI), exposing two core tools: `qdrant-store` and `qdrant-find`.

### Core Components

- **[mcp_server.py](../src/mcp_server_qdrant/mcp_server.py)**: `QdrantMCPServer(FastMCP)` class registers MCP tools using FastMCP decorators
- **[qdrant.py](../src/mcp_server_qdrant/qdrant.py)**: `QdrantConnector` handles all Qdrant operations (store/search/collection management)
- **[settings.py](../src/mcp_server_qdrant/settings.py)**: Pydantic settings classes (`QdrantSettings`, `EmbeddingProviderSettings`, `ToolSettings`, `ChunkingSettings`) load from environment variables
- **[embeddings/](../src/mcp_server_qdrant/embeddings/)**: Provider abstraction (`EmbeddingProvider` ABC) with FastEmbed, OpenAI, Model2Vec, and Gemini implementations
- **[common/filters.py](../src/mcp_server_qdrant/common/filters.py)**: Dynamic filterable field system using Qdrant conditions
- **[chunking.py](../src/mcp_server_qdrant/chunking.py)**: RAG document chunking (semantic/sentence/fixed strategies) - from mahmoudimus fork
- **[cli_ingest.py](../src/mcp_server_qdrant/cli_ingest.py)**: Bulk document ingestion CLI tool - from mahmoudimus fork
- **[sets.py](../src/mcp_server_qdrant/sets.py)**: Set-based filtering for organizing documents - from mahmoudimus fork

### Key Architectural Patterns

**Environment-First Configuration**: ALL config via environment variables (see `settings.py`). No CLI args supported.

**Dual Vector Format Support**: `QdrantConnector.store()` handles:

- **Legacy**: Single vector with `text` payload field (for backward compatibility)
- **Named vectors**: `{vector_name: embedding}` with `document` and `metadata` payload structure

**Dynamic Tool Signature Generation**: `wrap_filters()` in [common/wrap_filters.py](../src/mcp_server_qdrant/common/wrap_filters.py) dynamically replaces `query_filter` parameter with individual filter fields based on `FilterableField` configuration, auto-generating proper FastMCP signatures.

**Provider Factory Pattern**: `create_embedding_provider()` in [embeddings/factory.py](../src/mcp_server_qdrant/embeddings/factory.py) instantiates providers based on `EMBEDDING_PROVIDER` env var.

## Development Workflows

### Running Tests

```bash
uv run pytest                     # All tests
uv run pytest tests/test_qdrant_integration.py  # Specific test
```

### Local Development with MCP Inspector

```bash
QDRANT_URL=":memory:" COLLECTION_NAME="test" \
fastmcp dev src/mcp_server_qdrant/server.py
# Opens browser at http://localhost:5173 for interactive testing
```

### Running the Server

```bash
# Stdio (default, for Claude Desktop)
QDRANT_URL="http://localhost:6333" COLLECTION_NAME="my-collection" \
uvx mcp-server-qdrant

# SSE transport (for Cursor/Windsurf/remote clients)
FASTMCP_PORT=8000 uvx mcp-server-qdrant --transport sse

# Docker
docker build -t mcp-server-qdrant .
docker run -p 8000:8000 -e QDRANT_URL="..." mcp-server-qdrant
```

### Project Entry Point

[main.py](../src/mcp_server_qdrant/main.py) is the CLI entry point (defined in `pyproject.toml` scripts). It parses `--transport` arg, then imports and runs `mcp` from [server.py](../src/mcp_server_qdrant/server.py).

## Code Conventions

### Settings & Environment Variables

- Use Pydantic `BaseSettings` with `validation_alias` for env vars (e.g., `validation_alias="QDRANT_URL"`)
- **CRITICAL**: `QDRANT_URL` and `QDRANT_LOCAL_PATH` are mutually exclusive
- Default embedding: `sentence-transformers/all-MiniLM-L6-v2` (FastEmbed)
- For OpenAI: set `EMBEDDING_PROVIDER=openai`, `EMBEDDING_MODEL=text-embedding-3-small`, and `OPENAI_API_KEY`

### Filterable Fields System

Define searchable metadata fields in `QdrantSettings.filterable_fields`:

```python
filterable_fields = [
    FilterableField(
        name="source",
        description="Source of the document",
        field_type="keyword",  # keyword|integer|float|boolean
        condition="==",  # ==|!=|>|>=|<|<=|any|except
        required=False
    )
]
```

These auto-generate Qdrant payload indexes AND tool parameters via `wrap_filters()`.

### Async Patterns

- ALL embedding methods are `async` (`embed_documents`, `embed_query`)
- ALL Qdrant operations use `AsyncQdrantClient`
- Test fixtures use `@pytest.fixture` with `async def`
- Run async tests with `@pytest.mark.asyncio`

### Embedding Provider Contract

Implement 4 methods in `EmbeddingProvider` ABC:

1. `async embed_documents(documents: list[str]) -> list[list[float]]`
2. `async embed_query(query: str) -> list[float]`
3. `get_vector_name() -> str` - Returns vector name or empty string for legacy single-vector format
4. `get_vector_size() -> int` - Returns embedding dimension

### Tool Registration Pattern

In `QdrantMCPServer.setup_tools()`:

```python
@self.tool(description=self.tool_settings.tool_find_description)
async def find(ctx: Context, query: Annotated[str, Field(...)], ...):
    results = await self.qdrant_connector.search(query, ...)
    return "\n".join(self.format_entry(e) for e in results)
```

## Critical Implementation Details

### Payload Structure Handling

In [qdrant.py](../src/mcp_server_qdrant/qdrant.py#L80-L95), the store method checks `get_vector_name()`:

- If named vector: `{"document": text, "metadata": {...}}`
- If legacy: `{"text": text, ...metadata}` (flat structure)

This ensures compatibility with existing Qdrant databases created before named-vector support.

### Collection Auto-Creation

`_ensure_collection_exists()` creates collections with proper vector config and payload indexes for filterable fields. Always called before store/search.

### Metadata Path Convention

All metadata stored under `metadata` key (defined in `settings.METADATA_PATH`). Filters reference fields as `metadata.field_name`.

### OpenAI Integration

See [OPENAI_IMPLEMENTATION.md](../OPENAI_IMPLEMENTATION.md) for details on OpenAI embedding provider added for backward compatibility with existing databases using `text-embedding-3-small` (1536 dims).

### RAG Features Integration

See [RAG_ATTRIBUTION.md](../RAG_ATTRIBUTION.md) for comprehensive documentation on:
- Document chunking strategies (semantic/sentence/fixed)
- Bulk ingest CLI tool (`qdrant-ingest`)
- Set-based filtering for knowledge base organization
- Source: mahmoudimus/mcp-server-qdrant fork, Apache-2.0 license

### Chunking Strategies

[chunking.py](../src/mcp_server_qdrant/chunking.py) provides:

[chunking.py](../src/mcp_server_qdrant/chunking.py) provides:

- `ChunkStrategy.SEMANTIC`: Paragraph-based with sentence boundaries (requires NLTK)
- `ChunkStrategy.SENTENCE`: Sentence-level chunking
- `ChunkStrategy.FIXED`: Fixed-size with overlap
- Optional tiktoken for token-aware chunking

## FastMCP Specifics

- Use `@self.tool()` decorator for tools (NOT `@mcp.tool()` - instance method)
- `Context` parameter provides execution context but rarely needed
- Type hints with `Annotated[type, Field(description="...")]` auto-generate tool schemas
- Tool descriptions from `ToolSettings` can be customized via env vars for different use cases (e.g., code search vs memory)

## Testing Patterns

```python
@pytest.fixture
async def qdrant_connector(embedding_provider):
    return QdrantConnector(
        qdrant_url=":memory:",  # In-memory for tests
        qdrant_api_key=None,
        collection_name=f"test_{uuid.uuid4().hex}",
        embedding_provider=embedding_provider,
    )

@pytest.mark.asyncio
async def test_store_and_search(qdrant_connector):
    entry = Entry(content="...", metadata={"key": "value"})
    await qdrant_connector.store(entry)
    results = await qdrant_connector.search("query")
    assert len(results) > 0
```

## Common Pitfalls

- **Don't add CLI arguments** - use environment variables via Pydantic settings
- **Don't forget `await`** on all Qdrant/embedding operations
- **Remember dual payload format** when modifying store/search logic
- **Test with `:memory:` Qdrant** for fast, isolated tests
- **Check `get_vector_name()`** return value before assuming named vectors
- When adding new embedding providers, update [factory.py](../src/mcp_server_qdrant/embeddings/factory.py) enum and factory function

## VS Code Configuration

See `.vscode/mcp.json` for workspace MCP server config. Use `"type": "stdio"` with `uv run` for local development.
