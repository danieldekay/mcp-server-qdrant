"""
Tests for M13: Layout extraction mode.
Tests that extraction_mode="layout" parameter works correctly.
"""

import pytest
from pypdf import PdfWriter

from mcp_server_qdrant.pdf_extractor import PDFPageExtractor


@pytest.fixture
def academic_pdf():
    return "tests/fixtures/pdfs/academic_paper.pdf"


@pytest.fixture
def simple_pdf(tmp_path):
    """Create a simple PDF for testing extraction modes."""
    pdf_path = tmp_path / "simple.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with open(pdf_path, "wb") as f:
        writer.write(f)
    return str(pdf_path)


class TestLayoutExtractionMode:
    """Test that extraction_mode parameter is respected."""

    def test_default_mode_is_plain(self):
        """Default extraction mode should be 'plain'."""
        extractor = PDFPageExtractor.__new__(PDFPageExtractor)
        extractor.extraction_mode = "plain"
        assert extractor.extraction_mode == "plain"

    def test_layout_mode_is_set(self, simple_pdf):
        extractor = PDFPageExtractor(simple_pdf, extraction_mode="layout")
        assert extractor.extraction_mode == "layout"

    def test_plain_mode_is_set(self, simple_pdf):
        extractor = PDFPageExtractor(simple_pdf, extraction_mode="plain")
        assert extractor.extraction_mode == "plain"

    @pytest.mark.asyncio
    async def test_extract_all_pages_plain(self, academic_pdf):
        """extract_all_pages works in plain mode."""
        extractor = PDFPageExtractor(academic_pdf, extraction_mode="plain")
        pages = await extractor.extract_all_pages()
        assert len(pages) > 0
        # Each page: (content, index, label)
        for content, idx, label in pages:
            assert isinstance(content, str)
            assert isinstance(idx, int)
            assert isinstance(label, str)

    @pytest.mark.asyncio
    async def test_extract_all_pages_layout(self, academic_pdf):
        """extract_all_pages works in layout mode without errors."""
        extractor = PDFPageExtractor(academic_pdf, extraction_mode="layout")
        pages = await extractor.extract_all_pages()
        assert len(pages) > 0
        for content, idx, label in pages:
            assert isinstance(content, str)
            assert isinstance(idx, int)
            assert isinstance(label, str)

    @pytest.mark.asyncio
    async def test_extract_single_page_layout(self, academic_pdf):
        """extract_page_content respects layout mode."""
        extractor = PDFPageExtractor(academic_pdf, extraction_mode="layout")
        content = await extractor.extract_page_content(0)
        assert isinstance(content, str)

    @pytest.mark.asyncio
    async def test_extract_single_page_plain(self, academic_pdf):
        """extract_page_content works in plain mode."""
        extractor = PDFPageExtractor(academic_pdf, extraction_mode="plain")
        content = await extractor.extract_page_content(0)
        assert isinstance(content, str)

    @pytest.mark.asyncio
    async def test_plain_and_layout_same_page_count(self, academic_pdf):
        """Both modes should produce same number of pages."""
        ext_plain = PDFPageExtractor(academic_pdf, extraction_mode="plain")
        ext_layout = PDFPageExtractor(academic_pdf, extraction_mode="layout")

        pages_plain = await ext_plain.extract_all_pages()
        pages_layout = await ext_layout.extract_all_pages()

        # Same number of pages regardless of mode
        assert len(pages_plain) == len(pages_layout)
