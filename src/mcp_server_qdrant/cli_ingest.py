"""
CLI tool for ingesting documents into Qdrant.

Provides bulk document ingestion capabilities for building knowledge bases.

Source: https://github.com/mahmoudimus/mcp-server-qdrant
Commit: 5af3f72f1afd1afa8dce39976cd29191ddb69887
Author: Mahmoud Rusty Abdelkader (@mahmoudimus)
License: Apache-2.0
"""

import argparse
import asyncio
import logging
import os
import re
import sys
from pathlib import Path
from typing import List

from mcp_server_qdrant.embeddings.factory import create_embedding_provider
from mcp_server_qdrant.qdrant import Entry, QdrantConnector
from mcp_server_qdrant.settings import ChunkingSettings, EmbeddingProviderSettings, QdrantSettings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Supported file extensions
SUPPORTED_EXTENSIONS = {
    # Text documents
    ".txt",
    ".md",
    ".markdown",
    # Code files
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".go",
    ".rs",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".rb",
    ".php",
    ".sh",
    ".bash",
    # Config files
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".xml",
    ".ini",
    ".env",
    # Web
    ".html",
    ".css",
    ".scss",
    # Data
    ".csv",
    ".sql",
}


def find_files(
    path: Path, include_pattern: str | None = None, exclude_pattern: str | None = None
) -> List[Path]:
    """
    Find all supported files in a directory.
    :param path: Path to search
    :param include_pattern: Regex pattern for files to include
    :param exclude_pattern: Regex pattern for files to exclude
    :return: List of file paths
    """
    files = []

    if path.is_file():
        if path.suffix in SUPPORTED_EXTENSIONS:
            files.append(path)
        return files

    # Search directory recursively
    for file_path in path.rglob("*"):
        if not file_path.is_file():
            continue

        # Check if file extension is supported
        if file_path.suffix not in SUPPORTED_EXTENSIONS:
            continue

        # Apply include pattern
        if include_pattern:
            if not re.search(include_pattern, str(file_path)):
                continue

        # Apply exclude pattern
        if exclude_pattern:
            if re.search(exclude_pattern, str(file_path)):
                continue

        files.append(file_path)

    return files


async def ingest_file(
    file_path: Path, connector: QdrantConnector, collection_name: str, metadata: dict
) -> bool:
    """
    Ingest a single file into Qdrant.
    :param file_path: Path to file
    :param connector: Qdrant connector
    :param collection_name: Collection name
    :param metadata: Additional metadata
    :return: True if successful
    """
    try:
        # Read file content
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        if not content.strip():
            logger.warning(f"Skipping empty file: {file_path}")
            return False

        # Prepare metadata
        file_metadata = {
            "filename": file_path.name,
            "filepath": str(file_path),
            "extension": file_path.suffix,
            **metadata,
        }

        # Create entry
        entry = Entry(content=content, metadata=file_metadata)

        # Store in Qdrant
        await connector.store(entry, collection_name=collection_name)

        logger.info(f"Ingested: {file_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to ingest {file_path}: {e}")
        return False


async def ingest_command(args):
    """Handle the ingest command."""
    path = Path(args.path)
    if not path.exists():
        logger.error(f"Path does not exist: {path}")
        return 1

    # Load settings
    qdrant_settings = QdrantSettings(
        location=args.url or os.getenv("QDRANT_URL"),
        api_key=args.api_key or os.getenv("QDRANT_API_KEY"),
        collection_name=args.collection or os.getenv("COLLECTION_NAME", "default"),
    )

    embedding_settings = EmbeddingProviderSettings(
        model_name=args.embedding_model or os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
    )

    chunking_settings = ChunkingSettings(
        enable_chunking=args.enable_chunking or os.getenv("ENABLE_CHUNKING", "false").lower() == "true",
        max_chunk_size=int(args.max_chunk_size or os.getenv("MAX_CHUNK_SIZE", "512")),
        chunk_overlap=int(args.chunk_overlap or os.getenv("CHUNK_OVERLAP", "50")),
        chunk_strategy=args.chunk_strategy or os.getenv("CHUNK_STRATEGY", "semantic"),
    )

    # Create embedding provider
    embedding_provider = create_embedding_provider(embedding_settings)

    # Create connector
    connector = QdrantConnector(
        qdrant_url=qdrant_settings.location,
        qdrant_api_key=qdrant_settings.api_key,
        collection_name=qdrant_settings.collection_name,
        embedding_provider=embedding_provider,
        enable_chunking=chunking_settings.enable_chunking,
        chunk_strategy=chunking_settings.chunk_strategy,
        max_chunk_size=chunking_settings.max_chunk_size,
        chunk_overlap=chunking_settings.chunk_overlap,
    )

    # Find files
    logger.info(f"Searching for files in: {path}")
    files = find_files(path, args.include, args.exclude)
    logger.info(f"Found {len(files)} files to ingest")

    if not files:
        logger.warning("No files found matching criteria")
        return 0

    # Prepare metadata
    metadata = {}
    if args.knowledge_base:
        metadata["knowledge_base"] = args.knowledge_base
    if args.doc_type:
        metadata["doc_type"] = args.doc_type

    # Ingest files
    successful = 0
    failed = 0

    for file_path in files:
        if await ingest_file(file_path, connector, qdrant_settings.collection_name, metadata):
            successful += 1
        else:
            failed += 1

    logger.info(f"Ingestion complete: {successful} successful, {failed} failed")
    return 0


async def list_command(args):
    """Handle the list command."""
    # Load settings
    qdrant_settings = QdrantSettings(
        location=args.url or os.getenv("QDRANT_URL"),
        api_key=args.api_key or os.getenv("QDRANT_API_KEY"),
    )

    embedding_settings = EmbeddingProviderSettings()
    embedding_provider = create_embedding_provider(embedding_settings)

    connector = QdrantConnector(
        qdrant_url=qdrant_settings.location,
        qdrant_api_key=qdrant_settings.api_key,
        collection_name=None,
        embedding_provider=embedding_provider,
    )

    # List collections
    collections = await connector.get_collection_names()

    if not collections:
        print("No collections found")
        return 0

    print("Available collections:")
    for collection in collections:
        print(f"  - {collection}")

    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Qdrant document ingestion tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest documents into Qdrant")
    ingest_parser.add_argument("path", help="Path to file or directory")
    ingest_parser.add_argument("--url", help="Qdrant server URL")
    ingest_parser.add_argument("--api-key", help="Qdrant API key")
    ingest_parser.add_argument("--collection", help="Collection name")
    ingest_parser.add_argument("--embedding-model", help="Embedding model name")
    ingest_parser.add_argument("--knowledge-base", help="Knowledge base name for metadata")
    ingest_parser.add_argument("--doc-type", help="Document type for metadata")
    ingest_parser.add_argument("--include", help="Regex pattern for files to include")
    ingest_parser.add_argument("--exclude", help="Regex pattern for files to exclude")
    ingest_parser.add_argument("--enable-chunking", action="store_true", help="Enable document chunking")
    ingest_parser.add_argument("--chunk-strategy", choices=["semantic", "sentence", "fixed"], help="Chunking strategy")
    ingest_parser.add_argument("--max-chunk-size", type=int, help="Maximum chunk size")
    ingest_parser.add_argument("--chunk-overlap", type=int, help="Chunk overlap")

    # List command
    list_parser = subparsers.add_parser("list", help="List all collections")
    list_parser.add_argument("--url", help="Qdrant server URL")
    list_parser.add_argument("--api-key", help="Qdrant API key")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Run command
    if args.command == "ingest":
        return asyncio.run(ingest_command(args))
    elif args.command == "list":
        return asyncio.run(list_command(args))

    return 0


if __name__ == "__main__":
    sys.exit(main())
