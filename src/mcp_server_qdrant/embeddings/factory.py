from mcp_server_qdrant.embeddings.base import EmbeddingProvider
from mcp_server_qdrant.embeddings.types import EmbeddingProviderType
from mcp_server_qdrant.settings import EmbeddingProviderSettings


def create_embedding_provider(settings: EmbeddingProviderSettings) -> EmbeddingProvider:
    """
    Create an embedding provider based on the specified type.
    :param settings: The settings for the embedding provider.
    :return: An instance of the specified embedding provider.
    """
    if settings.provider_type == EmbeddingProviderType.FASTEMBED:
        from mcp_server_qdrant.embeddings.fastembed import FastEmbedProvider

        return FastEmbedProvider(settings.model_name)
    elif settings.provider_type == EmbeddingProviderType.OPENAI:
        from mcp_server_qdrant.embeddings.openai import OpenAIProvider

        return OpenAIProvider(settings.model_name)
    elif settings.provider_type == EmbeddingProviderType.GEMINI:
        from mcp_server_qdrant.embeddings.gemini import GeminiProvider

        return GeminiProvider(settings.model_name)
    elif settings.provider_type == EmbeddingProviderType.OPENROUTER:
        from mcp_server_qdrant.embeddings.openrouter import OpenRouterProvider

        return OpenRouterProvider(settings.model_name)
    else:
        raise ValueError(f"Unsupported embedding provider: {settings.provider_type}")
