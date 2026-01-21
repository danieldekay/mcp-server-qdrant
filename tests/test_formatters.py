"""
Tests for entry formatter implementations.

Validates different formatting strategies and their outputs.
"""

import pytest

from mcp_server_qdrant.constants import PDFMetadataKeys
from mcp_server_qdrant.formatters import (
    JSONEntryFormatter,
    MarkdownEntryFormatter,
    PlainTextEntryFormatter,
    XMLEntryFormatter,
)
from mcp_server_qdrant.qdrant import Entry


class TestEntryFormatters:
    """Test suite for entry formatter implementations."""

    @pytest.fixture
    def basic_entry(self):
        """Entry without PDF metadata."""
        return Entry(
            content="This is test content",
            metadata={"source": "test", "category": "demo"},
        )

    @pytest.fixture
    def pdf_entry(self):
        """Entry with PDF page metadata."""
        return Entry(
            content="PDF page content",
            metadata={
                PDFMetadataKeys.DOCUMENT_ID: "test_document.pdf",
                PDFMetadataKeys.PAGE_LABEL: "iv",
                PDFMetadataKeys.PHYSICAL_PAGE_INDEX: 3,
                PDFMetadataKeys.TOTAL_PAGES: 10,
            },
        )

    def test_xml_formatter_basic_entry(self, basic_entry):
        """Test XML formatter with basic entry."""
        formatter = XMLEntryFormatter()
        result = formatter.format(basic_entry)

        assert "<entry>" in result
        assert "<content>This is test content</content>" in result
        assert "<metadata>" in result
        assert "source" in result
        assert "category" in result

    def test_xml_formatter_pdf_entry(self, pdf_entry):
        """Test XML formatter with PDF entry."""
        formatter = XMLEntryFormatter()
        result = formatter.format(pdf_entry)

        assert "<entry>" in result
        assert "<content>PDF page content</content>" in result
        assert "<page>Document: test_document.pdf, Page: iv" in result
        assert "(physical page 4)" in result
        assert "<metadata>" in result

    def test_json_formatter_basic_entry(self, basic_entry):
        """Test JSON formatter with basic entry."""
        import json

        formatter = JSONEntryFormatter()
        result = formatter.format(basic_entry)

        parsed = json.loads(result)
        assert parsed["content"] == "This is test content"
        assert parsed["metadata"]["source"] == "test"
        assert parsed["metadata"]["category"] == "demo"
        assert "page_info" not in parsed

    def test_json_formatter_pdf_entry(self, pdf_entry):
        """Test JSON formatter with PDF entry."""
        import json

        formatter = JSONEntryFormatter()
        result = formatter.format(pdf_entry)

        parsed = json.loads(result)
        assert parsed["content"] == "PDF page content"
        assert "page_info" in parsed
        assert parsed["page_info"]["document_id"] == "test_document.pdf"
        assert parsed["page_info"]["page_label"] == "iv"
        assert parsed["page_info"]["physical_page_index"] == 3

    def test_plain_text_formatter_basic_entry(self, basic_entry):
        """Test plain text formatter with basic entry."""
        formatter = PlainTextEntryFormatter()
        result = formatter.format(basic_entry)

        assert "--- Entry ---" in result
        assert "This is test content" in result
        assert "--- End Entry ---" in result

    def test_plain_text_formatter_pdf_entry(self, pdf_entry):
        """Test plain text formatter with PDF entry."""
        formatter = PlainTextEntryFormatter()
        result = formatter.format(pdf_entry)

        assert "--- Entry from test_document.pdf, Page iv" in result
        assert "(physical page 4)" in result
        assert "PDF page content" in result
        assert "--- End Entry ---" in result

    def test_markdown_formatter_basic_entry(self, basic_entry):
        """Test Markdown formatter with basic entry."""
        formatter = MarkdownEntryFormatter()
        result = formatter.format(basic_entry)

        assert "## Entry" in result
        assert "This is test content" in result
        assert "---" in result

    def test_markdown_formatter_pdf_entry(self, pdf_entry):
        """Test Markdown formatter with PDF entry."""
        formatter = MarkdownEntryFormatter()
        result = formatter.format(pdf_entry)

        assert "## Entry: test_document.pdf, Page iv" in result
        assert "(physical page 4)" in result
        assert "PDF page content" in result
        assert "---" in result

    def test_formatters_with_none_metadata(self):
        """Test formatters handle None metadata gracefully."""
        entry = Entry(content="Content without metadata", metadata=None)

        xml_formatter = XMLEntryFormatter()
        json_formatter = JSONEntryFormatter()
        text_formatter = PlainTextEntryFormatter()
        md_formatter = MarkdownEntryFormatter()

        # Should not raise exceptions
        xml_result = xml_formatter.format(entry)
        json_result = json_formatter.format(entry)
        text_result = text_formatter.format(entry)
        md_result = md_formatter.format(entry)

        # All should contain the content
        assert "Content without metadata" in xml_result
        assert "Content without metadata" in json_result
        assert "Content without metadata" in text_result
        assert "Content without metadata" in md_result

    def test_formatters_with_empty_metadata(self):
        """Test formatters handle empty metadata dict."""
        entry = Entry(content="Content with empty metadata", metadata={})

        xml_formatter = XMLEntryFormatter()
        json_formatter = JSONEntryFormatter()

        xml_result = xml_formatter.format(entry)
        json_result = json_formatter.format(entry)

        assert "Content with empty metadata" in xml_result
        assert "Content with empty metadata" in json_result
