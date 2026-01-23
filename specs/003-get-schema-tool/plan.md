# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]
**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Implement a new MCP tool `qdrant-get-schema` that exposes the current runtime configuration (collection name, vector dimensions, active filter fields) to agents. This enables agents to discover the "schema" dynamically, reducing hallucinations and configuration errors. Additionally, provide a `qdrant-mcp` Agent Skill to document how to use this tool alongside `qdrant-store` and `qdrant-find`.

## Technical Context

**Language/Version**: Python 3.10+
**Primary Dependencies**: FastMCP (server), Pydantic (settings), Qdrant Client
**Storage**: N/A (Read-only inspection of memory/settings)
**Testing**: pytest with `@pytest.mark.asyncio`
**Target Platform**: Cross-platform (container/local)
**Project Type**: MCP Server
**Performance Goals**: Instant response (<50ms), purely in-memory inspection.
**Constraints**: Must sanitize any secrets (though settings logic usually handles this, we explicitly won't return API keys).
**Scale/Scope**: Single new tool + 1 documentation file.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Environment-First Configuration**: PASS. The tool will purely reflect the state of `QdrantSettings` and `EmbeddingProviderSettings` which are initialized from environment variables.
- **II. Async-First Architecture**: PASS. The tool will be implemented as an `async def` function registered with FastMCP.
- **III. Backward Compatibility & Dual Format Support**: PASS. The tool will report the `vector_name` and `vector_size` from the active provider, correctly reflecting broadly whether legacy or named vectors are in use.
- **IV. Provider Abstraction & Extensibility**: PASS. The tool will interact with the `EmbeddingProvider` interface (`get_vector_size()`, `get_vector_name()`) rather than specific implementations.
- **V. Test Coverage & Isolation**: PASS. Plan includes adding a new test file `tests/test_get_schema.py` using the existing fixture patterns (in-memory Qdrant).

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature. Delete unused options and expand the chosen structure with
  real paths (e.g., apps/admin, packages/something). The delivered plan must
  not include Option labels.
-->

```text
# [REMOVE IF UNUSED] Option 1: Single project (DEFAULT)
src/
├── models/
├── services/
├── cli/
└── lib/

tests/
├── contract/
├── integration/
└── unit/

# [REMOVE IF UNUSED] Option 2: Web application (when "frontend" + "backend" detected)
backend/
├── src/
│   ├── models/
│   ├── services/
│   └── api/
└── tests/

frontend/
├── src/
│   ├── components/
│   ├── pages/
│   └── services/
└── tests/

# [REMOVE IF UNUSED] Option 3: Mobile + API (when "iOS/Android" detected)
api/
└── [same as backend above]

ios/ or android/
└── [platform-specific structure: feature modules, UI flows, platform tests]
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
