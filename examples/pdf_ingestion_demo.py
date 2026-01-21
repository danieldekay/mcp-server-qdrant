import asyncio
import os
from pathlib import Path
from mcp_server_qdrant.qdrant import QdrantConnector, PDFPageEntry
from mcp_server_qdrant.pdf_extractor import PDFPageExtractor
from mcp_server_qdrant.embeddings.fastembed import FastEmbedProvider


async def main():
    # Setup
    pdf_path = "tests/fixtures/pdfs/academic_paper.pdf"
    if not os.path.exists(pdf_path):
        print(f"Please run the fixture generation script first to create {pdf_path}")
        return

    print(f"Analyzing PDF: {pdf_path}")
    extractor = PDFPageExtractor(pdf_path)

    # 1. Extract all pages
    pages = await extractor.extract_all_pages()
    print(f"Total pages: {len(pages)}")

    # 2. Setup Qdrant (in-memory for demo)
    provider = FastEmbedProvider()
    connector = QdrantConnector(
        qdrant_url=":memory:",
        qdrant_api_key=None,
        collection_name="demo-collection",
        embedding_provider=provider,
    )

    # 3. Ingest page-by-page
    print("Ingesting pages into Qdrant...")
    for content, physical_index, page_label in pages:
        entry = PDFPageEntry(
            content=content,
            physical_page_index=physical_index,
            page_label=page_label,
            document_id="academic_paper.pdf",
            total_pages=len(pages),
        )
        await connector.store(entry.to_entry())
        print(f"  Stored Physical Page {physical_index + 1} (Label: {page_label})")

    # 4. Search
    print("\nSearching for content in PDF...")
    results = await connector.search("test")
    for res in results:
        metadata = res.metadata
        print(
            f"Found match on Page {metadata.get('page_label')} (Physical: {metadata.get('physical_page_index') + 1})"
        )
        print(f"Content snippet: {res.content[:50]}...")


if __name__ == "__main__":
    asyncio.run(main())
