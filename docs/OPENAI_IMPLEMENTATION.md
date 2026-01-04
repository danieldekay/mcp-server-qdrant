# OpenAI Embedding Provider for Qdrant MCP Server

## Overview

This document describes the implementation of OpenAI embedding support for the official Qdrant MCP server, enabling compatibility with existing Qdrant databases that use OpenAI embeddings.

**Note:** This implementation has been successfully integrated alongside comprehensive RAG features from the [mahmoudimus/mcp-server-qdrant](https://github.com/mahmoudimus/mcp-server-qdrant) fork. See [RAG_ATTRIBUTION.md](RAG_ATTRIBUTION.md) for details on the RAG feature integration.

## Background

The official [qdrant/mcp-server-qdrant](https://github.com/qdrant/mcp-server-qdrant) only supports FastEmbed embeddings. However, our existing literature database was created with OpenAI's `text-embedding-3-small` model (1536 dimensions), making it incompatible with the standard MCP server.

## Implementation

### Changes Made

1. **Added OpenAI Embedding Provider Type**
   - Extended `EmbeddingProviderType` enum to include `OPENAI = "openai"`
   - Location: `src/mcp_server_qdrant/embeddings/types.py`

2. **Created OpenAI Embedding Provider**
   - New file: `src/mcp_server_qdrant/embeddings/openai.py`
   - Supports OpenAI embedding models: `text-embedding-3-small`, `text-embedding-3-large`, `text-embedding-ada-002`
   - Handles API key from environment variable or parameter
   - Compatible with both single vector and named vector collections

3. **Updated Embedding Factory**
   - Modified `create_embedding_provider()` in `src/mcp_server_qdrant/embeddings/factory.py`
   - Added OpenAI provider instantiation

4. **Enhanced Qdrant Connector Compatibility**
   - Modified `src/mcp_server_qdrant/qdrant.py` to handle both:
     - **Legacy format**: Single vectors with `text` payload field
     - **New format**: Named vectors with `document` payload field

5. **Added Dependencies**
   - Added `openai>=1.0.0` to `pyproject.toml`

### Key Features

- **Backward Compatibility**: Works with existing Qdrant databases
- **Flexible Payload Handling**: Supports both `text` and `document` payload structures
- **Vector Format Support**: Handles both single vectors and named vector collections
- **Environment Integration**: Uses existing OpenAI API keys from environment

## Configuration

### Environment Variables

```bash
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
OPENAI_API_KEY=your_openai_api_key_here
QDRANT_LOCAL_PATH=./path/to/qdrant/db
COLLECTION_NAME=your_collection_name
```

### VS Code MCP Configuration

Update `.vscode/mcp.json`:

```json
{
  "servers": {
    "qdrant": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "python", "-m", "mcp_server_qdrant.main"],
      "cwd": "../mcp-server-qdrant",
      "env": {
        "QDRANT_LOCAL_PATH": "../FoM2526/Folien+Lit/qdrant_db",
        "COLLECTION_NAME": "forschungsmethoden_literatur",
        "EMBEDDING_PROVIDER": "openai",
        "EMBEDDING_MODEL": "text-embedding-3-small",
        "OPENAI_API_KEY": "${env:OPENAI_API_KEY}",
        "TOOL_FIND_DESCRIPTION": "Suche nach relevanten Forschungsmethoden-Inhalten mit natürlicher Sprache. Verwende deutsche Begriffe für beste Ergebnisse.",
        "TOOL_STORE_DESCRIPTION": "Speichere wichtige Forschungsmethoden-Inhalte für spätere Verwendung. Der 'information' Parameter sollte den Hauptinhalt enthalten."
      }
    }
  }
}
```

## Testing Results

### Successful Integration Tests

✅ **OpenAI Provider Creation**: Successfully created provider with `text-embedding-3-small`
✅ **Database Connection**: Connected to existing literature database with 5,943 academic segments
✅ **Search Functionality**: Successfully searched for German academic content:

- "quantitative Forschungsmethoden"
- "Validität und Reliabilität"
- "Stichprobenziehung"
- "statistische Tests"

✅ **Storage Functionality**: Successfully stored and retrieved new content
✅ **Metadata Handling**: Correctly processed academic metadata (book, chapter, page references)

### Sample Search Results

```
📝 Searching for: 'quantitative Forschungsmethoden'
   ✅ Found 3 results
   1. , es können spontan auftretende neue Fragen spezifischen Datenerhebungsmethoden...
      📚 book: doering_2023, chapter: 2023_Doering
   2. 1 27 1.3 Empirische Studien planen und durchführen Quantitativer Forschungsprozess...
      📚 book: doering_2023, chapter: 2023_Doering
```

## Installation and Usage

1. **Clone and Setup**

   ```bash
   git clone https://github.com/qdrant/mcp-server-qdrant.git
   cd mcp-server-qdrant
   # Apply the OpenAI provider modifications
   uv sync
   ```

2. **Set Environment Variables**

   ```bash
   export OPENAI_API_KEY="your-key-here"
   export EMBEDDING_PROVIDER="openai"
   export EMBEDDING_MODEL="text-embedding-3-small"
   ```

3. **Test the Implementation**

   ```bash
   uv run python test_openai_provider.py
   uv run python test_mcp_integration.py
   ```

## Compatibility Matrix

| Database Format | Vector Type | Payload Field | Supported |
|----------------|-------------|---------------|-----------|
| Legacy (existing) | Single | `text` | ✅ |
| New (MCP standard) | Named | `document` | ✅ |
| Mixed | Both | Both | ✅ |

## Future Considerations

### Potential Contribution

This implementation could be contributed back to the official repository as it adds valuable functionality without breaking existing features.

### Improvements

1. **Configuration Validation**: Add validation for OpenAI model compatibility
2. **Async Optimization**: Consider connection pooling for high-volume usage
3. **Error Handling**: Enhanced error messages for API failures
4. **Testing**: Comprehensive test suite for all embedding providers

### Alternative Approaches

1. **Custom Vector Names**: Could implement custom vector naming for better organization
2. **Hybrid Collections**: Support collections with both FastEmbed and OpenAI vectors
3. **Migration Tools**: Utilities to convert between embedding formats

## Files Modified

```
mcp-server-qdrant/
├── src/mcp_server_qdrant/embeddings/
│   ├── types.py              # Added OPENAI enum
│   ├── factory.py            # Added OpenAI provider creation
│   └── openai.py             # New OpenAI provider implementation
├── src/mcp_server_qdrant/
│   └── qdrant.py             # Enhanced compatibility layer
├── pyproject.toml            # Added openai dependency
├── test_openai_provider.py   # OpenAI provider tests
├── test_mcp_integration.py   # Integration tests
└── inspect_database.py       # Database inspection tool
```

## Success Metrics

- ✅ **5,943 literature segments** accessible via MCP tools
- ✅ **German academic content** searchable with natural language
- ✅ **Existing database preservation** - no data migration required
- ✅ **VS Code integration** working with modified MCP server
- ✅ **Backward compatibility** maintained for future updates

This implementation successfully bridges the gap between the official Qdrant MCP server and existing OpenAI-based vector databases, enabling seamless semantic search and storage capabilities for academic research content.
