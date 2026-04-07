"""
Tests for M12: Index (Stichwortverzeichnis) detection and parsing.
Tests detect_index_start(), parse_index_entries(), build_page_to_terms_map().
"""

import pytest

from mcp_server_qdrant.pdf_extractor import PDFPageExtractor


class TestParseIndexEntries:
    """Test parsing of back-of-book index text."""

    def test_basic_index_entries(self):
        text = (
            "Machine Learning, 45, 67-72, 134\n"
            "Neural Networks, 23, 90-95\n"
            "Deep Learning, 100\n"
        )
        entries = PDFPageExtractor.parse_index_entries(text)

        assert "Machine Learning" in entries
        assert 45 in entries["Machine Learning"]
        assert (67, 72) in entries["Machine Learning"]
        assert 134 in entries["Machine Learning"]

        assert "Neural Networks" in entries
        assert 23 in entries["Neural Networks"]
        assert (90, 95) in entries["Neural Networks"]

        assert "Deep Learning" in entries
        assert 100 in entries["Deep Learning"]

    def test_german_index_entries(self):
        text = (
            "Kapazitätsplanung, 142, 156-160\n"
            "Qualitätsmanagement, 200, 215-220, 301\n"
        )
        entries = PDFPageExtractor.parse_index_entries(text)

        assert "Kapazitätsplanung" in entries
        assert 142 in entries["Kapazitätsplanung"]
        assert (156, 160) in entries["Kapazitätsplanung"]

        assert "Qualitätsmanagement" in entries
        assert len(entries["Qualitätsmanagement"]) == 3

    def test_en_dash_ranges(self):
        """Test that en-dash (–) and em-dash (—) ranges are recognized."""
        text = "Supply Chain, 45–50\nLogistics, 100—110\n"
        entries = PDFPageExtractor.parse_index_entries(text)

        assert "Supply Chain" in entries
        assert (45, 50) in entries["Supply Chain"]

        assert "Logistics" in entries
        assert (100, 110) in entries["Logistics"]

    def test_empty_text(self):
        entries = PDFPageExtractor.parse_index_entries("")
        assert entries == {}

    def test_no_index_entries(self):
        text = "This is just regular paragraph text without any index entries."
        entries = PDFPageExtractor.parse_index_entries(text)
        assert entries == {}

    def test_single_char_terms_skipped(self):
        """Terms shorter than 2 chars should be skipped."""
        text = "A, 5\nML, 10\n"
        entries = PDFPageExtractor.parse_index_entries(text)
        assert "A" not in entries
        assert "ML" in entries

    def test_numeric_only_terms_skipped(self):
        """Purely numeric terms should be skipped."""
        text = "123, 456\nValid Term, 789\n"
        entries = PDFPageExtractor.parse_index_entries(text)
        assert "123" not in entries
        assert "Valid Term" in entries


class TestBuildPageToTermsMap:
    """Test inverting index entries to page→terms mapping."""

    def test_basic_inversion(self):
        index_entries = {
            "Machine Learning": [45, (67, 69), 134],
            "Neural Networks": [45, 90],
        }
        page_map = PDFPageExtractor.build_page_to_terms_map(index_entries)

        assert "Machine Learning" in page_map[45]
        assert "Neural Networks" in page_map[45]
        assert "Machine Learning" in page_map[67]
        assert "Machine Learning" in page_map[68]
        assert "Machine Learning" in page_map[69]
        assert "Machine Learning" in page_map[134]
        assert "Neural Networks" in page_map[90]

    def test_empty_entries(self):
        page_map = PDFPageExtractor.build_page_to_terms_map({})
        assert page_map == {}

    def test_range_expansion(self):
        index_entries = {"Test": [(10, 13)]}
        page_map = PDFPageExtractor.build_page_to_terms_map(index_entries)
        assert page_map == {10: ["Test"], 11: ["Test"], 12: ["Test"], 13: ["Test"]}


class TestDetectIndexStart:
    """Test detection of back-of-book index start page."""

    def test_detect_via_outline(self):
        outline = [
            {"title": "Chapter 1", "page_index": 0, "level": 0},
            {"title": "Stichwortverzeichnis", "page_index": 50, "level": 0},
        ]
        result = PDFPageExtractor.detect_index_start(outline)
        assert result == 50

    def test_detect_via_outline_english(self):
        outline = [
            {"title": "Chapter 10", "page_index": 200, "level": 0},
            {"title": "Subject Index", "page_index": 250, "level": 0},
        ]
        result = PDFPageExtractor.detect_index_start(outline)
        assert result == 250

    def test_detect_via_outline_case_insensitive(self):
        outline = [
            {"title": "SACHREGISTER", "page_index": 100, "level": 0},
        ]
        result = PDFPageExtractor.detect_index_start(outline)
        assert result == 100

    def test_no_outline_no_pages(self):
        result = PDFPageExtractor.detect_index_start([])
        assert result is None

    def test_detect_via_heuristic(self):
        """Fallback: scan last pages for heading patterns."""
        pages_data = [
            ("Normal chapter content...", i, str(i + 1))
            for i in range(20)
        ]
        # Last page has index heading
        pages_data.append(("Stichwortverzeichnis\nMachine Learning, 45\n", 20, "21"))

        result = PDFPageExtractor.detect_index_start([], pages_data)
        assert result == 20

    def test_heuristic_only_scans_last_pages(self):
        """Index heading in early pages should NOT be detected as index start."""
        pages_data = [
            ("Index of figures\nSome content...", 0, "1"),
        ]
        # With 100 pages, page 0 should not be in scan range
        pages_data.extend(
            [("Normal content...", i, str(i + 1)) for i in range(1, 100)]
        )

        result = PDFPageExtractor.detect_index_start([], pages_data)
        # Page 0 is in the first pages, not the last 10%, so heuristic should not find it
        assert result is None
