"""
Tests for the OpenRouter embedding provider.

Uses mocks since OpenRouter requires API credentials.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestOpenRouterProviderInit:
    """Test OpenRouterProvider initialization and validation."""

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key-123"})
    def test_init_with_env_key(self):
        from mcp_server_qdrant.embeddings.openrouter import OpenRouterProvider

        provider = OpenRouterProvider("openai/text-embedding-3-small")
        assert provider.model_name == "openai/text-embedding-3-small"
        assert provider.get_vector_size() == 1536

    def test_init_with_explicit_key(self):
        from mcp_server_qdrant.embeddings.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            "openai/text-embedding-3-small", api_key="explicit-key"
        )
        assert provider.get_vector_size() == 1536

    @patch.dict("os.environ", {}, clear=True)
    def test_init_no_key_raises(self):
        from mcp_server_qdrant.embeddings.openrouter import OpenRouterProvider

        with pytest.raises(ValueError, match="OpenRouter API key is required"):
            OpenRouterProvider("openai/text-embedding-3-small")

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_init_unknown_model_no_dims_raises(self):
        from mcp_server_qdrant.embeddings.openrouter import OpenRouterProvider

        with pytest.raises(ValueError, match="Unknown dimensions"):
            OpenRouterProvider("some-vendor/unknown-model")

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_init_unknown_model_with_explicit_dims(self):
        from mcp_server_qdrant.embeddings.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            "some-vendor/unknown-model", dimensions=2048
        )
        assert provider.get_vector_size() == 2048

    @patch.dict(
        "os.environ",
        {"OPENROUTER_API_KEY": "test-key", "OPENROUTER_EMBEDDING_DIMENSIONS": "4096"},
    )
    def test_init_unknown_model_with_env_dims(self):
        from mcp_server_qdrant.embeddings.openrouter import OpenRouterProvider

        provider = OpenRouterProvider("some-vendor/unknown-model")
        assert provider.get_vector_size() == 4096

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_explicit_dims_override_known(self):
        """Explicit dimensions parameter takes priority over the lookup table."""
        from mcp_server_qdrant.embeddings.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(
            "openai/text-embedding-3-small", dimensions=512
        )
        assert provider.get_vector_size() == 512

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    def test_base_url(self):
        from mcp_server_qdrant.embeddings.openrouter import (
            OPENROUTER_BASE_URL,
            OpenRouterProvider,
        )

        provider = OpenRouterProvider("openai/text-embedding-3-small")
        assert str(provider.client.base_url).rstrip("/") == OPENROUTER_BASE_URL


class TestOpenRouterProviderMethods:
    """Test OpenRouterProvider embedding methods with mocked client."""

    @pytest.fixture
    def provider(self):
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            from mcp_server_qdrant.embeddings.openrouter import OpenRouterProvider

            return OpenRouterProvider("openai/text-embedding-3-small")

    def test_get_vector_name(self, provider):
        assert provider.get_vector_name() == ""

    def test_get_vector_size(self, provider):
        assert provider.get_vector_size() == 1536

    @pytest.mark.asyncio
    async def test_embed_query(self, provider):
        fake_embedding = [0.1] * 1536
        mock_item = MagicMock()
        mock_item.embedding = fake_embedding
        mock_response = MagicMock()
        mock_response.data = [mock_item]

        provider.client.embeddings.create = AsyncMock(return_value=mock_response)

        result = await provider.embed_query("test query")
        assert result == fake_embedding
        provider.client.embeddings.create.assert_awaited_once_with(
            input=["test query"],
            model="openai/text-embedding-3-small",
        )

    @pytest.mark.asyncio
    async def test_embed_documents(self, provider):
        fake_embeddings = [[0.1] * 1536, [0.2] * 1536]
        mock_items = []
        for emb in fake_embeddings:
            item = MagicMock()
            item.embedding = emb
            mock_items.append(item)
        mock_response = MagicMock()
        mock_response.data = mock_items

        provider.client.embeddings.create = AsyncMock(return_value=mock_response)

        result = await provider.embed_documents(["doc one", "doc two"])
        assert result == fake_embeddings
        provider.client.embeddings.create.assert_awaited_once_with(
            input=["doc one", "doc two"],
            model="openai/text-embedding-3-small",
        )


class TestOpenRouterKnownModels:
    """Verify the known models dimension lookup table."""

    @patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"})
    @pytest.mark.parametrize(
        "model,expected_dims",
        [
            ("openai/text-embedding-3-small", 1536),
            ("openai/text-embedding-3-large", 3072),
            ("baai/bge-m3", 1024),
            ("sentence-transformers/all-MiniLM-L6-v2", 384),
            ("sentence-transformers/all-mpnet-base-v2", 768),
        ],
    )
    def test_known_model_dimensions(self, model, expected_dims):
        from mcp_server_qdrant.embeddings.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(model)
        assert provider.get_vector_size() == expected_dims


class TestOpenRouterInFactory:
    """Test that the factory creates OpenRouterProvider."""

    @patch.dict(
        "os.environ",
        {
            "OPENROUTER_API_KEY": "test-key",
            "EMBEDDING_PROVIDER": "openrouter",
            "EMBEDDING_MODEL": "openai/text-embedding-3-small",
        },
    )
    def test_factory_creates_openrouter(self):
        from mcp_server_qdrant.embeddings.factory import create_embedding_provider
        from mcp_server_qdrant.embeddings.openrouter import OpenRouterProvider
        from mcp_server_qdrant.settings import EmbeddingProviderSettings

        settings = EmbeddingProviderSettings()
        provider = create_embedding_provider(settings)
        assert isinstance(provider, OpenRouterProvider)
