# DocQuill

> Advanced Python library for DOCX manipulation with Jinja-like templating, document merging, and high-quality PDF/HTML rendering.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

## ✨ Features

- **Jinja-like Placeholder System** – 20+ placeholder types with automatic formatting (text, dates, currency, phone, QR codes, tables, images, lists, conditional blocks)
- **Document Merging** – Selective merging of body, headers, footers, and styles with full OPC relationship preservation
- **PDF Rendering** – High-quality output via Rust backend (default) or ReportLab fallback
- **HTML Workflow** – Bidirectional DOCX ⇄ HTML conversion with editable HTML support
- **AI-Ready JSON Export** – Structured layout export for analysis and modification by AI/ML pipelines
- **Full DOCX Support** – Footnotes, endnotes, textboxes, watermarks, field codes, bookmarks, and more

## 🚀 Quick Start

```bash
pip install docx-interpreter
```

```python
from docx_interpreter import Document

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

## 🎯 Placeholder Types

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

## 🔧 Core API

```python
from docx_interpreter import Document

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

## 🏗️ Architecture

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

## 🤖 AI Integration

Export document layout as structured JSON for AI processing:

```python
# Export layout for AI analysis
layout = doc.pipeline()
layout.export_json("layout.json", format="optimized_pipeline")

# JSON contains:
# - Page structure with block positions (x, y, width, height)
# - Deduplicated styles and media references
# - Text content with formatting metadata
# - Semantic markers (source_uid, sequence)
```

## 📊 Comparison with Alternatives

| Feature | DocQuill | python-docx | Aspose.Words |
|---------|----------|-------------|--------------|
| Full DOCX parsing | ✅ | ⚠️ ~20% | ✅ |
| PDF rendering | ✅ | ❌ | ✅ |
| HTML rendering | ✅ | ❌ | ✅ |
| Placeholder engine | ✅ 20+ types | ❌ | ❌ |
| Document merger | ✅ | ❌ | ⚠️ |
| Native Python | ✅ | ✅ | ❌ (.NET wrapper) |
| Open source | ✅ Apache 2.0 | ✅ MIT | ❌ Commercial |
| Price | Free | Free | $999+/year |

## 🛠️ Technology Stack

- **Python 3.9+** – Core library, parser, layout engine
- **Rust (PyO3)** – High-performance PDF renderer
- **HarfBuzz** – Text shaping and metrics
- **ReportLab** – Fallback PDF backend

## 📝 License

Apache License 2.0 – see [LICENSE](LICENSE) for details.

## 🤝 Contributing

Contributions welcome! Please read the contribution guidelines before submitting PRs.

---

**DocQuill** – Professional document automation for Python.
