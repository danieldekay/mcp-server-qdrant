"""
Document chunking strategies for RAG.

Provides intelligent text splitting for better retrieval performance
with large documents.

Source: https://github.com/mahmoudimus/mcp-server-qdrant
Commit: 5af3f72f1afd1afa8dce39976cd29191ddb69887
Author: Mahmoud Rusty Abdelkader (@mahmoudimus)
License: Apache-2.0
"""

import logging
import re
from enum import Enum
from typing import List

logger = logging.getLogger(__name__)

# Try to import nltk, but make it optional
try:
    import nltk
    from nltk.tokenize import sent_tokenize

    NLTK_AVAILABLE = True
    # Download punkt tokenizer if not available
    try:
        nltk.data.find("tokenizers/punkt")
    except LookupError:
        logger.info("Downloading NLTK punkt tokenizer...")
        nltk.download("punkt", quiet=True)
except ImportError:
    NLTK_AVAILABLE = False
    logger.warning(
        "NLTK not available. Sentence chunking will use basic regex splitting."
    )

# Try to import tiktoken, but make it optional
try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.warning("Tiktoken not available. Using character-based chunking.")


class ChunkStrategy(Enum):
    """Chunking strategies for document splitting."""

    SEMANTIC = "semantic"
    SENTENCE = "sentence"
    FIXED = "fixed"


class DocumentChunker:
    """
    Handles document chunking using various strategies.
    """

    def __init__(
        self,
        strategy: ChunkStrategy = ChunkStrategy.SEMANTIC,
        max_chunk_size: int = 512,
        chunk_overlap: int = 50,
        encoding_name: str = "cl100k_base",
    ):
        """
        Initialize the document chunker.
        :param strategy: Chunking strategy to use
        :param max_chunk_size: Maximum size of each chunk (in tokens or characters)
        :param chunk_overlap: Overlap between chunks
        :param encoding_name: Tiktoken encoding name for token counting
        """
        self.strategy = strategy
        self.max_chunk_size = max_chunk_size
        self.chunk_overlap = chunk_overlap

        # Initialize tokenizer if available
        if TIKTOKEN_AVAILABLE:
            try:
                self.tokenizer = tiktoken.get_encoding(encoding_name)
            except Exception as e:
                logger.warning(f"Failed to load tiktoken encoding: {e}")
                self.tokenizer = None
        else:
            self.tokenizer = None

    def chunk_text(self, text: str) -> List[str]:
        """
        Split text into chunks based on the selected strategy.
        :param text: Text to chunk
        :return: List of text chunks
        """
        if not text or not text.strip():
            return []

        if self.strategy == ChunkStrategy.SEMANTIC:
            return self._semantic_chunking(text)
        elif self.strategy == ChunkStrategy.SENTENCE:
            return self._sentence_chunking(text)
        else:  # FIXED
            return self._fixed_chunking(text)

    def _count_tokens(self, text: str) -> int:
        """
        Count tokens in text.
        :param text: Text to count
        :return: Token count
        """
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        else:
            # Fallback to approximate character-based counting
            return len(text)

    def _semantic_chunking(self, text: str) -> List[str]:
        """
        Split text at natural boundaries (paragraphs, sentences).
        :param text: Text to chunk
        :return: List of chunks
        """
        chunks = []

        # First split by paragraphs
        paragraphs = re.split(r"\n\s*\n", text)

        current_chunk = ""
        current_size = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Split paragraph into sentences if needed
            sentences = self._split_sentences(para)

            for sentence in sentences:
                sentence_size = self._count_tokens(sentence)

                # If adding this sentence would exceed max size
                if current_size + sentence_size > self.max_chunk_size and current_chunk:
                    chunks.append(current_chunk.strip())
                    # Start new chunk with overlap from end of previous chunk
                    overlap_text = self._get_overlap_text(current_chunk)
                    current_chunk = (
                        overlap_text + " " + sentence if overlap_text else sentence
                    )
                    current_size = self._count_tokens(current_chunk)
                else:
                    current_chunk += (" " if current_chunk else "") + sentence
                    current_size += sentence_size

        # Add remaining chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def _sentence_chunking(self, text: str) -> List[str]:
        """
        Split text at sentence boundaries only.
        :param text: Text to chunk
        :return: List of chunks
        """
        sentences = self._split_sentences(text)
        chunks = []
        current_chunk = ""
        current_size = 0

        for sentence in sentences:
            sentence_size = self._count_tokens(sentence)

            if current_size + sentence_size > self.max_chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                overlap_text = self._get_overlap_text(current_chunk)
                current_chunk = (
                    overlap_text + " " + sentence if overlap_text else sentence
                )
                current_size = self._count_tokens(current_chunk)
            else:
                current_chunk += (" " if current_chunk else "") + sentence
                current_size += sentence_size

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def _fixed_chunking(self, text: str) -> List[str]:
        """
        Split text at fixed token/character boundaries.
        :param text: Text to chunk
        :return: List of chunks
        """
        if self.tokenizer:
            # Token-based chunking
            tokens = self.tokenizer.encode(text)
            chunks = []

            start = 0
            while start < len(tokens):
                end = start + self.max_chunk_size
                chunk_tokens = tokens[start:end]
                chunk_text = self.tokenizer.decode(chunk_tokens)
                chunks.append(chunk_text)
                start += self.max_chunk_size - self.chunk_overlap

            return chunks
        else:
            # Character-based chunking
            chunks = []
            start = 0
            text_len = len(text)

            while start < text_len:
                end = start + self.max_chunk_size
                chunk = text[start:end]
                chunks.append(chunk)
                start += self.max_chunk_size - self.chunk_overlap

            return chunks

    def _split_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences.
        :param text: Text to split
        :return: List of sentences
        """
        if NLTK_AVAILABLE:
            try:
                return sent_tokenize(text)
            except Exception as e:
                logger.warning(f"NLTK sentence tokenization failed: {e}")

        # Fallback to regex-based sentence splitting
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    def _get_overlap_text(self, text: str) -> str:
        """
        Get overlap text from end of chunk.
        :param text: Text to extract overlap from
        :return: Overlap text
        """
        if self.chunk_overlap <= 0:
            return ""

        # Split into sentences and take last few to fill overlap
        sentences = self._split_sentences(text)
        overlap_text = ""
        overlap_size = 0

        for sentence in reversed(sentences):
            sentence_size = self._count_tokens(sentence)
            if overlap_size + sentence_size <= self.chunk_overlap:
                overlap_text = sentence + (" " + overlap_text if overlap_text else "")
                overlap_size += sentence_size
            else:
                break

        return overlap_text.strip()
