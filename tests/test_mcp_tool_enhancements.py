import json

import pytest

from mcp_server_qdrant.embeddings.base import EmbeddingProvider
from mcp_server_qdrant.formatters import PlainTextEntryFormatter
from mcp_server_qdrant.mcp_server import QdrantMCPServer
from mcp_server_qdrant.qdrant import Entry
from mcp_server_qdrant.settings import (
    ChunkingSettings,
    DEFAULT_FILTERABLE_FIELDS,
    QdrantSettings,
    ToolSettings,
)


class FakeEmbeddingProvider(EmbeddingProvider):
    def _embed(self, text: str) -> list[float]:
        text_lower = text.lower()
        if "strong" in text_lower:
            return [1.0, 0.0]
        if "medium" in text_lower:
            return [0.8, 0.2]
        if "weak" in text_lower:
            return [0.2, 0.8]
        if "alpha" in text_lower:
            return [1.0, 0.0]
        return [0.0, 1.0]

    async def embed_documents(self, documents: list[str]) -> list[list[float]]:
        return [self._embed(document) for document in documents]

    async def embed_query(self, query: str) -> list[float]:
        return self._embed(query)

    def get_vector_name(self) -> str:
        return "test-vector"

    def get_vector_size(self) -> int:
        return 2


class DummyCtx:
    async def debug(self, *args, **kwargs):
        return None


def make_qdrant_settings(**overrides) -> QdrantSettings:
    base = {
        "location": ":memory:",
        "api_key": None,
        "collection_name": None,
        "local_path": None,
        "search_limit": 10,
        "read_only": False,
        "allowed_collections": None,
        "allow_destructive_operations": False,
        "filterable_fields": DEFAULT_FILTERABLE_FIELDS,
        "allow_arbitrary_filter": False,
        "enable_semantic_set_matching": False,
        "sets_config_path": None,
    }
    base.update(overrides)
    return QdrantSettings.model_construct(**base)


def make_server(**settings_overrides) -> QdrantMCPServer:
    return QdrantMCPServer(
        tool_settings=ToolSettings(),
        qdrant_settings=make_qdrant_settings(**settings_overrides),
        embedding_provider=FakeEmbeddingProvider(),
        chunking_settings=ChunkingSettings(),
        entry_formatter=PlainTextEntryFormatter(),
    )


async def get_tool(server: QdrantMCPServer, name: str):
    tools = await server.get_tools()
    if isinstance(tools, dict):
        return tools.get(name)
    return next((tool for tool in tools if getattr(tool, "name", None) == name), None)


@pytest.mark.asyncio
async def test_find_all_ranks_results_globally():
    server = make_server()
    await server.qdrant_connector.store(
        Entry(content="alpha strong result", metadata={"document_id": "doc-a"}),
        collection_name="collection-a",
    )
    await server.qdrant_connector.store(
        Entry(content="alpha weak result", metadata={"document_id": "doc-b"}),
        collection_name="collection-b",
    )
    await server.qdrant_connector.store(
        Entry(content="alpha medium result", metadata={"document_id": "doc-c"}),
        collection_name="collection-c",
    )

    tool = await get_tool(server, "qdrant-find-all")
    result = await tool.fn(DummyCtx(), query="alpha", query_mode="balanced", limit=3)

    assert isinstance(result, list)
    assert "3 result(s)" in result[0]
    assert "alpha strong result" in result[1]
    assert "Collection: collection-a" in result[1]
    assert "alpha medium result" in result[2]
    assert "alpha weak result" in result[3]


@pytest.mark.asyncio
async def test_get_schema_exposes_examples_and_policies():
    server = make_server(
        allowed_collections=["course-a", "course-b"],
        allow_destructive_operations=True,
    )

    tool = await get_tool(server, "qdrant-get-schema")
    schema = json.loads(await tool.fn(DummyCtx()))

    assert "examples" in schema
    assert "semantic_search" in schema["examples"]
    assert "query_modes" in schema
    assert schema["query_modes"]["precision"]["min_score"] == 0.45
    assert schema["policies"]["allowed_collections"] == ["course-a", "course-b"]
    assert schema["policies"]["allow_destructive_operations"] is True


@pytest.mark.asyncio
async def test_find_tool_schema_includes_query_mode():
    server = make_server()
    tool = await get_tool(server, "qdrant-find")

    if hasattr(tool, "parameters"):
        props = tool.parameters.get("properties", {})
    else:
        props = tool.inputSchema.get("properties", {})

    assert "query_mode" in props


@pytest.mark.asyncio
async def test_collection_admin_tools_create_list_and_delete():
    server = make_server(allow_destructive_operations=True)

    create_tool = await get_tool(server, "qdrant-create-collection")
    list_tool = await get_tool(server, "qdrant-list-collections")
    delete_tool = await get_tool(server, "qdrant-delete-collection")

    created = await create_tool.fn(DummyCtx(), collection_name="course-admin")
    assert created == "Created collection 'course-admin'."

    listed = await list_tool.fn(DummyCtx())
    assert "course-admin" in listed

    deleted = await delete_tool.fn(DummyCtx(), collection_name="course-admin")
    assert deleted == "Deleted collection 'course-admin'."


@pytest.mark.asyncio
async def test_delete_collection_requires_destructive_flag():
    server = make_server()
    delete_tool = await get_tool(server, "qdrant-delete-collection")

    with pytest.raises(ValueError, match="Destructive operations are disabled"):
        await delete_tool.fn(DummyCtx(), collection_name="blocked-collection")


@pytest.mark.asyncio
async def test_collection_allowlist_blocks_mutation():
    server = make_server(allowed_collections=["allowed-course"])
    create_tool = await get_tool(server, "qdrant-create-collection")

    with pytest.raises(ValueError, match="is not allowed"):
        await create_tool.fn(DummyCtx(), collection_name="blocked-course")