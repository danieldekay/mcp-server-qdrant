"""
Docling-based PDF processor for semantic chunk ingestion.

Replaces the page-level pypdf extraction with structurally-aware,
semantically-chunked processing that preserves:
  - Printed book page numbers (not just PDF physical pages)
  - Heading hierarchy (H1 / H2 / H3)
  - Figure and table assets saved as PNG files
  - APA citation metadata per chunk

Usage::

    processor = DoclingProcessor(
        pdf_path=Path("book.pdf"),
        collection_name="mayring-qualitative",
        book_cfg={
            "apa": "Mayring, P., & Fenzl, T. (2022)...",
            "kurs": "Qualitative Methoden",
            "typ": "buchkapitel",
            "book_page_range": (100, 2000),
        },
        media_dir=Path("/path/to/ai-for-profs-data/media"),
    )
    chunks = processor.process()   # list[dict] – ready for Qdrant store
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional Docling imports – processor degrades gracefully if not installed
# ---------------------------------------------------------------------------
try:
    from docling.document_converter import DocumentConverter
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import PdfFormatOption
    from docling_core.transforms.chunker import HierarchicalChunker
    from docling_core.types.doc import DocItemLabel

    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
    logger.warning(
        "Docling not installed. Run `uv add docling` in mcp/qdrant/ to enable "
        "semantic chunking. Falling back to pypdf page-level extraction."
    )

# pypdf is always available (in pyproject.toml dependencies)
from pypdf import PdfReader  # noqa: E402 (after optional imports)

from mcp_server_qdrant.constants import DoclingMetadataKeys, PDFMetadataKeys

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MIN_CHUNK_LENGTH = 20       # chars – shorter chunks are artefacts (e.g. "43")
BOOK_PAGE_RANGE_DEFAULT = (100, 2000)  # plausible printed book page range
MIN_TEXT_CHARS_PER_PAGE = 80

OCR_MODE_AUTO = "auto"
OCR_MODE_ALWAYS = "always"
OCR_MODE_NEVER = "never"

ROMAN_PATTERN = re.compile(r"^\s*(x{0,3})(ix|iv|v?i{0,3})\s*$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Dataclass for a processed chunk
# ---------------------------------------------------------------------------
@dataclass
class ProcessedChunk:
    """One semantic unit ready for Qdrant ingestion."""

    content: str
    pdf_pages: list[int] = field(default_factory=list)
    book_pages: list[int] = field(default_factory=list)
    total_pages: int | None = None
    heading_l1: str | None = None
    heading_l2: str | None = None
    heading_l3: str | None = None
    chapter: str | None = None
    section: str | None = None
    chunk_type: str = "text"
    chunk_index: int = 0
    figure_paths: list[str] = field(default_factory=list)
    table_index: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, book_cfg: dict, collection_name: str, filename: str) -> dict:
        """Serialize to flat Qdrant payload dict."""
        book_pages = sorted(self.book_pages)
        payload: dict[str, Any] = {
            # Content
            "content": self.content,
            # Page numbers
            DoclingMetadataKeys.PDF_PAGES: sorted(self.pdf_pages),
            DoclingMetadataKeys.BOOK_PAGES: book_pages,
            DoclingMetadataKeys.BOOK_PAGE_START: book_pages[0] if book_pages else None,
            DoclingMetadataKeys.BOOK_PAGE_END: book_pages[-1] if book_pages else None,
            PDFMetadataKeys.TOTAL_PAGES: self.total_pages,
            # Structure
            DoclingMetadataKeys.HEADING_L1: self.heading_l1,
            DoclingMetadataKeys.HEADING_L2: self.heading_l2,
            DoclingMetadataKeys.HEADING_L3: self.heading_l3,
            DoclingMetadataKeys.CHAPTER: self.chapter or self.heading_l1,
            DoclingMetadataKeys.SECTION: self.section or self.heading_l2,
            PDFMetadataKeys.CHAPTER_TITLE: self.chapter or self.heading_l1,
            DoclingMetadataKeys.CHUNK_TYPE: self.chunk_type,
            DoclingMetadataKeys.CHUNK_INDEX: self.chunk_index,
            # Media
            DoclingMetadataKeys.FIGURE_PATHS: self.figure_paths,
            DoclingMetadataKeys.TABLE_INDEX: self.table_index,
            # Citation
            DoclingMetadataKeys.APA_CITATION: book_cfg.get("apa", ""),
            DoclingMetadataKeys.KURS: book_cfg.get("kurs", ""),
            DoclingMetadataKeys.TYP: book_cfg.get("typ", "lehrbuch"),
            # Legacy keys (for backwards compat with existing MCP tools)
            PDFMetadataKeys.FILENAME: filename,
            PDFMetadataKeys.DOCUMENT_ID: collection_name,
            PDFMetadataKeys.PAGE_LABEL: str(book_pages[0]) if book_pages else "",
            PDFMetadataKeys.PHYSICAL_PAGE_INDEX: (sorted(self.pdf_pages)[0] - 1) if self.pdf_pages else 0,
            "apa_zitation": book_cfg.get("apa", ""),  # double-key for legacy tools
            "kurs": book_cfg.get("kurs", ""),
        }
        # Strip None values
        return {k: v for k, v in payload.items() if v is not None}


# ---------------------------------------------------------------------------
# Main processor class
# ---------------------------------------------------------------------------
class DoclingProcessor:
    """
    Process a PDF into semantic chunks using Docling + pypdf fallback.

    Parameters
    ----------
    pdf_path:
        Absolute path to the source PDF.
    collection_name:
        Qdrant collection name (also used as media sub-directory name).
    book_cfg:
        Book configuration dict from BOOKS catalogue in ingest_all.py.
        Expected keys: ``apa``, ``kurs``, ``typ``, ``book_page_range`` (optional).
    media_dir:
        Root directory for extracted media assets.
        Figures are saved to ``{media_dir}/{collection_name}/``.
    """

    def __init__(
        self,
        pdf_path: Path,
        collection_name: str,
        book_cfg: dict,
        media_dir: Path | None = None,
    ) -> None:
        if not DOCLING_AVAILABLE:
            raise ImportError(
                "docling is not installed. Run `cd mcp/qdrant && uv add docling`."
            )
        self.pdf_path = Path(pdf_path)
        self.collection_name = collection_name
        self.book_cfg = book_cfg
        self.book_page_range: tuple[int, int] = book_cfg.get(
            "book_page_range", BOOK_PAGE_RANGE_DEFAULT
        )
        self.media_dir = Path(media_dir) if media_dir else None
        self.ocr_mode = self._resolve_ocr_mode()
        self.extract_figures = self._resolve_extract_figures()

        self._doc = None            # DoclingDocument (text + structure)
        self._doc_with_images = None  # DoclingDocument with rendered pictures
        self._page_mapping: dict[int, int] = {}   # pdf_page → book_page
        self._asset_dir: Path | None = None
        self._ocr_enabled = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self) -> list[ProcessedChunk]:
        """
        Full processing pipeline.

        Returns list of ProcessedChunk objects, one per semantic unit.
        """
        logger.info("DoclingProcessor: converting %s", self.pdf_path.name)

        # Step 1: Convert (text only – fast)
        self._ocr_enabled = self.ocr_mode == OCR_MODE_ALWAYS
        self._convert_text(do_ocr=self._ocr_enabled)
        if self.ocr_mode == OCR_MODE_AUTO and self._needs_ocr_fallback():
            logger.info(
                "Retrying %s with OCR because the non-OCR pass yielded too little text",
                self.pdf_path.name,
            )
            self._ocr_enabled = True
            self._convert_text(do_ocr=True)

        # Step 2: Build page mapping (book page numbers)
        self._page_mapping = self._build_page_mapping()
        logger.info(
            "Page mapping: %d/%d pages mapped",
            len(self._page_mapping),
            len(list(self._doc.pages)),
        )

        # Step 3: Extract images if media_dir configured
        image_map: dict[int, list[str]] = {}
        if self.media_dir is not None and self.extract_figures:
            image_map = self._extract_and_save_images()

        # Step 4: Chunk and enrich
        chunks = self._build_chunks(image_map)
        logger.info("DoclingProcessor: %d chunks produced", len(chunks))
        return chunks

    # ------------------------------------------------------------------
    # Step 1: Docling conversion
    # ------------------------------------------------------------------

    def _convert_text(self, *, do_ocr: bool) -> None:
        """Run DocumentConverter (text pipeline only, no image rendering)."""
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=PdfPipelineOptions(
                        do_ocr=do_ocr,
                        generate_picture_images=False,
                    )
                )
            }
        )
        result = converter.convert(str(self.pdf_path))
        self._doc = result.document

    def _convert_with_images(self, *, do_ocr: bool) -> None:
        """Run a second Docling pass with picture rendering enabled."""
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=PdfPipelineOptions(
                        do_ocr=do_ocr,
                        generate_picture_images=True,
                    )
                )
            }
        )
        result = converter.convert(str(self.pdf_path))
        self._doc_with_images = result.document

    # ------------------------------------------------------------------
    # Step 2: Page number mapping
    # ------------------------------------------------------------------

    def _build_page_mapping(self) -> dict[int, int]:
        """
        Build {pdf_page_no → book_page_no} mapping.

        Strategy:
        0. pypdf page_labels (most reliable – embedded in PDF metadata)
        1. Docling PAGE_HEADER / PAGE_FOOTER elements (fallback)
        2. pypdf: scan first + last 3 lines of each page (secondary fallback)
        3. Linear extrapolation from first known page
        """
        mapping: dict[int, int] = {}
        front_matter: dict[int, str] = {}

        # --- Strategy 0: pypdf page_labels (preferred) ---
        # These are embedded in the PDF and are the most accurate source.
        # Springer books have correct Arabic labels (e.g. '334') directly accessible.
        self._pypdf_label_map(mapping, front_matter)

        # --- Strategy 1: Docling header/footer labels (only if labels not sufficient) ---
        if len(mapping) < len(list(self._doc.pages)) // 2:
            hf_labels = {DocItemLabel.PAGE_HEADER, DocItemLabel.PAGE_FOOTER}
            for item, _ in self._doc.iterate_items():
                if not hasattr(item, "label") or item.label not in hf_labels:
                    continue
                prov = item.prov[0] if item.prov else None
                if not prov:
                    continue
                pdf_page = prov.page_no
                if pdf_page in mapping or pdf_page in front_matter:
                    continue
                text = getattr(item, "text", "") or ""
                self._parse_page_number(pdf_page, text, mapping, front_matter)

        # --- Strategy 2: pypdf line scan (secondary fallback) ---
        if len(mapping) < len(list(self._doc.pages)) // 2:
            self._pypdf_page_scan(mapping, front_matter)

        # --- Strategy 3: Linear extrapolation ---
        num_pages = len(list(self._doc.pages))
        if mapping:
            first_pdf = min(mapping)
            first_book = mapping[first_pdf]
            for pdf_pg in range(first_pdf, num_pages + 1):
                if pdf_pg not in mapping and pdf_pg not in front_matter:
                    mapping[pdf_pg] = first_book + (pdf_pg - first_pdf)

        return mapping

    def _pypdf_label_map(
        self, mapping: dict[int, int], front_matter: dict[int, str]
    ) -> None:
        """
        Build mapping from pypdf page_labels (PDF metadata).

        PDF page_labels are the most reliable source of book page numbers as they
        are set by the publisher. Arabic numeric labels are used as book pages;
        Roman numeral labels mark front matter.
        """
        try:
            reader = PdfReader(str(self.pdf_path))
            if not hasattr(reader, "page_labels"):
                return
            lo, hi = self.book_page_range
            for idx, label in enumerate(reader.page_labels):
                pdf_page = idx + 1  # 1-based
                if pdf_page in mapping or pdf_page in front_matter:
                    continue
                label = (label or "").strip()
                if not label:
                    continue
                # Roman numerals → front matter
                if ROMAN_PATTERN.match(label):
                    front_matter[pdf_page] = label.lower()
                    continue
                # Pure Arabic → book page if in range
                if label.isdigit():
                    n = int(label)
                    if lo <= n <= hi:
                        mapping[pdf_page] = n
                    continue
                # Non-numeric publisher labels like 'C1' belong to front matter.
                front_matter[pdf_page] = label.lower()
        except Exception as exc:
            logger.warning("pypdf label map failed: %s", exc)

    def _parse_page_number(
        self,
        pdf_page: int,
        text: str,
        mapping: dict[int, int],
        front_matter: dict[int, str],
    ) -> None:
        """Extract and classify a page number from header/footer text."""
        text = text.strip()
        # Roman numerals → front matter
        if ROMAN_PATTERN.match(text) and pdf_page not in mapping:
            front_matter[pdf_page] = text.lower()
            return
        # Arabic numbers in plausible book range
        lo, hi = self.book_page_range
        for num_str in re.findall(r"\b(\d{2,4})\b", text):
            n = int(num_str)
            if lo <= n <= hi and pdf_page not in mapping:
                mapping[pdf_page] = n
                return

    def _pypdf_page_scan(
        self, mapping: dict[int, int], front_matter: dict[int, str]
    ) -> None:
        """Scan first and last 3 text lines per page to extract page numbers."""
        reader = PdfReader(str(self.pdf_path))
        for pdf_idx in range(len(reader.pages)):
            pdf_page = pdf_idx + 1
            if pdf_page in mapping or pdf_page in front_matter:
                continue
            raw = reader.pages[pdf_idx].extract_text() or ""
            lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
            candidates = (lines[:3] + lines[-3:]) if len(lines) > 6 else lines
            for line in candidates:
                self._parse_page_number(pdf_page, line, mapping, front_matter)
                if pdf_page in mapping:
                    break

    # ------------------------------------------------------------------
    # Step 3: Image extraction
    # ------------------------------------------------------------------

    def _extract_and_save_images(self) -> dict[int, list[str]]:
        """
        Run Docling with image rendering and save each figure as PNG.

        Returns {pdf_page_no: [absolute_path_str, ...]} mapping.
        """
        if not self._has_picture_candidates():
            logger.info(
                "Skipping image rendering for %s because Docling found no picture candidates",
                self.pdf_path.name,
            )
            return {}

        asset_dir = self.media_dir / self.collection_name
        asset_dir.mkdir(parents=True, exist_ok=True)
        self._asset_dir = asset_dir

        logger.info("Extracting images → %s", asset_dir)
        self._convert_with_images(do_ocr=self._ocr_enabled)

        image_map: dict[int, list[str]] = {}
        fig_counters: dict[int, int] = {}  # pdf_page → counter

        doc = self._doc_with_images
        for pic in doc.pictures:
            prov = pic.prov[0] if pic.prov else None
            if not prov:
                continue
            page_no = prov.page_no

            # Get PIL image from Docling
            try:
                pil_img = pic.get_image(doc)
            except Exception:
                pil_img = None
            if pil_img is None:
                # Try via image attribute (older Docling API)
                try:
                    pil_img = pic.image.pil_image  # type: ignore[attr-defined]
                except Exception:
                    continue
            if pil_img is None:
                continue

            # Build filename
            fig_counters[page_no] = fig_counters.get(page_no, 0) + 1
            fname = f"p{page_no:03d}_fig{fig_counters[page_no]:02d}.png"
            fpath = asset_dir / fname
            pil_img.save(str(fpath))

            image_map.setdefault(page_no, []).append(str(fpath))
            logger.debug("Saved figure: %s", fname)

        logger.info(
            "Saved %d figures across %d pages",
            sum(len(v) for v in image_map.values()),
            len(image_map),
        )
        return image_map

    def _needs_ocr_fallback(self) -> bool:
        """Detect scanned or text-poor PDFs and retry with OCR when needed."""
        page_count = len(list(self._doc.pages)) or 1
        total_text_chars = 0

        for item, _ in self._doc.iterate_items():
            text = (getattr(item, "text", "") or "").strip()
            total_text_chars += len(text)

        chars_per_page = total_text_chars / page_count
        logger.info(
            "Non-OCR text density for %s: %.1f chars/page",
            self.pdf_path.name,
            chars_per_page,
        )
        return chars_per_page < MIN_TEXT_CHARS_PER_PAGE

    def _has_picture_candidates(self) -> bool:
        """Return True when the first Docling pass already detected pictures."""
        pictures = getattr(self._doc, "pictures", None)
        if pictures is None:
            return True
        return any(True for _ in pictures)

    def _resolve_ocr_mode(self) -> str:
        """Resolve OCR mode from book config or environment."""
        raw_value = self.book_cfg.get(
            "docling_ocr",
            os.environ.get("DOCLING_OCR_MODE", OCR_MODE_AUTO),
        )
        normalized = str(raw_value).strip().lower()
        aliases = {
            "1": OCR_MODE_ALWAYS,
            "true": OCR_MODE_ALWAYS,
            "yes": OCR_MODE_ALWAYS,
            "on": OCR_MODE_ALWAYS,
            "0": OCR_MODE_NEVER,
            "false": OCR_MODE_NEVER,
            "no": OCR_MODE_NEVER,
            "off": OCR_MODE_NEVER,
        }
        normalized = aliases.get(normalized, normalized)
        if normalized not in {OCR_MODE_AUTO, OCR_MODE_ALWAYS, OCR_MODE_NEVER}:
            return OCR_MODE_AUTO
        return normalized

    def _resolve_extract_figures(self) -> bool:
        """Resolve whether figure rendering should be attempted at all."""
        raw_value = self.book_cfg.get(
            "extract_figures",
            os.environ.get("DOCLING_EXTRACT_FIGURES", "true"),
        )
        return str(raw_value).strip().lower() not in {"0", "false", "no", "off"}

    # ------------------------------------------------------------------
    # Step 4: Chunking and metadata enrichment
    # ------------------------------------------------------------------

    def _build_chunks(self, image_map: dict[int, list[str]]) -> list[ProcessedChunk]:
        """Apply HierarchicalChunker and enrich each chunk with metadata."""
        chunker = HierarchicalChunker()
        raw_chunks = list(chunker.chunk(self._doc))
        total_pages = len(list(self._doc.pages))

        results: list[ProcessedChunk] = []
        table_counter = 0

        for idx, raw in enumerate(raw_chunks):
            text = raw.text.strip() if raw.text else ""
            if len(text) < MIN_CHUNK_LENGTH:
                continue  # filter artefacts

            # Collect PDF pages for this chunk
            pdf_pages: set[int] = set()
            for di in raw.meta.doc_items or []:
                for prov in di.prov or []:
                    pdf_pages.add(prov.page_no)

            # Map to book pages
            book_pages = sorted(
                self._page_mapping[p] for p in pdf_pages if p in self._page_mapping
            )

            # Extract headings (up to 3 levels)
            headings: list[str] = list(raw.meta.headings or [])
            h1 = headings[0] if len(headings) > 0 else None
            h2 = headings[1] if len(headings) > 1 else None
            h3 = headings[2] if len(headings) > 2 else None

            # Determine chunk type
            chunk_type = self._classify_chunk(raw, text)
            if chunk_type == "table":
                table_counter += 1

            # Figure paths: assign images from pages covered by this chunk
            fig_paths: list[str] = []
            if chunk_type in ("figure", "text"):
                for pg in sorted(pdf_pages):
                    fig_paths.extend(image_map.get(pg, []))

            chunk = ProcessedChunk(
                content=text,
                pdf_pages=sorted(pdf_pages),
                book_pages=book_pages,
                total_pages=total_pages,
                heading_l1=h1,
                heading_l2=h2,
                heading_l3=h3,
                chapter=h1,
                section=h2,
                chunk_type=chunk_type,
                chunk_index=idx,
                figure_paths=fig_paths,
                table_index=table_counter if chunk_type == "table" else None,
            )
            results.append(chunk)

        return results

    @staticmethod
    def _classify_chunk(raw_chunk: Any, text: str) -> str:
        """Classify chunk type from Docling DocItemLabel."""
        try:
            from docling_core.types.doc import DocItemLabel

            for di in raw_chunk.meta.doc_items or []:
                label = getattr(di, "label", None)
                if label == DocItemLabel.PICTURE:
                    return "figure"
                if label == DocItemLabel.TABLE:
                    return "table"
                if label in (
                    DocItemLabel.SECTION_HEADER,
                    DocItemLabel.PAGE_HEADER,
                ):
                    return "section_header"
                if label == DocItemLabel.LIST_ITEM:
                    return "list_item"
        except Exception:
            pass
        return "text"
