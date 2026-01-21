# PDF Page-by-Page Ingestion

This feature allows you to ingest PDF documents into Qdrant, where each page is stored as a separate entry with precise metadata for page numbers and labels.

## Overview

Unlike standard text ingestion, PDF ingestion:

1. Splits the document by physical pages.
2. Extracts text from each page independently.
3. Preserves original page labels (Roman numerals, chapter prefixes, etc.).
4. Stores both `physical_page_index` (0-based) and `page_label` (standard numbering) in metadata.

## Usage

### Bulk Ingestion via CLI

Use the `qdrant-ingest` tool to process directories containing PDF files:

```bash
uv run qdrant-ingest ingest /path/to/my/pdfs \
  --collection research-papers \
  --knowledge-base "My Library"
```

### Filtering in Search

You can filter results by document name or page index:

- `document_id`: The filename of the PDF.
- `physical_page_index`: The sequential 0-based index.
- `page_label`: The original page number/label from the PDF.

Example search using MCP tool:

```json
{
  "query": "quantum computing",
  "document_id": "nature_paper.pdf",
  "physical_page_index": 5
}
```

## Configuration

You can enable/disable PDF ingestion via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_PDF_INGESTION` | `true` | Set to `false` to disable PDF processing. |

## Supported Metadata

Each page entry contains the following metadata:

- `document_id`: Filename of the PDF.
- `physical_page_index`: 0-based position in the file.
- `page_label`: The string label from the PDF (e.g., "iv", "45").
- `total_pages`: Total page count of the source document.
- `filename`: Same as `document_id`.
- `filepath`: Full path to the original file.

## Troubleshooting

### No Text Extracted

If a PDF page is ingested but contains no text, it might be a scanned image. This tool currently does not support OCR. You may need to run the PDF through an OCR tool before ingestion.

### Corrupted PDF

If the ingestion tool fails with a "Corrupted PDF" error, try opening the PDF in a viewer and "printing to PDF" to create a fresh, standard-compliant file.

### No Page Labels

If search results show "Page 1", "Page 2" instead of your document's numbering, the PDF might not have internal page labels defined. In this case, the system falls back to the physical page position (1-based).

### Performance for Large PDFs

For extremely large PDFs (>1000 pages), ingestion might take several minutes. Ensure your database connection is stable and monitor the CLI progress logs.

## Requirements

- `pypdf>=5.1.0` (included in dependencies)
