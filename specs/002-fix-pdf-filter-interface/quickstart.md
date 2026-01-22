# Quickstart: Using PDF Filter Parameters in MCP

**Feature**: Fix PDF Filter Parameter Exposure
**Audience**: MCP client users (Claude Desktop, Cursor, VS Code, etc.)

## What This Feature Provides

Filter your PDF document searches by:

- **document_id**: Search within a specific PDF document
- **physical_page_index**: Jump to a specific page position (0-based)
- **page_label**: Find content by original page number (e.g., "iv", "45")

## Prerequisites

1. PDF documents ingested using feature 001 (page-by-page ingestion)
2. MCP server running with PDF metadata fields configured
3. MCP client connected to the server

## Basic Usage

### Filter by Document ID

Find content within a specific PDF:

```json
{
  "tool": "qdrant-find",
  "arguments": {
    "query": "neural networks",
    "collection_name": "papers",
    "document_id": "ml-fundamentals.pdf"
  }
}
```

**Result**: Only pages from `ml-fundamentals.pdf` are searched.

### Filter by Physical Page Index

Jump to a specific page position:

```json
{
  "tool": "qdrant-find",
  "arguments": {
    "query": "introduction",
    "collection_name": "papers",
    "physical_page_index": 0
  }
}
```

**Result**: Only the first page (index 0) across all documents.

### Filter by Page Label

Search using original document page numbers:

```json
{
  "tool": "qdrant-find",
  "arguments": {
    "query": "conclusion",
    "collection_name": "papers",
    "page_label": "95"
  }
}
```

**Result**: Pages labeled "95" in any document (useful for citations).

## Advanced Usage

### Combine Filters

Search a specific page in a specific document:

```json
{
  "tool": "qdrant-find",
  "arguments": {
    "query": "methodology",
    "collection_name": "papers",
    "document_id": "research-paper.pdf",
    "physical_page_index": 5
  }
}
```

**Result**: Only page 5 of `research-paper.pdf`.

### Handle Custom Page Numbering

For PDFs with Roman numerals or custom numbering:

```json
{
  "tool": "qdrant-find",
  "arguments": {
    "query": "preface",
    "collection_name": "books",
    "page_label": "iv"
  }
}
```

**Result**: The page labeled "iv" (Roman numeral 4).

## Common Patterns

### Pattern 1: Document-Specific Search

**Use Case**: "Find all mentions of 'regression' in the ML textbook"

```json
{
  "query": "regression",
  "collection_name": "textbooks",
  "document_id": "ml-textbook.pdf"
}
```

### Pattern 2: Page Range Simulation

**Use Case**: "Search pages 10-20 of a document"

Since range filters aren't directly supported, make multiple queries:

```python
for page_index in range(10, 21):
    results = qdrant_find(
        query="term",
        collection_name="papers",
        document_id="paper.pdf",
        physical_page_index=page_index
    )
```

### Pattern 3: Citation Lookup

**Use Case**: "Verify a citation from page 42 of the thesis"

```json
{
  "query": "hypothesis",
  "collection_name": "thesis",
  "document_id": "phd-thesis.pdf",
  "page_label": "42"
}
```

## Troubleshooting

### Issue: Filter parameters not visible

**Symptoms**:

- MCP client doesn't show document_id, physical_page_index, or page_label parameters
- Tool signature only shows query and collection_name

**Solutions**:

1. Restart your MCP client completely (not just reload)
2. Check environment variables: `env | grep QDRANT`
3. Verify you're connected to the correct server instance
4. Use MCP Inspector to verify tool schema: `fastmcp dev src/mcp_server_qdrant/server.py`

### Issue: Filters return no results

**Symptoms**:

- Query with filters returns empty list
- Same query without filters returns results

**Causes & Solutions**:

1. **Wrong document_id**: Check exact filename (case-sensitive)

   ```json
   // Wrong
   "document_id": "paper.PDF"

   // Correct
   "document_id": "paper.pdf"
   ```

2. **Wrong page index**: Remember 0-based indexing

   ```json
   // Page 1 is index 0
   "physical_page_index": 0  // First page
   ```

3. **Wrong page label**: Check PDF's internal page labels

   ```json
   // Some PDFs have "Page 1", "Page 2", not "1", "2"
   "page_label": "Page 1"  // Not just "1"
   ```

### Issue: Type errors

**Symptoms**:

- Error: "Expected integer, got string"
- Parameter validation fails

**Solution**: Ensure correct types:

```json
{
  "physical_page_index": 5,      // ✅ Integer, not "5"
  "document_id": "paper.pdf",    // ✅ String
  "page_label": "42"             // ✅ String, even for numbers
}
```

## Verification Steps

### 1. Check Tool Schema in MCP Inspector

```bash
cd /path/to/mcp-server-qdrant
fastmcp dev src/mcp_server_qdrant/server.py
# Open browser at http://localhost:5173
```

Look for `qdrant-find` tool and verify it shows 5 parameters:

- query (string, required)
- collection_name (string, required)
- document_id (string, optional)
- physical_page_index (integer, optional)
- page_label (string, optional)

### 2. Test Basic Filtering

**Step 1**: Ingest a test PDF

```bash
uv run qdrant-ingest ingest test.pdf --collection test
```

**Step 2**: Query without filters

```json
{"query": "test", "collection_name": "test"}
```

Should return results.

**Step 3**: Query with document_id filter

```json
{"query": "test", "collection_name": "test", "document_id": "test.pdf"}
```

Should return same or fewer results.

### 3. Verify Metadata is Stored

Use the inspection script:

```python
import asyncio
from qdrant_client import AsyncQdrantClient

async def check_metadata():
    client = AsyncQdrantClient(path="./qdrant_storage")
    points = await client.scroll(
        collection_name="test",
        limit=1,
        with_payload=True
    )
    print(points[0][0].payload)  # Should show metadata.document_id, etc.

asyncio.run(check_metadata())
```

## Best Practices

### DO

✅ Use `document_id` for single-document searches (faster)
✅ Use `page_label` for citation accuracy
✅ Combine filters to narrow results effectively
✅ Handle empty result lists gracefully

### DON'T

❌ Don't assume page_label is always numeric
❌ Don't use 1-based indexing for physical_page_index
❌ Don't filter without checking if metadata exists
❌ Don't mix physical_page_index and page_label (they may differ)

## Examples from Real Use Cases

### Academic Research

**Scenario**: Cite a specific page from a paper

```json
{
  "query": "experimental results",
  "collection_name": "literature",
  "document_id": "smith2023.pdf",
  "page_label": "7"
}
```

**Output**: Content from page 7, formatted for citation: "Smith et al. (2023), p. 7"

### Legal Document Review

**Scenario**: Review a specific section of a contract

```json
{
  "query": "liability clause",
  "collection_name": "contracts",
  "document_id": "vendor-agreement.pdf",
  "page_label": "Appendix B"
}
```

**Output**: All mentions in the appendix section.

### Technical Documentation

**Scenario**: Find API documentation for a specific version

```json
{
  "query": "authentication",
  "collection_name": "docs",
  "document_id": "api-v2.3-reference.pdf",
  "physical_page_index": 12
}
```

**Output**: Authentication section from exact page.

## Performance Notes

- **Filter overhead**: Negligible (< 1ms)
- **Index utilization**: All three fields are indexed
- **Recommended practice**: Always use `document_id` when possible to reduce search space

## Next Steps

After mastering basic filtering:

1. Explore combining with semantic search queries
2. Build document navigation interfaces
3. Implement citation extraction workflows
4. Integrate with RAG pipelines for document-aware responses

## Support

If filters still don't work after following this guide:

1. Check research.md for detailed technical analysis
2. Run diagnostic scripts in tests/ directory
3. Enable debug logging: `export FASTMCP_DEBUG=true`
4. Report issue with MCP Inspector output
