# AGENTS.md

## Project Overview

**mcp-server-qdrant** is a Model Context Protocol (MCP) server that provides semantic memory and retrieval capabilities using Qdrant vector database. Built on the FastMCP framework (similar to FastAPI), it bridges LLM applications with vector search functionality.

**Key Technologies:**

- Python 3.10+ with async/await patterns
- FastMCP for MCP server implementation
- Qdrant vector database (AsyncQdrantClient)
- Multiple embedding providers: FastEmbed, OpenAI, Model2Vec, Gemini
- RAG features: document chunking, bulk ingestion, set-based filtering
- Pydantic for settings and validation

**Architecture:**

- `mcp_server.py` - Main server class with tool registration
- `qdrant.py` - Qdrant connector handling all database operations
- `embeddings/` - Provider abstraction with multiple implementations
- `settings.py` - Environment-based configuration
- `chunking.py` - RAG document chunking strategies
- `cli_ingest.py` - Bulk document ingestion tool

## Setup Commands

**Install dependencies:**

```bash
uv sync
```

**Set required environment variables:**

```bash
export QDRANT_URL="http://localhost:6333"
export COLLECTION_NAME="my-collection"
export EMBEDDING_PROVIDER="fastembed"  # or "openai", "model2vec", "gemini"
export EMBEDDING_MODEL="sentence-transformers/all-MiniLM-L6-v2"
```

**For OpenAI provider (optional):**

```bash
export EMBEDDING_PROVIDER="openai"
export EMBEDDING_MODEL="text-embedding-3-small"
export OPENAI_API_KEY="your-api-key"
```

**Start the MCP server (stdio transport):**

```bash
uv run mcp-server-qdrant
```

**Start with SSE transport (for remote clients):**

```bash
FASTMCP_PORT=8000 uv run mcp-server-qdrant --transport sse
```

**Run the MCP inspector for interactive testing:**

```bash
fastmcp dev src/mcp_server_qdrant/server.py
```

## Development Workflow

**Package manager:** This project uses `uv` for dependency management. All commands should be run with `uv run` prefix.

**Environment-first configuration:** ALL configuration is via environment variables. No CLI arguments are supported for server settings (only `--transport` flag for protocol selection).

**Transport protocols:**

- `stdio` (default) - Standard input/output for local MCP clients like Claude Desktop
- `sse` - Server-Sent Events for remote clients like Cursor/Windsurf
- `streamable-http` - Modern HTTP streaming transport

**Key development patterns:**

1. All Qdrant operations use `AsyncQdrantClient` (async/await)
2. All embedding methods are async (`embed_documents`, `embed_query`)
3. Pydantic settings classes with `validation_alias` for env vars
4. FastMCP decorators for tool registration: `@self.tool()`
5. Dual vector format support (legacy single vector + named vectors)

**Local Qdrant for testing:**

```bash
# Use in-memory Qdrant (no server needed)
export QDRANT_URL=":memory:"
```

**Docker development:**

```bash
docker build -t mcp-server-qdrant .
docker run -p 8000:8000 \
  -e QDRANT_URL="http://host.docker.internal:6333" \
  -e COLLECTION_NAME="test" \
  mcp-server-qdrant
```

## Testing Instructions

**Run all tests:**

```bash
uv run pytest
```

**Run specific test file:**

```bash
uv run pytest tests/test_qdrant_integration.py
uv run pytest tests/test_openai_provider.py
uv run pytest tests/test_fastembed_integration.py
```

**Run tests with coverage:**

```bash
uv run pytest --cov=src/mcp_server_qdrant --cov-report=term-missing
```

**Run specific test function:**

```bash
uv run pytest tests/test_qdrant_integration.py::test_store_and_search -v
```

**Test file locations:**

- `tests/test_qdrant_integration.py` - Core Qdrant connector tests
- `tests/test_openai_provider.py` - OpenAI embedding provider tests
- `tests/test_fastembed_integration.py` - FastEmbed provider tests
- `tests/test_mcp_integration.py` - Full MCP server integration tests
- `tests/test_settings.py` - Settings validation tests

**Testing patterns:**

- All async tests use `@pytest.mark.asyncio` decorator
- Use `@pytest.fixture` with `async def` for async fixtures
- In-memory Qdrant (`:memory:`) for isolated tests
- Random collection names (`f"test_{uuid.uuid4().hex}"`) to avoid conflicts

**CI/CD:** Tests run on GitHub Actions for Python 3.10, 3.11, 3.12, 3.13 via `.github/workflows/pytest.yaml`

## Code Style Guidelines

**Python conventions:** Follow PEP 8 and patterns in `.github/instructions/python.instructions.md`

**Type hints:** Required for all functions

```python
async def store(self, entry: Entry, *, collection_name: str | None = None) -> None:
```

**Docstrings:** Follow PEP 257 with detailed parameter descriptions

```python
def find_files(path: Path, include_pattern: str | None = None) -> List[Path]:
    """
    Find all supported files in a directory.
    :param path: Path to search
    :param include_pattern: Regex pattern for files to include
    :return: List of file paths
    """
```

**Settings pattern:** Use Pydantic BaseSettings with validation_alias

```python
class QdrantSettings(BaseSettings):
    location: str | None = Field(default=None, validation_alias="QDRANT_URL")
```

**Async patterns:**

- ALL embedding operations must be async
- ALL Qdrant operations must use AsyncQdrantClient
- Use `await` for all async calls

**Embedding provider contract:** Implement 4 methods in `EmbeddingProvider` ABC:

1. `async embed_documents(documents: list[str]) -> list[list[float]]`
2. `async embed_query(query: str) -> list[float]`
3. `get_vector_name() -> str` - Returns vector name or empty string
4. `get_vector_size() -> int` - Returns embedding dimension

**Tool registration pattern:**

```python
@self.tool(description=self.tool_settings.tool_find_description)
async def find(ctx: Context, query: Annotated[str, Field(...)], ...):
    results = await self.qdrant_connector.search(query, ...)
    return [self.format_entry(e) for e in results]
```

**Naming conventions:**

- Files: snake_case (`mcp_server.py`, `cli_ingest.py`)
- Classes: PascalCase (`QdrantConnector`, `EmbeddingProvider`)
- Functions/methods: snake_case (`embed_documents`, `create_embedding_provider`)
- Constants: SCREAMING_SNAKE_CASE (`METADATA_PATH`, `DEFAULT_TOOL_STORE_DESCRIPTION`)

**Import organization:** Use isort

```python
# Standard library
import logging
from typing import Any

# Third-party
from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient

# Local
from mcp_server_qdrant.embeddings.base import EmbeddingProvider
```

**Comments:** Follow `.github/instructions/self-explanatory-code-commenting.instructions.md`

- Comment WHY, not WHAT
- Explain business logic and non-obvious algorithms
- Document API constraints and gotchas
- No redundant or obvious comments

## Build and Deployment

**Build package:**

```bash
uv build
```

**Install locally:**

```bash
uv pip install -e .
```

**Run without installation:**

```bash
uvx mcp-server-qdrant
```

**Docker build:**

```bash
docker build -t mcp-server-qdrant .
```

**Docker deployment:**

```bash
docker run -d \
  -p 8000:8000 \
  -e FASTMCP_HOST="0.0.0.0" \
  -e QDRANT_URL="http://your-qdrant:6333" \
  -e QDRANT_API_KEY="your-key" \
  -e COLLECTION_NAME="production" \
  -e EMBEDDING_PROVIDER="openai" \
  -e OPENAI_API_KEY="your-openai-key" \
  mcp-server-qdrant
```

**VS Code MCP configuration (`.vscode/mcp.json`):**

```json
{
  "servers": {
    "qdrant": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "python", "-m", "mcp_server_qdrant.main"],
      "cwd": "/path/to/mcp-server-qdrant",
      "env": {
        "QDRANT_URL": "http://localhost:6333",
        "COLLECTION_NAME": "my-collection",
        "EMBEDDING_PROVIDER": "fastembed"
      }
    }
  }
}
```

## CLI Tools

**Bulk document ingestion:**

```bash
# Ingest directory of documents
uv run qdrant-ingest ingest /path/to/docs \
  --collection my-knowledge-base \
  --knowledge-base "Project Documentation" \
  --enable-chunking \
  --chunk-strategy semantic \
  --max-chunk-size 512

# List all collections
uv run qdrant-ingest list --url http://localhost:6333

# Ingest with file filtering
uv run qdrant-ingest ingest /path/to/code \
  --include ".*\\.py$" \
  --exclude "test_.*\\.py$" \
  --doc-type "source-code"
```

**Supported file types for ingestion:**

- Code: `.py`, `.js`, `.ts`, `.tsx`, `.jsx`, `.java`, `.go`, `.rs`, `.c`, `.cpp`, `.rb`, `.php`, `.sh`
- Documents: `.txt`, `.md`, `.markdown`
- Config: `.json`, `.yaml`, `.yml`, `.toml`, `.xml`, `.ini`
- Web: `.html`, `.css`, `.scss`
- Data: `.csv`, `.sql`

## Configuration

**Critical environment variables:**

Required (one of):

- `QDRANT_URL` - Qdrant server URL (e.g., `http://localhost:6333` or `:memory:`)
- `QDRANT_LOCAL_PATH` - Local file path for Qdrant storage (mutually exclusive with QDRANT_URL)

Optional:

- `QDRANT_API_KEY` - API key for Qdrant Cloud
- `COLLECTION_NAME` - Default collection name (required if not provided in each tool call)
- `QDRANT_READ_ONLY` - Enable read-only mode (default: `false`)
- `QDRANT_SEARCH_LIMIT` - Max results per search (default: `10`)

Embedding configuration:

- `EMBEDDING_PROVIDER` - Provider type: `fastembed`, `openai`, `model2vec`, `gemini` (default: `fastembed`)
- `EMBEDDING_MODEL` - Model name (default: `sentence-transformers/all-MiniLM-L6-v2`)
- `OPENAI_API_KEY` - Required for OpenAI provider
- `GEMINI_API_KEY` - Required for Gemini provider

RAG features:

- `ENABLE_CHUNKING` - Enable document chunking (default: `false`)
- `MAX_CHUNK_SIZE` - Chunk size in tokens (default: `512`)
- `CHUNK_OVERLAP` - Overlap between chunks (default: `50`)
- `CHUNK_STRATEGY` - Strategy: `semantic`, `sentence`, or `fixed` (default: `semantic`)
- `QDRANT_ENABLE_SEMANTIC_SET_MATCHING` - Enable set-based filtering (default: `false`)
- `QDRANT_SETS_CONFIG` - Path to sets config file (default: `.qdrant_sets.json`)

**Filterable fields:** Define searchable metadata in `QdrantSettings.filterable_fields`:

```python
FilterableField(
    name="source",
    description="Source of the document",
    field_type="keyword",  # keyword|integer|float|boolean
    condition="==",  # ==|!=|>|>=|<|<=|any|except
    required=False
)
```

## Common Pitfalls

1. **Don't add CLI arguments** - Use environment variables via Pydantic settings
2. **Don't forget `await`** on all Qdrant/embedding operations
3. **Remember dual payload format** when modifying store/search logic:
   - Legacy: `{"text": content, ...metadata}` (flat structure)
   - Named vectors: `{"document": content, "metadata": {...}}`
4. **Test with `:memory:` Qdrant** for fast, isolated tests
5. **Check `get_vector_name()` return value** before assuming named vectors
6. **NLTK/tiktoken are optional** - Code must gracefully degrade if unavailable
7. **Instance methods in FastMCP** - Use `@self.tool()` NOT `@mcp.tool()`
8. **Collection auto-creation** - `_ensure_collection_exists()` called before operations

## Pull Request Guidelines

**Before submitting:**

1. Run all tests: `uv run pytest`
2. Check types: `uv run mypy src/`
3. Format code: `uv run ruff format .`
4. Lint code: `uv run ruff check .`
5. Update documentation if adding features
6. Add tests for new functionality

**Title format:** `[component] Brief description`

- Examples: `[embeddings] Add Gemini provider`, `[chunking] Fix overlap handling`

**Required checks:**

- All tests pass on Python 3.10, 3.11, 3.12, 3.13
- No type errors from mypy/pyright
- Ruff linting passes
- Pre-commit hooks pass

**Commit messages:**

- Follow conventional commits: `feat:`, `fix:`, `docs:`, `chore:`, `test:`
- Examples: `feat: add document chunking`, `fix: handle empty metadata`, `docs: update RAG examples`

## Debugging and Troubleshooting

**Enable debug logging:**

```bash
export FASTMCP_DEBUG=true
export FASTMCP_LOG_LEVEL=DEBUG
```

**Common issues:**

1. **Connection refused to Qdrant:**
   - Check `QDRANT_URL` is correct
   - Ensure Qdrant server is running: `docker ps | grep qdrant`
   - Try `:memory:` for testing without server

2. **Embedding dimension mismatch:**
   - Check existing collection vector size matches provider
   - Use `examples/inspect_database.py` to check collection config
   - Delete and recreate collection if needed

3. **Import errors (NLTK/tiktoken):**
   - These are optional dependencies for chunking
   - Code falls back gracefully if unavailable
   - Install if needed: `uv pip install nltk tiktoken`

4. **MCP client connection issues:**
   - Verify transport protocol matches client expectations
   - Check environment variables are loaded correctly
   - Use MCP Inspector for testing: `fastmcp dev src/mcp_server_qdrant/server.py`

**Inspection tools:**

```bash
# Inspect existing database
uv run python examples/inspect_database.py

# Test OpenAI provider connection
uv run python examples/extract_citation_info.py

# Quick search test
uv run python -c "
import asyncio
from mcp_server_qdrant.qdrant import QdrantConnector
from mcp_server_qdrant.embeddings.fastembed import FastEmbedProvider

async def test():
    provider = FastEmbedProvider('sentence-transformers/all-MiniLM-L6-v2')
    connector = QdrantConnector(':memory:', None, 'test', provider)
    # Add test code here

asyncio.run(test())
"
```

## Additional Resources

**Documentation:**

- [docs/README.md](docs/README.md) - Documentation index
- [docs/OPENAI_IMPLEMENTATION.md](docs/OPENAI_IMPLEMENTATION.md) - OpenAI provider details
- [docs/RAG_ATTRIBUTION.md](docs/RAG_ATTRIBUTION.md) - RAG features attribution
- [.github/copilot-instructions.md](.github/copilot-instructions.md) - Comprehensive developer guide

**Examples:**

- [examples/](examples/) - Example scripts for database inspection and usage
- [examples/README.md](examples/README.md) - Examples documentation

**Project information:**

- [PROJECT_STATUS.md](PROJECT_STATUS.md) - Current project status
- [CHANGELOG.md](CHANGELOG.md) - Version history

**Related projects:**

- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP specification
- [FastMCP](https://github.com/jlowin/fastmcp) - FastMCP framework
- [Qdrant](https://qdrant.tech/) - Qdrant vector database
- [mahmoudimus/mcp-server-qdrant](https://github.com/mahmoudimus/mcp-server-qdrant) - RAG features source
