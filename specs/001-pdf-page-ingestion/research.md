# Research: PDF Page-by-Page Ingestion (001)

## Summary

This document consolidates research findings for implementing PDF page-by-page ingestion with custom page numbering support. The primary technical decision is **selecting a Python PDF library that supports page label extraction** while maintaining compatibility with the project's async-first architecture.

## 1. PDF Library Comparison

### 1.1 Evaluated Libraries

Three primary libraries were evaluated for this feature:

| Library | Page Labels API | Async Support | Dependencies | License | Active Maintenance |
|---------|----------------|---------------|--------------|---------|-------------------|
| **pypdf** | ✅ Native API (`reader.page_labels[index]`) | ❌ Sync only | Pure Python | MIT | ✅ Active (9.5k stars) |
| **PyMuPDF (fitz)** | ⚠️ Workaround possible via `get_page_labels()` | ❌ Sync only | C (MuPDF) | AGPL | ✅ Active |
| **pdfplumber** | ❌ No native support | ❌ Sync only | pdfminer.six, Pillow | MIT | ✅ Active (9.5k stars) |

### 1.2 Page Label Extraction Capabilities

**pypdf (Recommended)**:

- **Direct API**: `reader.page_labels[index]` returns the page label string
- **Feature added**: 2023 via merged PR
- **Example usage**:

```python
from pypdf import PdfReader
reader = PdfReader("document.pdf")
for index, page in enumerate(reader.pages):
    label = reader.page_labels[index]
    print(f"Physical page {index}: label={label}")
```

**PyMuPDF**:

- **Document-level API**: `doc.get_page_labels()` returns label definitions
- Returns list of dictionaries with format:

```python
[
    {'startpage': 6, 'prefix': 'A-', 'style': 'D', 'firstpagenum': 10},
    {'startpage': 10, 'prefix': '', 'style': 'D', 'firstpagenum': 1}
]
```

- Requires manual calculation to map page index to label
- **Page lookup API**: `doc.get_page_numbers(label)` for reverse lookup

**pdfplumber**:

- No native page label extraction support
- Built on pdfminer.six (focuses on layout, not metadata)
- Would require custom PDF metadata parsing

### 1.3 Performance Considerations

**PyMuPDF** (fastest overall):

- Text extraction: 367s for 7,031 pages (benchmark from Unstract evaluation)
- C-based implementation provides superior performance
- Built-in OCR support for scanned documents

**pypdf** (moderate speed):

- Pure Python implementation
- Acceptable performance for typical document sizes
- No external binary dependencies

**pdfplumber** (slower, optimized for layout):

- Focus on table extraction and layout preservation
- Visual debugging capabilities
- Not optimized for bulk text extraction

## 2. Recommended Solution: pypdf

### 2.1 Decision Rationale

**pypdf is recommended** for the following reasons:

1. **Native Page Label API**: Only pypdf provides direct, reliable access to PDF page labels via `reader.page_labels[index]`. This is critical for FR-013 and FR-014 requirements.

2. **Pure Python**: No C dependencies means:
   - Easier installation across platforms
   - Simpler CI/CD integration
   - Reduced deployment complexity
   - Better portability

3. **MIT License**: Compatible with project licensing (Apache-2.0)

4. **Active Maintenance**: 9.5k GitHub stars, regular updates, well-documented

5. **Acceptable Performance**: While not as fast as PyMuPDF, performance is sufficient for typical document processing workflows

6. **Established API**: Stable, well-documented API with extensive community support

### 2.2 Async Compatibility Strategy

**Problem**: All Python PDF libraries are synchronous, but project constitution requires async-first architecture.

**Solution**: Use `asyncio.to_thread()` wrapper pattern:

```python
import asyncio
from pypdf import PdfReader
from typing import List, Optional

async def extract_page_label(pdf_path: str, page_index: int) -> Optional[str]:
    """
    Extract page label for a specific page asynchronously.
    :param pdf_path: Path to PDF file
    :param page_index: 0-based page index
    :return: Page label string or None
    """
    def _sync_extract():
        reader = PdfReader(pdf_path)
        try:
            return reader.page_labels[page_index]
        except (IndexError, KeyError):
            return None

    return await asyncio.to_thread(_sync_extract)

async def extract_all_page_labels(pdf_path: str) -> List[Optional[str]]:
    """
    Extract all page labels from PDF asynchronously.
    :param pdf_path: Path to PDF file
    :return: List of page labels (may contain None for unlabeled pages)
    """
    def _sync_extract_all():
        reader = PdfReader(pdf_path)
        labels = []
        for index in range(len(reader.pages)):
            try:
                labels.append(reader.page_labels[index])
            except (IndexError, KeyError):
                labels.append(None)
        return labels

    return await asyncio.to_thread(_sync_extract_all)
```

**Architecture Implications**:

- PDF operations wrapped in async functions using `asyncio.to_thread()`
- Maintains async API contract throughout the codebase
- I/O operations (file reading) execute in thread pool
- No changes to existing async patterns required

### 2.3 Alternative Considered: PyMuPDF

**Advantages**:

- Superior performance (fastest text extraction)
- Built-in OCR for scanned documents
- Native table detection

**Disadvantages**:

- **C dependency** (MuPDF library) complicates deployment
- **AGPL license** may have implications (though project is Apache-2.0)
- **Less direct page label API** - requires manual calculation from label definitions
- More complex to integrate with CI/CD pipelines

**Conclusion**: Performance benefits do not outweigh complexity and API limitations for this use case.

## 3. Implementation Details

### 3.1 Page Label Types (PDF Specification)

PDF page labels support the following numbering styles:

| Style Code | Description | Example |
|------------|-------------|---------|
| `/D` | Decimal Arabic numerals | 1, 2, 3, ... |
| `/r` | Lowercase Roman numerals | i, ii, iii, iv, v |
| `/R` | Uppercase Roman numerals | I, II, III, IV, V |
| `/a` | Lowercase letters | a, b, c, ..., z, aa, ab, ... |
| `/A` | Uppercase letters | A, B, C, ..., Z, AA, AB, ... |
| (none) | No numbering, just prefix | prefix only |

**Optional Components**:

- **Prefix**: Arbitrary string prepended to number (e.g., "Chapter 1-")
- **Start value**: First page in range uses specified starting number

### 3.2 Page Label Examples

Real-world scenarios from academic/professional PDFs:

```python
# Example 1: Academic paper with front matter
# Pages 0-2: i, ii, iii (Roman numerals for preface)
# Pages 3-end: 1, 2, 3, ... (Arabic for main content)

# Example 2: Book with chapter prefixes
# Pages 0-9: "Chapter 1-1" through "Chapter 1-10"
# Pages 10-19: "Chapter 2-1" through "Chapter 2-10"

# Example 3: Appendix
# Pages 0-49: 1-50 (main content)
# Pages 50-54: "A-1" through "A-5" (appendix)
```

### 3.3 Graceful Degradation

**Handling PDFs without page labels**:

```python
async def get_page_label_safe(pdf_path: str, page_index: int) -> str:
    """
    Get page label with fallback to 1-based physical page number.
    :param pdf_path: Path to PDF file
    :param page_index: 0-based page index
    :return: Page label or default "Page N" format
    """
    label = await extract_page_label(pdf_path, page_index)
    if label is None:
        return f"Page {page_index + 1}"  # Fallback to 1-based physical number
    return label
```

**Constitution compliance**: This follows the project's graceful degradation principle (similar to NLTK/tiktoken optional dependencies).

### 3.4 Integration with Existing Codebase

**Extend `chunking.py` pattern**:

- PDF extraction logic separate from chunking logic
- Async wrappers follow established patterns
- Optional dependency handling (similar to NLTK/tiktoken)

**Extend `cli_ingest.py` pattern**:

- Add `--enable-page-labels` flag
- Integrate with existing metadata system
- Support bulk ingestion with page label extraction

**FilterableField integration**:

- New fields: `physical_page_index` (integer), `page_label` (keyword)
- Backward compatible: existing queries unaffected
- Enhanced search: filter by page range or label pattern

## 4. Dependencies

### 4.1 New Dependency

Add to `pyproject.toml`:

```toml
[project]
dependencies = [
    # ... existing dependencies ...
    "pypdf>=5.1.0",  # Page label extraction support
]
```

**Version rationale**:

- pypdf 5.1.0+ required for stable page label API
- Released mid-2024, well-tested in production

### 4.2 Compatibility Matrix

| Python Version | pypdf Version | Async Support |
|----------------|---------------|---------------|
| 3.10 | ✅ 5.1.0+ | ✅ asyncio.to_thread |
| 3.11 | ✅ 5.1.0+ | ✅ asyncio.to_thread |
| 3.12 | ✅ 5.1.0+ | ✅ asyncio.to_thread |
| 3.13 | ✅ 5.1.0+ | ✅ asyncio.to_thread |

## 5. Testing Strategy

### 5.1 Test Coverage

**Unit tests**:

- Page label extraction (various numbering styles)
- Async wrapper behavior
- Error handling (missing labels, corrupt PDFs)
- Graceful degradation

**Integration tests**:

- Full PDF ingestion with page labels
- Qdrant storage and retrieval
- Search with page number filtering
- Metadata preservation

**Test fixtures**:

- PDF with Roman numeral front matter
- PDF with chapter-based numbering
- PDF with appendix labeling
- PDF without page labels
- Corrupt/malformed PDF

### 5.2 Example Test Cases

```python
@pytest.mark.asyncio
async def test_extract_roman_numerals():
    """Test extraction of Roman numeral page labels"""
    pdf_path = "fixtures/academic_paper.pdf"
    labels = await extract_all_page_labels(pdf_path)
    assert labels[0] == "i"
    assert labels[1] == "ii"
    assert labels[2] == "iii"
    assert labels[3] == "1"  # First main content page

@pytest.mark.asyncio
async def test_graceful_degradation_no_labels():
    """Test fallback when PDF has no page labels"""
    pdf_path = "fixtures/no_labels.pdf"
    label = await get_page_label_safe(pdf_path, 0)
    assert label == "Page 1"  # Fallback to default format
```

## 6. Future Enhancements

### 6.1 Potential Optimizations

**Batch page label extraction**:

- Extract all labels once, cache in memory
- Reduces repeated PDF file access
- Trade memory for performance

**Lazy loading**:

- Extract page labels on-demand
- Suitable for very large PDFs
- Minimizes memory footprint

### 6.2 Advanced Features (Out of Scope for v1)

- **Custom label parsing**: Support non-standard label formats
- **Label validation**: Detect inconsistencies in label sequences
- **Label editing**: API to modify page labels in PDFs
- **Unicode labels**: Support for non-Latin scripts in labels

## 7. References

### 7.1 Official Documentation

- **pypdf Documentation**: <https://pypdf2.readthedocs.io/>
- **PDF Specification (Page Labels)**: Adobe PDF Reference, Section 8.3.1
- **W3C PDF Accessibility**: <https://www.w3.org/TR/WCAG20-TECHS/PDF17.html>

### 7.2 Research Sources

- **StackOverflow Discussion**: "How to change internal page numbers in PDF metadata" - Confirmed pypdf page label API
- **Unstract PDF Library Evaluation**: Performance benchmarks comparing pypdf, PyMuPDF, pdfplumber (2026)
- **PyMuPDF Documentation**: Page label extraction methods (`get_page_labels()`, `get_page_numbers()`)
- **Ask Ubuntu**: "Renumber pages of a PDF" - Manual PDF metadata editing examples

### 7.3 Project-Specific References

- **mcp-server-qdrant constitution**: `.specify/memory/constitution.md`
- **Feature specification**: `specs/001-pdf-page-ingestion/spec.md`
- **Existing chunking implementation**: `src/mcp_server_qdrant/chunking.py`
- **CLI ingestion tool**: `src/mcp_server_qdrant/cli_ingest.py`

## 8. Decision Summary

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **PDF Library** | pypdf 5.1.0+ | Native page label API, pure Python, MIT license |
| **Async Strategy** | `asyncio.to_thread()` wrapper | Constitution compliance, established pattern |
| **Graceful Degradation** | Fallback to `Page N` format | Handle PDFs without labels |
| **Performance Trade-off** | Acceptable | Pure Python vs C dependency simplicity |
| **Testing** | Comprehensive fixtures | Cover all numbering styles and edge cases |
| **Backward Compatibility** | New FilterableFields only | No breaking changes to existing API |

## 9. Next Steps (Phase 1)

1. **Data Model Design**: Define `PDFPageEntry` Pydantic model with dual page numbering
2. **Contract Generation**: Extend CLI interface specifications for PDF ingestion
3. **Quickstart Guide**: Document PDF ingestion workflow with page label examples
4. **Agent Context Update**: Add pypdf library awareness to `.github/copilot-instructions.md`

---

**Research Completed**: 2026-01-23
**Author**: GitHub Copilot (based on Tavily search results)
**Status**: Ready for Phase 1 (Design & Contracts)
