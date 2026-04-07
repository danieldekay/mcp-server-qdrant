"""
Tests for teaching metadata constants and filterable fields (M8).
"""

from unittest.mock import patch

import pytest

from mcp_server_qdrant.constants import PDFMetadataKeys, TeachingMetadataKeys
from mcp_server_qdrant.settings import DEFAULT_FILTERABLE_FIELDS, QdrantSettings


class TestTeachingMetadataKeys:
    """Verify TeachingMetadataKeys constants exist."""

    def test_course_id(self):
        assert TeachingMetadataKeys.COURSE_ID == "course_id"

    def test_chapter(self):
        assert TeachingMetadataKeys.CHAPTER == "chapter"

    def test_chapter_title(self):
        assert TeachingMetadataKeys.CHAPTER_TITLE == "chapter_title"

    def test_textbook(self):
        assert TeachingMetadataKeys.TEXTBOOK == "textbook"

    def test_content_type(self):
        assert TeachingMetadataKeys.CONTENT_TYPE == "content_type"

    def test_language(self):
        assert TeachingMetadataKeys.LANGUAGE == "language"


class TestDefaultFilterableFields:
    """Verify teaching metadata fields are in default filterable fields."""

    def _field_names(self):
        return [f.name for f in DEFAULT_FILTERABLE_FIELDS]

    def test_includes_pdf_fields(self):
        names = self._field_names()
        assert PDFMetadataKeys.DOCUMENT_ID in names
        assert PDFMetadataKeys.PAGE_LABEL in names
        assert PDFMetadataKeys.PHYSICAL_PAGE_INDEX in names

    def test_includes_teaching_fields(self):
        names = self._field_names()
        assert TeachingMetadataKeys.COURSE_ID in names
        assert TeachingMetadataKeys.CONTENT_TYPE in names
        assert TeachingMetadataKeys.LANGUAGE in names

    def test_course_id_field_config(self):
        field = next(
            f for f in DEFAULT_FILTERABLE_FIELDS
            if f.name == TeachingMetadataKeys.COURSE_ID
        )
        assert field.field_type == "keyword"
        assert field.condition == "=="

    def test_content_type_field_config(self):
        field = next(
            f for f in DEFAULT_FILTERABLE_FIELDS
            if f.name == TeachingMetadataKeys.CONTENT_TYPE
        )
        assert field.field_type == "keyword"
        assert field.condition == "=="

    @patch.dict("os.environ", {"QDRANT_URL": ":memory:"})
    def test_qdrant_settings_uses_defaults(self):
        settings = QdrantSettings()
        names = [f.name for f in settings.filterable_fields]
        assert TeachingMetadataKeys.COURSE_ID in names
        assert TeachingMetadataKeys.CONTENT_TYPE in names
