# Tasks: Get Schema Tool

**Input**: Design documents from `/specs/003-get-schema-tool/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Tests are NOT explicitly requested in the spec, so test tasks are omitted. We will rely on manual testing via the MCP Inspector and examples.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

This project uses single-project structure: `src/mcp_server_qdrant/`, `tests/` at repository root.

---

## Phase 1: Setup

**Purpose**: Project initialization and basic structure

- [x] T001 Create feature branch `003-get-schema-tool` from master

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T002 Review existing `QdrantMCPServer.setup_tools()` method in src/mcp_server_qdrant/mcp_server.py to understand tool registration pattern
- [x] T003 Review existing settings classes (`QdrantSettings`, `EmbeddingProviderSettings`, `ChunkingSettings`) in src/mcp_server_qdrant/settings.py

**Checkpoint**: Foundation reviewed - user story implementation can now begin

---

## Phase 3: User Story 1 - Dynamic Schema Inspection (Priority: P1) 🎯 MVP

**Goal**: Implement `qdrant-get-schema` tool that returns JSON with collection config, embedding provider, vector dimensions, and filterable fields

**Independent Test**: Call `qdrant-get-schema` via MCP Inspector, verify JSON output matches schema in contracts/tool-schema.json

### Implementation for User Story 1

- [x] T004 [US1] Implement `get_schema()` async method in src/mcp_server_qdrant/mcp_server.py that builds schema dict from settings
- [x] T005 [US1] Add logic to extract storage_mode ("memory" if `:memory:`, "local" if `local_path`, else "remote") in get_schema method
- [x] T006 [US1] Add logic to extract embedding provider info (provider type, model name, vector_size, vector_name) in get_schema method
- [x] T007 [US1] Add logic to extract filterable_fields from `self.qdrant_settings.filterable_fields` in get_schema method
- [x] T008 [US1] Add logic to extract RAG settings (chunking_enabled, pdf_ingestion_enabled) in get_schema method
- [x] T009 [US1] Register `get_schema` tool with FastMCP `@self.tool()` decorator in setup_tools() method
- [x] T010 [US1] Return JSON-serialized string from get_schema method

**Checkpoint**: User Story 1 complete - tool is callable via MCP and returns valid JSON

---

## Phase 4: User Story 2 - Collection Configuration Verification (Priority: P2)

**Goal**: Ensure `qdrant-get-schema` correctly reports collection_name and storage mode for debugging

**Independent Test**: Set `COLLECTION_NAME="test-collection"` and call tool, verify output includes correct collection name

### Implementation for User Story 2

- [x] T011 [US2] Verify get_schema includes `collection_name` field (should already be implemented in US1)
- [x] T012 [US2] Add debug logging in get_schema to log when schema is requested in src/mcp_server_qdrant/mcp_server.py
- [x] T013 [US2] Test manually with different configurations (`:memory:`, `QDRANT_LOCAL_PATH`, remote URL)

**Checkpoint**: User Story 2 complete - debugging capabilities verified

---

## Phase 5: User Story 3 - Agent Skill for MCP Usage (Priority: P2)

**Goal**: Create comprehensive GitHub Copilot Skill that teaches agents how to USE the MCP tools (not implement them)

**Independent Test**: Load skill in Copilot, ask "how do I search for memories?", verify skill provides workflow using `qdrant-find` and mentions `qdrant-get-schema`

### Implementation for User Story 3

- [x] T014 [P] [US3] Create directory .github/skills/qdrant-mcp/
- [x] T015 [US3] Create .github/skills/qdrant-mcp/SKILL.md with frontmatter (name, description with keywords)
- [x] T016 [US3] Add "When to Use This Skill" section listing: semantic search, memory storage, schema inspection, filtering queries
- [x] T017 [US3] Add "Prerequisites" section (MCP server running, tools available)
- [x] T018 [US3] Add "Step-by-Step Workflows" section with three workflows: 1) Inspect Schema First, 2) Search Memories, 3) Store Information
- [x] T019 [US3] Add "Tool Reference" section documenting qdrant-get-schema, qdrant-find, qdrant-store parameters
- [x] T020 [US3] Add "Common Patterns" section with examples using filters (document_id, page_label)
- [x] T021 [US3] Add "Troubleshooting" table with common issues and solutions

**Checkpoint**: User Story 3 complete - skill documentation ready for agent use

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, examples, and final validation

- [x] T022 [P] Create example script examples/test_get_schema.py demonstrating tool usage
- [x] T023 [P] Update README.md to mention new `qdrant-get-schema` tool in tools section
- [x] T024 [P] Update CHANGELOG.md with feature entry for version increment
- [ ] T025 Validate all acceptance scenarios from spec.md using MCP Inspector
- [x] T026 Run full test suite to ensure no regressions: `uv run pytest`

---

## Dependencies & Execution Strategy

### User Story Completion Order

1. **Phase 1-2**: Setup and Foundation (blocking, must complete first)
2. **Phase 3 (US1)**: Core get-schema implementation (MVP - can deploy independently)
3. **Phase 4 (US2)**: Verification features (extends US1)
4. **Phase 5 (US3)**: Agent skill documentation (independent, can run parallel with US2)
5. **Phase 6**: Polish (requires all stories complete)

### Parallel Execution Opportunities

**Phase 3 (US1)**:

- Tasks T004-T008 can be developed iteratively in the same method
- Task T010 (JSON serialization) depends on T004-T008

**Phase 5 (US3)**:

- Task T014 (create directory) must complete first
- Tasks T015-T021 can be written in sequence but are content-focused

**Phase 6 (Polish)**:

- Tasks T022-T024 can run in parallel (different files)
- Tasks T025-T026 must run sequentially after T022-T024

### Independent Test Criteria per Story

**US1**: Call `qdrant-get-schema`, parse JSON, verify contains all required fields from schema
**US2**: Run with different env configs, verify collection_name and storage_mode accuracy
**US3**: Load skill in Copilot, verify agent can discover and use tools effectively

### Implementation Strategy

**MVP Scope**: Complete Phase 3 (US1) only for initial release. This delivers the core capability agents need.

**Incremental Delivery**:

1. US1 → Deploy basic schema inspection
2. US2 → Add debugging features
3. US3 → Publish agent documentation for broader adoption

---

## Task Summary

- **Total Tasks**: 26
- **User Story 1 (P1)**: 7 tasks (T004-T010) - MVP
- **User Story 2 (P2)**: 3 tasks (T011-T013)
- **User Story 3 (P2)**: 8 tasks (T014-T021)
- **Setup/Foundation**: 3 tasks (T001-T003)
- **Polish**: 5 tasks (T022-T026)
- **Parallel Opportunities**: 5 tasks marked with [P]

**Estimated Effort**: ~4-6 hours total

- US1: 2-3 hours (core implementation)
- US2: 0.5 hour (verification)
- US3: 1.5-2 hours (documentation)
- Polish: 0.5 hour (validation)
