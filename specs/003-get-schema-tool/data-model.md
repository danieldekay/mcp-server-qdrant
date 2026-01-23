# Data Model: Get Schema Tool

## 1. Schema Response Object

This object represents the JSON structure returned by the `qdrant-get-schema` tool.

```typescript
interface SchemaResponse {
  collection_name: string;
  storage_mode: "memory" | "local" | "remote";

  embedding: {
    provider: string;       // e.g. "fastembed", "openai"
    model: string;          // e.g. "sentence-transformers/..."
    vector_size: number;    // e.g. 384
    vector_name: string | null; // e.g. "fastembed_384" or null (legacy)
  };

  filters: Array<{
    name: string;
    type: "keyword" | "integer" | "float" | "boolean";
    description: string;
    condition: string | null; // e.g. "==", ">"
  }>;

  rag_settings?: {
    chunking_enabled: boolean;
    pdf_ingestion_enabled: boolean;
  };
}
```

## 2. Agent Skill Structure

Structure for `.github/skills/qdrant-mcp/SKILL.md`.

```markdown
---
name: qdrant-mcp
description: ...
---

# Qdrant MCP Usage

## Capabilities
- Memory retrieval
- Memory storage
- Schema inspection

## Workflow
1. Inspect Schema
2. Search (Find)
3. Store
```
