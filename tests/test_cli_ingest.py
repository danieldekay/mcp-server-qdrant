"""Tests for CLI document ingestion."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from mcp_server_qdrant.cli_ingest import find_files, ingest_file, SUPPORTED_EXTENSIONS


class TestFindFiles:
    """Test file discovery."""

    def test_find_single_file(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("print('hello')")
        files = find_files(f)
        assert files == [f]

    def test_single_unsupported_file(self, tmp_path):
        f = tmp_path / "test.docx"
        f.write_text("fake docx")
        files = find_files(f)
        assert files == []

    def test_find_in_directory(self, tmp_path):
        (tmp_path / "a.py").write_text("code")
        (tmp_path / "b.md").write_text("docs")
        (tmp_path / "c.jpg").write_text("image")  # unsupported
        files = find_files(tmp_path)
        extensions = {f.suffix for f in files}
        assert ".py" in extensions
        assert ".md" in extensions
        assert ".jpg" not in extensions

    def test_recursive_discovery(self, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "deep.py").write_text("code")
        files = find_files(tmp_path)
        assert any(f.name == "deep.py" for f in files)

    def test_include_pattern(self, tmp_path):
        (tmp_path / "keep.py").write_text("code")
        (tmp_path / "skip.md").write_text("docs")
        files = find_files(tmp_path, include_pattern=r"\.py$")
        assert all(f.suffix == ".py" for f in files)

    def test_exclude_pattern(self, tmp_path):
        (tmp_path / "keep.py").write_text("code")
        (tmp_path / "skip.py").write_text("skip")
        files = find_files(tmp_path, exclude_pattern=r"skip")
        assert all("skip" not in f.name for f in files)

    def test_invalid_include_regex_returns_empty(self, tmp_path):
        (tmp_path / "test.py").write_text("code")
        files = find_files(tmp_path, include_pattern=r"[invalid")
        assert files == []

    def test_invalid_exclude_regex_returns_empty(self, tmp_path):
        (tmp_path / "test.py").write_text("code")
        files = find_files(tmp_path, exclude_pattern=r"[invalid")
        assert files == []

    def test_empty_directory(self, tmp_path):
        files = find_files(tmp_path)
        assert files == []

    def test_supported_extensions_includes_common_types(self):
        for ext in [".py", ".md", ".json", ".pdf", ".txt", ".yaml"]:
            assert ext in SUPPORTED_EXTENSIONS


class TestIngestFile:
    """Test single file ingestion."""

    @pytest.mark.asyncio
    async def test_ingest_text_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("Hello World")

        connector = AsyncMock()
        connector.upsert_document_entries.return_value = {
            "mode": "created",
            "stored": 1,
            "updated": 0,
            "deleted": 0,
        }
        result = await ingest_file(f, connector, "test_collection", {})
        assert result is True
        connector.upsert_document_entries.assert_called_once()

    @pytest.mark.asyncio
    async def test_ingest_empty_file_returns_false(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("")

        connector = AsyncMock()
        result = await ingest_file(f, connector, "test_collection", {})
        assert result is False
        connector.upsert_document_entries.assert_not_called()

    @pytest.mark.asyncio
    async def test_ingest_whitespace_file_returns_false(self, tmp_path):
        f = tmp_path / "blank.txt"
        f.write_text("   \n\t  ")

        connector = AsyncMock()
        result = await ingest_file(f, connector, "test_collection", {})
        assert result is False

    @pytest.mark.asyncio
    async def test_ingest_file_with_metadata(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("print('hello')")

        connector = AsyncMock()
        connector.upsert_document_entries.return_value = {
            "mode": "created",
            "stored": 1,
            "updated": 0,
            "deleted": 0,
        }
        metadata = {"doc_type": "code", "knowledge_base": "test"}
        result = await ingest_file(f, connector, "test_collection", metadata)
        assert result is True

        # Check metadata passed
        call_args = connector.upsert_document_entries.call_args
        entry = call_args[0][0][0]
        assert entry.metadata["doc_type"] == "code"
        assert call_args.kwargs["document_id"] == "test.py"

    @pytest.mark.asyncio
    async def test_ingest_file_store_error(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("content")

        connector = AsyncMock()
        connector.upsert_document_entries.side_effect = Exception("Connection failed")
        result = await ingest_file(f, connector, "test_collection", {})
        assert result is False
