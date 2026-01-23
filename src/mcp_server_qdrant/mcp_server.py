import json
import logging
from typing import Annotated, Any, Optional

from fastmcp import Context, FastMCP
from pydantic import Field
from qdrant_client import models

from mcp_server_qdrant.common.filters import make_indexes
from mcp_server_qdrant.common.func_tools import make_partial_function
from mcp_server_qdrant.common.wrap_filters import wrap_filters
from mcp_server_qdrant.embeddings.base import EmbeddingProvider
from mcp_server_qdrant.embeddings.factory import create_embedding_provider
from mcp_server_qdrant.formatters import EntryFormatter, XMLEntryFormatter
from mcp_server_qdrant.qdrant import ArbitraryFilter, Entry, Metadata, QdrantConnector
from mcp_server_qdrant.settings import (
    ChunkingSettings,
    EmbeddingProviderSettings,
    QdrantSettings,
    ToolSettings,
)

logger = logging.getLogger(__name__)


# FastMCP is an alternative interface for declaring the capabilities
# of the server. Its API is based on FastAPI.
class QdrantMCPServer(FastMCP):
    """
    A MCP server for Qdrant.
    """

    def __init__(
        self,
        tool_settings: ToolSettings,
        qdrant_settings: QdrantSettings,
        embedding_provider_settings: Optional[EmbeddingProviderSettings] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        chunking_settings: Optional[ChunkingSettings] = None,
        entry_formatter: Optional[EntryFormatter] = None,
        name: str = "mcp-server-qdrant",
        instructions: str | None = None,
        **settings: Any,
    ):
        self.tool_settings = tool_settings
        self.qdrant_settings = qdrant_settings
        self.chunking_settings = chunking_settings or ChunkingSettings()
        self.entry_formatter = entry_formatter or XMLEntryFormatter()

        if embedding_provider_settings and embedding_provider:
            raise ValueError(
                "Cannot provide both embedding_provider_settings and embedding_provider"
            )

        if not embedding_provider_settings and not embedding_provider:
            raise ValueError(
                "Must provide either embedding_provider_settings or embedding_provider"
            )

        self.embedding_provider_settings: Optional[EmbeddingProviderSettings] = None
        self.embedding_provider: Optional[EmbeddingProvider] = None

        if embedding_provider_settings:
            self.embedding_provider_settings = embedding_provider_settings
            self.embedding_provider = create_embedding_provider(
                embedding_provider_settings
            )
        else:
            self.embedding_provider_settings = None
            self.embedding_provider = embedding_provider

        assert self.embedding_provider is not None, "Embedding provider is required"

        self.qdrant_connector = QdrantConnector(
            qdrant_settings.location,
            qdrant_settings.api_key,
            qdrant_settings.collection_name,
            self.embedding_provider,
            qdrant_settings.local_path,
            make_indexes(qdrant_settings.filterable_fields_dict()),
            enable_chunking=self.chunking_settings.enable_chunking,
            chunk_strategy=self.chunking_settings.chunk_strategy,
            max_chunk_size=self.chunking_settings.max_chunk_size,
            chunk_overlap=self.chunking_settings.chunk_overlap,
        )

        super().__init__(name=name, instructions=instructions, **settings)

        self.setup_tools()

    def format_entry(self, entry: Entry) -> str:
        """
        Format an entry using the configured formatter.
        Can be overridden in subclasses or customized via constructor injection.
        :param entry: Entry to format
        :return: Formatted string
        """
        return self.entry_formatter.format(entry)

    def _determine_storage_mode(self) -> str:
        """
        Determine the storage mode based on Qdrant settings.
        :return: Storage mode: "memory", "local", or "remote"
        """
        if self.qdrant_settings.local_path:
            return "local"
        elif (
            self.qdrant_settings.location
            and self.qdrant_settings.location != ":memory:"
        ):
            return "remote"
        return "memory"

    def _get_embedding_provider_info(self) -> tuple[str, str]:
        """
        Extract embedding provider type and model name.
        :return: Tuple of (provider_type, model_name)
        """
        provider_type = (
            self.embedding_provider_settings.provider_type.value
            if self.embedding_provider_settings
            else "unknown"
        )
        model_name = (
            self.embedding_provider_settings.model_name
            if self.embedding_provider_settings
            else "unknown"
        )
        return provider_type, model_name

    def _extract_filterable_fields(self) -> list[dict[str, Any]]:
        """
        Extract filterable field configurations as dictionaries.
        :return: List of filter field dictionaries
        """
        filters = []
        if self.qdrant_settings.filterable_fields:
            for field in self.qdrant_settings.filterable_fields:
                filters.append(
                    {
                        "name": field.name,
                        "type": field.field_type,
                        "description": field.description,
                        "condition": field.condition,
                    }
                )
        return filters

    def setup_tools(self):
        """
        Register the tools in the server.
        """

        async def store(
            ctx: Context,
            information: Annotated[str, Field(description="Text to store")],
            collection_name: Annotated[
                str, Field(description="The collection to store the information in")
            ],
            # The `metadata` parameter is defined as non-optional, but it can be None.
            # If we set it to be optional, some of the MCP clients, like Cursor, cannot
            # handle the optional parameter correctly.
            metadata: Annotated[
                Metadata | None,
                Field(
                    description="Extra metadata stored along with memorised information. Any json is accepted."
                ),
            ] = None,
        ) -> str:
            """
            Store some information in Qdrant.
            :param ctx: The context for the request.
            :param information: The information to store.
            :param metadata: JSON metadata to store with the information, optional.
            :param collection_name: The name of the collection to store the information in, optional. If not provided,
                                    the default collection is used.
            :return: A message indicating that the information was stored.
            """
            await ctx.debug(f"Storing information {information} in Qdrant")

            entry = Entry(content=information, metadata=metadata)

            await self.qdrant_connector.store(entry, collection_name=collection_name)
            if collection_name:
                return f"Remembered: {information} in collection {collection_name}"
            return f"Remembered: {information}"

        async def find(
            ctx: Context,
            query: Annotated[str, Field(description="What to search for")],
            collection_name: Annotated[
                str, Field(description="The collection to search in")
            ],
            query_filter: ArbitraryFilter | None = None,
        ) -> list[str] | None:
            """
            Find memories in Qdrant.
            :param ctx: The context for the request.
            :param query: The query to use for the search.
            :param collection_name: The name of the collection to search in, optional. If not provided,
                                    the default collection is used.
            :param query_filter: The filter to apply to the query.
            :return: A list of entries found or None.
            """

            # Log query_filter
            await ctx.debug(f"Query filter: {query_filter}")

            query_filter = models.Filter(**query_filter) if query_filter else None

            await ctx.debug(f"Finding results for query {query}")

            entries = await self.qdrant_connector.search(
                query,
                collection_name=collection_name,
                limit=self.qdrant_settings.search_limit,
                query_filter=query_filter,
            )
            if not entries:
                return None
            content = [
                f"Results for the query '{query}'",
            ]
            for entry in entries:
                content.append(self.format_entry(entry))
            return content

        find_foo = find
        store_foo = store

        filterable_conditions = (
            self.qdrant_settings.filterable_fields_dict_with_conditions()
        )

        # Diagnostic logging to help debug missing filter exposure in MCP schema
        logger.info(
            "Filterable fields: %s",
            self.qdrant_settings.filterable_fields,
        )
        logger.info(
            "Filterable conditions count: %d",
            len(filterable_conditions),
        )
        logger.info("Filterable conditions: %s", filterable_conditions)

        if len(filterable_conditions) > 0:
            find_foo = wrap_filters(find_foo, filterable_conditions)
        elif not self.qdrant_settings.allow_arbitrary_filter:
            find_foo = make_partial_function(find_foo, {"query_filter": None})

        if self.qdrant_settings.collection_name:
            find_foo = make_partial_function(
                find_foo, {"collection_name": self.qdrant_settings.collection_name}
            )
            store_foo = make_partial_function(
                store_foo, {"collection_name": self.qdrant_settings.collection_name}
            )

        self.tool(
            find_foo,
            name="qdrant-find",
            description=self.tool_settings.tool_find_description,
        )

        if not self.qdrant_settings.read_only:
            self.tool(
                store_foo,
                name="qdrant-store",
                description=self.tool_settings.tool_store_description,
            )

        async def get_schema(ctx: Context) -> str:
            """
            Get the current server configuration schema.
            Returns JSON with collection name, embedding provider details, filterable fields, and RAG settings.
            :param ctx: The context for the request.
            :return: JSON string containing the server schema.
            """
            await ctx.debug("Retrieving server schema configuration")

            storage_mode = self._determine_storage_mode()
            provider_type, model_name = self._get_embedding_provider_info()
            vector_size = self.embedding_provider.get_vector_size()
            vector_name = self.embedding_provider.get_vector_name() or None
            filters = self._extract_filterable_fields()

            schema = {
                "collection_name": self.qdrant_settings.collection_name or "default",
                "storage_mode": storage_mode,
                "embedding": {
                    "provider": provider_type,
                    "model": model_name,
                    "vector_size": vector_size,
                    "vector_name": vector_name,
                },
                "filters": filters,
                "rag_settings": {
                    "chunking_enabled": self.chunking_settings.enable_chunking,
                    "pdf_ingestion_enabled": True,
                },
            }

            return json.dumps(schema, indent=2)

        self.tool(
            get_schema,
            name="qdrant-get-schema",
            description="Get the current server configuration schema including collection name, embedding provider, filterable fields, and RAG settings. Use this to discover what filters are available before searching.",
        )
