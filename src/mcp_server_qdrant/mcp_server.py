import json
import logging
from typing import Annotated, Any, Literal, Optional

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

QUERY_MODE_DEFAULTS: dict[str, dict[str, int | float | None]] = {
    "balanced": {"limit": 10, "min_score": None},
    "precision": {"limit": 5, "min_score": 0.45},
    "recall": {"limit": 15, "min_score": 0.2},
}


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

    def _filter_allowed_collections(self, collections: list[str]) -> list[str]:
        """Apply collection allowlist rules when configured."""
        if not self.qdrant_settings.allowed_collections:
            return collections
        allowed = set(self.qdrant_settings.allowed_collections)
        return [collection for collection in collections if collection in allowed]

    def _enforce_collection_access(
        self,
        collection_name: str,
        *,
        destructive: bool = False,
    ) -> None:
        """Validate collection access for mutable and destructive operations."""
        if (
            self.qdrant_settings.allowed_collections
            and collection_name not in self.qdrant_settings.allowed_collections
        ):
            raise ValueError(
                f"Collection '{collection_name}' is not allowed by QDRANT_ALLOWED_COLLECTIONS."
            )

        if destructive and not self.qdrant_settings.allow_destructive_operations:
            raise ValueError(
                "Destructive operations are disabled. Set "
                "QDRANT_ALLOW_DESTRUCTIVE_OPERATIONS=true to enable collection deletion."
            )

    def _resolve_collection_name(self, collection_name: str | None) -> str:
        """Resolve an optional collection name against the configured default."""
        resolved = collection_name or self.qdrant_settings.collection_name
        if not resolved:
            raise ValueError(
                "No collection specified. Provide collection_name or configure COLLECTION_NAME."
            )
        return resolved

    def _resolve_query_mode(
        self,
        query_mode: str,
        limit: int,
        min_score: float | None,
    ) -> tuple[int, float | None]:
        """Resolve limit and score threshold from the selected query mode."""
        mode_defaults = QUERY_MODE_DEFAULTS[query_mode]
        resolved_limit = limit
        if limit == QUERY_MODE_DEFAULTS["balanced"]["limit"]:
            resolved_limit = int(mode_defaults["limit"] or limit)

        resolved_min_score = min_score
        if min_score is None:
            resolved_min_score = mode_defaults["min_score"]

        return resolved_limit, resolved_min_score

    def _build_schema_examples(self) -> dict[str, Any]:
        """Provide concrete examples so MCP clients can discover common flows."""
        collection_name = self.qdrant_settings.collection_name or "<collection_name>"
        examples: dict[str, Any] = {
            "semantic_search": {
                "tool": "qdrant-find",
                "arguments": {
                    "query": "service operations strategy",
                    "collection_name": collection_name,
                    "query_mode": "balanced",
                },
            },
            "precision_search": {
                "tool": "qdrant-find",
                "arguments": {
                    "query": "queueing theory",
                    "collection_name": collection_name,
                    "query_mode": "precision",
                },
            },
            "keyword_search": {
                "tool": "qdrant-keyword-search",
                "arguments": {
                    "keyword": "Stichprobe",
                    "collection_name": collection_name,
                    "limit": 5,
                },
            },
            "list_documents": {
                "tool": "qdrant-list-documents",
                "arguments": {"collection_name": collection_name},
            },
            "list_chapters": {
                "tool": "qdrant-list-chapters",
                "arguments": {"collection_name": collection_name},
            },
            "inventory": {
                "tool": "qdrant-get-inventory",
                "arguments": {"collection_name": collection_name},
            },
            "verify_ingestion": {
                "tool": "qdrant-verify-ingestion",
                "arguments": {"collection_name": collection_name},
            },
        }

        filter_names = {field["name"] for field in self._extract_filterable_fields()}
        if "document_id" in filter_names:
            examples["document_lookup"] = {
                "tool": "qdrant-find",
                "arguments": {
                    "query": "Kapazitatsplanung",
                    "collection_name": collection_name,
                    "document_id": "operations-management.pdf",
                    "query_mode": "precision",
                },
            }
        if "page_label" in filter_names:
            examples["page_lookup"] = {
                "tool": "qdrant-find",
                "arguments": {
                    "query": "Lineare Regression",
                    "collection_name": collection_name,
                    "page_label": "45",
                    "query_mode": "precision",
                },
            }

        return examples

    def setup_tools(self):
        """
        Register the tools in the server.
        """

        async def store(
            ctx: Context,
            information: Annotated[str, Field(description="Text to store")],
            collection_name: Annotated[
                str | None,
                Field(
                    description=(
                        "The collection to store the information in "
                        "(optional when COLLECTION_NAME is configured)"
                    )
                ),
            ] = None,
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

            collection_name = self._resolve_collection_name(collection_name)
            self._enforce_collection_access(collection_name)

            entry = Entry(content=information, metadata=metadata)

            await self.qdrant_connector.store(entry, collection_name=collection_name)
            return f"Remembered: {information} in collection {collection_name}"

        async def find(
            ctx: Context,
            query: Annotated[str, Field(description="What to search for")],
            collection_name: Annotated[
                str | None,
                Field(
                    description=(
                        "The collection to search in "
                        "(optional when COLLECTION_NAME is configured)"
                    )
                ),
            ] = None,
            query_mode: Annotated[
                Literal["balanced", "precision", "recall"],
                Field(
                    default="balanced",
                    description=(
                        "Retrieval preset: balanced for general semantic search, "
                        "precision for fewer higher-confidence results, recall for broader exploration."
                    ),
                ),
            ] = "balanced",
            query_filter: ArbitraryFilter | None = None,
            limit: Annotated[
                int,
                Field(
                    default=10,
                    ge=1,
                    le=50,
                    description="Number of results to return (1–50, default 10)",
                ),
            ] = 10,
            min_score: Annotated[
                float | None,
                Field(
                    default=None,
                    ge=0.0,
                    le=1.0,
                    description=(
                        "Minimum similarity score (0.0–1.0). "
                        "Filters out low-quality matches. "
                        "Typical useful range: 0.35–0.55 for MiniLM."
                    ),
                ),
            ] = None,
        ) -> list[str] | None:
            """
            Find memories in Qdrant.
            :param ctx: The context for the request.
            :param query: The query to use for the search.
            :param collection_name: The name of the collection to search in, optional. If not provided,
                                    the default collection is used.
            :param query_filter: The filter to apply to the query.
            :param limit: Maximum number of results to return.
            :param min_score: Minimum similarity score threshold.
            :return: A list of entries found or None.
            """

            # Log query_filter
            await ctx.debug(f"Query filter: {query_filter}")

            collection_name = self._resolve_collection_name(collection_name)
            self._enforce_collection_access(collection_name)

            query_filter = models.Filter(**query_filter) if query_filter else None
            resolved_limit, resolved_min_score = self._resolve_query_mode(
                query_mode,
                limit,
                min_score,
            )

            await ctx.debug(f"Finding results for query {query}")

            entries = await self.qdrant_connector.search(
                query,
                collection_name=collection_name,
                limit=resolved_limit,
                query_filter=query_filter,
                score_threshold=resolved_min_score,
            )
            if not entries:
                return None
            scores = [e.score for e in entries if e.score is not None]
            score_summary = ""
            if scores:
                score_summary = f" | scores: {min(scores):.3f}–{max(scores):.3f}"
            content = [
                f"Results for '{query}': {len(entries)} result(s){score_summary}",
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
                "collections": await self.qdrant_connector.get_collections_info(),
                "query_modes": QUERY_MODE_DEFAULTS,
                "examples": self._build_schema_examples(),
                "policies": {
                    "allowed_collections": self.qdrant_settings.allowed_collections,
                    "allow_destructive_operations": self.qdrant_settings.allow_destructive_operations,
                },
            }

            return json.dumps(schema, indent=2)

        self.tool(
            get_schema,
            name="qdrant-get-schema",
            description="Get the current server configuration schema including collection name, embedding provider, filterable fields, and RAG settings. Use this to discover what filters are available before searching.",
        )

        if not self.qdrant_settings.read_only:

            async def ingest_pdf(
                ctx: Context,
                file_path: Annotated[
                    str, Field(description="Absolute path to the PDF file")
                ],
                collection_name: Annotated[
                    str | None,
                    Field(
                        description=(
                            "Target collection name "
                            "(optional when COLLECTION_NAME is configured)"
                        )
                    ),
                ] = None,
                document_id: Annotated[
                    str | None,
                    Field(
                        description="Document identifier (defaults to filename stem)"
                    ),
                ] = None,
                extra_metadata: Annotated[
                    Metadata | None,
                    Field(
                        description=(
                            "Additional metadata stored with every page, e.g. "
                            '{"apa_zitation": "Döring (2023)", "kurs": "Forschungsmethoden", '
                            '"language": "de", "content_type": "textbook"}'
                        )
                    ),
                ] = None,
            ) -> str:
                """
                Ingest a PDF file page-by-page into the knowledge base.
                Each page becomes a separate searchable entry with page metadata.
                :param ctx: The context for the request.
                :param file_path: Absolute path to the PDF file.
                :param collection_name: Target collection name.
                :param document_id: Optional document identifier.
                :return: Summary of ingestion results.
                """
                import os
                from pathlib import Path

                from mcp_server_qdrant.pdf_extractor import PDFPageExtractor

                pdf_path = Path(file_path)

                # Path traversal protection
                allowed_base = os.getenv("QDRANT_INGEST_BASE_PATH", "")
                if allowed_base:
                    resolved = str(pdf_path.resolve())
                    if not resolved.startswith(
                        str(Path(allowed_base).resolve())
                    ):
                        return (
                            f"Error: Path outside allowed directory: "
                            f"{allowed_base}"
                        )

                if not pdf_path.exists():
                    return f"Error: File not found: {file_path}"
                if not pdf_path.suffix.lower() == ".pdf":
                    return f"Error: Not a PDF file: {file_path}"

                doc_id = document_id or pdf_path.stem

                collection_name = self._resolve_collection_name(collection_name)
                self._enforce_collection_access(collection_name)

                await ctx.debug(
                    f"Ingesting PDF '{pdf_path.name}' into '{collection_name}'"
                )

                extractor = PDFPageExtractor(str(pdf_path))
                pages = await extractor.extract_all_pages()

                entries: list[Entry] = []
                for content, physical_index, page_label in pages:
                    if not content.strip():
                        continue
                    page_metadata: dict = {
                        "document_id": doc_id,
                        "physical_page_index": physical_index,
                        "page_label": page_label,
                        "total_pages": len(pages),
                        "filename": pdf_path.name,
                    }
                    if extra_metadata:
                        page_metadata.update(extra_metadata)
                    entry = Entry(
                        content=content,
                        metadata=page_metadata,
                    )
                    entries.append(entry)

                result = await self.qdrant_connector.upsert_document_entries(
                    entries,
                    collection_name=collection_name,
                    document_id=doc_id,
                )

                return (
                    f"Processed {len(entries)}/{len(pages)} pages from '{pdf_path.name}' "
                    f"into '{collection_name}' ({result['mode']}, stored={result['stored']}, "
                    f"updated={result['updated']}, deleted={result['deleted']})"
                )

            self.tool(
                ingest_pdf,
                name="qdrant-ingest-pdf",
                description=(
                    "Ingest a PDF file page-by-page into the knowledge base. "
                    "Each page is stored as a separate searchable entry with "
                    "page number metadata."
                ),
            )

        async def list_documents(
            ctx: Context,
            collection_name: Annotated[
                str | None,
                Field(description="The collection to inspect (optional when COLLECTION_NAME is configured)"),
            ] = None,
        ) -> str:
            """
            List all ingested documents in a collection with page counts and metadata.
            :param ctx: The context for the request.
            :param collection_name: The collection to inspect.
            :return: Formatted summary of all documents.
            """
            collection_name = self._resolve_collection_name(collection_name)
            self._enforce_collection_access(collection_name)
            await ctx.debug(f"Listing documents in collection '{collection_name}'")
            docs = await self.qdrant_connector.list_documents(
                collection_name=collection_name
            )
            if not docs:
                return f"No documents found in collection '{collection_name}'."

            lines = [
                f"Documents in '{collection_name}' ({len(docs)} document(s)):",
            ]
            for doc in docs:
                doc_id = doc["document_id"]
                filename = doc.get("filename", "")
                page_count = doc["page_count"]
                total_pages = doc.get("total_pages", 0)
                apa = doc.get("apa_zitation", "")

                line = f"  • {doc_id}"
                if filename and filename != doc_id:
                    line += f" ({filename})"
                line += f" — {page_count} chunks indexed"
                if total_pages and total_pages != page_count:
                    line += f" / {total_pages} total pages"
                if apa:
                    line += f"\n    Citation: {apa[:120]}"
                lines.append(line)

            return "\n".join(lines)

        self.tool(
            list_documents,
            name="qdrant-list-documents",
            description=(
                "List all ingested documents in the collection with page counts and metadata. "
                "Use this to discover what textbooks, slides, or notes are in the knowledge base."
            ),
        )

        async def keyword_search(
            ctx: Context,
            keyword: Annotated[
                str,
                Field(
                    description=(
                        "Word or phrase to search for in the full text. "
                        "Case-insensitive. Use for exact terms, author names, "
                        "or specific concepts you know appear verbatim in the text."
                    )
                ),
            ],
            collection_name: Annotated[
                str | None,
                Field(description="The collection to search in (optional when COLLECTION_NAME is configured)"),
            ] = None,
            document_id: Annotated[
                str | None,
                Field(description="Restrict search to a specific document (optional)"),
            ] = None,
            limit: Annotated[
                int,
                Field(description="Maximum number of results to return (default 10)"),
            ] = 10,
        ) -> list[str] | None:
            """
            Full-text keyword search in the knowledge base.
            Finds pages that contain the exact keyword/phrase (case-insensitive).
            Complements semantic search: use when looking for specific terms,
            author names, method names, or technical vocabulary.
            :param ctx: The context for the request.
            :param keyword: The word or phrase to find.
            :param collection_name: The collection to search in.
            :param document_id: Optionally restrict to a specific document.
            :param limit: Maximum number of results.
            :return: List of matching entries or None.
            """
            collection_name = self._resolve_collection_name(collection_name)
            self._enforce_collection_access(collection_name)
            await ctx.debug(f"Keyword search: '{keyword}' in '{collection_name}'")
            entries = await self.qdrant_connector.keyword_search(
                keyword,
                collection_name=collection_name,
                document_id=document_id,
                limit=limit,
            )
            if not entries:
                return None
            content = [f"Keyword search for '{keyword}': {len(entries)} result(s)"]
            for entry in entries:
                content.append(self.format_entry(entry))
            return content

        self.tool(
            keyword_search,
            name="qdrant-keyword-search",
            description=(
                "Full-text keyword search in the knowledge base. "
                "Finds pages containing exact words or phrases (case-insensitive). "
                "Use for specific terms, author names, or technical vocabulary. "
                "Complements qdrant-find (semantic search)."
            ),
        )

        async def list_chapters(
            ctx: Context,
            collection_name: Annotated[
                str | None,
                Field(description="The collection to inspect (optional when COLLECTION_NAME is configured)"),
            ] = None,
            document_id: Annotated[
                str | None,
                Field(description="Restrict to a specific document (optional)"),
            ] = None,
        ) -> str:
            """
            List all chapters/sections from the document bookmarks (table of contents).
            Shows chapter titles with their starting page numbers.
            :param ctx: The context for the request.
            :param collection_name: The collection to inspect.
            :param document_id: Optionally restrict to a specific document.
            :return: Formatted table of contents.
            """
            collection_name = self._resolve_collection_name(collection_name)
            self._enforce_collection_access(collection_name)
            await ctx.debug(f"Listing chapters in '{collection_name}'")
            chapters = await self.qdrant_connector.list_chapters(
                collection_name=collection_name,
                document_id=document_id,
            )
            if not chapters:
                return "No chapter information found. Documents may not have bookmark metadata."

            lines = [f"Table of Contents ({len(chapters)} chapter(s)):"]
            prev_doc = None
            for ch in chapters:
                doc_id = ch.get("document_id", "")
                if doc_id != prev_doc:
                    lines.append(f"\n  [{doc_id}]")
                    prev_doc = doc_id
                page = ch["first_page_label"]
                title = ch["chapter_title"]
                lines.append(f"    p.{page:>6}  {title}")

            return "\n".join(lines)

        self.tool(
            list_chapters,
            name="qdrant-list-chapters",
            description=(
                "List all chapters and sections from the ingested documents "
                "(extracted from PDF bookmarks). Shows the table of contents "
                "with page numbers. Use before searching to understand document structure."
            ),
        )

        async def get_inventory(
            ctx: Context,
            collection_name: Annotated[
                str | None,
                Field(description="The collection to inspect (optional when COLLECTION_NAME is configured)"),
            ] = None,
            document_id: Annotated[
                str | None,
                Field(description="Restrict inventory to a specific document (optional)"),
            ] = None,
        ) -> str:
            """Return a structured inventory of documents, chapters, and citation metadata."""
            collection_name = self._resolve_collection_name(collection_name)
            self._enforce_collection_access(collection_name)
            await ctx.debug(f"Building inventory for '{collection_name}'")
            inventory = await self.qdrant_connector.get_inventory(
                collection_name=collection_name,
                document_id=document_id,
            )
            return json.dumps(inventory, ensure_ascii=False, indent=2)

        self.tool(
            get_inventory,
            name="qdrant-get-inventory",
            description=(
                "Return a structured inventory of documents, chapters, page ranges, and citation metadata. "
                "Use this for textbook validation, syllabus mapping, and retrieval planning."
            ),
        )

        async def verify_ingestion(
            ctx: Context,
            collection_name: Annotated[
                str | None,
                Field(description="The collection to verify (optional when COLLECTION_NAME is configured)"),
            ] = None,
            document_id: Annotated[
                str | None,
                Field(description="Restrict verification to a specific document (optional)"),
            ] = None,
        ) -> str:
            """Check whether an ingested document exposes the metadata needed for citation-rich retrieval."""
            collection_name = self._resolve_collection_name(collection_name)
            self._enforce_collection_access(collection_name)
            await ctx.debug(f"Verifying ingestion quality for '{collection_name}'")
            verification = await self.qdrant_connector.verify_ingestion(
                collection_name=collection_name,
                document_id=document_id,
            )
            return json.dumps(verification, ensure_ascii=False, indent=2)

        self.tool(
            verify_ingestion,
            name="qdrant-verify-ingestion",
            description=(
                "Validate ingestion quality for one collection or document, including chapter coverage, "
                "book-page metadata, section-header availability, and warnings for legacy fallback cases."
            ),
        )

        async def find_all(
            ctx: Context,
            query: Annotated[
                str,
                Field(description="Search query across all collections"),
            ],
            collection_names: Annotated[
                list[str] | None,
                Field(
                    description=(
                        "Optional list of collection names to search. "
                        "If omitted, all accessible collections are searched."
                    )
                ),
            ] = None,
            query_mode: Annotated[
                Literal["balanced", "precision", "recall"],
                Field(description="Retrieval preset used for each collection"),
            ] = "balanced",
            limit: Annotated[
                int,
                Field(description="Max results per collection"),
            ] = 3,
            min_score: Annotated[
                float | None,
                Field(
                    default=None,
                    ge=0.0,
                    le=1.0,
                    description="Optional minimum similarity score for all collections.",
                ),
            ] = None,
        ) -> list[str] | None:
            """
            Search across all collections in the Qdrant server.
            :param ctx: The context for the request.
            :param query: The search query.
            :param collection_names: Optional collection subset to search.
            :param limit: Max results per collection.
            :return: Combined results from all collections.
            """
            if collection_names:
                for collection_name in collection_names:
                    self._enforce_collection_access(collection_name)
                collections = collection_names
            else:
                collections = self._filter_allowed_collections(
                    await self.qdrant_connector.get_collection_names()
                )
            if not collections:
                return None

            resolved_limit, resolved_min_score = self._resolve_query_mode(
                query_mode,
                limit,
                min_score,
            )

            await ctx.debug(
                f"Searching '{query}' across {len(collections)} collections"
            )

            aggregated_entries: list[Entry] = []
            for coll in collections:
                entries = await self.qdrant_connector.search(
                    query,
                    collection_name=coll,
                    limit=resolved_limit,
                    score_threshold=resolved_min_score,
                )
                for entry in entries:
                    entry.metadata = dict(entry.metadata or {})
                    entry.metadata["_collection"] = coll
                    aggregated_entries.append(entry)

            if not aggregated_entries:
                return None

            aggregated_entries.sort(
                key=lambda entry: (
                    entry.score is not None,
                    entry.score if entry.score is not None else float("-inf"),
                ),
                reverse=True,
            )

            scores = [entry.score for entry in aggregated_entries if entry.score is not None]
            score_summary = ""
            if scores:
                score_summary = f" | scores: {min(scores):.3f}–{max(scores):.3f}"

            all_results: list[str] = [
                (
                    f"Results for '{query}' across {len(collections)} collections: "
                    f"{len(aggregated_entries)} result(s){score_summary}"
                ),
            ]
            for entry in aggregated_entries:
                all_results.append(self.format_entry(entry))
            return all_results

        self.tool(
            find_all,
            name="qdrant-find-all",
            description=(
                "Search across ALL collections in the knowledge base. "
                "Use when you need to find content across multiple courses "
                "or document sets. Optionally restrict the search to an explicit "
                "list of collections. Results are globally ranked by score."
            ),
        )

        async def list_collections(ctx: Context) -> str:
            """List all accessible collections with their statistics."""
            await ctx.debug("Listing collections")
            collections = self._filter_allowed_collections(
                await self.qdrant_connector.get_collections_info()
            )
            if not collections:
                return "No collections found."

            lines = [f"Collections ({len(collections)} total):"]
            for collection in collections:
                lines.append(
                    (
                        f"  • {collection['name']} — {collection['points_count']} points, "
                        f"{collection['vectors_count']} vectors, status={collection['status']}"
                    )
                )
            return "\n".join(lines)

        self.tool(
            list_collections,
            name="qdrant-list-collections",
            description="List all accessible collections with point counts and status.",
        )

        if not self.qdrant_settings.read_only:

            async def create_collection(
                ctx: Context,
                collection_name: Annotated[
                    str,
                    Field(description="Collection name to create"),
                ],
            ) -> str:
                """Create an empty collection using the active embedding configuration."""
                self._enforce_collection_access(collection_name)
                await ctx.debug(f"Creating collection '{collection_name}'")
                created = await self.qdrant_connector.create_collection(collection_name)
                if created:
                    return f"Created collection '{collection_name}'."
                return f"Collection '{collection_name}' already exists."

            async def delete_collection(
                ctx: Context,
                collection_name: Annotated[
                    str,
                    Field(description="Collection name to delete"),
                ],
            ) -> str:
                """Delete a collection when destructive operations are enabled."""
                self._enforce_collection_access(collection_name, destructive=True)
                await ctx.debug(f"Deleting collection '{collection_name}'")
                deleted = await self.qdrant_connector.delete_collection(collection_name)
                if deleted:
                    return f"Deleted collection '{collection_name}'."
                return f"Collection '{collection_name}' does not exist."

            self.tool(
                create_collection,
                name="qdrant-create-collection",
                description="Create a collection using the active vector configuration.",
            )

            self.tool(
                delete_collection,
                name="qdrant-delete-collection",
                description=(
                    "Delete a collection. Requires QDRANT_ALLOW_DESTRUCTIVE_OPERATIONS=true."
                ),
            )

            async def delete_document(
                ctx: Context,
                document_id: Annotated[
                    str,
                    Field(description="Document identifier to delete"),
                ],
                collection_name: Annotated[
                    str | None,
                    Field(
                        description=(
                            "Collection containing the document "
                            "(optional when COLLECTION_NAME is configured)"
                        )
                    ),
                ] = None,
            ) -> str:
                """Delete all points associated with a document identifier."""
                collection_name = self._resolve_collection_name(collection_name)
                self._enforce_collection_access(collection_name, destructive=True)
                await ctx.debug(
                    f"Deleting document '{document_id}' from '{collection_name}'"
                )
                deleted = await self.qdrant_connector.delete_document(
                    document_id,
                    collection_name=collection_name,
                )
                return (
                    f"Deleted {deleted} point(s) for document '{document_id}' from "
                    f"'{collection_name}'."
                )

            async def delete_by_filter(
                ctx: Context,
                collection_name: Annotated[
                    str | None,
                    Field(
                        description=(
                            "Collection to delete from "
                            "(optional when COLLECTION_NAME is configured)"
                        )
                    ),
                ] = None,
                query_filter: ArbitraryFilter | None = None,
            ) -> str:
                """Delete points selected by metadata filters."""
                collection_name = self._resolve_collection_name(collection_name)
                self._enforce_collection_access(collection_name, destructive=True)
                if not query_filter:
                    raise ValueError(
                        "At least one filter is required for qdrant-delete-by-filter."
                    )

                await ctx.debug(f"Deleting by filter in '{collection_name}'")
                deleted = await self.qdrant_connector.delete_by_filter(
                    collection_name=collection_name,
                    query_filter=models.Filter(**query_filter),
                )
                return f"Deleted {deleted} point(s) from '{collection_name}'."

            delete_by_filter_foo = delete_by_filter
            if len(filterable_conditions) > 0:
                delete_by_filter_foo = wrap_filters(
                    delete_by_filter_foo,
                    filterable_conditions,
                )
            elif not self.qdrant_settings.allow_arbitrary_filter:
                delete_by_filter_foo = make_partial_function(
                    delete_by_filter_foo,
                    {"query_filter": None},
                )

            self.tool(
                delete_document,
                name="qdrant-delete-document",
                description=(
                    "Delete all chunks/pages for a document_id. Requires "
                    "QDRANT_ALLOW_DESTRUCTIVE_OPERATIONS=true."
                ),
            )

            self.tool(
                delete_by_filter_foo,
                name="qdrant-delete-by-filter",
                description=(
                    "Delete points by metadata filter. Requires at least one filter and "
                    "QDRANT_ALLOW_DESTRUCTIVE_OPERATIONS=true."
                ),
            )

            async def replace_document(
                ctx: Context,
                information: Annotated[
                    str,
                    Field(description="Full document text to create or replace"),
                ],
                document_id: Annotated[
                    str,
                    Field(description="Stable document identifier"),
                ],
                collection_name: Annotated[
                    str | None,
                    Field(
                        description=(
                            "Collection containing the document "
                            "(optional when COLLECTION_NAME is configured)"
                        )
                    ),
                ] = None,
                metadata: Annotated[
                    Metadata | None,
                    Field(
                        description=(
                            "Metadata stored for the document, for example course_id, "
                            "content_type, language, or chapter information."
                        )
                    ),
                ] = None,
            ) -> str:
                """Create or replace a document as an idempotent upsert operation."""
                collection_name = self._resolve_collection_name(collection_name)
                self._enforce_collection_access(collection_name)
                await ctx.debug(
                    f"Replacing or creating document '{document_id}' in '{collection_name}'"
                )

                result = await self.qdrant_connector.upsert_document_entries(
                    [Entry(content=information, metadata=metadata)],
                    collection_name=collection_name,
                    document_id=document_id,
                )
                return (
                    f"Document '{document_id}' in '{collection_name}': {result['mode']} "
                    f"(stored={result['stored']}, updated={result['updated']}, deleted={result['deleted']})"
                )

            async def update_document_metadata(
                ctx: Context,
                document_id: Annotated[
                    str,
                    Field(description="Document identifier to update"),
                ],
                metadata: Annotated[
                    Metadata,
                    Field(description="Metadata keys and values to merge into the document"),
                ],
                collection_name: Annotated[
                    str | None,
                    Field(
                        description=(
                            "Collection containing the document "
                            "(optional when COLLECTION_NAME is configured)"
                        )
                    ),
                ] = None,
            ) -> str:
                """Update metadata for all chunks/pages of a document without re-embedding."""
                collection_name = self._resolve_collection_name(collection_name)
                self._enforce_collection_access(collection_name)
                await ctx.debug(
                    f"Updating metadata for document '{document_id}' in '{collection_name}'"
                )
                updated = await self.qdrant_connector.update_document_metadata(
                    document_id,
                    metadata,
                    collection_name=collection_name,
                )
                return (
                    f"Updated metadata for {updated} point(s) in document '{document_id}' "
                    f"within '{collection_name}'."
                )

            self.tool(
                replace_document,
                name="qdrant-replace-document",
                description=(
                    "Create or replace a document idempotently. Unchanged content updates metadata only; "
                    "changed content is reindexed."
                ),
            )

            self.tool(
                update_document_metadata,
                name="qdrant-update-document-metadata",
                description=(
                    "Update metadata for all chunks/pages of a document without re-embedding the content."
                ),
            )
