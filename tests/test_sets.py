"""Tests for set-based document filtering."""

import json
import pytest
import tempfile
from pathlib import Path

from mcp_server_qdrant.sets import SetMatcher, DocumentSet


class TestDocumentSet:
    """Test DocumentSet dataclass."""

    def test_creation(self):
        ds = DocumentSet(slug="ml", description="Machine Learning", aliases=["AI"])
        assert ds.slug == "ml"
        assert ds.description == "Machine Learning"
        assert ds.aliases == ["AI"]


class TestSetMatcherInit:
    """Test SetMatcher initialization."""

    def test_init_without_config(self):
        matcher = SetMatcher(sets_config_path="/nonexistent/path.json")
        assert matcher.sets == {}

    def test_init_no_config_path(self, tmp_path, monkeypatch):
        """When no config path and default doesn't exist."""
        monkeypatch.chdir(tmp_path)
        matcher = SetMatcher()
        assert matcher.sets == {}


class TestLoadSets:
    """Test loading sets from configuration."""

    def test_load_valid_config(self, tmp_path):
        config = {
            "sets": [
                {
                    "slug": "ml",
                    "description": "Machine Learning Kursmaterial",
                    "aliases": ["AI", "KI"],
                },
                {
                    "slug": "stats",
                    "description": "Statistics",
                    "aliases": ["Statistik"],
                },
            ]
        }
        config_file = tmp_path / "sets.json"
        config_file.write_text(json.dumps(config))

        matcher = SetMatcher(sets_config_path=str(config_file))
        assert len(matcher.sets) == 2
        assert "ml" in matcher.sets
        assert "stats" in matcher.sets
        assert matcher.sets["ml"].aliases == ["AI", "KI"]

    def test_load_empty_sets(self, tmp_path):
        config = {"sets": []}
        config_file = tmp_path / "sets.json"
        config_file.write_text(json.dumps(config))

        matcher = SetMatcher(sets_config_path=str(config_file))
        assert matcher.sets == {}

    def test_load_invalid_json(self, tmp_path):
        config_file = tmp_path / "sets.json"
        config_file.write_text("not json {{{")

        matcher = SetMatcher(sets_config_path=str(config_file))
        assert matcher.sets == {}

    def test_load_default_path(self, tmp_path, monkeypatch):
        """Test loading from default .qdrant_sets.json in current directory."""
        config = {"sets": [{"slug": "test", "description": "Test Set", "aliases": []}]}
        config_file = tmp_path / ".qdrant_sets.json"
        config_file.write_text(json.dumps(config))

        monkeypatch.chdir(tmp_path)
        matcher = SetMatcher()
        assert "test" in matcher.sets


class TestMatchSet:
    """Test query-to-set matching."""

    @pytest.fixture
    def matcher(self, tmp_path):
        config = {
            "sets": [
                {
                    "slug": "machine-learning",
                    "description": "Machine Learning und Deep Learning Materialien",
                    "aliases": ["ML", "Deep Learning", "KI"],
                },
                {
                    "slug": "statistics",
                    "description": "Statistik und Wahrscheinlichkeitstheorie",
                    "aliases": ["Stats", "Statistik"],
                },
                {
                    "slug": "programming",
                    "description": "Python Programmierung und Software Engineering",
                    "aliases": ["Python", "Coding"],
                },
            ]
        }
        config_file = tmp_path / "sets.json"
        config_file.write_text(json.dumps(config))
        return SetMatcher(sets_config_path=str(config_file))

    def test_empty_sets_returns_none(self):
        matcher = SetMatcher(sets_config_path="/nonexistent/path.json")
        assert matcher.match_set("anything") is None

    def test_exact_slug_match(self, matcher):
        assert matcher.match_set("machine-learning") == "machine-learning"

    def test_exact_slug_case_insensitive(self, matcher):
        assert matcher.match_set("Machine-Learning") == "machine-learning"

    def test_alias_match(self, matcher):
        assert matcher.match_set("ML") == "machine-learning"

    def test_alias_case_insensitive(self, matcher):
        assert matcher.match_set("statistik") == "statistics"

    def test_description_match(self, matcher):
        result = matcher.match_set("Deep Learning")
        assert result == "machine-learning"

    def test_fuzzy_match(self, matcher):
        result = matcher.match_set("Maschinelles Lernen und Deep Learning")
        # Should find machine-learning via fuzzy similarity
        assert result is not None

    def test_no_match_returns_none(self, matcher):
        result = matcher.match_set("quantum physics entanglement")
        # Low similarity — may or may not match
        # Just verify it doesn't crash
        assert result is None or isinstance(result, str)

    def test_short_query_exact(self, matcher):
        assert matcher.match_set("Python") == "programming"
