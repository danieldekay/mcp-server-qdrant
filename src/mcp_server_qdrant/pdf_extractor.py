import asyncio
import logging
from typing import List, Tuple
from pathlib import Path

try:
    from pypdf import PdfReader

    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

logger = logging.getLogger(__name__)


class PDFPageExtractor:
    """
    Asynchronous PDF page extraction using pypdf.
    Wraps synchronous pypdf operations in asyncio.to_thread() to maintain
    async-first architecture as per project constitution.
    """

    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        if not PYPDF_AVAILABLE:
            raise ImportError(
                "pypdf is not installed. Please install it with 'pip install pypdf>=5.1.0'."
            )
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {self.pdf_path}")

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
            reader = PdfReader(str(self.pdf_path))
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
                reader = PdfReader(str(self.pdf_path))
                page = reader.pages[page_index]
                return page.extract_text() or ""
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
                reader = PdfReader(str(self.pdf_path))
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

        # Extract all pages sequentially in thread to avoid pypdf thread-safety issues
        def _extract_all():
            reader = PdfReader(str(self.pdf_path))
            pages_data = []
            for i in range(len(reader.pages)):
                try:
                    content = reader.pages[i].extract_text() or ""
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
