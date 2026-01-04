# Examples and Utilities

This directory contains example scripts and utility tools for working with mcp-server-qdrant.

## Database Tools

- **[inspect_database.py](inspect_database.py)** - Inspect Qdrant database contents
  - View collection information
  - Check vector dimensions
  - Examine payload structures

## Citation and Extraction Tools

- **[extract_citation_info.py](extract_citation_info.py)** - Extract citation information from academic sources
  - Parse book, chapter, and page references
  - Format academic metadata

- **[quick_citation_extractor.py](quick_citation_extractor.py)** - Quick citation extraction utility
  - Simplified citation parsing
  - Batch processing support

## MCP Integration

- **[run_mcp_wrapper.py](run_mcp_wrapper.py)** - Wrapper script for running MCP server
  - Environment configuration
  - Custom startup options
  - Integration examples

## Testing

Additional test files have been moved to the [../tests/](../tests/) directory:

- `test_openai_provider.py` - OpenAI provider tests
- `test_mcp_integration.py` - MCP integration tests

## Usage

Each script contains inline documentation. Run with `--help` for usage information:

```bash
python examples/inspect_database.py --help
```

Or use with uv:

```bash
uv run python examples/inspect_database.py
```
