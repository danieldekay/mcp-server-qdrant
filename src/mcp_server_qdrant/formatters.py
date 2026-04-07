"""
Entry formatting strategies for different output formats.

Provides abstraction for formatting Entry objects into various
representations (XML, JSON, plain text, etc.).
"""

from abc import ABC, abstractmethod
from typing import Any

from mcp_server_qdrant.constants import PDFMetadataKeys, TeachingMetadataKeys
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

    def _build_reference(self, metadata: dict[str, Any] | None) -> dict[str, Any]:
        """Build a normalized reference block for result formatting."""
        if not metadata:
            return {}

        reference: dict[str, Any] = {}

        if metadata.get("_collection"):
            reference["collection"] = metadata["_collection"]

        if metadata.get(PDFMetadataKeys.DOCUMENT_ID):
            reference["document_id"] = metadata[PDFMetadataKeys.DOCUMENT_ID]

        if metadata.get(PDFMetadataKeys.PAGE_LABEL) is not None:
            reference["page_label"] = metadata[PDFMetadataKeys.PAGE_LABEL]

        if metadata.get(PDFMetadataKeys.PHYSICAL_PAGE_INDEX) is not None:
            reference["physical_page_index"] = metadata[
                PDFMetadataKeys.PHYSICAL_PAGE_INDEX
            ]

        chapter_title = metadata.get(TeachingMetadataKeys.CHAPTER_TITLE) or metadata.get(
            PDFMetadataKeys.CHAPTER_TITLE
        )
        if chapter_title:
            reference["chapter_title"] = chapter_title

        if metadata.get(TeachingMetadataKeys.COURSE_ID):
            reference["course_id"] = metadata[TeachingMetadataKeys.COURSE_ID]

        if metadata.get(TeachingMetadataKeys.CONTENT_TYPE):
            reference["content_type"] = metadata[TeachingMetadataKeys.CONTENT_TYPE]

        if metadata.get(TeachingMetadataKeys.LANGUAGE):
            reference["language"] = metadata[TeachingMetadataKeys.LANGUAGE]

        return reference

    def _build_reference_text(self, metadata: dict[str, Any] | None) -> str:
        """Render reference metadata as a concise human-readable citation line."""
        reference = self._build_reference(metadata)
        if not reference:
            return ""

        parts: list[str] = []
        if reference.get("collection"):
            parts.append(f"Collection: {reference['collection']}")
        if reference.get("course_id"):
            parts.append(f"Course: {reference['course_id']}")
        if reference.get("document_id"):
            parts.append(f"Document: {reference['document_id']}")
        if reference.get("page_label") is not None:
            page_info = f"Page: {reference['page_label']}"
            physical_index = reference.get("physical_page_index")
            if physical_index is not None:
                page_info += f" (physical page {physical_index + 1})"
            parts.append(page_info)
        if reference.get("chapter_title"):
            parts.append(f"Chapter: {reference['chapter_title']}")
        if reference.get("content_type"):
            parts.append(f"Type: {reference['content_type']}")
        if reference.get("language"):
            parts.append(f"Language: {reference['language']}")

        return "; ".join(parts)


class XMLEntryFormatter(EntryFormatter):
    """Format entries as XML-like structure."""

    def format(self, entry: Entry) -> str:
        """
        Format entry as XML-like structure.
        :param entry: Entry to format
        :return: XML-formatted string
        """
        import json
        from xml.sax.saxutils import escape

        metadata = entry.metadata or {}
        entry_metadata = json.dumps(metadata) if metadata else ""
        score_attr = f' score="{entry.score:.3f}"' if entry.score is not None else ""
        escaped_content = escape(entry.content)
        reference_text = self._build_reference_text(metadata)
        reference_xml = f"<reference>{escape(reference_text)}</reference>" if reference_text else ""

        if self._is_pdf_entry(metadata):
            document_id = escape(str(metadata.get(PDFMetadataKeys.DOCUMENT_ID, "")))
            page_label = escape(str(metadata.get(PDFMetadataKeys.PAGE_LABEL, "")))
            physical_index = metadata.get(PDFMetadataKeys.PHYSICAL_PAGE_INDEX)

            physical_info = (
                f" (physical page {physical_index + 1})"
                if physical_index is not None
                else ""
            )

            return (
                f"<entry{score_attr}>"
                f"<content>{escaped_content}</content>"
                f"<page>Document: {document_id}, Page: {page_label}{physical_info}</page>"
                f"{reference_xml}"
                f"<metadata>{entry_metadata}</metadata>"
                f"</entry>"
            )

        return (
            f"<entry{score_attr}>"
            f"<content>{escaped_content}</content>"
            f"{reference_xml}"
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

        if entry.score is not None:
            result["score"] = round(entry.score, 3)

        reference = self._build_reference(metadata)
        if reference:
            result["reference"] = reference

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

        score_info = f" [score: {entry.score:.3f}]" if entry.score is not None else ""
        reference_text = self._build_reference_text(metadata)

        if self._is_pdf_entry(metadata):
            document_id = metadata.get(PDFMetadataKeys.DOCUMENT_ID)
            page_label = metadata.get(PDFMetadataKeys.PAGE_LABEL)
            physical_index = metadata.get(PDFMetadataKeys.PHYSICAL_PAGE_INDEX)

            physical_info = (
                f" (physical page {physical_index + 1})"
                if physical_index is not None
                else ""
            )
            parts = [
                f"--- Entry from {document_id}, Page {page_label}{physical_info}{score_info} ---",
            ]
            if reference_text:
                parts.append(reference_text)
            parts.append(entry.content)
            parts.append("--- End Entry ---")
            return "\n".join(parts)

        if reference_text:
            return (
                f"--- Entry{score_info} ---\n"
                f"{reference_text}\n"
                f"{entry.content}\n"
                f"--- End Entry ---"
            )

        return f"--- Entry{score_info} ---\n{entry.content}\n--- End Entry ---"


class MarkdownEntryFormatter(EntryFormatter):
    """Format entries as Markdown with proper structure."""

    def format(self, entry: Entry) -> str:
        """
        Format entry as Markdown.
        :param entry: Entry to format
        :return: Markdown-formatted string
        """
        metadata = entry.metadata or {}
        score_info = f" (score: {entry.score:.3f})" if entry.score is not None else ""
        reference_text = self._build_reference_text(metadata)

        if self._is_pdf_entry(metadata):
            document_id = metadata.get(PDFMetadataKeys.DOCUMENT_ID)
            page_label = metadata.get(PDFMetadataKeys.PAGE_LABEL)
            physical_index = metadata.get(PDFMetadataKeys.PHYSICAL_PAGE_INDEX)

            physical_info = (
                f" (physical page {physical_index + 1})"
                if physical_index is not None
                else ""
            )
            parts = [f"## Entry: {document_id}, Page {page_label}{physical_info}{score_info}"]
            if reference_text:
                parts.append(reference_text)
            parts.append(entry.content)
            parts.append("---")
            return "\n\n".join(parts) + "\n"

        if reference_text:
            return (
                f"## Entry{score_info}\n\n"
                f"{reference_text}\n\n"
                f"{entry.content}\n\n"
                f"---\n"
            )

        return f"## Entry{score_info}\n\n{entry.content}\n\n---\n"
