import uuid

import pytest

from qdrant_client import models

from mcp_server_qdrant.common.filters import make_filter
from mcp_server_qdrant.common.wrap_filters import wrap_filters
from mcp_server_qdrant.common.func_tools import make_partial_function
from mcp_server_qdrant.settings import QdrantSettings, FilterableField
from mcp_server_qdrant.qdrant import Entry
from mcp_server_qdrant.embeddings.fastembed import FastEmbedProvider
from mcp_server_qdrant.qdrant import QdrantConnector


@pytest.fixture
async def embedding_provider():
    return FastEmbedProvider(model_name="sentence-transformers/all-MiniLM-L6-v2")


@pytest.fixture
async def qdrant_connector(embedding_provider):
    collection_name = f"test_pdf_filters_{uuid.uuid4().hex}"
    connector = QdrantConnector(
        qdrant_url=":memory:",
        qdrant_api_key=None,
        collection_name=collection_name,
        embedding_provider=embedding_provider,
    )

    yield connector


def test_wrap_filters_signature_contains_pdf_fields():
    settings = QdrantSettings()
    filterable = settings.filterable_fields_dict_with_conditions()

    def find(
        query: str,
        collection_name: str,
        query_filter: models.Filter | None = None,
    ) -> list[str]:
        return []

    wrapped = wrap_filters(find, filterable)
    params = wrapped.__signature__.parameters

    assert "document_id" in params
    assert "physical_page_index" in params
    assert "page_label" in params


def test_make_partial_function_preserves_filter_params():
    """Ensure make_partial_function removes only the fixed parameter and keeps filter params in the signature."""

    def find(
        query: str,
        collection_name: str,
        document_id: str | None = None,
        physical_page_index: int | None = None,
        page_label: str | None = None,
        query_filter: models.Filter | None = None,
    ) -> list[str]:
        return []

    partial = make_partial_function(find, {"collection_name": "default"})
    params = partial.__signature__.parameters

    assert "collection_name" not in params
    assert "document_id" in params
    assert "physical_page_index" in params
    assert "page_label" in params


def test_make_filter_generates_expected_conditions():
    settings = QdrantSettings()
    filterable = settings.filterable_fields_dict()

    values = {
        "document_id": "doc1",
        "physical_page_index": 5,
        "page_label": "45",
    }

    f = make_filter(filterable, values)
    # The produced filter should include 'must' conditions for each provided value
    assert "must" in f
    must_keys = {c["key"] for c in f["must"]}
    assert "metadata.document_id" in must_keys
    assert "metadata.physical_page_index" in must_keys
    assert "metadata.page_label" in must_keys


@pytest.mark.asyncio
async def test_search_filters_by_document_id_and_page(qdrant_connector):
    # Prepare entries
    e1 = Entry(
        content="Content A",
        metadata={"document_id": "doc1", "page_label": "45", "physical_page_index": 4},
    )
    e2 = Entry(
        content="Content B",
        metadata={"document_id": "doc1", "page_label": "46", "physical_page_index": 5},
    )
    e3 = Entry(
        content="Other Doc",
        metadata={"document_id": "doc2", "page_label": "1", "physical_page_index": 0},
    )

    await qdrant_connector.store(e1)
    await qdrant_connector.store(e2)
    await qdrant_connector.store(e3)

    # Search within doc1
    settings = QdrantSettings()
    filterable = settings.filterable_fields_dict()
    qfilter = make_filter(filterable, {"document_id": "doc1"})
    results = await qdrant_connector.search(
        "Content", query_filter=models.Filter(**qfilter)
    )
    assert any("Content A" in r.content or "Content B" in r.content for r in results)
    assert all(r.metadata.get("document_id") == "doc1" for r in results)

    # Search specific page index
    qfilter2 = make_filter(
        filterable, {"document_id": "doc1", "physical_page_index": 5}
    )
    results2 = await qdrant_connector.search(
        "Content", query_filter=models.Filter(**qfilter2)
    )
    assert len(results2) == 1
    assert results2[0].metadata.get("physical_page_index") == 5

    # Search by page_label
    qfilter3 = make_filter(filterable, {"page_label": "45"})
    results3 = await qdrant_connector.search(
        "Content", query_filter=models.Filter(**qfilter3)
    )
    assert len(results3) == 1
    assert results3[0].metadata.get("page_label") == "45"


@pytest.mark.asyncio
async def test_physical_page_index_edge_cases(qdrant_connector):
    # Prepare entries
    e1 = Entry(
        content="Page0",
        metadata={"document_id": "docx", "page_label": "1", "physical_page_index": 0},
    )
    e2 = Entry(
        content="Page1",
        metadata={"document_id": "docx", "page_label": "2", "physical_page_index": 1},
    )
    await qdrant_connector.store(e1)
    await qdrant_connector.store(e2)

    settings = QdrantSettings()
    filterable = settings.filterable_fields_dict()

    # physical_page_index==0 should return the first page
    q0 = make_filter(filterable, {"physical_page_index": 0})
    r0 = await qdrant_connector.search("Page", query_filter=models.Filter(**q0))
    assert any(r.metadata.get("physical_page_index") == 0 for r in r0)

    # Out-of-range page index returns empty
    q_oob = make_filter(filterable, {"physical_page_index": 999})
    r_oob = await qdrant_connector.search("Page", query_filter=models.Filter(**q_oob))
    assert len(r_oob) == 0

    # Combining document_id and page_index filters
    q_combo = make_filter(filterable, {"document_id": "docx", "physical_page_index": 1})
    r_combo = await qdrant_connector.search(
        "Page", query_filter=models.Filter(**q_combo)
    )
    assert len(r_combo) == 1
    assert r_combo[0].metadata.get("physical_page_index") == 1


def test_physical_page_index_schema_is_integer():
    from mcp_server_qdrant.server import mcp

    tools = asyncio.get_event_loop().run_until_complete(mcp.get_tools())
    find_tool = (
        tools.get("qdrant-find")
        if isinstance(tools, dict)
        else next((t for t in tools if getattr(t, "name", None) == "qdrant-find"), None)
    )
    assert find_tool is not None

    # Inspect parameters schema
    if hasattr(find_tool, "parameters"):
        props = find_tool.parameters.get("properties", {})
    else:
        props = {}

    phys_schema = props.get("physical_page_index")
    assert phys_schema is not None
    # schema may be of 'anyOf' form, ensure integer type present
    if "type" in phys_schema:
        assert phys_schema["type"] == "integer"
    else:
        anyof = phys_schema.get("anyOf", [])
        types = {s.get("type") for s in anyof if isinstance(s, dict)}
        assert "integer" in types


import asyncio

import pytest


@pytest.mark.asyncio
async def test_mcp_tool_schema_includes_pdf_filters():
    from mcp_server_qdrant.server import mcp

    # Support both FastMCP API names (`list_tools` or `get_tools`)
    tools_getter = getattr(mcp, "list_tools", None) or getattr(mcp, "get_tools", None)
    assert tools_getter is not None, "MCP server does not expose a tools listing method"
    tools_raw = await tools_getter()

    # FastMCP may return a dict mapping name->tool or an iterable of tool objects
    if isinstance(tools_raw, dict):
        find_tool = tools_raw.get("qdrant-find")
    else:
        tools = list(tools_raw)
        find_tool = next(
            (t for t in tools if getattr(t, "name", None) == "qdrant-find"), None
        )

    assert find_tool is not None, "qdrant-find tool not registered in MCP server"

    # Different FastMCP versions expose the input schema under different attributes
    if hasattr(find_tool, "parameters"):
        props = find_tool.parameters.get("properties", {})
    elif hasattr(find_tool, "inputSchema"):
        props = find_tool.inputSchema.get("properties", {})
    else:
        # Fallback: attempt to call schema() and inspect
        try:
            schema = find_tool.schema()
            props = schema.get("properties", {})
        except Exception:
            props = {}

    assert "document_id" in props
    assert "physical_page_index" in props
    assert "page_label" in props


@pytest.mark.asyncio
async def test_page_label_schema_and_behavior(qdrant_connector):
    """Validate page_label schema is string and behavior for different labels"""
    # Schema check
    from mcp_server_qdrant.server import mcp

    tools = await mcp.get_tools()
    find_tool = (
        tools.get("qdrant-find")
        if isinstance(tools, dict)
        else next((t for t in tools if getattr(t, "name", None) == "qdrant-find"), None)
    )
    assert find_tool is not None

    if hasattr(find_tool, "parameters"):
        props2 = find_tool.parameters.get("properties", {})
    else:
        props2 = {}

    label_schema = props2.get("page_label")
    assert label_schema is not None
    if "type" in label_schema:
        assert label_schema["type"] == "string"
    else:
        anyof = label_schema.get("anyOf", [])
        types = {s.get("type") for s in anyof if isinstance(s, dict)}
        assert "string" in types

    # Behavioral tests
    a = Entry(
        content="Roman",
        metadata={"document_id": "r", "page_label": "iv", "physical_page_index": 3},
    )
    b = Entry(
        content="Num",
        metadata={"document_id": "n", "page_label": "45", "physical_page_index": 44},
    )
    c = Entry(
        content="Spec",
        metadata={
            "document_id": "s",
            "page_label": "Appendix A",
            "physical_page_index": 120,
        },
    )

    await qdrant_connector.store(a)
    await qdrant_connector.store(b)
    await qdrant_connector.store(c)

    settings = QdrantSettings()
    filterable = settings.filterable_fields_dict()

    q_roman = make_filter(filterable, {"page_label": "iv"})
    r_roman = await qdrant_connector.search(
        "Roman", query_filter=models.Filter(**q_roman)
    )
    assert len(r_roman) == 1 and r_roman[0].metadata.get("page_label") == "iv"

    q_num = make_filter(filterable, {"page_label": "45"})
    r_num = await qdrant_connector.search("Num", query_filter=models.Filter(**q_num))
    assert len(r_num) == 1 and r_num[0].metadata.get("page_label") == "45"

    q_spec = make_filter(filterable, {"page_label": "Appendix A"})
    r_spec = await qdrant_connector.search("Spec", query_filter=models.Filter(**q_spec))
    assert len(r_spec) == 1 and r_spec[0].metadata.get("page_label") == "Appendix A"


@pytest.mark.asyncio
async def test_mcp_end_to_end_find_by_document_id():
    """End-to-end test: store entries via mcp.qdrant_connector and call qdrant-find tool"""
    from mcp_server_qdrant.server import mcp

    # Replace server connector with an in-memory connector for test isolation
    original_connector = mcp.qdrant_connector
    test_provider = FastEmbedProvider(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    test_collection = f"test_mcp_end_to_end_{uuid.uuid4().hex}"
    test_connector = QdrantConnector(
        qdrant_url=":memory:",
        qdrant_api_key=None,
        collection_name=test_collection,
        embedding_provider=test_provider,
    )
    mcp.qdrant_connector = test_connector

    try:
        # Store entries using the test connector
        e1 = Entry(
            content="E1",
            metadata={
                "document_id": "enddoc",
                "page_label": "1",
                "physical_page_index": 0,
            },
        )
        e2 = Entry(
            content="E2",
            metadata={
                "document_id": "enddoc",
                "page_label": "2",
                "physical_page_index": 1,
            },
        )
        await mcp.qdrant_connector.store(e1, collection_name=test_collection)
        await mcp.qdrant_connector.store(e2, collection_name=test_collection)

        # Call the function tool
        tools = await mcp.get_tools()
        find_tool = (
            tools.get("qdrant-find")
            if isinstance(tools, dict)
            else next(
                (t for t in tools if getattr(t, "name", None) == "qdrant-find"), None
            )
        )
        assert find_tool is not None

        # Invoke the tool's underlying function directly with a dummy Context to avoid run() requiring active context
        class DummyCtx:
            async def debug(self, *args, **kwargs):
                return None

        res = await find_tool.fn(
            DummyCtx(), query="E", collection_name=test_collection, document_id="enddoc"
        )
        assert isinstance(res, list)
        assert any("E1" in r or "E2" in r for r in res)
    finally:
        # Restore original connector to avoid side effects
        mcp.qdrant_connector = original_connector
