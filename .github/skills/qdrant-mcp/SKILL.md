---
name: qdrant-mcp
description: "Practical guide for running and using the mcp-server-qdrant (Qdrant MCP server). Use when asked how to start the server, inspect MCP tool schemas, call `qdrant-get-schema`/`qdrant-find`/`qdrant-store`, configure PDF filters, or debug tool parameter exposure. Keywords: qdrant, mcp, fastmcp, qdrant-find, qdrant-store, qdrant-get-schema, schema inspection, pdf filters, inspector, ingestion"
license: Complete terms in LICENSE
---

# Qdrant MCP: usage, inspection, and troubleshooting ✅

This skill explains how to run the Qdrant MCP server, inspect tool schemas (UI or programmatically), call its tools (`qdrant-get-schema`, `qdrant-find`, `qdrant-store`), use PDF-related filters, and troubleshoot common issues.

## When to use this skill

- When you need to start or configure the MCP server for local development ⚙️
- When you want to inspect or validate the current server configuration dynamically 🔍
- When you want to inspect or validate a tool schema (e.g., confirm `document_id`/`page_label`) 🔎
- When you want to store or search memories programmatically or via MCP clients 🧠
- When diagnosing filter exposure or schema caching issues in clients (Inspector/VS Code/Claude) 🐞

## Prerequisites

- Python 3.10+ and project dependencies installed (use `uv sync` / `uv pip install -r` per repo) 🐍
- Qdrant storage:
  - **Recommended for local use:** Use a local persistent on-disk database (set `QDRANT_LOCAL_PATH`)
  - Testing: Use `:memory:` mode
  - Production: Use a remote Qdrant server URL
- Recommended: `fastmcp` available for using the inspector UI (`fastmcp dev`) - optional for programmatic inspection

## VS Code Installation (.vscode/mcp.json)

To add this server to your VS Code MCP setup, assuming it is installed as a git submodule or subrepo (e.g., in `modules/mcp-server-qdrant`), use the following config. Note the use of `${workspaceFolder}` to keep paths relative and portable.

```json
{
  "mcpServers": {
    "qdrant": {
      "command": "uv",
      "args": [
        "run",
        "mcp-server-qdrant"
      ],
      "cwd": "${workspaceFolder}/modules/mcp-server-qdrant",
      "env": {
        "QDRANT_LOCAL_PATH": "./qdrant_db",
        "COLLECTION_NAME": "my-collection",
        "EMBEDDING_PROVIDER": "fastembed",
        "EMBEDDING_MODEL": "sentence-transformers/all-MiniLM-L6-v2"
      }
    }
  }
}
```

> **Note**: Don't forget to run `uv sync` inside the `modules/mcp-server-qdrant` folder first to set up the environment!

## Quickstart: run the server (stdio transport)

1. Set required environment variables (example using local DB):

```bash
# Prefer local file DB for persistence:
export QDRANT_LOCAL_PATH="./qdrant_db"
# OR for testing/remote server:
# export QDRANT_URL=":memory:"

export COLLECTION_NAME="my-collection"
export EMBEDDING_PROVIDER="fastembed"
```

1. Start the server via the package CLI:

```bash
uv run mcp-server-qdrant --transport stdio   # default transport
# or for SSE transport
uvx mcp-server-qdrant --transport sse
```

1. (Optional) For interactive tool inspection, start the MCP Inspector:

```bash
fastmcp dev src/mcp_server_qdrant/server.py
# open http://localhost:5173 and find `qdrant-find` / `qdrant-store`
```

> Tip: If `fastmcp` is not installed or not on PATH, use the programmatic inspection method below.

## Inspect tool schemas programmatically (no Inspector)

- Use `mcp.get_tools()` in a short Python snippet to retrieve tool registration and input schemas.

Example (run inside project environment):

```python
import asyncio
from mcp_server_qdrant.server import mcp

async def dump_tools():
    tools = await mcp.get_tools()
    print(tools)

asyncio.run(dump_tools())
```

Look for `qdrant-find` in the returned mapping or list. Validate `inputSchema` (or `parameters`) contains `document_id`, `physical_page_index`, and `page_label` when PDF filtering is enabled.

## Using the tools

### qdrant-get-schema (NEW): Inspect current configuration 🔍

**Purpose**: Discover what filters are available, what embedding model is active, and what collection you're connected to.

**Signature**: `qdrant-get-schema()` (no arguments)

**Returns**: JSON with:
- `collection_name`: Which collection is active
- `storage_mode`: "memory", "local", or "remote"
- `embedding`: Provider, model name, vector dimensions
- `filters`: List of available filterable fields with types and conditions
- `rag_settings`: Chunking and PDF ingestion status

**When to use**: ALWAYS call this FIRST before using `qdrant-find` to discover available filters dynamically.

**Example response**:
```json
{
  "collection_name": "my-docs",
  "storage_mode": "local",
  "embedding": {
    "provider": "fastembed",
    "model": "sentence-transformers/all-MiniLM-L6-v2",
    "vector_size": 384,
    "vector_name": "fastembed_384"
  },
  "filters": [
    {
      "name": "document_id",
      "type": "keyword",
      "description": "The unique identifier of the document",
      "condition": "=="
    },
    {
      "name": "physical_page_index",
      "type": "integer",
      "description": "The 0-based physical index of the page",
      "condition": "=="
    },
    {
      "name": "page_label",
      "type": "keyword",
      "description": "The original page numbering label (e.g., 'iv', '45')",
      "condition": "=="
    }
  ],
  "rag_settings": {
    "chunking_enabled": false,
    "pdf_ingestion_enabled": true
  }
}
```

### qdrant-store: store information

  - Signature: `qdrant-store(information: str, collection_name: str, metadata: dict | None = None)`
  - Use to persist content + metadata (e.g., `document_id`, `page_label`, `physical_page_index`)

### qdrant-find: search memories

  - Signature: `qdrant-find(query: str, collection_name: str, [document_id], [physical_page_index], [page_label], ...)`
  - Filters are optional; combine any subset of them to narrow results.
  - **Pro tip**: Call `qdrant-get-schema` first to see exactly what filters are available!

### Example: programmatic call

```python
from mcp_server_qdrant.server import mcp

# Call tool function directly (use in tests or simple scripts)
# The `fn` attribute is the underlying function - accepts a Context-like object
class DummyCtx:
    async def debug(self, *args, **kwargs):
        return None

res = await mcp.get_tools()  # or use mcp.get_tool('qdrant-find') depending on FastMCP version
# Or invoke find tool's fn directly: await find_tool.fn(DummyCtx(), query='foo', collection_name='test', document_id='doc1')
```

## PDF filter guidance

- Fields available: `document_id` (string), `physical_page_index` (integer, 0-based), `page_label` (string)
- Ensure `QdrantSettings.filterable_fields` contains PDF entries with `condition` set (defaults are provided by the project)
- If filters are missing from tool schema, verify:
  - No environment override of filterable fields (check env vars containing `FILTER`)
  - `mcp.get_tools()` shows the parameters (programmatic check)
  - Restart client to clear cached schemas (some clients cache remote tool schemas)

Helpful examples in repo:

- `examples/diagnose_filter_settings.py` — checks settings initialization and whether `wrap_filters()` would be applied
- `tests/test_pdf_filter_interface.py` — integration tests demonstrating usage and expected behavior

## Ingesting documents & PDFs

- Bulk ingestion CLI: `uv run qdrant-ingest ingest /path/to/docs --collection my-collection` (supports PDFs, code, text, etc.)
- PDF ingestion is page-by-page and stores `document_id`, `page_label`, and `physical_page_index` in metadata
- Chunking: enable with `ENABLE_CHUNKING=true` and configure `MAX_CHUNK_SIZE`, `CHUNK_OVERLAP`, `CHUNK_STRATEGY`

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `qdrant-find` missing filters in client UI | Client cached schema or `filterable_fields` overridden | Restart client, run `examples/diagnose_filter_settings.py`, and call `mcp.get_tools()` programmatically |
| `fastmcp` not found | `fastmcp` not installed or PATH missing | Install via project tooling (`uv pip install fastmcp` or `pip install fastmcp`) |
| Filter calls succeed but not visible in UI | Client display/caching issue | Confirm programmatically then restart client; file a FastMCP issue if necessary |
| Empty or unexpected search results | Filters mismatched (e.g., string vs integer) or metadata absent | Inspect stored payloads using `examples/inspect_database.py` and ensure metadata keys are present |

## References

- Project README: `README.md`
- RAG features & chunking: `docs/RAG_ATTRIBUTION.md` and `src/mcp_server_qdrant/chunking.py`
- OpenAI provider details: `docs/OPENAI_IMPLEMENTATION.md`
- Tests and examples: `tests/test_pdf_filter_interface.py`, `examples/diagnose_filter_settings.py`, `examples/inspect_fastmcp_tools.py`

---

If you want, I can also add a small `scripts/` helper (e.g., `scripts/dump_tool_schema.py`) that prints the current `qdrant-find` schema programmatically. Would you like me to add that script now? ✨
