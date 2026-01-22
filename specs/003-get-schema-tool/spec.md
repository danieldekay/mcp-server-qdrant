# Feature Specification: Get Schema Tool

**Feature Branch**: `003-get-schema-tool`
**Created**: 2026-01-22
**Status**: Draft
**Input**: User description: "a new command for the mcp server to get the current schema"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dynamic Schema Inspection (Priority: P1)

As an AI assistant connected to the MCP server, I want to know exactly which metadata fields I can filter by and what vector configuration is active, so that I can construct valid `qdrant-find` queries without hallucinating non-existent filters.

**Why this priority**: Essential for reliable agent interaction. Without this, agents have to guess field names (like `document_id` vs `filename`) or trial-and-error, leading to errors.

**Independent Test**: Can be fully tested by calling `qdrant-get-schema` and verifying the JSON output contains current `filterable_fields` and vector dimension info.

**Acceptance Scenarios**:

1. **Given** the MCP server is running with standard configuration, **When** I call `qdrant-get-schema`, **Then** I receive a JSON object listing all configured filterable fields (e.g., `document_id`, `page_label`) including their types and descriptions.
2. **Given** the MCP server is configured with a specific embedding model (e.g., OpenAI), **When** I call `qdrant-get-schema`, **Then** the output reflects the correct vector dimension (e.g., 1536) and provider name.
3. **Given** specific environment variables set custom filter fields, **When** I call `qdrant-get-schema`, **Then** the custom fields appear in the output.

---

### User Story 2 - Collection Configuration Verification (Priority: P2)

As a developer debugging the system, I want to verify that the collection name and local/remote connection details are what I expect, so I can confirm I'm querying the right database.

**Why this priority**: Useful for troubleshooting connection issues or verify environment variable precedence.

**Independent Test**: Configure server with specific `COLLECTION_NAME`, call tool, verify output.

**Acceptance Scenarios**:

1. **Given** `COLLECTION_NAME="my-research-docs"`, **When** I call `qdrant-get-schema`, **Then** the output includes `"collection_name": "my-research-docs"`.
2. **Given** I am using `:memory:` storage, **When** I call `qdrant-get-schema`, **Then** the output indicates in-memory storage mode.

---

### User Story 3 - Agent Skill for MCP Usage (Priority: P2)

As an AI agent (MCP Client), I want a dedicated GitHub Copilot Skill (`.github/skills/qdrant-mcp`) that teaches me how to *use* the available tools (`qdrant-store`, `qdrant-find`, `qdrant-get-schema`), so I can interact with the vector database effectively without having to read the server source code.

**Why this priority**: Ensures the tool is actually usable by agents. Provides the "documentation" layer for the new `get-schema` tool and existing tools.

**Constraints**:

- Must be located at `.github/skills/qdrant-mcp/SKILL.md`.
- Must focus purely on **using** the tools (consumption), NOT implementing or modifying the server code.
- Must leverage the `qdrant-get-schema` tool (from US1) as the primary way for the agent to orient itself.

**Acceptance Scenarios**:

1. **Given** the `qdrant-mcp` skill is loaded, **When** I ask "how do I search for memories?", **Then** the skill provides a clear workflow using `qdrant-find` (and `qdrant-get-schema` to check filters first).
2. **Given** the skill instructions, **When** I need to know the database structure, **Then** the skill explicitly directs me to use `qdrant-get-schema` locally to get ground truth.
3. **Given** I am writing a prompt to store data, **Then** the skill explains the `qdrant-store` parameters (JSON metadata) without showing Python implementations.

### Edge Cases

- **Config Misalignment**: What happens if the Qdrant server's actual collection has different vector size than the local settings?
  - *Expectation*: The tool reports the *Settings* configuration (what the code expects), but could optionally warn if it can inspect the remote. For MVP, reporting Settings is sufficient as that dictates the `store` behavior.
- **No Filter Fields**: What happens if no filterable fields are defined?
  - *Expectation*: Returns an empty list for `filterable_fields`, not an error.

## Functional Requirements *(mandatory)*

- **FR-001**: System MUST expose a new MCP tool named `qdrant-get-schema`.
- **FR-002**: The `qdrant-get-schema` tool MUST accept no arguments (empty input schema).
- **FR-003**: The tool MUST return a JSON object (or stringified JSON) containing the current server configuration.
- **FR-004**: The output MUST include the configured `collection_name`.
- **FR-005**: The output MUST include `embedding_provider` details: provider type, model name, and vector dimension.
- **FR-006**: The output MUST include a `filterable_fields` list, detailing each field's name, type, description, and filter condition.
- **FR-007**: The tool MUST pull this information dynamically from the loaded settings classes (`QdrantSettings`, `EmbeddingProviderSettings`), ensuring it reflects the active runtime configuration (including environment variable overrides).

### Documentation & Skills

- **DOC-001**: A new GitHub Copilot Skill MUST be created at `.github/skills/qdrant-mcp/SKILL.md`.
- **DOC-002**: The skill MUST instruct agents on how to use `qdrant-get-schema` to discover capabilities.
- **DOC-003**: The skill MUST provide usage examples for `qdrant-find` (search) and `qdrant-store` (memory) geared towards an agent user (not a developer).

### Key Entities *(include if feature involves data)*

- **Schema Definition**: A read-only representation of the server's capabilities, including storage location (collection), semantic configuration (embeddings), and access paths (filters).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Agents/Users can retrieve the full configuration schema in a single tool call.
- **SC-002**: The returned schema accurately matches the server's internal state (e.g., correct vector dimension for the selected provider).
- **SC-003**: The tool effectively prevents hallmark "guessing" errors by providing agents with the exact list of valid filter keys.
