#!/usr/bin/env python3
"""
Inspect the existing Qdrant database to understand its structure
"""
import asyncio
from pathlib import Path
from qdrant_client import AsyncQdrantClient

async def inspect_database():
    """Inspect the existing Qdrant database"""
    
    try:
        # Connect to existing database
        qdrant_path = "/Users/jk/Library/CloudStorage/OneDrive-Personal/Dokumente/Github/FoM2526/Folien+Lit/qdrant_db"
        collection_name = "forschungsmethoden_literatur"
        
        client = AsyncQdrantClient(path=qdrant_path)
        
        # Check if collection exists
        collections = await client.get_collections()
        print(f"📂 Available collections: {[c.name for c in collections.collections]}")
        
        if collection_name not in [c.name for c in collections.collections]:
            print(f"❌ Collection '{collection_name}' not found!")
            return
        
        # Get collection info
        collection_info = await client.get_collection(collection_name)
        print(f"\n📊 Collection '{collection_name}' info:")
        print(f"   Points count: {collection_info.points_count}")
        print(f"   Vectors config: {collection_info.config.params.vectors}")
        
        # Show vector configurations
        if hasattr(collection_info.config.params.vectors, 'items'):
            for vector_name, vector_config in collection_info.config.params.vectors.items():
                print(f"   Vector '{vector_name}': size={vector_config.size}, distance={vector_config.distance}")
        else:
            # Single vector configuration
            print(f"   Single vector: size={collection_info.config.params.vectors.size}, distance={collection_info.config.params.vectors.distance}")
        
        # Get a few sample points to understand the structure
        print(f"\n🔍 Sample points:")
        sample_points = await client.scroll(collection_name, limit=3, with_payload=True, with_vectors=True)
        
        for i, point in enumerate(sample_points[0], 1):
            print(f"\n   Point {i}:")
            print(f"     ID: {point.id}")
            if point.payload:
                payload_keys = list(point.payload.keys())
                print(f"     Payload keys: {payload_keys}")
                if 'document' in point.payload:
                    doc_preview = str(point.payload['document'])[:100].replace('\n', ' ')
                    if len(str(point.payload['document'])) > 100:
                        doc_preview += "..."
                    print(f"     Document preview: {doc_preview}")
            if point.vector:
                if isinstance(point.vector, dict):
                    print(f"     Vector names: {list(point.vector.keys())}")
                    for vec_name, vec_data in point.vector.items():
                        print(f"       {vec_name}: {len(vec_data)} dimensions")
                else:
                    print(f"     Vector: {len(point.vector)} dimensions")
        
        await client.close()
        return True
        
    except Exception as e:
        print(f"❌ Error inspecting database: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(inspect_database())
    if not success:
        exit(1)