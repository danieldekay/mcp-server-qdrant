"""
Tests for score field in search results (M2).

Validates that the Entry model carries scores and formatters render them.
"""

import uuid

import pytest

from mcp_server_qdrant.constants import PDFMetadataKeys
from mcp_server_qdrant.embeddings.fastembed import FastEmbedProvider
from mcp_server_qdrant.formatters import (
    JSONEntryFormatter,
    MarkdownEntryFormatter,
    PlainTextEntryFormatter,
    XMLEntryFormatter,
)
from mcp_server_qdrant.qdrant import Entry, QdrantConnector


class TestScoreInEntry:
    """Tests for the score field on Entry model."""

    def test_entry_default_score_is_none(self):
        entry = Entry(content="hello")
        assert entry.score is None

    def test_entry_accepts_score(self):
        entry = Entry(content="hello", score=0.95)
        assert entry.score == 0.95


class TestScoreInFormatters:
    """Tests that formatters render score when present."""

    @pytest.fixture
    def scored_entry(self):
        return Entry(
            content="test content",
            metadata={"source": "test"},
            score=0.873,
        )

    @pytest.fixture
    def scored_pdf_entry(self):
        return Entry(
            content="PDF content",
            metadata={
                PDFMetadataKeys.DOCUMENT_ID: "doc.pdf",
                PDFMetadataKeys.PAGE_LABEL: "42",
                PDFMetadataKeys.PHYSICAL_PAGE_INDEX: 41,
            },
            score=0.912,
        )

    @pytest.fixture
    def unscored_entry(self):
        return Entry(content="no score", metadata={})

    def test_xml_formatter_includes_score(self, scored_entry):
        result = XMLEntryFormatter().format(scored_entry)
        assert 'score="0.873"' in result

    def test_xml_formatter_no_score_when_none(self, unscored_entry):
        result = XMLEntryFormatter().format(unscored_entry)
        assert "score=" not in result

    def test_xml_formatter_pdf_with_score(self, scored_pdf_entry):
        result = XMLEntryFormatter().format(scored_pdf_entry)
        assert 'score="0.912"' in result
        assert "Document: doc.pdf" in result

    def test_json_formatter_includes_score(self, scored_entry):
        import json

        result = json.loads(JSONEntryFormatter().format(scored_entry))
        assert result["score"] == 0.873

    def test_json_formatter_no_score_when_none(self, unscored_entry):
        import json

        result = json.loads(JSONEntryFormatter().format(unscored_entry))
        assert "score" not in result

    def test_plain_text_formatter_includes_score(self, scored_entry):
        result = PlainTextEntryFormatter().format(scored_entry)
        assert "[score: 0.873]" in result

    def test_markdown_formatter_includes_score(self, scored_entry):
        result = MarkdownEntryFormatter().format(scored_entry)
        assert "(score: 0.873)" in result


class TestScoreFromQdrantSearch:
    """Integration test: score populated from actual Qdrant search."""

    @pytest.fixture
    async def embedding_provider(self):
        return FastEmbedProvider(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )

    @pytest.fixture
    async def connector(self, embedding_provider):
        collection = f"test_score_{uuid.uuid4().hex}"
        connector = QdrantConnector(
            qdrant_url=":memory:",
            qdrant_api_key=None,
            collection_name=collection,
            embedding_provider=embedding_provider,
        )
        yield connector

    @pytest.mark.asyncio
    async def test_search_results_have_scores(self, connector):
        await connector.store(
            Entry(content="Machine learning is a subset of AI")
        )
        results = await connector.search("artificial intelligence")
        assert len(results) == 1
        assert results[0].score is not None
        assert 0.0 <= results[0].score <= 1.0
