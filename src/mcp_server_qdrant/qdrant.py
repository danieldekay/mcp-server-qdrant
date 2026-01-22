import logging
import uuid
from typing import Any

from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient, models

from mcp_server_qdrant.constants import PDFMetadataKeys
from mcp_server_qdrant.embeddings.base import EmbeddingProvider
from mcp_server_qdrant.settings import METADATA_PATH

logger = logging.getLogger(__name__)

# Import chunking only if enabled
try:
    from mcp_server_qdrant.chunking import ChunkStrategy, DocumentChunker

    CHUNKING_AVAILABLE = True
except ImportError:
    CHUNKING_AVAILABLE = False
    logger.warning(
        "Chunking not available. Install nltk and tiktoken for RAG features."
    )

Metadata = dict[str, Any]
ArbitraryFilter = dict[str, Any]


class Entry(BaseModel):
    """
    A single entry in the Qdrant collection.
    """

    content: str
    metadata: Metadata | None = None


class PDFPageEntry(Entry):
    """
    A specialized entry for PDF pages with explicit page metadata.
    """

    physical_page_index: int
    page_label: str
    document_id: str
    total_pages: int

    def to_entry(self) -> Entry:
        """Convert to a standard Entry with metadata mapped correctly."""
        metadata = self.metadata or {}
        metadata.update(
            {
                PDFMetadataKeys.PHYSICAL_PAGE_INDEX: self.physical_page_index,
                PDFMetadataKeys.PAGE_LABEL: self.page_label,
                PDFMetadataKeys.DOCUMENT_ID: self.document_id,
                PDFMetadataKeys.TOTAL_PAGES: self.total_pages,
            }
        )
        return Entry(content=self.content, metadata=metadata)


class QdrantConnector:
    """
    Encapsulates the connection to a Qdrant server and all the methods to interact with it.
    :param qdrant_url: The URL of the Qdrant server.
    :param qdrant_api_key: The API key to use for the Qdrant server.
    :param collection_name: The name of the default collection to use. If not provided, each tool will require
                            the collection name to be provided.
    :param embedding_provider: The embedding provider to use.
    :param qdrant_local_path: The path to the storage directory for the Qdrant client, if local mode is used.
    """

    def __init__(
        self,
        qdrant_url: str | None,
        qdrant_api_key: str | None,
        collection_name: str | None,
        embedding_provider: EmbeddingProvider,
        qdrant_local_path: str | None = None,
        field_indexes: dict[str, models.PayloadSchemaType] | None = None,
        enable_chunking: bool = False,
        chunk_strategy: str = "semantic",
        max_chunk_size: int = 512,
        chunk_overlap: int = 50,
    ):
        self._qdrant_url = qdrant_url.rstrip("/") if qdrant_url else None
        self._qdrant_api_key = qdrant_api_key
        self._default_collection_name = collection_name
        self._embedding_provider = embedding_provider
        self._client = AsyncQdrantClient(
            location=qdrant_url, api_key=qdrant_api_key, path=qdrant_local_path
        )
        self._field_indexes = field_indexes

        # Initialize chunker if enabled
        self._enable_chunking = enable_chunking and CHUNKING_AVAILABLE
        self._chunker = None
        if self._enable_chunking:
            try:
                strategy = ChunkStrategy(chunk_strategy)
                self._chunker = DocumentChunker(
                    strategy=strategy,
                    max_chunk_size=max_chunk_size,
                    chunk_overlap=chunk_overlap,
                )
                logger.info(
                    f"Document chunking enabled: {chunk_strategy}, max_size={max_chunk_size}, overlap={chunk_overlap}"
                )
            except Exception as e:
                logger.error(f"Failed to initialize chunker: {e}")
                self._enable_chunking = False

    async def get_collection_names(self) -> list[str]:
        """
        Get the names of all collections in the Qdrant server.
        :return: A list of collection names.
        """
        response = await self._client.get_collections()
        return [collection.name for collection in response.collections]

    async def store(self, entry: Entry, *, collection_name: str | None = None):
        """
        Store some information in the Qdrant collection, along with the specified metadata.
        If chunking is enabled, the document will be split and each chunk stored separately.
        :param entry: The entry to store in the Qdrant collection.
        :param collection_name: The name of the collection to store the information in, optional. If not provided,
                                the default collection is used.
        """
        collection_name = collection_name or self._default_collection_name
        if collection_name is None:
            raise ValueError("Collection name must be provided")
        await self._ensure_collection_exists(collection_name)

        # Handle chunking if enabled
        if self._enable_chunking and self._chunker:
            chunks = self._chunker.chunk_text(entry.content)
            if len(chunks) > 1:
                logger.info(f"Document split into {len(chunks)} chunks")
                # Store each chunk separately
                for i, chunk in enumerate(chunks):
                    chunk_metadata = entry.metadata.copy() if entry.metadata else {}
                    chunk_metadata["chunk_index"] = i
                    chunk_metadata["total_chunks"] = len(chunks)
                    chunk_metadata["is_chunk"] = True
                    chunk_entry = Entry(content=chunk, metadata=chunk_metadata)
                    await self._store_single(
                        chunk_entry, collection_name=collection_name
                    )
                return

        # Store as single entry (no chunking or only one chunk)
        await self._store_single(entry, collection_name=collection_name)

    async def _store_single(self, entry: Entry, *, collection_name: str):
        """
        Store a single entry in the Qdrant collection.
        :param entry: The entry to store.
        :param collection_name: The name of the collection.
        """
        # Embed the document
        # ToDo: instead of embedding text explicitly, use `models.Document`,
        # it should unlock usage of server-side inference.
        embeddings = await self._embedding_provider.embed_documents([entry.content])

        # Add to Qdrant
        vector_name = self._embedding_provider.get_vector_name()

        # Handle both named vectors and single vector collections
        if vector_name:
            # Named vector collection (new format)
            vector_data = {vector_name: embeddings[0]}
            payload = {"document": entry.content, METADATA_PATH: entry.metadata}
        else:
            # Single vector collection (legacy compatibility)
            vector_data = embeddings[0]
            # Use legacy format with 'text' field for compatibility
            payload = {"text": entry.content}
            if entry.metadata:
                payload.update(entry.metadata)

        await self._client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=uuid.uuid4().hex,
                    vector=vector_data,
                    payload=payload,
                )
            ],
        )

    async def search(
        self,
        query: str,
        *,
        collection_name: str | None = None,
        limit: int = 10,
        query_filter: models.Filter | None = None,
    ) -> list[Entry]:
        """
        Find points in the Qdrant collection. If there are no entries found, an empty list is returned.
        :param query: The query to use for the search.
        :param collection_name: The name of the collection to search in, optional. If not provided,
                                the default collection is used.
        :param limit: The maximum number of entries to return.
        :param query_filter: The filter to apply to the query, if any.

        :return: A list of entries found.
        """
        collection_name = collection_name or self._default_collection_name
        collection_exists = await self._client.collection_exists(collection_name)
        if not collection_exists:
            return []

        # Embed the query
        # ToDo: instead of embedding text explicitly, use `models.Document`,
        # it should unlock usage of server-side inference.

        query_vector = await self._embedding_provider.embed_query(query)
        vector_name = self._embedding_provider.get_vector_name()

        # Search in Qdrant
        # Handle both named vectors and single vector collections
        if vector_name:
            # Try named vector first; if not present, gracefully fall back to single-vector query
            try:
                search_results = await self._client.query_points(
                    collection_name=collection_name,
                    query=query_vector,
                    using=vector_name,
                    limit=limit,
                    query_filter=query_filter,
                )
            except ValueError as e:
                msg = str(e)
                if (
                    "not found in the collection" in msg
                    or "is not found in the collection" in msg
                ):
                    logger.warning(
                        "Vector name '%s' not found in collection '%s'; falling back to single-vector query",
                        vector_name,
                        collection_name,
                    )
                    search_results = await self._client.query_points(
                        collection_name=collection_name,
                        query=query_vector,
                        limit=limit,
                        query_filter=query_filter,
                    )
                else:
                    raise
        else:
            # Single vector collection (legacy compatibility)
            search_results = await self._client.query_points(
                collection_name=collection_name,
                query=query_vector,
                limit=limit,
                query_filter=query_filter,
            )

        entries = []
        for result in search_results.points:
            # Handle different payload structures
            if "document" in result.payload:
                # New format (MCP server format)
                content = result.payload["document"]
                metadata = result.payload.get("metadata")
            elif "text" in result.payload:
                # Legacy format (existing database format)
                content = result.payload["text"]
                # Extract metadata from other fields
                metadata = {k: v for k, v in result.payload.items() if k != "text"}
            else:
                # Fallback: use entire payload as content
                content = str(result.payload)
                metadata = None

            entries.append(Entry(content=content, metadata=metadata))

        return entries

    async def _ensure_collection_exists(self, collection_name: str):
        """
        Ensure that the collection exists, creating it if necessary.
        :param collection_name: The name of the collection to ensure exists.
        """
        collection_exists = await self._client.collection_exists(collection_name)
        if not collection_exists:
            # Create the collection with the appropriate vector size
            vector_size = self._embedding_provider.get_vector_size()

            # Use the vector name as defined in the embedding provider
            vector_name = self._embedding_provider.get_vector_name()
            await self._client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    vector_name: models.VectorParams(
                        size=vector_size,
                        distance=models.Distance.COSINE,
                    )
                },
            )

            # Create payload indexes if configured

            if self._field_indexes:
                for field_name, field_type in self._field_indexes.items():
                    await self._client.create_payload_index(
                        collection_name=collection_name,
                        field_name=field_name,
                        field_schema=field_type,
                    )
