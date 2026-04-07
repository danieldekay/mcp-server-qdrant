import uuid

import pytest
from qdrant_client import models

from mcp_server_qdrant.constants import PDFMetadataKeys, SystemMetadataKeys
from mcp_server_qdrant.embeddings.fastembed import FastEmbedProvider
from mcp_server_qdrant.qdrant import Entry, QdrantConnector, compute_content_hash


@pytest.fixture
async def embedding_provider():
    return FastEmbedProvider(model_name="sentence-transformers/all-MiniLM-L6-v2")


@pytest.fixture
async def connector(embedding_provider):
    collection = f"test_lifecycle_{uuid.uuid4().hex}"
    connector = QdrantConnector(
        qdrant_url=":memory:",
        qdrant_api_key=None,
        collection_name=collection,
        embedding_provider=embedding_provider,
    )
    yield connector


@pytest.mark.asyncio
async def test_upsert_document_entries_updates_metadata_without_duplicates(connector):
    document_id = "syllabus.md"
    first_entry = Entry(
        content="Operations management introduces process design.",
        metadata={"semester": "ws2026", PDFMetadataKeys.DOCUMENT_ID: document_id},
    )
    second_entry = Entry(
        content="Operations management introduces process design.",
        metadata={"semester": "ss2027", "language": "de", PDFMetadataKeys.DOCUMENT_ID: document_id},
    )

    created = await connector.upsert_document_entries(
        [first_entry],
        collection_name=connector._default_collection_name,
        document_id=document_id,
    )
    updated = await connector.upsert_document_entries(
        [second_entry],
        collection_name=connector._default_collection_name,
        document_id=document_id,
    )

    points = await connector.get_document_points(
        document_id,
        collection_name=connector._default_collection_name,
    )
    assert created["mode"] == "created"
    assert updated["mode"] == "metadata_updated"
    assert len(points) == 1

    content, metadata = connector._extract_content_and_metadata(points[0].payload)
    assert content == first_entry.content
    assert metadata["semester"] == "ss2027"
    assert metadata["language"] == "de"
    assert metadata[SystemMetadataKeys.CONTENT_HASH] == compute_content_hash(first_entry.content)


@pytest.mark.asyncio
async def test_upsert_document_entries_replaces_changed_content(connector):
    document_id = "lecture-notes.md"
    original = Entry(
        content="Old lecture notes",
        metadata={PDFMetadataKeys.DOCUMENT_ID: document_id},
    )
    replacement = Entry(
        content="Updated lecture notes",
        metadata={PDFMetadataKeys.DOCUMENT_ID: document_id, "language": "en"},
    )

    await connector.upsert_document_entries(
        [original],
        collection_name=connector._default_collection_name,
        document_id=document_id,
    )
    result = await connector.upsert_document_entries(
        [replacement],
        collection_name=connector._default_collection_name,
        document_id=document_id,
    )

    search_results = await connector.search(
        "updated lecture",
        collection_name=connector._default_collection_name,
    )
    assert result["mode"] == "replaced"
    assert result["deleted"] == 1
    assert len(search_results) == 1
    assert search_results[0].content == "Updated lecture notes"
    assert search_results[0].metadata["language"] == "en"


@pytest.mark.asyncio
async def test_delete_document_removes_all_matching_points(connector):
    document_id = "textbook.pdf"
    entries = [
        Entry(
            content="Page one",
            metadata={
                PDFMetadataKeys.DOCUMENT_ID: document_id,
                PDFMetadataKeys.PAGE_LABEL: "1",
                PDFMetadataKeys.PHYSICAL_PAGE_INDEX: 0,
            },
        ),
        Entry(
            content="Page two",
            metadata={
                PDFMetadataKeys.DOCUMENT_ID: document_id,
                PDFMetadataKeys.PAGE_LABEL: "2",
                PDFMetadataKeys.PHYSICAL_PAGE_INDEX: 1,
            },
        ),
    ]

    await connector.upsert_document_entries(
        entries,
        collection_name=connector._default_collection_name,
        document_id=document_id,
    )
    deleted = await connector.delete_document(
        document_id,
        collection_name=connector._default_collection_name,
    )
    remaining = await connector.get_document_points(
        document_id,
        collection_name=connector._default_collection_name,
    )

    assert deleted == 2
    assert remaining == []


@pytest.mark.asyncio
async def test_delete_by_filter_removes_subset(connector):
    await connector.store(
        Entry(
            content="German content",
            metadata={"language": "de", PDFMetadataKeys.DOCUMENT_ID: "doc-de"},
        ),
        collection_name=connector._default_collection_name,
    )
    await connector.store(
        Entry(
            content="English content",
            metadata={"language": "en", PDFMetadataKeys.DOCUMENT_ID: "doc-en"},
        ),
        collection_name=connector._default_collection_name,
    )

    deleted = await connector.delete_by_filter(
        collection_name=connector._default_collection_name,
        query_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="metadata.language",
                    match=models.MatchValue(value="de"),
                )
            ]
        ),
    )
    remaining = await connector.search(
        "content",
        collection_name=connector._default_collection_name,
    )

    assert deleted == 1
    assert len(remaining) == 1
    assert remaining[0].metadata["language"] == "en"