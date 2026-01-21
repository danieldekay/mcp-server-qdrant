#!/usr/bin/env python3
"""
Wrapper script to run the MCP server with proper environment loading
"""
import os
import sys
from pathlib import Path

# Load environment from the FoM project (adjusted for local workspace)
env_file = Path("/Users/dekay/Dokumente/projects/programmieren/FoM/test.env")
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(env_file)
        print(f"✅ Loaded environment from {env_file}", file=sys.stderr)
    except ImportError:
        # Fallback: manually parse .env file
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip().strip('"').strip("'")

# Ensure local package source is importable (src layout)
repo_root = Path(__file__).parent
src_dir = repo_root / "src"
if src_dir.exists():
    sys.path.insert(0, str(src_dir))

# Set MCP-specific environment variables (local Qdrant + OpenAI embeddings)
os.environ['QDRANT_LOCAL_PATH'] = "/Users/dekay/Dokumente/projects/programmieren/FoM/db/qdrant_db"

# Allow override via MCP_COLLECTION_NAME or existing COLLECTION_NAME
default_collection = 'forschungsmethoden_literatur'
override_collection = os.environ.get('MCP_COLLECTION_NAME') or os.environ.get('COLLECTION_NAME')
os.environ['COLLECTION_NAME'] = override_collection or default_collection
# Respect existing embedding settings; otherwise default to fastembed for portability
# Allow explicit overrides via MCP_EMBEDDING_PROVIDER/MODEL for spawned scenarios
provider_override = os.environ.get('MCP_EMBEDDING_PROVIDER')
model_override = os.environ.get('MCP_EMBEDDING_MODEL')

if provider_override:
    os.environ['EMBEDDING_PROVIDER'] = provider_override
else:
    os.environ.setdefault('EMBEDDING_PROVIDER', 'fastembed')

if model_override:
    os.environ['EMBEDDING_MODEL'] = model_override
else:
    os.environ.setdefault('EMBEDDING_MODEL', 'BAAI/bge-small-en-v1.5')
os.environ['TOOL_FIND_DESCRIPTION'] = 'Suche nach relevanten Forschungsmethoden-Inhalten mit natürlicher Sprache. Verwende deutsche Begriffe für beste Ergebnisse.'
os.environ['TOOL_STORE_DESCRIPTION'] = 'Speichere wichtige Forschungsmethoden-Inhalte für spätere Verwendung. Der information Parameter sollte den Hauptinhalt enthalten.'

# Validate required environment conditionally
embedding_provider = os.environ.get('EMBEDDING_PROVIDER', '').lower()
# If fastembed is selected but an OpenAI model name leaked in from the environment,
# force a compatible fastembed model to prevent startup failures.
if embedding_provider == 'fastembed':
    model = os.environ.get('EMBEDDING_MODEL', '')
    if not model or model.startswith('text-embedding-'):
        os.environ['EMBEDDING_MODEL'] = 'BAAI/bge-small-en-v1.5'
        print("✅ Adjusted EMBEDDING_MODEL to 'BAAI/bge-small-en-v1.5' for fastembed provider", file=sys.stderr)
if embedding_provider == 'openai':
    if not os.environ.get('OPENAI_API_KEY'):
        print("❌ Error: OPENAI_API_KEY not found in environment and EMBEDDING_PROVIDER is 'openai'!", file=sys.stderr)
        sys.exit(1)

if os.environ.get('OPENAI_API_KEY'):
    print(f"✅ OpenAI API key loaded: {os.environ.get('OPENAI_API_KEY', '')[:8]}...", file=sys.stderr)
# Default to copying to avoid lock contention with other local clients
copy_requested = os.environ.get('MCP_QDRANT_COPY', '1') in ('1', 'true', 'True')
if copy_requested:
    try:
        import tempfile
        import shutil
        src_path = os.environ.get('QDRANT_LOCAL_PATH')
        if src_path and os.path.isdir(src_path):
            tmp_dir = tempfile.mkdtemp(prefix="qdrant_db_mcp_")
            dst_path = os.path.join(tmp_dir, "qdrant_db_copy")
            shutil.copytree(src_path, dst_path)
            os.environ['QDRANT_LOCAL_PATH'] = dst_path
            print(f"✅ Using copied Qdrant DB at: {dst_path}", file=sys.stderr)
        else:
            print("⚠ MCP_QDRANT_COPY requested but source path missing; using original path", file=sys.stderr)
    except Exception as copy_err:
        print(f"⚠ Failed to copy Qdrant DB: {copy_err}; using original path", file=sys.stderr)

# Optional: auto-detect collection and vector size to select a compatible provider/model
try:
    from qdrant_client import QdrantClient
    q_path = os.environ.get('QDRANT_LOCAL_PATH')
    coll = os.environ.get('COLLECTION_NAME')
    if q_path and coll:
        client = QdrantClient(path=q_path)
        try:
            # Ensure collection exists; if not, choose the first available
            collections = client.get_collections()
            existing = [c.name for c in collections.collections]
            if coll not in existing and existing:
                coll = existing[0]
                os.environ['COLLECTION_NAME'] = coll
                print(f"⚠ COLLECTION_NAME not found, using '{coll}' instead", file=sys.stderr)

            info = client.get_collection(coll)
            vectors_cfg = info.config.params.vectors
            # Determine dimension for single-vector collections only
            if not hasattr(vectors_cfg, 'items'):
                dim = vectors_cfg.size
                if dim == 1536:
                    # Prefer OpenAI small by default for 1536-dim collections
                    # Treat only MCP_* as explicit overrides; built-in defaults can be changed
                    if not os.environ.get('MCP_EMBEDDING_PROVIDER'):
                        os.environ['EMBEDDING_PROVIDER'] = 'openai'
                        os.environ.setdefault('EMBEDDING_MODEL', 'text-embedding-3-small')
                        print("✅ Auto-selected OpenAI embeddings for 1536-dim collection (text-embedding-3-small)", file=sys.stderr)
                elif dim == 384:
                    # Ensure a 384-dim fastembed model
                    if not os.environ.get('MCP_EMBEDDING_PROVIDER'):
                        os.environ['EMBEDDING_PROVIDER'] = 'fastembed'
                        os.environ.setdefault('EMBEDDING_MODEL', 'BAAI/bge-small-en-v1.5')
                        print("✅ Auto-selected FastEmbed BGE small for 384-dim collection", file=sys.stderr)
        finally:
            try:
                client.close()
            except Exception:
                pass
except Exception as autodetect_err:
    print(f"⚠ Embedding auto-detect skipped: {autodetect_err}", file=sys.stderr)

# Recompute embedding provider after auto-detect and validate OpenAI requirements
embedding_provider = os.environ.get('EMBEDDING_PROVIDER', '').lower()
if embedding_provider == 'fastembed':
    model = os.environ.get('EMBEDDING_MODEL', '')
    if not model or model.startswith('text-embedding-'):
        os.environ['EMBEDDING_MODEL'] = 'BAAI/bge-small-en-v1.5'
        print("✅ Adjusted EMBEDDING_MODEL to 'BAAI/bge-small-en-v1.5' for fastembed provider", file=sys.stderr)
elif embedding_provider == 'openai':
    if not os.environ.get('OPENAI_API_KEY'):
        print("❌ Error: OPENAI_API_KEY not found in environment and EMBEDDING_PROVIDER is 'openai'!", file=sys.stderr)
        sys.exit(1)

print(f"✅ Qdrant path: {os.environ.get('QDRANT_LOCAL_PATH')}", file=sys.stderr)
print(f"✅ Embedding provider: {os.environ.get('EMBEDDING_PROVIDER')} | model: {os.environ.get('EMBEDDING_MODEL')}", file=sys.stderr)
print(f"✅ Embedding provider: {os.environ.get('EMBEDDING_PROVIDER')} | model: {os.environ.get('EMBEDDING_MODEL')}", file=sys.stderr)

# Try to import the packaged entrypoint; if that fails, run the server module via runpy
try:
    from mcp_server_qdrant.main import main as server_main
    server_main()
except Exception:
    try:
        import runpy
        runpy.run_path(str(src_dir / "mcp_server_qdrant/server.py"), run_name="__main__")
    except Exception as e:
        print(f"❌ Error starting MCP server: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)