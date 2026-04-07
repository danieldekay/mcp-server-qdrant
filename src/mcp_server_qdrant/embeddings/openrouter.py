import os
from typing import Optional

try:
    from openai import AsyncOpenAI
except ImportError:
    raise ImportError(
        "openai package not found. Install it with: pip install openai"
    )

from mcp_server_qdrant.embeddings.base import EmbeddingProvider

# OpenRouter proxies many providers; dimensions extracted from model descriptions
_KNOWN_DIMENSIONS: dict[str, int] = {
    "openai/text-embedding-3-small": 1536,
    "openai/text-embedding-3-large": 3072,
    "openai/text-embedding-ada-002": 1536,
    "google/gemini-embedding-001": 3072,
    "mistralai/mistral-embed-2312": 1024,
    "mistralai/codestral-embed-2505": 1024,
    "baai/bge-base-en-v1.5": 768,
    "baai/bge-large-en-v1.5": 1024,
    "baai/bge-m3": 1024,
    "intfloat/e5-base-v2": 768,
    "intfloat/e5-large-v2": 1024,
    "intfloat/multilingual-e5-large": 1024,
    "thenlper/gte-base": 768,
    "thenlper/gte-large": 1024,
    "sentence-transformers/all-MiniLM-L6-v2": 384,
    "sentence-transformers/all-MiniLM-L12-v2": 384,
    "sentence-transformers/all-mpnet-base-v2": 768,
    "sentence-transformers/multi-qa-mpnet-base-dot-v1": 768,
    "sentence-transformers/paraphrase-MiniLM-L6-v2": 384,
}

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider(EmbeddingProvider):
    """
    OpenRouter embedding provider. Uses the OpenAI-compatible API at
    https://openrouter.ai/api/v1/embeddings to access many embedding models
    from a single endpoint.

    :param model_name: Model ID on OpenRouter (e.g. "openai/text-embedding-3-small").
    :param api_key: OpenRouter API key. Falls back to OPENROUTER_API_KEY env var.
    :param dimensions: Override for vector dimensions. Falls back to
        OPENROUTER_EMBEDDING_DIMENSIONS env var, then built-in lookup table.
    """

    def __init__(
        self,
        model_name: str,
        api_key: Optional[str] = None,
        dimensions: Optional[int] = None,
    ):
        self.model_name = model_name

        resolved_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not resolved_key:
            raise ValueError(
                "OpenRouter API key is required. Provide it as a parameter "
                "or set OPENROUTER_API_KEY environment variable."
            )

        self.client = AsyncOpenAI(
            api_key=resolved_key,
            base_url=OPENROUTER_BASE_URL,
        )

        # Resolve dimensions: explicit param > env var > known table
        if dimensions is not None:
            self._dimensions = dimensions
        else:
            env_dims = os.getenv("OPENROUTER_EMBEDDING_DIMENSIONS")
            if env_dims is not None:
                self._dimensions = int(env_dims)
            elif model_name in _KNOWN_DIMENSIONS:
                self._dimensions = _KNOWN_DIMENSIONS[model_name]
            else:
                raise ValueError(
                    f"Unknown dimensions for OpenRouter model '{model_name}'. "
                    f"Set OPENROUTER_EMBEDDING_DIMENSIONS env var or use a known model: "
                    f"{sorted(_KNOWN_DIMENSIONS.keys())}"
                )

    async def embed_documents(self, documents: list[str]) -> list[list[float]]:
        response = await self.client.embeddings.create(
            input=documents,
            model=self.model_name,
        )
        return [item.embedding for item in response.data]

    async def embed_query(self, query: str) -> list[float]:
        response = await self.client.embeddings.create(
            input=[query],
            model=self.model_name,
        )
        return response.data[0].embedding

    def get_vector_name(self) -> str:
        return ""

    def get_vector_size(self) -> int:
        return self._dimensions
