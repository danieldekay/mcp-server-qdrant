import uuid

import pytest

from mcp_server_qdrant.embeddings.base import EmbeddingProvider
from mcp_server_qdrant.pdf_extractor import PDFPageExtractor
from mcp_server_qdrant.qdrant import Entry, QdrantConnector


class IndexRegressionEmbeddingProvider(EmbeddingProvider):
    TERMS = [
        "machine learning",
        "neural networks",
        "deep learning",
        "kapazitatsplanung",
        "qualitatsmanagement",
    ]

    def _embed(self, text: str) -> list[float]:
        lower_text = text.lower()
        return [1.0 if term in lower_text else 0.0 for term in self.TERMS]

    async def embed_documents(self, documents: list[str]) -> list[list[float]]:
        return [self._embed(document) for document in documents]

    async def embed_query(self, query: str) -> list[float]:
        return self._embed(query)

    def get_vector_name(self) -> str:
        return "index-regression"

    def get_vector_size(self) -> int:
        return len(self.TERMS)


@pytest.fixture
async def connector():
    collection = f"test_retrieval_{uuid.uuid4().hex}"
    connector = QdrantConnector(
        qdrant_url=":memory:",
        qdrant_api_key=None,
        collection_name=collection,
        embedding_provider=IndexRegressionEmbeddingProvider(),
    )
    yield connector


INDEX_TEXT = (
    "Machine Learning, 45, 67-72, 134\n"
    "Neural Networks, 23, 90-95\n"
    "Deep Learning, 100\n"
    "Kapazitatsplanung, 142, 156-160\n"
    "Qualitatsmanagement, 200, 215-220, 301\n"
)


async def populate_textbook_pages(connector: QdrantConnector, document_id: str) -> dict[str, set[str]]:
    index_entries = PDFPageExtractor.parse_index_entries(INDEX_TEXT)
    page_map = PDFPageExtractor.build_page_to_terms_map(index_entries)

    expected_pages: dict[str, set[str]] = {}
    pages_to_seed = [23, 45, 67, 90, 100, 142, 156, 200, 215, 301]
    for page in pages_to_seed:
        terms = page_map.get(page, [])
        if not terms:
            continue

        content = (
            f"Page {page} discusses "
            + ", ".join(terms)
            + " in the context of operations and analytics."
        )
        await connector.store(
            Entry(
                content=content,
                metadata={
                    "document_id": document_id,
                    "page_label": str(page),
                    "physical_page_index": page - 1,
                },
            ),
            collection_name=connector._default_collection_name,
        )

        for term in terms:
            expected_pages.setdefault(term, set()).add(str(page))

    return expected_pages


@pytest.mark.asyncio
async def test_keyword_search_matches_index_expected_pages(connector):
    expected_pages = await populate_textbook_pages(connector, "textbook.pdf")

    results = await connector.keyword_search(
        "Machine Learning",
        collection_name=connector._default_collection_name,
        document_id="textbook.pdf",
        limit=10,
    )

    found_pages = {result.metadata["page_label"] for result in results}
    assert found_pages <= expected_pages["Machine Learning"]
    assert "45" in found_pages
    assert "67" in found_pages


@pytest.mark.asyncio
async def test_semantic_search_matches_index_expected_pages(connector):
    expected_pages = await populate_textbook_pages(connector, "textbook.pdf")

    results = await connector.search(
        "Qualitatsmanagement",
        collection_name=connector._default_collection_name,
        limit=5,
        score_threshold=0.1,
    )

    found_pages = {result.metadata["page_label"] for result in results}
    assert found_pages <= expected_pages["Qualitatsmanagement"]
    assert found_pages & {"200", "215", "301"}


@pytest.mark.asyncio
async def test_index_terms_form_a_repeatable_retrieval_golden_set(connector):
    expected_pages = await populate_textbook_pages(connector, "textbook.pdf")

    golden_queries = {
        "Machine Learning": {"45", "67", "134"},
        "Deep Learning": {"100"},
        "Kapazitatsplanung": {"142", "156"},
    }

    for query, minimum_expected in golden_queries.items():
        results = await connector.search(
            query,
            collection_name=connector._default_collection_name,
            limit=5,
                score_threshold=0.1,
        )
        found_pages = {result.metadata["page_label"] for result in results}
        assert found_pages <= expected_pages[query]
        assert found_pages & minimum_expected