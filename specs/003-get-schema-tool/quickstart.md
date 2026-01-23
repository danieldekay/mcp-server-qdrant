# Quickstart: Get Schema Tool

## Overview

The `qdrant-get-schema` tool allows you to inspect the current server configuration.

## Usage

### 1. Call the Tool

Request the tool with no arguments:

```json
{
  "name": "qdrant-get-schema",
  "arguments": {}
}
```

### 2. Interpret Response

The tool returns a JSON string. Parse it to understand capabilities:

```json
{
  "collection_name": "my-docs",
  "storage_mode": "memory",
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
      "description": "Unique ID",
      "condition": "=="
    }
  ]
}
```

### 3. Use for Filtering

Use the `filters` list to construct valid queries for `qdrant-find`:

```python
# If schema shows "document_id" is available:
results = await qdrant_find(query="...", document_id="doc_123")
```
