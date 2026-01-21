"""
Edge case tests for PDF page-by-page ingestion.

Tests scenarios like corrupted PDFs, password-protected files,
empty documents, and concurrent extraction.
"""

import asyncio
import uuid
from pathlib import Path

import pytest
from pypdf import PdfWriter

from mcp_server_qdrant.embeddings.fastembed import FastEmbedProvider
from mcp_server_qdrant.pdf_extractor import PDFPageExtractor
from mcp_server_qdrant.qdrant import PDFPageEntry, QdrantConnector


@pytest.fixture
def test_fixtures_dir(tmp_path):
    """Create temporary directory for test fixtures."""
    fixtures_dir = tmp_path / "edge_case_pdfs"
    fixtures_dir.mkdir()
    return fixtures_dir


@pytest.fixture
def empty_pdf(test_fixtures_dir):
    """Generate an empty PDF with 0 pages."""
    pdf_path = test_fixtures_dir / "empty.pdf"
    writer = PdfWriter()
    with open(pdf_path, "wb") as f:
        writer.write(f)
    return pdf_path


@pytest.fixture
async def qdrant_connector():
    """Create in-memory Qdrant connector for testing."""
    embedding_provider = FastEmbedProvider(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    connector = QdrantConnector(
        qdrant_url=":memory:",
        qdrant_api_key=None,
        collection_name=f"test_edge_cases_{uuid.uuid4().hex}",
        embedding_provider=embedding_provider,
    )
    return connector


class TestPDFEdgeCases:
    """Edge case test suite for PDF ingestion."""

    @pytest.mark.asyncio
    async def test_empty_pdf(self, empty_pdf):
        """Test handling of PDF with 0 pages."""
        extractor = PDFPageExtractor(str(empty_pdf))

        page_count = await extractor.get_page_count()
        assert page_count == 0, "Empty PDF should have 0 pages"

        pages = await extractor.extract_all_pages()
        assert len(pages) == 0, "Empty PDF should return empty list"

    @pytest.mark.asyncio
    async def test_nonexistent_pdf(self):
        """Test handling of nonexistent PDF file."""
        nonexistent_path = "/tmp/nonexistent_file_12345.pdf"

        with pytest.raises(FileNotFoundError) as exc_info:
            PDFPageExtractor(nonexistent_path)

        assert "PDF file not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_corrupted_pdf(self, test_fixtures_dir):
        """Test handling of corrupted PDF file."""
        corrupted_path = test_fixtures_dir / "corrupted.pdf"

        with open(corrupted_path, "w") as f:
            f.write("This is not a valid PDF file")

        extractor = PDFPageExtractor(str(corrupted_path))

        with pytest.raises(Exception):
            await extractor.get_page_count()

    @pytest.mark.asyncio
    async def test_pdf_without_text(self, test_fixtures_dir):
        """Test PDF with pages containing no extractable text."""
        from pypdf import PdfWriter

        pdf_path = test_fixtures_dir / "no_text.pdf"
        writer = PdfWriter()

        writer.add_blank_page(width=612, height=792)
        writer.add_blank_page(width=612, height=792)

        with open(pdf_path, "wb") as f:
            writer.write(f)

        extractor = PDFPageExtractor(str(pdf_path))
        pages = await extractor.extract_all_pages()

        assert len(pages) == 2, "Should extract 2 blank pages"

        for content, phys_idx, label in pages:
            assert content == "", f"Page {phys_idx} should have empty content"
            # pypdf may return page numbers as '1', '2', etc. for blank pages
            assert label is not None, f"Should have a label"

    @pytest.mark.asyncio
    async def test_concurrent_extraction(self, test_fixtures_dir):
        """Test concurrent extraction from multiple PDFs."""
        from pypdf import PdfReader, PdfWriter

        pdf_paths = []
        for i in range(3):
            pdf_path = test_fixtures_dir / f"concurrent_{i}.pdf"
            writer = PdfWriter()
            page = writer.add_blank_page(width=612, height=792)

            with open(pdf_path, "wb") as f:
                writer.write(f)

            pdf_paths.append(pdf_path)

        async def extract_pdf(path):
            extractor = PDFPageExtractor(str(path))
            return await extractor.extract_all_pages()

        tasks = [extract_pdf(path) for path in pdf_paths]
        results = await asyncio.gather(*tasks)

        assert len(results) == 3, "Should extract all 3 PDFs"
        for result in results:
            assert len(result) == 1, "Each PDF has 1 page"

    @pytest.mark.asyncio
    async def test_pdf_ingestion_with_empty_pages(
        self, test_fixtures_dir, qdrant_connector
    ):
        """Test ingesting PDF with some empty pages."""
        from pypdf import PdfWriter

        pdf_path = test_fixtures_dir / "mixed_content.pdf"
        writer = PdfWriter()

        writer.add_blank_page(width=612, height=792)
        writer.add_blank_page(width=612, height=792)

        with open(pdf_path, "wb") as f:
            writer.write(f)

        extractor = PDFPageExtractor(str(pdf_path))
        pages_data = await extractor.extract_all_pages()

        non_empty_count = 0
        for content, physical_index, page_label in pages_data:
            if content.strip():
                entry = PDFPageEntry(
                    content=content,
                    metadata={"source": "test"},
                    physical_page_index=physical_index,
                    page_label=page_label,
                    document_id="mixed_content.pdf",
                    total_pages=len(pages_data),
                )
                await qdrant_connector.store(entry.to_entry())
                non_empty_count += 1

        assert non_empty_count == 0, (
            "Should not store entries for empty pages in this test"
        )

    @pytest.mark.asyncio
    async def test_invalid_page_index(self, test_fixtures_dir):
        """Test accessing invalid page index gracefully handles error."""
        from pypdf import PdfWriter

        pdf_path = test_fixtures_dir / "single_page.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)

        with open(pdf_path, "wb") as f:
            writer.write(f)

        extractor = PDFPageExtractor(str(pdf_path))

        # Should return empty string and log error instead of raising
        content = await extractor.extract_page_content(999)
        assert content == "", "Should return empty string for invalid index"

    @pytest.mark.asyncio
    async def test_special_characters_in_filename(self, test_fixtures_dir):
        """Test PDF with special characters in filename."""
        from pypdf import PdfWriter

        special_name = "test file [with] (special) chars & symbols.pdf"
        pdf_path = test_fixtures_dir / special_name
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)

        with open(pdf_path, "wb") as f:
            writer.write(f)

        extractor = PDFPageExtractor(str(pdf_path))
        assert extractor.pdf_path.exists(), "Should handle special characters in path"

        page_count = await extractor.get_page_count()
        assert page_count == 1

    @pytest.mark.asyncio
    async def test_pdf_with_many_pages(self, test_fixtures_dir):
        """Test PDF with many pages (performance check)."""
        from pypdf import PdfWriter

        page_count = 100
        pdf_path = test_fixtures_dir / "many_pages.pdf"
        writer = PdfWriter()

        for i in range(page_count):
            writer.add_blank_page(width=612, height=792)

        with open(pdf_path, "wb") as f:
            writer.write(f)

        extractor = PDFPageExtractor(str(pdf_path))

        pages = await extractor.extract_all_pages()
        assert len(pages) == page_count, f"Should extract all {page_count} pages"

        for i, (content, phys_idx, label) in enumerate(pages):
            assert phys_idx == i, f"Physical index should match: {i}"
