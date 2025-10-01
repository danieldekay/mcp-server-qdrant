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
os.environ['EMBEDDING_PROVIDER'] = 'openai'
os.environ['EMBEDDING_MODEL'] = 'text-embedding-3-small'
os.environ['TOOL_FIND_DESCRIPTION'] = 'Suche nach relevanten Forschungsmethoden-Inhalten mit natürlicher Sprache. Verwende deutsche Begriffe für beste Ergebnisse.'
os.environ['TOOL_STORE_DESCRIPTION'] = 'Speichere wichtige Forschungsmethoden-Inhalte für spätere Verwendung. Der information Parameter sollte den Hauptinhalt enthalten.'

# Validate required environment
if not os.environ.get('OPENAI_API_KEY'):
    print("❌ Error: OPENAI_API_KEY not found in environment!", file=sys.stderr)
    sys.exit(1)

print(f"✅ OpenAI API key loaded: {os.environ.get('OPENAI_API_KEY', '')[:8]}...", file=sys.stderr)
print(f"✅ Qdrant path: {os.environ.get('QDRANT_LOCAL_PATH')}", file=sys.stderr)

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