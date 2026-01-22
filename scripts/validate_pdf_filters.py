import asyncio
import os
import sys
from pathlib import Path

# Ensure src is in path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcp_server_qdrant.server import mcp
from mcp_server_qdrant.qdrant import Entry, QdrantConnector
from mcp_server_qdrant.embeddings.fastembed import FastEmbedProvider


async def demo():
    print("🚀 Starting Qdrant MCP PDF Feature Demo")
    print("-" * 50)

    # 1. Setup in-memory Qdrant for isolation
    print("📦 Setting up in-memory database...")
    collection_name = "demo_pdf_collection"

    # Swap out the connector for this demo to ensure we use :memory:
    provider = FastEmbedProvider(model_name="sentence-transformers/all-MiniLM-L6-v2")
    connector = QdrantConnector(
        qdrant_url=":memory:",
        qdrant_api_key=None,
        collection_name=collection_name,
        embedding_provider=provider,
    )
    mcp.qdrant_connector = connector

    # 2. Store some mock PDF data
    print("📝 Storing mock PDF pages...")
    entries = [
        Entry(
            content="Use the qdrant-find tool to search memories.",
            metadata={
                "document_id": "manual.pdf",
                "physical_page_index": 0,
                "page_label": "i",
            },
        ),
        Entry(
            content="The document_id filter allows narrowing scope to a file.",
            metadata={
                "document_id": "manual.pdf",
                "physical_page_index": 5,
                "page_label": "4",
            },
        ),
        Entry(
            content="This content is from a completely different document.",
            metadata={
                "document_id": "other.pdf",
                "physical_page_index": 0,
                "page_label": "1",
            },
        ),
    ]

    for e in entries:
        await connector.store(e, collection_name=collection_name)
    print(f"✅ Stored {len(entries)} pages.")
    print("-" * 50)

    # 3. Inspect Tool Schema
    print("🔍 Inspecting qdrant-find Tool Schema...")
    tools = await mcp.get_tools()
    find_tool = (
        tools.get("qdrant-find")
        if isinstance(tools, dict)
        else next(t for t in tools if t.name == "qdrant-find")
    )

    # FastMCP v2.8+ exposes parameters/inputSchema
    schema = getattr(find_tool, "parameters", getattr(find_tool, "inputSchema", {}))
    props = schema.get("properties", {})

    print("✅ Tool Parameters Found:")
    for param in ["document_id", "physical_page_index", "page_label"]:
        if param in props:
            print(f"   - {param}: {props[param].get('type') or 'defined'}")
        else:
            print(f"   ❌ {param} MISSING!")
    print("-" * 50)

    # 4. Execute Search with Filters
    print("🧪 Executing Searches...")

    # Helper to run tool
    async def run_query(desc, **kwargs):
        print(f"\n📋 Test: {desc}")
        print(
            f"   Input: query='{kwargs.get('query')}' Filters={ {k: v for k, v in kwargs.items() if k != 'query' and k != 'collection_name'} }"
        )

        # Mock context class required by FastMCP tools
        class MockContext:
            request_id = "demo-req"

            async def debug(self, msg):
                pass

            async def info(self, msg):
                pass

            async def error(self, msg):
                pass

        # Call the underlying function directly
        results = await find_tool.fn(
            MockContext(), **kwargs, collection_name=collection_name
        )

        if results:
            print(f"   ✅ Found {len(results)} matches:")
            for res in results:
                # Parse the formatted string result to just show snippets if possible, or print whole thing
                print(f"      -> {res[:100]}...")
        else:
            print("   ⚠️ No results found.")

    # A. Search by document_id
    await run_query(
        "Filter by document_id='manual.pdf'", query="tool", document_id="manual.pdf"
    )

    # B. Search by page_label
    await run_query("Filter by page_label='4'", query="scope", page_label="4")

    # C. Search by physical_page_index
    await run_query(
        "Filter by physical_page_index=0", query="content", physical_page_index=0
    )

    print("\n" + "=" * 50)
    print("✅ Demo Complete")


if __name__ == "__main__":
    asyncio.run(demo())
