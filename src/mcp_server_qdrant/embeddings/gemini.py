import os
from typing import Optional

try:
    import google.generativeai as genai

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from mcp_server_qdrant.embeddings.base import EmbeddingProvider


class GeminiProvider(EmbeddingProvider):
    """
    Google Gemini implementation of the embedding provider.
    :param model_name: The Gemini embedding model name.
    :param api_key: Google API key. Falls back to GOOGLE_API_KEY env var.
    """

    _MODEL_DIMENSIONS = {
        "models/embedding-001": 768,
        "models/text-embedding-004": 768,
    }

    def __init__(self, model_name: str, api_key: Optional[str] = None):
        if not GEMINI_AVAILABLE:
            raise ImportError(
                "google-generativeai is not installed. "
                "Install with: pip install google-generativeai"
            )

        self.model_name = model_name
        resolved_key = api_key or os.getenv("GOOGLE_API_KEY")

        if not resolved_key:
            raise ValueError(
                "Google API key is required. Provide it as a parameter "
                "or set GOOGLE_API_KEY environment variable."
            )

        genai.configure(api_key=resolved_key)

        # Normalize model name for dimension lookup
        lookup_name = model_name
        if not model_name.startswith("models/"):
            lookup_name = f"models/{model_name}"

        if lookup_name not in self._MODEL_DIMENSIONS:
            raise ValueError(
                f"Unsupported Gemini embedding model: {model_name}. "
                f"Supported: {list(self._MODEL_DIMENSIONS.keys())}"
            )
        self._lookup_name = lookup_name

    async def embed_documents(self, documents: list[str]) -> list[list[float]]:
        """Embed a list of documents into vectors."""
        import asyncio

        def _embed():
            result = genai.embed_content(
                model=self._lookup_name,
                content=documents,
                task_type="retrieval_document",
            )
            return result["embedding"]

        return await asyncio.to_thread(_embed)

    async def embed_query(self, query: str) -> list[float]:
        """Embed a query into a vector."""
        import asyncio

        def _embed():
            result = genai.embed_content(
                model=self._lookup_name,
                content=query,
                task_type="retrieval_query",
            )
            return result["embedding"]

        return await asyncio.to_thread(_embed)

    def get_vector_name(self) -> str:
        """Get the name of the vector for the Qdrant collection."""
        return ""

    def get_vector_size(self) -> int:
        """Get the size of the vector for the Qdrant collection."""
        return self._MODEL_DIMENSIONS[self._lookup_name]
