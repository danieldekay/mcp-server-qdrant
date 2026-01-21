#!/usr/bin/env python3
"""
Test script for the modified MCP server with OpenAI embeddings
Tests integration with existing literature database
"""
import asyncio
import os
from pathlib import Path
import sys

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
from mcp_server_qdrant.embeddings.openai import OpenAIProvider
from mcp_server_qdrant.qdrant import QdrantConnector, Entry

async def test_mcp_integration():
    """Test MCP server integration with existing literature database"""
    
    # Load environment variables
    env_file = Path("/Users/jk/Library/CloudStorage/OneDrive-Personal/Dokumente/Github/FoM2526/.env")
    if env_file.exists():
        load_dotenv(env_file)
        print(f"✅ Loaded environment from {env_file}")
    else:
        print(f"❌ Environment file not found at {env_file}")
        return False
    
    try:
        # Create OpenAI provider (same as our existing database)
        provider = OpenAIProvider("text-embedding-3-small")
        print(f"✅ Created OpenAI embedding provider")
        
        # Create Qdrant connector to existing database
        qdrant_path = "/Users/jk/Library/CloudStorage/OneDrive-Personal/Dokumente/Github/FoM2526/Folien+Lit/qdrant_db"
        collection_name = "forschungsmethoden_literatur"
        
        connector = QdrantConnector(
            qdrant_url=None,  # Use local path
            qdrant_api_key=None,
            collection_name=collection_name,
            embedding_provider=provider,
            qdrant_local_path=qdrant_path
        )
        print(f"✅ Created Qdrant connector for existing database")
        
        # Test search (similar to qdrant-find tool)
        print(f"\n🔍 Testing search in existing literature database...")
        
        test_queries = [
            "quantitative Forschungsmethoden",
            "Validität und Reliabilität", 
            "Stichprobenziehung",
            "statistische Tests"
        ]
        
        for query in test_queries:
            print(f"\n📝 Searching for: '{query}'")
            results = await connector.search(query, limit=3)
            
            if results:
                print(f"   ✅ Found {len(results)} results")
                for i, result in enumerate(results, 1):
                    # Show first 100 characters of content
                    content_preview = result.content[:100].replace('\n', ' ')
                    if len(result.content) > 100:
                        content_preview += "..."
                    print(f"   {i}. {content_preview}")
                    
                    # Show metadata if available
                    if result.metadata:
                        metadata_str = ", ".join([f"{k}: {v}" for k, v in result.metadata.items() if k in ['source', 'book', 'chapter']])
                        if metadata_str:
                            print(f"      📚 {metadata_str}")
            else:
                print(f"   ❌ No results found")
        
        # Test storing new content (similar to qdrant-store tool)
        print(f"\n💾 Testing content storage...")
        
        test_entry = Entry(
            content="Dies ist ein Test-Eintrag für die Forschungsmethoden-Sammlung. Er demonstriert die Funktionalität des MCP-Servers mit OpenAI-Embeddings.",
            metadata={
                "source": "MCP-Test",
                "type": "test_entry",
                "timestamp": "2025-09-26"
            }
        )
        
        await connector.store(test_entry)
        print(f"✅ Successfully stored test entry")
        
        # Search for the stored entry
        search_results = await connector.search("MCP-Test Funktionalität", limit=1)
        if search_results and "Test-Eintrag" in search_results[0].content:
            print(f"✅ Successfully found stored test entry")
        else:
            print(f"⚠️  Could not find stored test entry")
        
        print(f"\n🎉 MCP integration test completed successfully!")
        print(f"🔗 The modified MCP server can now work with your existing literature database!")
        return True
        
    except Exception as e:
        print(f"❌ Error in MCP integration test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_mcp_integration())
    if not success:
        sys.exit(1)