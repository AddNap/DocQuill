<p align="center">
  <img src="assets/logo.svg" alt="DocQuill Logo" width="200">
</p>

<h1 align="center">DocQuill</h1>

<p align="center">
  <strong>Professional Python library for DOCX manipulation with Jinja-like templating, document merging, and high-quality PDF/HTML rendering.</strong>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-Apache%202.0-blue.svg" alt="License: Apache 2.0"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python 3.9+"></a>
  <a href="https://github.com/AddNap/DocQuill"><img src="https://img.shields.io/github/stars/AddNap/DocQuill?style=social" alt="GitHub Stars"></a>
</p>

## ✨ Features

- **Jinja-like Placeholder System** – 20+ placeholder types with automatic formatting (text, dates, currency, phone, QR codes, tables, images, lists, conditional blocks)
- **Document Merging** – Selective merging of body, headers, footers, and styles with full OPC relationship preservation
- **PDF Rendering** – High-quality output via Rust backend (default) or ReportLab fallback
- **HTML Workflow** – Bidirectional DOCX ⇄ HTML conversion with editable HTML support
- **AI-Ready JSON Export** – Structured layout export for analysis and modification by AI/ML pipelines
- **Full DOCX Support** – Footnotes, endnotes, textboxes, watermarks, field codes, bookmarks, and more

## 📦 Project Structure

This is a monorepo containing multiple packages:

```
packages/
├── docquill_core/       # Main Python package (pip install docquill)
├── docquill_pdf_rust/   # Optional high-performance Rust PDF renderer
└── docquill_pro/        # Future PRO modules (xlsx, pptx, pdf_ai)
```

## Quick Start

```bash
pip install docquill
```

For high-performance PDF rendering (2-5x faster, no Rust compiler needed):

```bash
pip install docquill[rust]
```

Pre-built wheels available for Linux, macOS (Intel/Apple Silicon), and Windows.

```python
from docquill import Document

# Open and fill a template
doc = Document.open("template.docx")
doc.fill_placeholders({
    "TEXT:Name": "John Doe",
    "DATE:IssueDate": "2025-01-15",
    "CURRENCY:Amount": 1500.50,
    "TABLE:Items": {
        "headers": ["Product", "Qty", "Price"],
        "rows": [["Laptop", "1", "4500"], ["Mouse", "2", "50"]]
    }
})

# Render to PDF and HTML
doc.to_pdf("output.pdf")
doc.to_html("output.html")
```

## 📚 Documentation

- [**Getting Started**](docs/getting-started.md) – Installation, basic usage, and first steps
- [**API Reference**](docs/api-reference.md) – Complete method documentation
- [**Architecture**](docs/architecture.md) – System design, data flow, and internals
- [**AI Integration**](docs/ai-integration.md) – JSON export format and AI workflow examples

## Placeholder Types

| Type | Example | Output |
|------|---------|--------|
| `TEXT` | `{{ TEXT:Name }}` | Plain text |
| `DATE` | `{{ DATE:IssueDate }}` | Formatted date |
| `CURRENCY` | `{{ CURRENCY:Amount }}` | `1,500.50 USD` |
| `PHONE` | `{{ PHONE:Contact }}` | `+1 234 567 890` |
| `QR` | `{{ QR:Code }}` | QR code image |
| `TABLE` | `{{ TABLE:Items }}` | Dynamic table |
| `IMAGE` | `{{ IMAGE:Logo }}` | Embedded image |
| `LIST` | `{{ LIST:Features }}` | Bullet/numbered list |
| `CONDITIONAL` | `{{ START_Offer }}...{{ END_Offer }}` | Show/hide block |

## Core API

```python
from docquill import Document

# Document lifecycle
doc = Document.open("file.docx")      # Open existing
doc = Document.create()                # Create new
doc.save("output.docx")                # Save

# Content manipulation
doc.fill_placeholders(data)            # Fill template placeholders
doc.replace_text("old", "new")         # Find and replace
doc.add_paragraph("text", style="Heading1")

# Rendering
doc.to_pdf("out.pdf", backend="rust")  # PDF with Rust renderer
doc.to_html("out.html", editable=True) # Editable HTML
doc.update_from_html_file("edited.html") # Import HTML changes

# Merging
doc.merge("other.docx", page_break=True)
doc.merge_selective({
    "body": Document.open("content.docx"),
    "headers": Document.open("header.docx")
})

# Layout pipeline
layout = doc.pipeline()                # Get UnifiedLayout
```

## Architecture

```
DOCX File
    ↓
PackageReader + XMLParser (full DOCX parsing)
    ↓
Document Model (paragraphs, tables, images, styles)
    ↓
LayoutPipeline (pagination, text metrics, footnotes)
    ↓
UnifiedLayout (pages with positioned blocks)
    ↓
PDFCompiler / HTMLExporter
    ↓
PDF / HTML Output
```

## AI Integration

Export document layout as structured JSON for AI processing:

```python
# Export layout for AI analysis
doc.to_json("layout.json", optimized=True)

# JSON contains:
# - Page structure with block positions (x, y, width, height)
# - Deduplicated styles and media references
# - Text content with formatting metadata
# - Semantic markers (source_uid, sequence)
```

## Development

### Building from source

```bash
# Clone the repository
git clone https://github.com/AddNap/DocQuill.git
cd DocQuill

# Install docquill_core in development mode
cd packages/docquill_core
pip install -e ".[dev]"

# (Optional) Install Rust PDF renderer
pip install docquill-pdf-rust
# Or build from source (requires Rust toolchain):
# cd ../docquill_pdf_rust && pip install maturin && maturin develop --release
```

### Running tests

```bash
# From project root
pytest tests/
```

## Technology Stack

- **Python 3.9+** – Core library, parser, layout engine
- **Rust (PyO3)** – High-performance PDF renderer and WMF/EMF/EMF+ converter
- **HarfBuzz** – Text shaping and metrics
- **ReportLab** – Fallback PDF backend

## 📝 License

Apache License 2.0 – see [LICENSE](LICENSE) for details.

## 🤝 Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting PRs.

---

**DocQuill** – Professional document automation for Python.
