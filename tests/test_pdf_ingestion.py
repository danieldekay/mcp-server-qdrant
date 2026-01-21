import pytest
from pathlib import Path
from mcp_server_qdrant.constants import PDFMetadataKeys
from mcp_server_qdrant.pdf_extractor import PDFPageExtractor
from mcp_server_qdrant.qdrant import QdrantConnector, PDFPageEntry
from mcp_server_qdrant.embeddings.fastembed import FastEmbedProvider


@pytest.fixture
def academic_pdf():
    return "tests/fixtures/pdfs/academic_paper.pdf"


@pytest.fixture
def book_pdf():
    return "tests/fixtures/pdfs/book_chapter.pdf"


@pytest.mark.asyncio
async def test_pdf_extractor_labels(academic_pdf):
    extractor = PDFPageExtractor(academic_pdf)
    labels = [label for _, _, label in await extractor.extract_all_pages()]

    # academic_paper.pdf: 3 pages roman (i, ii, iii), then 5 pages arabic (1, 2, 3, 4, 5)
    assert labels[0] == "i"
    assert labels[1] == "ii"
    assert labels[2] == "iii"
    assert labels[3] == "1"
    assert labels[7] == "5"


@pytest.mark.asyncio
async def test_pdf_extractor_custom_start(book_pdf):
    extractor = PDFPageExtractor(book_pdf)
    labels = [label for _, _, label in await extractor.extract_all_pages()]

    # book_chapter.pdf: starts at page 45
    assert labels[0] == "45"
    assert labels[1] == "46"
    assert labels[4] == "49"


@pytest.mark.asyncio
async def test_pdf_ingestion_metadata(academic_pdf):
    extractor = PDFPageExtractor(academic_pdf)
    pages = await extractor.extract_all_pages()

    provider = FastEmbedProvider("sentence-transformers/all-MiniLM-L6-v2")
    connector = QdrantConnector(
        qdrant_url=":memory:",
        qdrant_api_key=None,
        collection_name="test-pdf",
        embedding_provider=provider,
    )

    # Ingest first page
    content, idx, label = pages[0]
    entry = PDFPageEntry(
        content=content,
        physical_page_index=idx,
        page_label=label,
        document_id="paper.pdf",
        total_pages=len(pages),
    )
    await connector.store(entry.to_entry())

    # Search and verify metadata
    results = await connector.search("test")
    assert len(results) > 0
    meta = results[0].metadata
    assert meta[PDFMetadataKeys.PHYSICAL_PAGE_INDEX] == 0
    assert meta[PDFMetadataKeys.PAGE_LABEL] == "i"
    assert meta[PDFMetadataKeys.DOCUMENT_ID] == "paper.pdf"
