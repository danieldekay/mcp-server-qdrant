# Research Phase: Get Schema Tool

## 1. Technical Unknowns & Resolution

### Unknown 1: FastMCP Empty Tool Signature

**Question**: Can we register a tool with no arguments?
**Finding**: Yes, FastMCP supports parameter-less tools.
**Decision**:

```python
@self.tool(description="...")
async def get_schema(ctx: Context) -> str:
    ...
```

We will include `ctx` for unified logging (debug logs) similar to existing tools.

### Unknown 2: Accessing Provider Config

**Question**: How to access the model name if it's not on the `EmbeddingProvider` interface?
**Finding**:

- `EmbeddingProvider` ABC does *not* expose `model_name`.
- However, `QdrantMCPServer` holds `self.embedding_provider_settings`.
- If `embedding_provider_settings` is None (e.g. manually injected provider), we might lose visibility into the model name.
**Decision**:
- We should read `self.embedding_provider_settings.model_name` if available.
- If not, fall back to "unknown".
- Vector dimension and name are available via the provider interface.

## 2. Design Choices

### Output Schema (JSON)

We will return a stringified JSON object. Structure:

```json
{
  "collection_name": "string",
  "storage_mode": "memory|local|distributed",
  "embedding": {
    "provider": "string",
    "model": "string",
    "vector_size": 123,
    "vector_name": "string (or null)"
  },
  "filters": [
    {
      "name": "string",
      "type": "keyword|integer...",
      "description": "string",
      "condition": "=="
    }
  ],
  "rag_settings": {
    "chunking_enabled": true,
    "pdf_ingestion_enabled": true
  }
}
```

### Agent Skill Location

**Decision**: Place in `.github/skills/qdrant-mcp/SKILL.md`.
**Rationale**: Adheres to the user request and standard .github structure for project skills. Use the `.github/skills/skill-creator` skill to improve it.

## 3. Implementation Strategy

1. **Modify `QdrantMCPServer`**: Add `get_schema` tool in `setup_tools`.
2. **Logic**:
    - Build dict from `self.qdrant_settings`.
    - Build dict from `self.embedding_provider` + `settings`.
    - Dump to JSON string.
3. **Testing**:
    - `tests/test_get_schema.py`: Call tool, parse JSON, assert keys.
