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


@pytest.mark.asyncio
async def test_update_document_metadata_updates_all_points(connector):
    document_id = "course-pack.pdf"
    entries = [
        Entry(
            content="Intro page",
            metadata={
                PDFMetadataKeys.DOCUMENT_ID: document_id,
                PDFMetadataKeys.PAGE_LABEL: "1",
                PDFMetadataKeys.PHYSICAL_PAGE_INDEX: 0,
            },
        ),
        Entry(
            content="Methods page",
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

    updated = await connector.update_document_metadata(
        document_id,
        {"course_id": "om-ws2026", "language": "de"},
        collection_name=connector._default_collection_name,
    )

    results = await connector.search(
        "page",
        collection_name=connector._default_collection_name,
    )

    assert updated == 2
    assert len(results) == 2
    assert all(result.metadata["course_id"] == "om-ws2026" for result in results)
    assert all(result.metadata["language"] == "de" for result in results)


@pytest.mark.asyncio
async def test_list_chapters_accepts_docling_chapter_metadata(connector):
    document_id = "docling-book.pdf"
    entries = [
        Entry(
            content="Grundlagen der Forschung",
            metadata={
                PDFMetadataKeys.DOCUMENT_ID: document_id,
                PDFMetadataKeys.PAGE_LABEL: "10",
                PDFMetadataKeys.PHYSICAL_PAGE_INDEX: 35,
                "chapter": "Empirische Sozialforschung im Überblick",
            },
        ),
        Entry(
            content="Weiterführende Inhalte",
            metadata={
                PDFMetadataKeys.DOCUMENT_ID: document_id,
                PDFMetadataKeys.PAGE_LABEL: "12",
                PDFMetadataKeys.PHYSICAL_PAGE_INDEX: 37,
                "chapter": "Empirische Sozialforschung im Überblick",
            },
        ),
    ]

    await connector.upsert_document_entries(
        entries,
        collection_name=connector._default_collection_name,
        document_id=document_id,
    )

    chapters = await connector.list_chapters(
        collection_name=connector._default_collection_name,
        document_id=document_id,
    )

    assert len(chapters) == 1
    assert chapters[0]["chapter_title"] == "Empirische Sozialforschung im Überblick"
    assert chapters[0]["first_page_label"] == "10"


@pytest.mark.asyncio
async def test_list_chapters_prefers_top_level_docling_section_headers(connector):
    document_id = "doering-book.pdf"
    entries = [
        Entry(
            content="Vorwort",
            metadata={
                PDFMetadataKeys.DOCUMENT_ID: document_id,
                PDFMetadataKeys.PAGE_LABEL: "v",
                PDFMetadataKeys.PHYSICAL_PAGE_INDEX: 2,
                "chunk_type": "section_header",
                "heading_l1": "Vorwort",
            },
        ),
        Entry(
            content="1 Empirische Sozialforschung",
            metadata={
                PDFMetadataKeys.DOCUMENT_ID: document_id,
                PDFMetadataKeys.PAGE_LABEL: "1",
                PDFMetadataKeys.PHYSICAL_PAGE_INDEX: 27,
                "chunk_type": "section_header",
                "heading_l1": "1 Empirische Sozialforschung",
            },
        ),
        Entry(
            content="1.1 Der Forschungsprozess",
            metadata={
                PDFMetadataKeys.DOCUMENT_ID: document_id,
                PDFMetadataKeys.PAGE_LABEL: "3",
                PDFMetadataKeys.PHYSICAL_PAGE_INDEX: 29,
                "chunk_type": "section_header",
                "heading_l1": "1 Empirische Sozialforschung",
                "heading_l2": "1.1 Der Forschungsprozess",
            },
        ),
        Entry(
            content="Lernziele",
            metadata={
                PDFMetadataKeys.DOCUMENT_ID: document_id,
                PDFMetadataKeys.PAGE_LABEL: "4",
                PDFMetadataKeys.PHYSICAL_PAGE_INDEX: 30,
                "chunk_type": "section_header",
                "heading_l1": "1 Empirische Sozialforschung",
                "heading_l2": "Lernziele",
            },
        ),
    ]

    await connector.upsert_document_entries(
        entries,
        collection_name=connector._default_collection_name,
        document_id=document_id,
    )

    chapters = await connector.list_chapters(
        collection_name=connector._default_collection_name,
        document_id=document_id,
    )

    assert [chapter["chapter_title"] for chapter in chapters] == [
        "Vorwort",
        "1 Empirische Sozialforschung",
    ]


@pytest.mark.asyncio
async def test_list_chapters_uses_shallowest_numbering_for_excerpt_docs(connector):
    document_id = "mayring-excerpt.pdf"
    entries = [
        Entry(
            content="43.1 Was ist qualitative Inhaltsanalyse?",
            metadata={
                PDFMetadataKeys.DOCUMENT_ID: document_id,
                PDFMetadataKeys.PAGE_LABEL: "691",
                PDFMetadataKeys.PHYSICAL_PAGE_INDEX: 0,
                "chunk_type": "section_header",
                "heading_l1": "43.1 Was ist qualitative Inhaltsanalyse?",
            },
        ),
        Entry(
            content="43.1.1 Begriffsbestimmung",
            metadata={
                PDFMetadataKeys.DOCUMENT_ID: document_id,
                PDFMetadataKeys.PAGE_LABEL: "692",
                PDFMetadataKeys.PHYSICAL_PAGE_INDEX: 1,
                "chunk_type": "section_header",
                "heading_l1": "43.1 Was ist qualitative Inhaltsanalyse?",
                "heading_l2": "43.1.1 Begriffsbestimmung",
            },
        ),
        Entry(
            content="43.2 Grundprinzipien",
            metadata={
                PDFMetadataKeys.DOCUMENT_ID: document_id,
                PDFMetadataKeys.PAGE_LABEL: "693",
                PDFMetadataKeys.PHYSICAL_PAGE_INDEX: 2,
                "chunk_type": "section_header",
                "heading_l1": "43.2 Grundprinzipien",
            },
        ),
    ]

    await connector.upsert_document_entries(
        entries,
        collection_name=connector._default_collection_name,
        document_id=document_id,
    )

    chapters = await connector.list_chapters(
        collection_name=connector._default_collection_name,
        document_id=document_id,
    )

    assert [chapter["chapter_title"] for chapter in chapters] == [
        "43.1 Was ist qualitative Inhaltsanalyse?",
        "43.2 Grundprinzipien",
    ]


@pytest.mark.asyncio
async def test_list_chapters_compacts_legacy_docling_titles_without_section_headers(connector):
    document_id = "legacy-docling.pdf"
    entries = [
        Entry(
            content="Inhaltsverzeichnis",
            metadata={
                PDFMetadataKeys.DOCUMENT_ID: document_id,
                PDFMetadataKeys.PAGE_LABEL: "1",
                PDFMetadataKeys.PHYSICAL_PAGE_INDEX: 10,
                "chapter_title": "Inhaltsverzeichnis",
            },
        ),
        Entry(
            content="Kapitelauftakt",
            metadata={
                PDFMetadataKeys.DOCUMENT_ID: document_id,
                PDFMetadataKeys.PAGE_LABEL: "4",
                PDFMetadataKeys.PHYSICAL_PAGE_INDEX: 13,
                "chapter_title": "1.1 Grundlagen",
            },
        ),
        Entry(
            content="Unterabschnitt",
            metadata={
                PDFMetadataKeys.DOCUMENT_ID: document_id,
                PDFMetadataKeys.PAGE_LABEL: "5",
                PDFMetadataKeys.PHYSICAL_PAGE_INDEX: 14,
                "chapter_title": "1.1.1 Erkenntnisinteresse",
            },
        ),
        Entry(
            content="Nächster Abschnitt",
            metadata={
                PDFMetadataKeys.DOCUMENT_ID: document_id,
                PDFMetadataKeys.PAGE_LABEL: "7",
                PDFMetadataKeys.PHYSICAL_PAGE_INDEX: 16,
                "chapter_title": "1.2 Forschungsfragen",
            },
        ),
        Entry(
            content="Neues Hauptkapitel",
            metadata={
                PDFMetadataKeys.DOCUMENT_ID: document_id,
                PDFMetadataKeys.PAGE_LABEL: "15",
                PDFMetadataKeys.PHYSICAL_PAGE_INDEX: 24,
                "chapter_title": "2.1 Designs",
            },
        ),
        Entry(
            content="Tieferer Unterpunkt",
            metadata={
                PDFMetadataKeys.DOCUMENT_ID: document_id,
                PDFMetadataKeys.PAGE_LABEL: "16",
                PDFMetadataKeys.PHYSICAL_PAGE_INDEX: 25,
                "chapter_title": "2.1.3 Quasi-Experimente",
            },
        ),
        Entry(
            content="Nur tiefe Ebene vorhanden",
            metadata={
                PDFMetadataKeys.DOCUMENT_ID: document_id,
                PDFMetadataKeys.PAGE_LABEL: "30",
                PDFMetadataKeys.PHYSICAL_PAGE_INDEX: 39,
                "chapter_title": "3.4.2 Auswertung",
            },
        ),
    ]

    await connector.upsert_document_entries(
        entries,
        collection_name=connector._default_collection_name,
        document_id=document_id,
    )

    chapters = await connector.list_chapters(
        collection_name=connector._default_collection_name,
        document_id=document_id,
    )

    assert [chapter["chapter_title"] for chapter in chapters] == [
        "1.1 Grundlagen",
        "1.2 Forschungsfragen",
        "2.1 Designs",
        "3.4.2 Auswertung",
    ]
