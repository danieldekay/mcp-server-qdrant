"""Tests for document chunking strategies."""

import pytest
from unittest.mock import patch, MagicMock

from mcp_server_qdrant.chunking import DocumentChunker, ChunkStrategy


class TestChunkStrategyEnum:
    """Test ChunkStrategy enum values."""

    def test_semantic_value(self):
        assert ChunkStrategy.SEMANTIC.value == "semantic"

    def test_sentence_value(self):
        assert ChunkStrategy.SENTENCE.value == "sentence"

    def test_fixed_value(self):
        assert ChunkStrategy.FIXED.value == "fixed"


class TestDocumentChunkerInit:
    """Test DocumentChunker initialization."""

    def test_default_init(self):
        chunker = DocumentChunker()
        assert chunker.strategy == ChunkStrategy.SEMANTIC
        assert chunker.max_chunk_size == 512
        assert chunker.chunk_overlap == 50

    def test_custom_init(self):
        chunker = DocumentChunker(
            strategy=ChunkStrategy.FIXED,
            max_chunk_size=256,
            chunk_overlap=25,
        )
        assert chunker.strategy == ChunkStrategy.FIXED
        assert chunker.max_chunk_size == 256
        assert chunker.chunk_overlap == 25


class TestChunkTextDispatch:
    """Test chunk_text routing to correct strategy."""

    def test_empty_text_returns_empty_list(self):
        chunker = DocumentChunker()
        assert chunker.chunk_text("") == []

    def test_whitespace_only_returns_empty_list(self):
        chunker = DocumentChunker()
        assert chunker.chunk_text("   \n\t  ") == []

    def test_none_text_returns_empty_list(self):
        chunker = DocumentChunker()
        assert chunker.chunk_text(None) == []


class TestSemanticChunking:
    """Test semantic chunking strategy."""

    def test_short_text_single_chunk(self):
        chunker = DocumentChunker(strategy=ChunkStrategy.SEMANTIC, max_chunk_size=1000)
        text = "This is a short sentence. Another one."
        chunks = chunker.chunk_text(text)
        assert len(chunks) == 1
        assert "short sentence" in chunks[0]

    def test_paragraph_splitting(self):
        chunker = DocumentChunker(
            strategy=ChunkStrategy.SEMANTIC,
            max_chunk_size=20,
            chunk_overlap=0,
        )
        text = (
            "First paragraph with some extended content for testing purposes.\n\n"
            "Second paragraph with entirely different and longer content for the test."
        )
        chunks = chunker.chunk_text(text)
        assert len(chunks) >= 2

    def test_long_text_produces_multiple_chunks(self):
        chunker = DocumentChunker(
            strategy=ChunkStrategy.SEMANTIC,
            max_chunk_size=10,
            chunk_overlap=0,
        )
        text = "Sentence one is here. Sentence two is here. Sentence three is here. Sentence four is here."
        chunks = chunker.chunk_text(text)
        assert len(chunks) >= 2

    def test_overlap_included(self):
        chunker = DocumentChunker(
            strategy=ChunkStrategy.SEMANTIC,
            max_chunk_size=8,
            chunk_overlap=4,
        )
        text = "First sentence here. Second sentence here. Third sentence here. Fourth sentence here."
        chunks = chunker.chunk_text(text)
        if len(chunks) >= 2:
            # With overlap, later chunks may contain text from previous chunks
            all_text = " ".join(chunks)
            assert "First" in all_text
            assert "Fourth" in all_text


class TestSentenceChunking:
    """Test sentence chunking strategy."""

    def test_short_text_single_chunk(self):
        chunker = DocumentChunker(strategy=ChunkStrategy.SENTENCE, max_chunk_size=1000)
        text = "Hello world. This is a test."
        chunks = chunker.chunk_text(text)
        assert len(chunks) == 1

    def test_sentence_boundaries(self):
        chunker = DocumentChunker(
            strategy=ChunkStrategy.SENTENCE,
            max_chunk_size=8,
            chunk_overlap=0,
        )
        text = "First sentence here. Second sentence here. Third sentence here. Fourth sentence here."
        chunks = chunker.chunk_text(text)
        assert len(chunks) >= 2

    def test_all_content_preserved(self):
        chunker = DocumentChunker(
            strategy=ChunkStrategy.SENTENCE,
            max_chunk_size=8,
            chunk_overlap=0,
        )
        text = "Alpha sentence. Beta sentence. Gamma sentence."
        chunks = chunker.chunk_text(text)
        all_text = " ".join(chunks)
        assert "Alpha" in all_text
        assert "Beta" in all_text
        assert "Gamma" in all_text


class TestFixedChunking:
    """Test fixed-size chunking strategy."""

    def test_short_text_single_chunk(self):
        chunker = DocumentChunker(strategy=ChunkStrategy.FIXED, max_chunk_size=1000)
        text = "Small text"
        chunks = chunker.chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0] == "Small text"

    def test_character_based_splitting(self):
        """Test character-based chunking when tiktoken is not available."""
        chunker = DocumentChunker(
            strategy=ChunkStrategy.FIXED,
            max_chunk_size=10,
            chunk_overlap=0,
        )
        chunker.tokenizer = None  # Force character-based
        text = "ABCDEFGHIJ" * 3  # 30 characters
        chunks = chunker.chunk_text(text)
        assert len(chunks) == 3
        assert all(len(c) == 10 for c in chunks)

    def test_character_based_with_overlap(self):
        chunker = DocumentChunker(
            strategy=ChunkStrategy.FIXED,
            max_chunk_size=10,
            chunk_overlap=3,
        )
        chunker.tokenizer = None  # Force character-based
        text = "ABCDEFGHIJKLMNOPQRST"  # 20 chars
        chunks = chunker.chunk_text(text)
        # stride = 10 - 3 = 7, so chunks start at 0, 7, 14
        assert len(chunks) == 3
        assert chunks[0] == "ABCDEFGHIJ"
        assert chunks[1] == "HIJKLMNOPQ"

    def test_token_based_splitting(self):
        """Test with tiktoken if available."""
        chunker = DocumentChunker(
            strategy=ChunkStrategy.FIXED,
            max_chunk_size=5,
            chunk_overlap=0,
        )
        if chunker.tokenizer is not None:
            text = "This is a test sentence with multiple words for token chunking."
            chunks = chunker.chunk_text(text)
            assert len(chunks) >= 2


class TestSplitSentences:
    """Test sentence splitting helper."""

    def test_basic_splitting(self):
        chunker = DocumentChunker()
        sentences = chunker._split_sentences("Hello world. How are you? I am fine!")
        assert len(sentences) >= 3

    def test_empty_text(self):
        chunker = DocumentChunker()
        sentences = chunker._split_sentences("")
        assert sentences == [] or sentences == [""]

    def test_no_punctuation(self):
        chunker = DocumentChunker()
        sentences = chunker._split_sentences("No punctuation here")
        assert len(sentences) >= 1
        assert "No punctuation" in sentences[0]


class TestGetOverlapText:
    """Test overlap text extraction."""

    def test_zero_overlap(self):
        chunker = DocumentChunker(chunk_overlap=0)
        result = chunker._get_overlap_text("Any text here.")
        assert result == ""

    def test_negative_overlap(self):
        chunker = DocumentChunker(chunk_overlap=-5)
        result = chunker._get_overlap_text("Any text here.")
        assert result == ""

    def test_with_overlap(self):
        chunker = DocumentChunker(chunk_overlap=100)
        text = "First sentence. Second sentence. Last sentence."
        result = chunker._get_overlap_text(text)
        assert len(result) > 0
        assert "sentence" in result


class TestCountTokens:
    """Test token counting."""

    def test_character_fallback(self):
        chunker = DocumentChunker()
        chunker.tokenizer = None  # Force character-based
        assert chunker._count_tokens("hello") == 5

    def test_with_tokenizer(self):
        chunker = DocumentChunker()
        if chunker.tokenizer is not None:
            count = chunker._count_tokens("Hello world")
            assert count > 0
