# DocQuill

[![PyPI version](https://badge.fury.io/py/docquill.svg)](https://badge.fury.io/py/docquill)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**Professional DOCX document processing library** with AI-ready JSON export, PDF/HTML rendering, and round-trip editing.

## Features

- 📄 **Full DOCX Parsing** - Headers, footers, tables, images, styles, numbering
- 🔄 **Round-trip Editing** - DOCX → HTML → DOCX with formatting preservation
- 📊 **AI-Ready JSON Export** - Structured layout data for ML/NLP workflows
- 🖨️ **PDF Rendering** - Python (ReportLab) or high-performance Rust backend
- 🎨 **HTML Export** - Static or editable HTML output
- 📝 **Placeholder Engine** - 20+ placeholder types for document automation
- 🔀 **Document Merging** - Combine documents with OPC relationship handling

## Installation

```bash
pip install docquill
```

For high-performance PDF rendering with Rust:

```bash
pip install docquill[rust]
```

## Quick Start

```python
from docquill import Document

# Open and process a document
doc = Document.open("document.docx")

# Export to PDF
doc.to_pdf("output.pdf")

# Export to HTML
doc.to_html("output.html")

# Get AI-ready JSON layout
layout = doc.pipeline()
json_data = layout.to_json()

# Fill placeholders
doc.fill_placeholders({
    "company_name": "Acme Corp",
    "date": "2024-01-15"
})
doc.save("filled.docx")
```

## Documentation

See the [full documentation](https://github.com/AddNap/DocQuill/tree/main/docs) for:

- [Getting Started](https://github.com/AddNap/DocQuill/blob/main/docs/getting-started.md)
- [API Reference](https://github.com/AddNap/DocQuill/blob/main/docs/api-reference.md)
- [Architecture](https://github.com/AddNap/DocQuill/blob/main/docs/architecture.md)
- [AI Integration](https://github.com/AddNap/DocQuill/blob/main/docs/ai-integration.md)

## License

Apache License 2.0

