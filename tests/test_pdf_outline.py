"""
Tests for M11: Outline/Bookmark extraction and chapter assignment.
Tests extract_outline(), extract_document_metadata(), get_chapter_for_page().
"""

import pytest
from pypdf import PdfWriter

from mcp_server_qdrant.pdf_extractor import PDFPageExtractor


@pytest.fixture
def academic_pdf():
    return "tests/fixtures/pdfs/academic_paper.pdf"


@pytest.fixture
def book_pdf():
    return "tests/fixtures/pdfs/book_chapter.pdf"


@pytest.fixture
def pdf_with_outline(tmp_path):
    """Create a PDF with bookmarks/outline for testing."""
    pdf_path = tmp_path / "outlined.pdf"
    writer = PdfWriter()

    # Add pages with content
    for i in range(10):
        page = writer.add_blank_page(width=612, height=792)

    # Add outline/bookmarks
    writer.add_outline_item("Chapter 1: Introduction", 0)
    writer.add_outline_item("Chapter 2: Methods", 3)
    writer.add_outline_item("Chapter 3: Results", 6)
    writer.add_outline_item("Index", 9)

    with open(pdf_path, "wb") as f:
        writer.write(f)
    return str(pdf_path)


@pytest.fixture
def pdf_without_outline(tmp_path):
    """Create a PDF without bookmarks."""
    pdf_path = tmp_path / "no_outline.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)
    with open(pdf_path, "wb") as f:
        writer.write(f)
    return str(pdf_path)


class TestExtractOutline:
    """Test outline/bookmark extraction."""

    @pytest.mark.asyncio
    async def test_outline_from_pdf_with_bookmarks(self, pdf_with_outline):
        extractor = PDFPageExtractor(pdf_with_outline)
        outline = await extractor.extract_outline()

        assert len(outline) == 4
        assert outline[0]["title"] == "Chapter 1: Introduction"
        assert outline[0]["page_index"] == 0
        assert outline[0]["level"] == 0

        assert outline[1]["title"] == "Chapter 2: Methods"
        assert outline[1]["page_index"] == 3

        assert outline[2]["title"] == "Chapter 3: Results"
        assert outline[2]["page_index"] == 6

        assert outline[3]["title"] == "Index"
        assert outline[3]["page_index"] == 9

    @pytest.mark.asyncio
    async def test_outline_from_pdf_without_bookmarks(self, pdf_without_outline):
        extractor = PDFPageExtractor(pdf_without_outline)
        outline = await extractor.extract_outline()
        assert outline == []

    @pytest.mark.asyncio
    async def test_outline_on_real_academic_pdf(self, academic_pdf):
        """Test that outline extraction doesn't crash on real PDFs."""
        extractor = PDFPageExtractor(academic_pdf)
        outline = await extractor.extract_outline()
        # May or may not have outline — just verify no crash
        assert isinstance(outline, list)

    @pytest.mark.asyncio
    async def test_outline_on_real_book_pdf(self, book_pdf):
        """Test that outline extraction doesn't crash on real PDFs."""
        extractor = PDFPageExtractor(book_pdf)
        outline = await extractor.extract_outline()
        assert isinstance(outline, list)


class TestGetChapterForPage:
    """Test chapter assignment based on outline."""

    def test_chapter_assignment_basic(self):
        outline = [
            {"title": "Introduction", "page_index": 0, "level": 0},
            {"title": "Methods", "page_index": 5, "level": 0},
            {"title": "Results", "page_index": 10, "level": 0},
        ]

        assert PDFPageExtractor.get_chapter_for_page(outline, 0) == "Introduction"
        assert PDFPageExtractor.get_chapter_for_page(outline, 3) == "Introduction"
        assert PDFPageExtractor.get_chapter_for_page(outline, 5) == "Methods"
        assert PDFPageExtractor.get_chapter_for_page(outline, 7) == "Methods"
        assert PDFPageExtractor.get_chapter_for_page(outline, 10) == "Results"
        assert PDFPageExtractor.get_chapter_for_page(outline, 15) == "Results"

    def test_chapter_assignment_empty_outline(self):
        assert PDFPageExtractor.get_chapter_for_page([], 5) is None

    def test_chapter_assignment_page_before_first_chapter(self):
        outline = [
            {"title": "Chapter 1", "page_index": 3, "level": 0},
        ]
        # Page 0 is before the first chapter
        assert PDFPageExtractor.get_chapter_for_page(outline, 0) is None
        assert PDFPageExtractor.get_chapter_for_page(outline, 2) is None
        assert PDFPageExtractor.get_chapter_for_page(outline, 3) == "Chapter 1"

    def test_chapter_assignment_with_none_page_index(self):
        outline = [
            {"title": "Chapter 1", "page_index": None, "level": 0},
            {"title": "Chapter 2", "page_index": 5, "level": 0},
        ]
        # Should skip items with None page_index
        assert PDFPageExtractor.get_chapter_for_page(outline, 3) is None
        assert PDFPageExtractor.get_chapter_for_page(outline, 5) == "Chapter 2"


class TestExtractDocumentMetadata:
    """Test document-level metadata extraction."""

    @pytest.mark.asyncio
    async def test_metadata_on_real_academic_pdf(self, academic_pdf):
        extractor = PDFPageExtractor(academic_pdf)
        meta = await extractor.extract_document_metadata()
        assert isinstance(meta, dict)

    @pytest.mark.asyncio
    async def test_metadata_on_blank_pdf(self, pdf_without_outline):
        extractor = PDFPageExtractor(pdf_without_outline)
        meta = await extractor.extract_document_metadata()
        # PdfWriter doesn't set metadata by default
        assert isinstance(meta, dict)

    @pytest.mark.asyncio
    async def test_metadata_with_set_values(self, tmp_path):
        """Create a PDF with metadata and verify extraction."""
        pdf_path = tmp_path / "with_meta.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        writer.add_metadata(
            {
                "/Title": "Operations Management",
                "/Author": "Jay Heizer",
                "/Subject": "Business Textbook",
            }
        )
        with open(pdf_path, "wb") as f:
            writer.write(f)

        extractor = PDFPageExtractor(str(pdf_path))
        meta = await extractor.extract_document_metadata()
        assert meta["title"] == "Operations Management"
        assert meta["author"] == "Jay Heizer"
        assert meta["subject"] == "Business Textbook"
