"""
Constants used throughout the mcp-server-qdrant project.
"""


class PDFMetadataKeys:
    """Constant keys for PDF page metadata."""

    DOCUMENT_ID = "document_id"
    PAGE_LABEL = "page_label"
    PHYSICAL_PAGE_INDEX = "physical_page_index"
    TOTAL_PAGES = "total_pages"
    FILENAME = "filename"
    FILEPATH = "filepath"
    EXTENSION = "extension"
    CHAPTER_TITLE = "chapter_title"
    DOCUMENT_TITLE = "document_title"
    DOCUMENT_AUTHOR = "document_author"
    INDEX_TERMS = "index_terms"


class TeachingMetadataKeys:
    """Constant keys for teaching material metadata."""

    COURSE_ID = "course_id"
    CHAPTER = "chapter"
    CHAPTER_TITLE = "chapter_title"
    TEXTBOOK = "textbook"
    CONTENT_TYPE = "content_type"
    LANGUAGE = "language"
