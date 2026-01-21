<!--
Sync Impact Report:
Version: 0.0.0 → 1.0.0 (MAJOR - Initial constitution ratification)
Modified Principles: None (initial creation)
Added Sections: All core principles, Technical Standards, Development Workflow, Governance
Removed Sections: None
Templates Status:
  ✅ .specify/templates/plan-template.md - Validated
  ✅ .specify/templates/spec-template.md - Validated
  ✅ .specify/templates/tasks-template.md - Validated
Follow-up TODOs: None
-->

# mcp-server-qdrant Constitution

## Core Principles

### I. Environment-First Configuration

ALL configuration MUST be via environment variables using Pydantic BaseSettings with
`validation_alias`. NO CLI arguments for server settings except `--transport` flag
for protocol selection. This ensures:

- Consistent configuration across deployment environments
- Docker/container-friendly deployment
- Clear separation of runtime behavior from code
- Reproducible deployments via environment templates

**Rationale**: MCP servers must integrate seamlessly with various client environments
(Claude Desktop, Cursor, VS Code) where environment configuration is the standard.

### II. Async-First Architecture (NON-NEGOTIABLE)

ALL Qdrant operations MUST use `AsyncQdrantClient`. ALL embedding operations MUST be
async (`embed_documents`, `embed_query`). This is mandatory because:

- FastMCP framework is built on async/await patterns
- Blocking I/O in async contexts causes performance degradation
- Vector operations and embeddings involve network calls requiring concurrency
- Tests MUST use `@pytest.mark.asyncio` decorator for async test functions
- Use `await` for all async operations—missing `await` is a critical error

**Rationale**: The MCP protocol and FastMCP framework are inherently asynchronous.
Synchronous operations block the event loop and break the server contract.

### III. Backward Compatibility & Dual Format Support

The connector MUST support both legacy and modern payload structures:

- **Legacy**: Single vectors with `{"text": content, ...metadata}` (flat structure)
- **Modern**: Named vectors with `{"document": content, "metadata": {...}}`

Determine format via `EmbeddingProvider.get_vector_name()`:

- Empty string = legacy single vector format
- Non-empty = named vector format with specified name

**Rationale**: Existing Qdrant databases (including OpenAI-based collections) must
work without migration. Breaking existing integrations violates user trust.

### IV. Provider Abstraction & Extensibility

Embedding providers MUST implement the `EmbeddingProvider` ABC with exactly 4 methods:

1. `async embed_documents(documents: list[str]) -> list[list[float]]`
2. `async embed_query(query: str) -> list[float]`
3. `get_vector_name() -> str` - Vector name or empty string for legacy format
4. `get_vector_size() -> int` - Embedding dimension

New providers MUST be added to `embeddings/factory.py` enum and factory function.
Providers MUST be independently testable with in-memory Qdrant (`:memory:`).

**Rationale**: Multiple embedding providers (FastEmbed, OpenAI, Model2Vec, Gemini)
serve different use cases. Clear abstraction enables easy extension.

### V. Test Coverage & Isolation

Tests MUST:

- Use in-memory Qdrant (`:memory:`) for fast, isolated execution
- Generate random collection names (`f"test_{uuid.uuid4().hex}"`) to avoid conflicts
- Run successfully on Python 3.10, 3.11, 3.12, 3.13 (CI requirement)
- Use `@pytest.fixture` with `async def` for async fixtures
- Cover both happy paths and error conditions

Test files:

- `test_qdrant_integration.py` - Core connector operations
- `test_*_provider.py` - Individual embedding provider tests
- `test_mcp_integration.py` - End-to-end MCP server tests
- `test_settings.py` - Configuration validation

**Rationale**: Fast, isolated tests enable rapid development. Multi-version Python
support ensures broad compatibility. In-memory Qdrant eliminates external dependencies.

### VI. Graceful Degradation for Optional Features

Optional dependencies (NLTK, tiktoken for chunking) MUST degrade gracefully:

- Check availability at runtime with try/except imports
- Provide clear warning logs when features unavailable
- Fall back to simpler implementations (e.g., regex sentence splitting)
- Document optional dependencies in README and error messages

RAG features (chunking, sets) are disabled by default and require explicit
environment variable enablement (`ENABLE_CHUNKING`, `QDRANT_ENABLE_SEMANTIC_SET_MATCHING`).

**Rationale**: Core functionality must work without optional features. Users should
not be forced to install heavy dependencies (NLTK corpora) for basic usage.

### VII. Type Safety & Documentation Standards

ALL functions MUST have:

- Complete type hints using `typing` module or Python 3.10+ union syntax
- PEP 257 compliant docstrings with parameter descriptions
- Return type annotations

Follow PEP 8 style with these specifics:

- Files: `snake_case` (`mcp_server.py`, `cli_ingest.py`)
- Classes: `PascalCase` (`QdrantConnector`, `EmbeddingProvider`)
- Functions/methods: `snake_case` (`embed_documents`, `create_embedding_provider`)
- Constants: `SCREAMING_SNAKE_CASE` (`METADATA_PATH`, `DEFAULT_TOOL_STORE_DESCRIPTION`)

Use isort for import organization: standard library, third-party, local modules.

**Rationale**: Type hints enable static analysis (mypy, pyright) catching errors
before runtime. Clear documentation reduces onboarding friction and mistakes.

## Technical Standards

### FastMCP Integration Requirements

- Use `@self.tool()` decorator for tool registration (instance method, NOT `@mcp.tool()`)
- Type hints with `Annotated[type, Field(description="...")]` auto-generate tool schemas
- Tool descriptions loaded from `ToolSettings` (customizable via environment variables)
- `Context` parameter available but rarely needed—omit unless required

### Collection Management

- Collections MUST be auto-created via `_ensure_collection_exists()` before operations
- Vector config MUST match embedding provider dimensions (`get_vector_size()`)
- Payload indexes MUST be created for all filterable fields
- Metadata MUST be stored under `metadata` key (defined in `settings.METADATA_PATH`)

### Error Handling

- Use appropriate exception types with clear error messages
- Log errors with context (collection name, operation, parameters)
- Propagate async exceptions properly—don't catch and suppress without logging
- Validate environment variables at startup via Pydantic (fail fast)

## Development Workflow

### Pre-commit Checklist

Before submitting ANY code change:

1. Run all tests: `uv run pytest`
2. Check types: `uv run mypy src/`
3. Format code: `uv run ruff format .`
4. Lint code: `uv run ruff check .`
5. Update documentation if adding features/changing APIs
6. Add tests for new functionality

### Pull Request Requirements

**Title format**: `[component] Brief description`

- Examples: `[embeddings] Add Gemini provider`, `[chunking] Fix overlap handling`

**Required checks**:

- All tests pass on Python 3.10, 3.11, 3.12, 3.13
- No type errors from mypy/pyright
- Ruff linting passes
- Pre-commit hooks pass

**Commit messages**: Follow Conventional Commits

- Types: `feat:`, `fix:`, `docs:`, `chore:`, `test:`
- Examples: `feat: add document chunking`, `fix: handle empty metadata`

### Code Review Standards

Reviewers MUST verify:

- Async/await correctness (no blocking I/O, proper `await` usage)
- Type hints present and accurate
- Tests added for new code paths
- Backward compatibility maintained (dual payload format)
- Environment variables documented in README
- No CLI arguments added (except transport flag)

## Governance

This constitution supersedes all other coding practices and documentation. Any
conflict between this constitution and other guidelines (e.g., instruction files)
MUST be resolved in favor of the constitution.

### Amendment Process

1. Propose amendment with rationale in issue/PR
2. Discuss impact on existing code and compatibility
3. Update constitution with version bump (MAJOR/MINOR/PATCH per semver)
4. Update all dependent templates (plan, spec, tasks, commands)
5. Document amendment in Sync Impact Report

### Compliance

- All PRs MUST be reviewed for constitution compliance
- Violations MUST be corrected before merge
- Complexity MUST be justified (document WHY not WHAT)
- Technical debt MUST be tracked and prioritized

### Living Documentation

Runtime development guidance is maintained in:

- `.github/copilot-instructions.md` - Comprehensive developer guide
- `AGENTS.md` - Agent-focused operational instructions
- `.github/instructions/*.instructions.md` - Specific coding guidelines

These documents MUST stay synchronized with constitution principles.

**Version**: 1.0.0 | **Ratified**: 2026-01-21 | **Last Amended**: 2026-01-21
