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


class DoclingMetadataKeys:
    """Metadata keys for Docling-based semantic chunk ingestion."""

    # Page numbers
    PDF_PAGES = "pdf_pages"              # list[int] – physical PDF pages (1-based)
    BOOK_PAGES = "book_pages"            # list[int] – printed book page numbers
    BOOK_PAGE_START = "book_page_start"  # int – first printed page (for range queries)
    BOOK_PAGE_END = "book_page_end"      # int – last printed page

    # Document structure
    HEADING_L1 = "heading_l1"            # str – top-level chapter heading
    HEADING_L2 = "heading_l2"            # str – second-level section heading
    HEADING_L3 = "heading_l3"            # str – third-level sub-section heading
    CHAPTER = "chapter"                  # str – resolved chapter title for this chunk
    SECTION = "section"                  # str – resolved section title for this chunk

    # Chunk classification
    CHUNK_TYPE = "chunk_type"            # "text" | "figure" | "table" | "section_header" | "list_item"
    CHUNK_INDEX = "chunk_index"          # int – sequential index within document

    # Media assets
    FIGURE_PATHS = "figure_paths"        # list[str] – absolute paths to saved PNG images
    TABLE_INDEX = "table_index"          # int – table sequence number within document

    # Citation
    APA_CITATION = "apa_citation"        # str – full APA reference string

    # Course context
    KURS = "kurs"                        # str – course this book belongs to
    TYP = "typ"                          # str – "lehrbuch" | "buchkapitel" | "artikel"


class SystemMetadataKeys:
    """Internal metadata keys used for ingestion and lifecycle operations."""

    CONTENT_HASH = "content_hash"
