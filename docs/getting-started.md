# Getting Started

This guide covers installation, basic usage, and common workflows with DocQuill.

## Installation

```bash
pip install docx-interpreter
```

### Optional: Rust PDF Backend

For best PDF rendering performance, install the Rust backend:

```bash
# Requires Rust toolchain
pip install maturin
cd pdf_renderer_rust
maturin develop --release
```

## Basic Usage

### Opening and Saving Documents

```python
from docx_interpreter import Document

# Open existing document
doc = Document.open("template.docx")

# Create new document
doc = Document.create()

# Save document
doc.save("output.docx")
```

### Filling Templates

DocQuill uses a Jinja-like placeholder syntax: `{{ TYPE:Key }}`

```python
doc = Document.open("template.docx")

doc.fill_placeholders({
    "TEXT:CustomerName": "John Doe",
    "DATE:InvoiceDate": "2025-01-15",
    "CURRENCY:Total": 1234.56,
    "PHONE:Contact": "1234567890",
    "TABLE:LineItems": {
        "headers": ["Item", "Qty", "Price"],
        "rows": [
            ["Widget A", "10", "$50.00"],
            ["Widget B", "5", "$75.00"]
        ]
    },
    "IMAGE:Logo": "company_logo.png",
    "LIST:Features": ["Fast", "Reliable", "Easy to use"]
})

doc.save("filled_invoice.docx")
```

### Rendering to PDF

```python
# Default: Rust backend (fastest)
doc.to_pdf("output.pdf")

# With options
doc.to_pdf(
    "output.pdf",
    backend="rust",           # or "reportlab"
    page_size=(595, 842),     # A4 in points
    margins=(72, 72, 72, 72), # 1 inch margins
    watermark_opacity=0.3
)
```

### Rendering to HTML

```python
# Read-only HTML
doc.to_html("output.html")

# Editable HTML (for browser editing)
doc.to_html("editable.html", editable=True)

# With embedded images
doc.to_html("standalone.html", embed_images_as_data_uri=True)
```

### HTML Round-Trip Workflow

Edit documents in the browser and import changes back:

```python
# Export to editable HTML
doc.to_html("edit.html", editable=True)

# ... user edits in browser ...

# Import changes
doc.update_from_html_file("edit.html", preserve_structure=True)
doc.save("updated.docx")
```

## Document Manipulation

### Adding Content

```python
doc = Document.create()

# Add paragraphs
doc.add_paragraph("Document Title", style="Heading1")
doc.add_paragraph("Regular paragraph text.")

# Add formatted text
para = doc.add_paragraph("Text with ")
doc.add_run(para, "bold", bold=True)
doc.add_run(para, " and ")
doc.add_run(para, "italic", italic=True)
doc.add_run(para, " formatting.")

# Add colored text
para = doc.add_paragraph("")
doc.add_run(para, "Red text", font_color="FF0000")
doc.add_run(para, " and ")
doc.add_run(para, "green text", font_color="00FF00")
```

### Text Replacement

```python
# Simple replacement
doc.replace_text("OLD_VALUE", "NEW_VALUE")

# Case-insensitive
doc.replace_text("old", "new", case_sensitive=False)

# Body only (exclude headers/footers)
doc.replace_text("draft", "final", scope="body")
```

### Lists

```python
# Numbered list
numbered = doc.create_numbered_list()
p1 = doc.add_paragraph("First item")
p1.set_list(numbered, level=0)
p2 = doc.add_paragraph("Second item")
p2.set_list(numbered, level=0)

# Bullet list
bullets = doc.create_bullet_list()
p3 = doc.add_paragraph("Bullet point")
p3.set_list(bullets, level=0)
```

### Conditional Blocks

Show or hide sections based on conditions:

```python
# In template: {{ START_Premium }}...premium content...{{ END_Premium }}

doc.process_conditional_block("Premium", show=True)   # Show block
doc.process_conditional_block("Premium", show=False)  # Hide block
```

## Document Merging

### Full Merge

```python
main = Document.open("main.docx")
main.merge("appendix.docx", page_break=True)
main.save("combined.docx")
```

### Selective Merge

Combine elements from multiple documents:

```python
doc = Document.open("base.docx")

doc.merge_selective({
    "body": Document.open("content.docx"),
    "headers": Document.open("letterhead.docx"),
    "footers": Document.open("footer_template.docx"),
    "styles": Document.open("corporate_styles.docx")
})

doc.save("merged.docx")
```

### Header/Footer Only

```python
doc.merge_headers("header_template.docx")
doc.merge_footers("footer_template.docx")
```

## Convenience Functions

One-liner operations:

```python
from docx_interpreter import (
    fill_template,
    merge_documents,
    render_to_pdf,
    render_to_html,
    open_document,
    create_document
)

# Fill and save in one call
fill_template("template.docx", {"TEXT:Name": "John"}, "output.docx")

# Merge multiple documents
merge_documents("main.docx", ["part1.docx", "part2.docx"], "merged.docx")

# Direct rendering
render_to_pdf("document.docx", "output.pdf")
render_to_html("document.docx", "output.html", editable=True)
```

## Working with Metadata

```python
# Get document metadata
metadata = doc.get_metadata()
print(metadata['core_properties'])

# Individual properties
title = doc.get_title()
author = doc.get_author()
keywords = doc.get_keywords()

# Document statistics
stats = doc.get_stats()
print(f"Paragraphs: {stats['paragraphs']}")
print(f"Tables: {stats['tables']}")
print(f"Images: {stats['images']}")
```

## Watermarks

```python
# Add watermark
doc.add_watermark(
    "CONFIDENTIAL",
    angle=45,
    opacity=0.3,
    color="#FF0000",
    font_size=72
)

# Get existing watermarks
watermarks = doc.get_watermarks()
```

## Layout Pipeline

Access the internal layout representation:

```python
# Process document through layout pipeline
layout = doc.pipeline(
    page_size=(595, 842),      # A4
    margins=(72, 72, 72, 72),  # 1 inch
    apply_headers_footers=True
)

# Inspect layout
print(f"Pages: {len(layout.pages)}")
for page in layout.pages:
    print(f"  Page {page.number}: {len(page.blocks)} blocks")
```

## Error Handling

```python
from docx_interpreter import Document
from docx_interpreter.exceptions import DocxError, ParseError, RenderError

try:
    doc = Document.open("file.docx")
    doc.to_pdf("output.pdf")
except ParseError as e:
    print(f"Failed to parse document: {e}")
except RenderError as e:
    print(f"Failed to render: {e}")
except DocxError as e:
    print(f"Document error: {e}")
```

## Next Steps

- [API Reference](api-reference.md) – Complete method documentation
- [Architecture](architecture.md) – Understanding the internals
- [AI Integration](ai-integration.md) – Using DocQuill with AI/ML pipelines

