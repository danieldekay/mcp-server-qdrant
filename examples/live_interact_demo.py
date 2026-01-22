import asyncio
from mcp_server_qdrant.embeddings.fastembed import FastEmbedProvider
from mcp_server_qdrant.qdrant import QdrantConnector, Entry
from mcp_server_qdrant.formatters import XMLEntryFormatter


async def main():
    provider = FastEmbedProvider(model_name="sentence-transformers/all-MiniLM-L6-v2")

    connector = QdrantConnector(
        qdrant_url=":memory:",
        qdrant_api_key=None,
        collection_name="live-demo",
        embedding_provider=provider,
    )

    # Store a sample entry
    entry = Entry(
        content="The quick brown fox jumps over the lazy dog.",
        metadata={
            "document_id": "demo.pdf",
            "page_label": "1",
            "physical_page_index": 0,
        },
    )

    await connector.store(entry, collection_name="live-demo")

    # Search
    results = await connector.search(
        "quick brown fox", collection_name="live-demo", limit=5
    )

    fmt = XMLEntryFormatter()

    if not results:
        print("No results found")
        return

    for res in results:
        print(fmt.format(res))


if __name__ == "__main__":
    asyncio.run(main())
