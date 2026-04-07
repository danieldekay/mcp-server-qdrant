"""
Tests for the Gemini embedding provider (M5).

Uses mocks since google-generativeai requires API credentials.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestGeminiProviderInit:
    """Test GeminiProvider initialization and validation."""

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key-123"})
    @patch("google.generativeai.configure")
    def test_init_with_env_key(self, mock_configure):
        from mcp_server_qdrant.embeddings.gemini import GeminiProvider

        provider = GeminiProvider("models/embedding-001")
        assert provider.model_name == "models/embedding-001"
        mock_configure.assert_called_once_with(api_key="test-key-123")

    @patch("google.generativeai.configure")
    def test_init_with_explicit_key(self, mock_configure):
        from mcp_server_qdrant.embeddings.gemini import GeminiProvider

        provider = GeminiProvider("models/embedding-001", api_key="explicit-key")
        mock_configure.assert_called_once_with(api_key="explicit-key")

    @patch.dict("os.environ", {}, clear=True)
    @patch("google.generativeai.configure")
    def test_init_no_key_raises(self, mock_configure):
        from mcp_server_qdrant.embeddings.gemini import GeminiProvider

        with pytest.raises(ValueError, match="Google API key is required"):
            GeminiProvider("models/embedding-001")

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"})
    @patch("google.generativeai.configure")
    def test_init_unsupported_model_raises(self, mock_configure):
        from mcp_server_qdrant.embeddings.gemini import GeminiProvider

        with pytest.raises(ValueError, match="Unsupported Gemini"):
            GeminiProvider("not-a-real-model")

    @patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"})
    @patch("google.generativeai.configure")
    def test_normalizes_model_name(self, mock_configure):
        from mcp_server_qdrant.embeddings.gemini import GeminiProvider

        # Should accept without 'models/' prefix and normalize internally
        provider = GeminiProvider("embedding-001")
        assert provider._lookup_name == "models/embedding-001"


class TestGeminiProviderMethods:
    """Test GeminiProvider embedding methods with mocked API."""

    @pytest.fixture
    def provider(self):
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-key"}):
            with patch("google.generativeai.configure"):
                from mcp_server_qdrant.embeddings.gemini import GeminiProvider

                return GeminiProvider("models/embedding-001")

    def test_get_vector_name(self, provider):
        assert provider.get_vector_name() == ""

    def test_get_vector_size(self, provider):
        assert provider.get_vector_size() == 768

    @pytest.mark.asyncio
    async def test_embed_query(self, provider):
        fake_embedding = [0.1] * 768
        with patch(
            "google.generativeai.embed_content",
            return_value={"embedding": fake_embedding},
        ):
            result = await provider.embed_query("test query")
        assert result == fake_embedding

    @pytest.mark.asyncio
    async def test_embed_documents(self, provider):
        fake_embeddings = [[0.1] * 768, [0.2] * 768]
        with patch(
            "google.generativeai.embed_content",
            return_value={"embedding": fake_embeddings},
        ):
            result = await provider.embed_documents(["doc1", "doc2"])
        assert result == fake_embeddings


class TestGeminiProviderInFactory:
    """Test that the factory creates GeminiProvider."""

    @patch.dict(
        "os.environ",
        {
            "GOOGLE_API_KEY": "test-key",
            "EMBEDDING_PROVIDER": "gemini",
            "EMBEDDING_MODEL": "models/embedding-001",
        },
    )
    @patch("google.generativeai.configure")
    def test_factory_creates_gemini(self, mock_configure):
        from mcp_server_qdrant.embeddings.factory import create_embedding_provider
        from mcp_server_qdrant.embeddings.gemini import GeminiProvider
        from mcp_server_qdrant.settings import EmbeddingProviderSettings

        settings = EmbeddingProviderSettings()
        provider = create_embedding_provider(settings)
        assert isinstance(provider, GeminiProvider)
