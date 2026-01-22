"""
Example: Testing the qdrant-get-schema tool

This script demonstrates how to use the qdrant-get-schema tool
to inspect the current server configuration.
"""

import asyncio
import json
import os

from mcp_server_qdrant.embeddings.factory import create_embedding_provider
from mcp_server_qdrant.mcp_server import QdrantMCPServer
from mcp_server_qdrant.settings import (
    ChunkingSettings,
    EmbeddingProviderSettings,
    QdrantSettings,
    ToolSettings,
)


async def main():
    """Test the get_schema tool."""
    # Configure settings for in-memory testing
    os.environ["QDRANT_URL"] = ":memory:"
    os.environ["COLLECTION_NAME"] = "test-collection"
    os.environ["EMBEDDING_PROVIDER"] = "fastembed"
    os.environ["EMBEDDING_MODEL"] = "sentence-transformers/all-MiniLM-L6-v2"

    # Create server instance
    server = QdrantMCPServer(
        tool_settings=ToolSettings(),
        qdrant_settings=QdrantSettings(),
        embedding_provider_settings=EmbeddingProviderSettings(),
        chunking_settings=ChunkingSettings(),
    )

    # Get the tools
    tools = await server.get_tools()
    print(f"Available tools: {list(tools.keys())}")

    # Find the get_schema tool
    if "qdrant-get-schema" in tools:
        get_schema_tool = tools["qdrant-get-schema"]
        print(f"\nTool found: {get_schema_tool.name}")
        print(f"Description: {get_schema_tool.description}")

        # Create a dummy context
        class DummyContext:
            async def debug(self, msg):
                print(f"[DEBUG] {msg}")

        # Call the tool
        print("\n--- Calling qdrant-get-schema ---")
        result = await get_schema_tool.fn(DummyContext())
        
        # Parse and pretty-print the result
        schema = json.loads(result)
        print("\n--- Server Schema ---")
        print(json.dumps(schema, indent=2))

        # Validate schema structure
        print("\n--- Validation ---")
        assert "collection_name" in schema, "Missing collection_name"
        assert "storage_mode" in schema, "Missing storage_mode"
        assert "embedding" in schema, "Missing embedding"
        assert "filters" in schema, "Missing filters"
        assert "rag_settings" in schema, "Missing rag_settings"
        print("✅ All required fields present")

        # Display key information
        print(f"\nCollection: {schema['collection_name']}")
        print(f"Storage: {schema['storage_mode']}")
        print(f"Embedding: {schema['embedding']['provider']} - {schema['embedding']['model']}")
        print(f"Vector size: {schema['embedding']['vector_size']}")
        print(f"Available filters: {len(schema['filters'])}")
        for f in schema['filters']:
            print(f"  - {f['name']} ({f['type']}): {f['description']}")

    else:
        print("ERROR: qdrant-get-schema tool not found!")


if __name__ == "__main__":
    asyncio.run(main())
