"""
Tests for collection statistics via get_collections_info (M3).
"""

import uuid

import pytest

from mcp_server_qdrant.embeddings.fastembed import FastEmbedProvider
from mcp_server_qdrant.qdrant import Entry, QdrantConnector


@pytest.fixture
async def embedding_provider():
    return FastEmbedProvider(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )


@pytest.fixture
async def connector(embedding_provider):
    collection = f"test_stats_{uuid.uuid4().hex}"
    connector = QdrantConnector(
        qdrant_url=":memory:",
        qdrant_api_key=None,
        collection_name=collection,
        embedding_provider=embedding_provider,
    )
    yield connector


@pytest.mark.asyncio
async def test_collections_info_empty(connector):
    """No collections should exist before any store."""
    info = await connector.get_collections_info()
    assert info == []


@pytest.mark.asyncio
async def test_collections_info_after_store(connector):
    """After storing entries, collection stats should reflect the count."""
    await connector.store(Entry(content="First document"))
    await connector.store(Entry(content="Second document"))

    info = await connector.get_collections_info()
    assert len(info) == 1
    assert info[0]["name"] == connector._default_collection_name
    assert info[0]["points_count"] == 2
    assert info[0]["status"] == "green"


@pytest.mark.asyncio
async def test_collections_info_multiple_collections(connector, embedding_provider):
    """Stats should list all collections."""
    collection_a = f"test_a_{uuid.uuid4().hex}"
    collection_b = f"test_b_{uuid.uuid4().hex}"

    await connector.store(
        Entry(content="Content A"), collection_name=collection_a
    )
    await connector.store(
        Entry(content="Content B1"), collection_name=collection_b
    )
    await connector.store(
        Entry(content="Content B2"), collection_name=collection_b
    )

    info = await connector.get_collections_info()
    info_by_name = {c["name"]: c for c in info}

    assert collection_a in info_by_name
    assert collection_b in info_by_name
    assert info_by_name[collection_a]["points_count"] == 1
    assert info_by_name[collection_b]["points_count"] == 2
