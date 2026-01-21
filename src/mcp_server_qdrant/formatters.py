"""
Entry formatting strategies for different output formats.

Provides abstraction for formatting Entry objects into various
representations (XML, JSON, plain text, etc.).
"""

from abc import ABC, abstractmethod
from typing import Any

from mcp_server_qdrant.constants import PDFMetadataKeys
from mcp_server_qdrant.qdrant import Entry


class EntryFormatter(ABC):
    """Abstract base class for entry formatting strategies."""

    @abstractmethod
    def format(self, entry: Entry) -> str | list[str]:
        """
        Format an entry for display.
        :param entry: The entry to format
        :return: Formatted string or list of strings
        """
        pass

    def _is_pdf_entry(self, metadata: dict[str, Any] | None) -> bool:
        """
        Check if entry is a PDF page entry based on metadata.
        :param metadata: Entry metadata
        :return: True if entry has PDF page metadata
        """
        if not metadata:
            return False

        return (
            PDFMetadataKeys.DOCUMENT_ID in metadata
            and PDFMetadataKeys.PAGE_LABEL in metadata
        )


class XMLEntryFormatter(EntryFormatter):
    """Format entries as XML-like structure."""

    def format(self, entry: Entry) -> str:
        """
        Format entry as XML-like structure.
        :param entry: Entry to format
        :return: XML-formatted string
        """
        import json

        metadata = entry.metadata or {}
        entry_metadata = json.dumps(metadata) if metadata else ""

        if self._is_pdf_entry(metadata):
            document_id = metadata.get(PDFMetadataKeys.DOCUMENT_ID)
            page_label = metadata.get(PDFMetadataKeys.PAGE_LABEL)
            physical_index = metadata.get(PDFMetadataKeys.PHYSICAL_PAGE_INDEX)

            physical_info = (
                f" (physical page {physical_index + 1})"
                if physical_index is not None
                else ""
            )

            return (
                f"<entry>"
                f"<content>{entry.content}</content>"
                f"<page>Document: {document_id}, Page: {page_label}{physical_info}</page>"
                f"<metadata>{entry_metadata}</metadata>"
                f"</entry>"
            )

        return (
            f"<entry>"
            f"<content>{entry.content}</content>"
            f"<metadata>{entry_metadata}</metadata>"
            f"</entry>"
        )


class JSONEntryFormatter(EntryFormatter):
    """Format entries as JSON objects."""

    def format(self, entry: Entry) -> str:
        """
        Format entry as JSON.
        :param entry: Entry to format
        :return: JSON-formatted string
        """
        import json

        metadata = entry.metadata or {}

        result = {"content": entry.content, "metadata": metadata}

        if self._is_pdf_entry(metadata):
            result["page_info"] = {
                "document_id": metadata.get(PDFMetadataKeys.DOCUMENT_ID),
                "page_label": metadata.get(PDFMetadataKeys.PAGE_LABEL),
                "physical_page_index": metadata.get(
                    PDFMetadataKeys.PHYSICAL_PAGE_INDEX
                ),
            }

        return json.dumps(result, indent=2)


class PlainTextEntryFormatter(EntryFormatter):
    """Format entries as plain text with minimal formatting."""

    def format(self, entry: Entry) -> str:
        """
        Format entry as plain text.
        :param entry: Entry to format
        :return: Plain text formatted string
        """
        metadata = entry.metadata or {}

        if self._is_pdf_entry(metadata):
            document_id = metadata.get(PDFMetadataKeys.DOCUMENT_ID)
            page_label = metadata.get(PDFMetadataKeys.PAGE_LABEL)
            physical_index = metadata.get(PDFMetadataKeys.PHYSICAL_PAGE_INDEX)

            physical_info = (
                f" (physical page {physical_index + 1})"
                if physical_index is not None
                else ""
            )

            return (
                f"--- Entry from {document_id}, Page {page_label}{physical_info} ---\n"
                f"{entry.content}\n"
                f"--- End Entry ---"
            )

        return f"--- Entry ---\n{entry.content}\n--- End Entry ---"


class MarkdownEntryFormatter(EntryFormatter):
    """Format entries as Markdown with proper structure."""

    def format(self, entry: Entry) -> str:
        """
        Format entry as Markdown.
        :param entry: Entry to format
        :return: Markdown-formatted string
        """
        metadata = entry.metadata or {}

        if self._is_pdf_entry(metadata):
            document_id = metadata.get(PDFMetadataKeys.DOCUMENT_ID)
            page_label = metadata.get(PDFMetadataKeys.PAGE_LABEL)
            physical_index = metadata.get(PDFMetadataKeys.PHYSICAL_PAGE_INDEX)

            physical_info = (
                f" (physical page {physical_index + 1})"
                if physical_index is not None
                else ""
            )

            return (
                f"## Entry: {document_id}, Page {page_label}{physical_info}\n\n"
                f"{entry.content}\n\n"
                f"---\n"
            )

        return f"## Entry\n\n{entry.content}\n\n---\n"
