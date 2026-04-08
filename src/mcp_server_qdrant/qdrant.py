import hashlib
import logging
import re
import uuid
from typing import Any

from pydantic import BaseModel
from qdrant_client import AsyncQdrantClient, models

from mcp_server_qdrant.constants import (
    DoclingMetadataKeys,
    PDFMetadataKeys,
    SystemMetadataKeys,
)
from mcp_server_qdrant.embeddings.base import EmbeddingProvider
from mcp_server_qdrant.settings import METADATA_PATH

logger = logging.getLogger(__name__)


def normalize_text_for_hash(content: str) -> str:
    """Normalize content before hashing so duplicate detection is stable."""
    return re.sub(r"\s+", " ", content).strip()


def compute_content_hash(content: str) -> str:
    """Compute a stable hash for duplicate detection and metadata-only updates."""
    normalized = normalize_text_for_hash(content)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

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
    score: float | None = None


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


class DoclingChunkEntry(Entry):
    """
    A semantic chunk entry produced by the Docling pipeline.

    Contains rich academic metadata including printed book page numbers,
    heading hierarchy, chunk type classification, and figure asset paths.
    Stored directly as an Entry – all Docling metadata is flat in the
    metadata dict (populated by ProcessedChunk.to_dict()).
    """

    chunk_index: int = 0
    chunk_type: str = "text"
    book_pages: list[int] = []
    pdf_pages: list[int] = []

    def to_entry(self) -> Entry:
        """Return self as a plain Entry (metadata already fully populated)."""
        return Entry(content=self.content, metadata=self.metadata or {})


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

    async def get_collections_info(self) -> list[dict]:
        """
        Get statistics for all collections in the Qdrant server.
        :return: A list of dicts with name, points_count, vectors_count, status.
        """
        collections = await self.get_collection_names()
        result = []
        for name in collections:
            info = await self._client.get_collection(name)
            result.append({
                "name": name,
                "points_count": info.points_count,
                "vectors_count": info.vectors_count,
                "status": info.status.value,
            })
        return result

    def _build_vectors_config(self) -> dict[str, models.VectorParams] | models.VectorParams:
        """Build collection vector configuration for named and unnamed vectors."""
        vector_size = self._embedding_provider.get_vector_size()
        vector_params = models.VectorParams(
            size=vector_size,
            distance=models.Distance.COSINE,
        )
        vector_name = self._embedding_provider.get_vector_name()
        if vector_name:
            return {vector_name: vector_params}
        return vector_params

    async def create_collection(self, collection_name: str) -> bool:
        """
        Create a collection if it does not already exist.
        :param collection_name: The collection name to create.
        :return: True if created, False if it already existed.
        """
        if await self._client.collection_exists(collection_name):
            return False

        await self._client.create_collection(
            collection_name=collection_name,
            vectors_config=self._build_vectors_config(),
        )

        if self._field_indexes:
            for field_name, field_type in self._field_indexes.items():
                await self._client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field_name,
                    field_schema=field_type,
                )

        return True

    async def delete_collection(self, collection_name: str) -> bool:
        """
        Delete a collection if it exists.
        :param collection_name: The collection name to delete.
        :return: True if deleted, False if it did not exist.
        """
        if not await self._client.collection_exists(collection_name):
            return False

        await self._client.delete_collection(collection_name)
        return True

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

        metadata = dict(entry.metadata or {})
        metadata.setdefault(SystemMetadataKeys.CONTENT_HASH, compute_content_hash(entry.content))

        # Handle both named vectors and single vector collections
        if vector_name:
            # Named vector collection (new format)
            vector_data = {vector_name: embeddings[0]}
            payload = {"document": entry.content, METADATA_PATH: metadata}
        else:
            # Single vector collection (legacy compatibility)
            vector_data = embeddings[0]
            payload = {"document": entry.content, METADATA_PATH: metadata}

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
        score_threshold: float | None = None,
    ) -> list[Entry]:
        """
        Find points in the Qdrant collection. If there are no entries found, an empty list is returned.
        :param query: The query to use for the search.
        :param collection_name: The name of the collection to search in, optional. If not provided,
                                the default collection is used.
        :param limit: The maximum number of entries to return.
        :param query_filter: The filter to apply to the query, if any.
        :param score_threshold: Minimum similarity score (0.0–1.0). Results below this threshold are excluded.

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
                    score_threshold=score_threshold,
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
                        score_threshold=score_threshold,
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
                score_threshold=score_threshold,
            )

        entries = []
        for result in search_results.points:
            content, metadata = self._extract_content_and_metadata(result.payload)
            entries.append(
                Entry(
                    content=content,
                    metadata=self._public_metadata(metadata),
                    score=result.score,
                )
            )

        return entries

    def _extract_content_and_metadata(
        self,
        payload: dict[str, Any] | None,
    ) -> tuple[str, Metadata | None]:
        """Normalize payload parsing for new canonical and legacy record shapes."""
        payload = payload or {}
        if "document" in payload:
            return payload["document"], payload.get(METADATA_PATH) or payload.get("metadata")
        if "text" in payload:
            metadata = {k: v for k, v in payload.items() if k != "text"}
            return payload["text"], metadata or None
        return str(payload), None

    def _public_metadata(self, metadata: Metadata | None) -> Metadata | None:
        """Remove internal ingestion fields from metadata returned to callers."""
        if not metadata:
            return None
        cleaned = {
            key: value
            for key, value in metadata.items()
            if key != SystemMetadataKeys.CONTENT_HASH
        }
        return cleaned or None

    async def _scroll_all_points(
        self,
        collection_name: str,
        *,
        scroll_filter: models.Filter | None = None,
    ) -> list[Any]:
        """Collect all points matching a filter using the scroll API."""
        points: list[Any] = []
        offset = None

        while True:
            batch, next_offset = await self._client.scroll(
                collection_name=collection_name,
                offset=offset,
                scroll_filter=scroll_filter,
                limit=500,
                with_payload=True,
                with_vectors=False,
            )
            points.extend(batch)
            if next_offset is None:
                break
            offset = next_offset

        return points

    def _document_filter(self, document_id: str) -> models.Filter:
        """Build a filter that matches canonical and legacy document_id payloads."""
        return models.Filter(
            should=[
                models.FieldCondition(
                    key=f"{METADATA_PATH}.{PDFMetadataKeys.DOCUMENT_ID}",
                    match=models.MatchValue(value=document_id),
                ),
                models.FieldCondition(
                    key=PDFMetadataKeys.DOCUMENT_ID,
                    match=models.MatchValue(value=document_id),
                ),
            ]
        )

    def _entry_identity(self, metadata: Metadata | None, content: str) -> str:
        """Return a stable per-entry identity for updates and duplicate detection."""
        metadata = metadata or {}
        if metadata.get(PDFMetadataKeys.PHYSICAL_PAGE_INDEX) is not None:
            return f"page:{metadata[PDFMetadataKeys.PHYSICAL_PAGE_INDEX]}"
        if metadata.get("chunk_index") is not None:
            return f"chunk:{metadata['chunk_index']}"

        content_hash = metadata.get(SystemMetadataKeys.CONTENT_HASH) or compute_content_hash(content)
        return f"hash:{content_hash}"

    async def get_document_points(
        self,
        document_id: str,
        *,
        collection_name: str | None = None,
    ) -> list[Any]:
        """Return all points for a given document identifier."""
        collection_name = collection_name or self._default_collection_name
        if not collection_name:
            return []
        if not await self._client.collection_exists(collection_name):
            return []
        return await self._scroll_all_points(
            collection_name,
            scroll_filter=self._document_filter(document_id),
        )

    async def delete_document(
        self,
        document_id: str,
        *,
        collection_name: str | None = None,
    ) -> int:
        """Delete all points associated with a document identifier."""
        points = await self.get_document_points(document_id, collection_name=collection_name)
        if not points:
            return 0

        collection_name = collection_name or self._default_collection_name
        point_ids = [point.id for point in points]
        await self._client.delete(collection_name=collection_name, points_selector=point_ids)
        return len(point_ids)

    async def delete_by_filter(
        self,
        *,
        collection_name: str | None = None,
        query_filter: models.Filter,
    ) -> int:
        """Delete all points matched by a supplied filter."""
        collection_name = collection_name or self._default_collection_name
        if not collection_name:
            return 0
        if not await self._client.collection_exists(collection_name):
            return 0

        points = await self._scroll_all_points(collection_name, scroll_filter=query_filter)
        if not points:
            return 0

        point_ids = [point.id for point in points]
        await self._client.delete(collection_name=collection_name, points_selector=point_ids)
        return len(point_ids)

    async def upsert_document_entries(
        self,
        entries: list[Entry],
        *,
        collection_name: str | None = None,
        document_id: str,
    ) -> dict[str, int | str]:
        """
        Store or update a document as an idempotent operation.

        If the document already exists with identical content hashes, only metadata is
        updated. If content changed, existing points are replaced.
        """
        collection_name = collection_name or self._default_collection_name
        if collection_name is None:
            raise ValueError("Collection name must be provided")

        normalized_entries: list[Entry] = []
        for entry in entries:
            metadata = dict(entry.metadata or {})
            metadata.setdefault(PDFMetadataKeys.DOCUMENT_ID, document_id)
            metadata[SystemMetadataKeys.CONTENT_HASH] = compute_content_hash(entry.content)
            normalized_entries.append(Entry(content=entry.content, metadata=metadata))

        existing_points = await self.get_document_points(
            document_id,
            collection_name=collection_name,
        )

        if not existing_points:
            for entry in normalized_entries:
                await self.store(entry, collection_name=collection_name)
            return {
                "mode": "created",
                "stored": len(normalized_entries),
                "updated": 0,
                "deleted": 0,
            }

        existing_by_identity: dict[str, dict[str, Any]] = {}
        for point in existing_points:
            content, metadata = self._extract_content_and_metadata(point.payload)
            identity = self._entry_identity(metadata, content)
            existing_by_identity[identity] = {
                "point_id": point.id,
                "content": content,
                "metadata": metadata or {},
            }

        new_by_identity = {
            self._entry_identity(entry.metadata, entry.content): entry
            for entry in normalized_entries
        }

        same_document_shape = set(existing_by_identity) == set(new_by_identity)
        same_hashes = same_document_shape and all(
            existing_by_identity[identity]["metadata"].get(SystemMetadataKeys.CONTENT_HASH)
            == new_by_identity[identity].metadata.get(SystemMetadataKeys.CONTENT_HASH)
            for identity in new_by_identity
        )

        if same_hashes:
            updated = 0
            for identity, entry in new_by_identity.items():
                existing = existing_by_identity[identity]
                merged_metadata = dict(existing["metadata"])
                merged_metadata.update(entry.metadata or {})
                canonical_payload = {
                    "document": existing["content"],
                    METADATA_PATH: merged_metadata,
                }
                await self._client.overwrite_payload(
                    collection_name=collection_name,
                    payload=canonical_payload,
                    points=[existing["point_id"]],
                )
                updated += 1
            return {
                "mode": "metadata_updated",
                "stored": 0,
                "updated": updated,
                "deleted": 0,
            }

        deleted = await self.delete_document(document_id, collection_name=collection_name)
        for entry in normalized_entries:
            await self.store(entry, collection_name=collection_name)
        return {
            "mode": "replaced",
            "stored": len(normalized_entries),
            "updated": 0,
            "deleted": deleted,
        }

    async def update_document_metadata(
        self,
        document_id: str,
        metadata_updates: Metadata,
        *,
        collection_name: str | None = None,
    ) -> int:
        """
        Update metadata for all points belonging to a document.

        Returns the number of updated points.
        """
        collection_name = collection_name or self._default_collection_name
        if collection_name is None:
            raise ValueError("Collection name must be provided")

        points = await self.get_document_points(
            document_id,
            collection_name=collection_name,
        )
        if not points:
            return 0

        updated = 0
        for point in points:
            content, existing_metadata = self._extract_content_and_metadata(point.payload)
            merged_metadata = dict(existing_metadata or {})
            merged_metadata.update(metadata_updates)
            canonical_payload = {
                "document": content,
                METADATA_PATH: merged_metadata,
            }
            await self._client.overwrite_payload(
                collection_name=collection_name,
                payload=canonical_payload,
                points=[point.id],
            )
            updated += 1

        return updated

    async def list_documents(self, collection_name: str | None = None) -> list[dict]:
        """
        Return a summary of all distinct documents in the collection.
        Uses the Qdrant scroll API to page through all points.
        :param collection_name: The collection to inspect; uses the default if not given.
        :return: List of dicts with document_id, filename, page_count, total_pages, apa_zitation.
        """
        collection_name = collection_name or self._default_collection_name
        if not collection_name:
            return []
        if not await self._client.collection_exists(collection_name):
            return []

        documents: dict[str, dict] = {}
        offset = None

        while True:
            points, next_offset = await self._client.scroll(
                collection_name=collection_name,
                offset=offset,
                limit=500,
                with_payload=True,
                with_vectors=False,
            )

            for point in points:
                _content, meta = self._extract_content_and_metadata(point.payload)
                meta = meta or {}

                doc_id = meta.get("document_id", "<unknown>")
                if doc_id not in documents:
                    documents[doc_id] = {
                        "document_id": doc_id,
                        "filename": meta.get("filename", ""),
                        "total_pages": meta.get("total_pages", 0),
                        "apa_zitation": meta.get("apa_zitation", ""),
                        "page_count": 0,
                    }
                documents[doc_id]["page_count"] += 1

            if next_offset is None:
                break
            offset = next_offset

        return list(documents.values())

    async def get_inventory(
        self,
        collection_name: str | None = None,
        document_id: str | None = None,
    ) -> dict[str, Any]:
        """Return a lecturer-friendly inventory with document and chapter metadata."""
        collection_name = collection_name or self._default_collection_name
        inventory: dict[str, Any] = {
            "collection_name": collection_name,
            "document_count": 0,
            "documents": [],
        }
        if not collection_name:
            return inventory
        if not await self._client.collection_exists(collection_name):
            return inventory

        points = (
            await self.get_document_points(document_id, collection_name=collection_name)
            if document_id
            else await self._scroll_all_points(collection_name)
        )
        if not points:
            return inventory

        documents: dict[str, dict[str, Any]] = {}
        for point in points:
            _content, meta = self._extract_content_and_metadata(point.payload)
            meta = meta or {}

            doc_id = meta.get(PDFMetadataKeys.DOCUMENT_ID, "<unknown>")
            stats = documents.setdefault(
                doc_id,
                {
                    "document_id": doc_id,
                    "filename": meta.get(PDFMetadataKeys.FILENAME, ""),
                    "total_pages": meta.get(PDFMetadataKeys.TOTAL_PAGES, 0),
                    "apa_citation": meta.get("apa_zitation")
                    or meta.get(DoclingMetadataKeys.APA_CITATION)
                    or "",
                    "chunk_count": 0,
                    "page_label_count": 0,
                    "book_page_coverage": 0,
                    "chapter_title_coverage": 0,
                    "figure_count": 0,
                    "has_section_headers": False,
                    "chunk_types": {},
                    "book_page_start": None,
                    "book_page_end": None,
                },
            )

            stats["chunk_count"] += 1
            if meta.get(PDFMetadataKeys.PAGE_LABEL) is not None:
                stats["page_label_count"] += 1
            if meta.get(DoclingMetadataKeys.BOOK_PAGE_START) is not None:
                stats["book_page_coverage"] += 1
                start = meta.get(DoclingMetadataKeys.BOOK_PAGE_START)
                end = meta.get(DoclingMetadataKeys.BOOK_PAGE_END, start)
                stats["book_page_start"] = (
                    start
                    if stats["book_page_start"] is None
                    else min(stats["book_page_start"], start)
                )
                stats["book_page_end"] = (
                    end
                    if stats["book_page_end"] is None
                    else max(stats["book_page_end"], end)
                )
            if meta.get(PDFMetadataKeys.CHAPTER_TITLE):
                stats["chapter_title_coverage"] += 1

            chunk_type = meta.get(DoclingMetadataKeys.CHUNK_TYPE, "text")
            stats["chunk_types"][chunk_type] = stats["chunk_types"].get(chunk_type, 0) + 1
            if chunk_type == "section_header":
                stats["has_section_headers"] = True

            figure_paths = meta.get(DoclingMetadataKeys.FIGURE_PATHS) or []
            stats["figure_count"] += len(figure_paths)

        chapters = await self.list_chapters(
            collection_name=collection_name,
            document_id=document_id,
        )
        chapter_map: dict[str, list[dict[str, Any]]] = {}
        for chapter in chapters:
            chapter_map.setdefault(chapter.get("document_id", ""), []).append(chapter)

        inventory_documents: list[dict[str, Any]] = []
        for doc_id, stats in sorted(documents.items(), key=lambda item: item[0]):
            doc_chapters = chapter_map.get(doc_id, [])
            stats["chapter_count"] = len(doc_chapters)
            stats["chapters"] = doc_chapters
            stats["has_book_page_numbers"] = stats["book_page_coverage"] > 0
            stats["has_figures"] = stats["figure_count"] > 0
            inventory_documents.append(stats)

        inventory["document_count"] = len(inventory_documents)
        inventory["documents"] = inventory_documents
        return inventory

    async def verify_ingestion(
        self,
        collection_name: str | None = None,
        document_id: str | None = None,
    ) -> dict[str, Any]:
        """Return ingestion health checks and warnings for one collection or document."""
        inventory = await self.get_inventory(
            collection_name=collection_name,
            document_id=document_id,
        )
        verification: dict[str, Any] = {
            "collection_name": inventory.get("collection_name"),
            "document_count": inventory.get("document_count", 0),
            "status": "ok",
            "documents": [],
        }

        if not inventory.get("documents"):
            verification["status"] = "warning"
            return verification

        overall_warning = False
        for document in inventory["documents"]:
            warnings: list[str] = []
            if document["chunk_count"] == 0:
                warnings.append("No chunks indexed.")
            if document["page_label_count"] == 0:
                warnings.append("No page labels detected.")
            if document["chapter_title_coverage"] == 0:
                warnings.append("No chapter metadata detected.")
            if document["chapter_count"] == 0:
                warnings.append("No table-of-contents entries available.")
            if document["chapter_count"] > 0 and not document["has_section_headers"]:
                warnings.append(
                    "No section_header chunks detected; chapter inventory is using legacy fallback heuristics."
                )
            if not document["has_book_page_numbers"]:
                warnings.append("Printed book page numbers are missing.")

            status = "ok" if not warnings else "warning"
            overall_warning = overall_warning or bool(warnings)
            verification["documents"].append(
                {
                    "document_id": document["document_id"],
                    "filename": document.get("filename", ""),
                    "status": status,
                    "chunk_count": document["chunk_count"],
                    "chapter_count": document["chapter_count"],
                    "has_section_headers": document["has_section_headers"],
                    "has_book_page_numbers": document["has_book_page_numbers"],
                    "has_figures": document["has_figures"],
                    "warnings": warnings,
                }
            )

        if overall_warning:
            verification["status"] = "warning"
        return verification

    async def keyword_search(
        self,
        keyword: str,
        *,
        collection_name: str | None = None,
        document_id: str | None = None,
        limit: int = 10,
    ) -> list[Entry]:
        """
        Full-text keyword search using Qdrant's text payload index.
        Searches the 'document' field (and legacy 'text' field).
        :param keyword: Word or phrase to search for.
        :param collection_name: Collection to search; uses default if not given.
        :param document_id: Optionally restrict to a specific document.
        :param limit: Maximum number of results.
        :return: List of matching entries (no score – payload filter, not vector search).
        """
        collection_name = collection_name or self._default_collection_name
        if not collection_name:
            return []
        if not await self._client.collection_exists(collection_name):
            return []

        # Ensure text index exists on the 'document' field
        await self._ensure_text_index(collection_name)

        must_conditions: list[models.Condition] = [
            models.FieldCondition(
                key="document",
                match=models.MatchText(text=keyword),
            )
        ]
        if document_id:
            must_conditions.append(
                models.FieldCondition(
                    key="metadata.document_id",
                    match=models.MatchValue(value=document_id),
                )
            )

        query_filter = models.Filter(must=must_conditions)

        results, _ = await self._client.scroll(
            collection_name=collection_name,
            scroll_filter=query_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        entries = []
        for result in results:
            content, metadata = self._extract_content_and_metadata(result.payload)
            entries.append(
                Entry(content=content, metadata=self._public_metadata(metadata))
            )

        return entries

    async def list_chapters(
        self,
        collection_name: str | None = None,
        document_id: str | None = None,
    ) -> list[dict]:
        """
        Return the table of contents (distinct chapter_titles) for a document,
        ordered by first page appearance.
        :param collection_name: Collection to inspect; uses default if not given.
        :param document_id: Restrict to a specific document.
        :return: List of dicts with chapter_title, first_page_label, first_physical_index.
        """
        collection_name = collection_name or self._default_collection_name
        if not collection_name:
            return []
        if not await self._client.collection_exists(collection_name):
            return []

        chapters: dict[str, dict] = {}
        doc_candidates: dict[str, list[dict]] = {}
        offset = None

        must_conditions: list[models.Condition] = []
        if document_id:
            must_conditions.append(
                models.FieldCondition(
                    key="metadata.document_id",
                    match=models.MatchValue(value=document_id),
                )
            )
        scroll_filter = models.Filter(must=must_conditions) if must_conditions else None

        while True:
            points, next_offset = await self._client.scroll(
                collection_name=collection_name,
                offset=offset,
                scroll_filter=scroll_filter,
                limit=500,
                with_payload=True,
                with_vectors=False,
            )

            for point in points:
                content, meta = self._extract_content_and_metadata(point.payload)
                meta = meta or {}

                chunk_type = meta.get("chunk_type")
                chapter = self._resolve_chapter_title(content, meta)
                if not chapter:
                    continue

                physical = meta.get("physical_page_index", 999999)
                page_label = meta.get("page_label") or meta.get("book_page_start", "")
                doc_id = meta.get("document_id", "")
                heading_l1 = meta.get("heading_l1")
                heading_l2 = meta.get("heading_l2")
                heading_l3 = meta.get("heading_l3")

                doc_candidates.setdefault(doc_id, []).append(
                    {
                        "chapter_title": chapter,
                        "first_page_label": page_label,
                        "first_physical_index": physical,
                        "document_id": doc_id,
                        "_chunk_type": chunk_type,
                        "_heading_l1": heading_l1,
                        "_heading_l2": heading_l2,
                        "_heading_l3": heading_l3,
                        "_header_level": self._resolve_docling_header_level(
                            chapter,
                            meta,
                        ),
                        "_number_depth": self._chapter_number_depth(chapter),
                    }
                )

            if next_offset is None:
                break
            offset = next_offset

        for candidates in doc_candidates.values():
            for chapter in self._finalize_chapter_candidates(candidates):
                title = chapter["chapter_title"]
                if title not in chapters or (
                    chapter["first_physical_index"]
                    < chapters[title]["first_physical_index"]
                ):
                    chapters[title] = chapter

        return sorted(chapters.values(), key=lambda x: x["first_physical_index"])

    @staticmethod
    def _resolve_chapter_title(content: str, metadata: Metadata) -> str | None:
        """Prefer section-header content over inherited chapter metadata."""
        if metadata.get("chunk_type") == "section_header":
            header = content.strip()
            if header:
                return header
        return (
            metadata.get("chapter_title")
            or metadata.get("chapter")
            or metadata.get("heading_l1")
        )

    @staticmethod
    def _chapter_number_depth(title: str) -> int:
        """Return heading numbering depth, e.g. 43.1 -> 2, 43.1.1 -> 3."""
        match = re.match(r"^\s*(\d+(?:\.\d+)*)\b", title)
        if not match:
            return 0
        return match.group(1).count(".") + 1

    @staticmethod
    def _dotted_numbering(title: str) -> tuple[int, ...] | None:
        """Return dotted numbering tuples like (12, 4, 2) for structural headings."""
        match = re.match(r"^\s*(\d+(?:\.\d+)+)\b", title)
        if not match:
            return None
        return tuple(int(part) for part in match.group(1).split("."))

    @staticmethod
    def _resolve_docling_header_level(title: str, metadata: Metadata) -> int:
        """Resolve the actual Docling heading level for a section-header chunk."""
        if metadata.get("chunk_type") != "section_header":
            return 0

        if title == metadata.get("heading_l1"):
            return 1
        if title == metadata.get("heading_l2"):
            return 2
        if title == metadata.get("heading_l3"):
            return 3
        return 0

    @classmethod
    def _finalize_chapter_candidates(cls, chapters: list[dict]) -> list[dict]:
        """Collapse Docling section headers to a compact top-level TOC."""
        if not chapters:
            return []

        chapters = sorted(chapters, key=lambda item: item["first_physical_index"])
        has_section_headers = any(
            chapter.get("_chunk_type") == "section_header" for chapter in chapters
        )

        if has_section_headers:
            section_headers = [
                chapter
                for chapter in chapters
                if chapter.get("_chunk_type") == "section_header"
            ]
            positive_header_levels = [
                chapter["_header_level"]
                for chapter in section_headers
                if chapter["_header_level"] > 0
            ]
            if positive_header_levels:
                top_level_depth = min(positive_header_levels)
                chapters = [
                    chapter
                    for chapter in section_headers
                    if chapter.get("_header_level") == top_level_depth
                ]
            else:
                positive_depths = [
                    chapter["_number_depth"]
                    for chapter in section_headers
                    if chapter["_number_depth"] > 0
                ]
                top_level_depth = (
                    min(positive_depths) if positive_depths else None
                )
                chapters = [
                    chapter
                    for chapter in section_headers
                    if cls._is_top_level_section_header(
                        chapter,
                        top_level_depth,
                    )
                ]
        else:
            dotted_chapters = []
            min_depth_by_root: dict[int, int] = {}

            for chapter in chapters:
                numbering = cls._dotted_numbering(chapter["chapter_title"])
                if numbering is None:
                    continue
                dotted_chapters.append((chapter, numbering))
                root = numbering[0]
                depth = len(numbering)
                min_depth_by_root[root] = min(depth, min_depth_by_root.get(root, depth))

            if dotted_chapters:
                chapters = [
                    chapter
                    for chapter, numbering in dotted_chapters
                    if len(numbering) == min_depth_by_root[numbering[0]]
                ]

        deduped: dict[str, dict] = {}
        for chapter in chapters:
            title = chapter["chapter_title"]
            if title not in deduped:
                deduped[title] = {
                    key: value
                    for key, value in chapter.items()
                    if not key.startswith("_")
                }
        return list(deduped.values())

    @staticmethod
    def _is_top_level_section_header(
        chapter: dict, top_level_depth: int | None
    ) -> bool:
        """Keep only top-level section headers and real front-matter headings."""
        number_depth = chapter.get("_number_depth", 0)
        if number_depth > 0:
            return top_level_depth is None or number_depth == top_level_depth

        title = chapter.get("chapter_title", "")
        heading_l1 = chapter.get("_heading_l1") or ""
        return not heading_l1 or heading_l1 == title

    async def _ensure_text_index(self, collection_name: str) -> None:
        """
        Ensure a full-text payload index exists on the 'document' field.
        Safe to call multiple times – Qdrant ignores duplicate index creation.
        """
        try:
            await self._client.create_payload_index(
                collection_name=collection_name,
                field_name="document",
                field_schema=models.TextIndexParams(
                    type=models.TextIndexType.TEXT,
                    tokenizer=models.TokenizerType.WORD,
                    min_token_len=2,
                    max_token_len=15,
                    lowercase=True,
                ),
            )
        except Exception:
            # Index already exists or unsupported – silently continue
            pass

    async def _ensure_collection_exists(self, collection_name: str):
        """
        Ensure that the collection exists, creating it if necessary.
        :param collection_name: The name of the collection to ensure exists.
        """
        await self.create_collection(collection_name)
