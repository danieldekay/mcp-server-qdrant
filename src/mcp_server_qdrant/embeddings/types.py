from enum import Enum


class EmbeddingProviderType(Enum):
    FASTEMBED = "fastembed"
    OPENAI = "openai"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"
