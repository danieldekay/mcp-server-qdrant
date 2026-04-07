#!/usr/bin/env python3
"""
Test script for the OpenAI embedding provider
"""
import asyncio
import os
from pathlib import Path

# Add the src directory to Python path
import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mcp_server_qdrant.embeddings.openai import OpenAIProvider

async def test_openai_provider():
    """Test the OpenAI embedding provider"""

    # Load environment variables (project root .env or workspace root .env)
    env_file = Path(__file__).parent.parent / ".env"
    if not env_file.exists():
        env_file = Path(__file__).parent.parent.parent.parent / ".env"  # workspace root
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)
        print(f"✅ Loaded environment from {env_file}")
    else:
        print(f"⚠️  No .env file found. Please ensure OPENAI_API_KEY is set in environment.")
        if not os.environ.get("OPENAI_API_KEY"):
            return

    try:
        # Create provider with text-embedding-3-small (same as our database)
        provider = OpenAIProvider("text-embedding-3-small")
        print(f"✅ Created OpenAI provider with model: text-embedding-3-small")
        print(f"✅ Vector size: {provider.get_vector_size()}")
        print(f"✅ Vector name: {provider.get_vector_name()}")

        # Test embedding a single query
        test_query = "Was sind die wichtigsten Forschungsmethoden in der Psychologie?"
        print(f"\n🧪 Testing query embedding...")
        query_embedding = await provider.embed_query(test_query)
        print(f"✅ Query embedding size: {len(query_embedding)}")
        print(f"✅ First 5 values: {query_embedding[:5]}")

        # Test embedding multiple documents
        test_documents = [
            "Quantitative Forschungsmethoden verwenden numerische Daten",
            "Qualitative Methoden analysieren nicht-numerische Daten",
            "Mixed-Methods kombinieren beide Ansätze"
        ]
        print(f"\n🧪 Testing document embeddings...")
        doc_embeddings = await provider.embed_documents(test_documents)
        print(f"✅ Document embeddings count: {len(doc_embeddings)}")
        print(f"✅ Each embedding size: {len(doc_embeddings[0])}")

        print(f"\n🎉 All tests passed! OpenAI provider is working correctly.")
        return True

    except Exception as e:
        print(f"❌ Error testing OpenAI provider: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_openai_provider())
    if not success:
        sys.exit(1)
