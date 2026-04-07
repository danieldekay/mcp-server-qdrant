import asyncio
import logging
import re
from typing import List, Tuple
from pathlib import Path

try:
    from pypdf import PdfReader

    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

logger = logging.getLogger(__name__)

# Pattern for detecting index entries: "Term  123, 456-789" or "Term, 123" or "Term 123f."
# Group 1: term text (stops before trailing page numbers)
# Group 2: page refs (digits, ranges, f./ff., comma-separated)
INDEX_ENTRY_PATTERN = re.compile(
    r"^(.*?)\s+"
    r"(\d+(?:f{1,2}\.?)?(?:\s*[,;]\s*\d+(?:f{1,2}\.?)?|\s*[-–—]\s*\d+(?:f{1,2}\.?)?)*)\s*$",
    re.MULTILINE,
)
# Characters that mark a sub-entry in German academic indexes (indent with dash/bullet)
_SUBENTRY_RE = re.compile(r"^([\s]*[–—4]\s*[-]?)")

# Keywords that signal the start of a back-of-book index
INDEX_HEADING_KEYWORDS = [
    "stichwortverzeichnis",
    "sachregister",
    "schlagwortverzeichnis",
    "subject index",
    "index",
    "register",
]


class PDFPageExtractor:
    """
    Asynchronous PDF page extraction using pypdf.
    Wraps synchronous pypdf operations in asyncio.to_thread() to maintain
    async-first architecture as per project constitution.
    """

    def __init__(self, pdf_path: str, extraction_mode: str = "plain"):
        self.pdf_path = Path(pdf_path)
        self.extraction_mode = extraction_mode
        self._reader: "PdfReader | None" = None
        if not PYPDF_AVAILABLE:
            raise ImportError(
                "pypdf is not installed. Please install it with 'pip install pypdf>=5.1.0'."
            )
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {self.pdf_path}")

    def _get_reader(self) -> "PdfReader":
        """Return a cached PdfReader instance (created on first access)."""
        if self._reader is None:
            self._reader = PdfReader(str(self.pdf_path))
        return self._reader

    def _extract_text_from_page(self, page) -> str:
        """
        Extract text from a single page using the configured extraction mode.
        :param page: pypdf PageObject
        :return: Extracted text
        """
        if self.extraction_mode == "layout":
            return page.extract_text(
                extraction_mode="layout", layout_mode_space_vertically=False
            ) or ""
        return page.extract_text() or ""

    @staticmethod
    def format_page_label(label: str, physical_index: int) -> str:
        """
        Format the page label for display.
        :param label: The label extracted from PDF
        :param physical_index: 0-based physical index (fallback)
        :return: Formatted label string
        """
        if not label or label.strip() == "":
            return f"Page {physical_index + 1}"
        return label.strip()

    async def get_page_count(self) -> int:
        """Get the total number of pages in the PDF."""

        def _get_count():
            reader = self._get_reader()
            return len(reader.pages)

        return await asyncio.to_thread(_get_count)

    async def extract_page_content(self, page_index: int) -> str:
        """
        Extract text content from a specific page asynchronously.
        :param page_index: 0-based page index
        :return: Extracted text content
        """

        def _extract():
            try:
                reader = self._get_reader()
                page = reader.pages[page_index]
                return self._extract_text_from_page(page)
            except Exception as e:
                logger.error(
                    f"Failed to extract text from page {page_index} of {self.pdf_path}: {e}"
                )
                return ""

        return await asyncio.to_thread(_extract)

    async def extract_page_label(self, page_index: int) -> str:
        """
        Extract page label (e.g., 'iv', '45', 'Appendix A') for a specific page.
        Falls back to 'Page N' format (1-based) if labels are unavailable.
        :param page_index: 0-based page index
        :return: Page label string
        """

        def _extract_label():
            try:
                reader = self._get_reader()
                label = reader.page_labels[page_index]
                return self.format_page_label(str(label), page_index)
            except (IndexError, KeyError, Exception) as e:
                logger.debug(
                    f"Page label not found for index {page_index} in {self.pdf_path}: {e}"
                )
                return self.format_page_label("", page_index)

        return await asyncio.to_thread(_extract_label)

    async def extract_all_pages(self) -> List[Tuple[str, int, str]]:
        """
        Extract content and labels for all pages in the PDF.
        :return: List of tuples (content, physical_index, page_label)
        """

        def _extract_all():
            reader = self._get_reader()
            pages_data = []
            for i in range(len(reader.pages)):
                try:
                    content = self._extract_text_from_page(reader.pages[i])
                    try:
                        label = self.format_page_label(str(reader.page_labels[i]), i)
                    except (IndexError, KeyError):
                        label = self.format_page_label("", i)
                    pages_data.append((content, i, label))
                except Exception as e:
                    logger.error(f"Error processing page {i} of {self.pdf_path}: {e}")
                    pages_data.append(("", i, self.format_page_label("", i)))
            return pages_data

        return await asyncio.to_thread(_extract_all)

    # --- M11: Outline/Bookmark Extraction ---

    @staticmethod
    def _parse_outline(reader: "PdfReader", outline_items, level: int = 0) -> list[dict]:
        """
        Recursively parse the PDF outline (bookmarks) into a flat list.
        :param reader: PdfReader instance
        :param outline_items: Outline items (possibly nested lists)
        :param level: Current nesting level (0 = top-level)
        :return: List of dicts with 'title', 'page_index', 'level'
        """
        result = []
        for item in outline_items:
            if isinstance(item, list):
                result.extend(PDFPageExtractor._parse_outline(reader, item, level + 1))
            elif hasattr(item, "title"):
                try:
                    page_num = reader.get_destination_page_number(item)
                except Exception:
                    page_num = None
                result.append({
                    "title": item.title,
                    "page_index": page_num,
                    "level": level,
                })
        return result

    async def extract_outline(self) -> list[dict]:
        """
        Extract the document outline (bookmarks/table of contents).
        :return: List of dicts with 'title', 'page_index', 'level'.
                 Empty list if no outline exists.
        """

        def _extract():
            reader = self._get_reader()
            outline = reader.outline
            if not outline:
                return []
            return PDFPageExtractor._parse_outline(reader, outline)

        return await asyncio.to_thread(_extract)

    async def extract_document_metadata(self) -> dict:
        """
        Extract document-level metadata (title, author, subject, creator).
        :return: Dict with available metadata fields, empty dict if none.
        """

        def _extract():
            reader = self._get_reader()
            meta = reader.metadata
            if not meta:
                return {}
            result = {}
            if meta.title:
                result["title"] = meta.title
            if meta.author:
                result["author"] = meta.author
            if meta.subject:
                result["subject"] = meta.subject
            if meta.creator:
                result["creator"] = meta.creator
            return result

        return await asyncio.to_thread(_extract)

    @staticmethod
    def get_chapter_for_page(outline: list[dict], page_index: int) -> str | None:
        """
        Determine which chapter/section a page belongs to based on the outline.
        Finds the deepest outline entry whose page_index <= the given page.
        :param outline: Parsed outline from extract_outline()
        :param page_index: 0-based physical page index
        :return: Title of the matching outline entry, or None
        """
        best_match = None
        for item in outline:
            item_page = item.get("page_index")
            if item_page is not None and item_page <= page_index:
                if best_match is None or item_page >= best_match["page_index"]:
                    best_match = item
        return best_match["title"] if best_match else None

    # --- M12: Index (Stichwortverzeichnis) Detection and Parsing ---

    @staticmethod
    def detect_index_start(
        outline: list[dict],
        pages_data: List[Tuple[str, int, str]] | None = None,
    ) -> int | None:
        """
        Detect the starting page of a back-of-book index (Stichwortverzeichnis).

        Strategy A: Check outline/bookmarks for index heading keywords,
                    but only in the last 15% of the document to avoid false
                    positives from table-of-contents entries mid-book.
        Strategy B (fallback): Scan last 10% of pages for heading patterns.

        :param outline: Parsed outline from extract_outline()
        :param pages_data: All pages data (content, index, label) for heuristic fallback
        :return: 0-based page index where the index starts, or None
        """
        # Strategy A: bookmarks — restricted to last 15% to avoid false positives
        # from ToC entries or chapter headers that contain index keywords mid-book
        total_pages = len(pages_data) if pages_data else 0
        min_index_page = int(total_pages * 0.85) if total_pages > 0 else 0

        for item in outline:
            title_lower = item.get("title", "").lower()
            page_index = item.get("page_index")
            if page_index is None:
                continue
            if page_index < min_index_page:
                continue
            if any(kw in title_lower for kw in INDEX_HEADING_KEYWORDS):
                return page_index

        # Strategy B: heuristic scan of last pages
        if pages_data:
            total = len(pages_data)
            scan_start = max(0, total - max(10, total // 10))
            for content, idx, _label in pages_data[scan_start:]:
                first_lines = content[:500].lower()
                if any(kw in first_lines for kw in INDEX_HEADING_KEYWORDS):
                    return idx

        return None

    @staticmethod
    def parse_index_entries(text: str) -> dict[str, list[int | tuple[int, int]]]:
        """
        Parse index entries from raw text of index pages.
        Handles German Springer-style indexes:
          - Space-separated term and pages: "Reliabilität 115, 438"
          - Sub-entries starting with – or 4: "– koeffizienten 438"
            merged with their parent: → "Reliabilitätskoeffizienten"
          - Page ranges: "45–72"
          - Follower notation: "45f." / "45ff."
          - Comma-separated pages: "45, 67, 89"

        :param text: Raw text of one or more index pages
        :return: Dict mapping terms to lists of page numbers/ranges
        """
        entries: dict[str, list[int | tuple[int, int]]] = {}
        current_parent: str | None = None

        for line in text.splitlines():
            original = line
            line = line.strip()
            if not line:
                continue

            # Detect sub-entry: line starts with –, —, or the Springer bullet (4)
            sub_match = _SUBENTRY_RE.match(original)
            is_sub = sub_match is not None
            if is_sub:
                # Strip the sub-entry prefix chars, keep any trailing connector
                line = _SUBENTRY_RE.sub("", original).strip()

            # Match term + page numbers
            m = INDEX_ENTRY_PATTERN.match(line)
            if not m:
                continue

            term = m.group(1).strip().rstrip(",")
            pages_str = m.group(2)

            # Skip overly short or numeric-only terms
            if len(term) < 2 or term.isdigit():
                continue

            # Build full term: attach sub-entry to parent
            if is_sub and current_parent:
                # Strip leading dashes/hyphens from sub-entry (compound or descriptive)
                # Always join with space for consistent, searchable terms:
                # "Reliabilität -koeffizient" → "Reliabilität koeffizient"
                # "Reliabilität qualitativer Datensätze" → as-is
                sub_clean = term.lstrip("- ").strip()
                full_term = f"{current_parent} {sub_clean}"
            else:
                full_term = term
                current_parent = term  # update parent for following sub-entries

            # Parse page references
            page_refs: list[int | tuple[int, int]] = []
            for part in re.split(r"[,;]\s*", pages_str):
                # Strip f./ff. follower notation
                part = re.sub(r"f{1,2}\.?$", "", part.strip())
                range_match = re.match(r"(\d+)\s*[-–—]\s*(\d+)", part)
                if range_match:
                    page_refs.append(
                        (int(range_match.group(1)), int(range_match.group(2)))
                    )
                elif part.isdigit():
                    page_refs.append(int(part))

            if page_refs:
                existing = entries.get(full_term, [])
                existing.extend(page_refs)
                entries[full_term] = existing

        return entries

    @staticmethod
    def build_page_to_terms_map(
        index_entries: dict[str, list[int | tuple[int, int]]],
    ) -> dict[int, list[str]]:
        """
        Invert the index: from term→pages to page→terms.
        :param index_entries: Output of parse_index_entries()
        :return: Dict mapping page numbers to lists of terms
        """
        page_map: dict[int, list[str]] = {}
        for term, refs in index_entries.items():
            for ref in refs:
                if isinstance(ref, tuple):
                    for p in range(ref[0], ref[1] + 1):
                        page_map.setdefault(p, []).append(term)
                else:
                    page_map.setdefault(ref, []).append(term)
        return page_map
