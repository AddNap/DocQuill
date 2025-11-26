# DocQuill PDF Rust

High-performance Rust-based PDF renderer for [DocQuill](https://github.com/AddNap/DocQuill).

## Overview

This package provides a Rust implementation of the PDF rendering engine for DocQuill, offering significant performance improvements over the pure Python ReportLab backend.

## Features

- ⚡ **High Performance** - 3-5x faster PDF generation than ReportLab
- 🎨 **Full Feature Support** - Shadows, rounded borders, dashed/dotted lines
- 📊 **Table Rendering** - Colspan/rowspan support
- 🖼️ **Image Handling** - Efficient image embedding
- 🔤 **Font Support** - TrueType font embedding

## Installation

```bash
pip install docquill-pdf-rust
```

Or install with DocQuill:

```bash
pip install docquill[rust]
```

## Building from Source

Requires Rust toolchain and maturin:

```bash
# Install maturin
pip install maturin

# Build and install
cd packages/docquill_pdf_rust
maturin develop --release
```

## Usage

When installed, DocQuill automatically uses the Rust renderer:

```python
from docquill import Document

doc = Document.open("document.docx")
doc.to_pdf("output.pdf")  # Uses Rust renderer if available
```

To explicitly select the renderer:

```python
doc.to_pdf("output.pdf", renderer="rust")   # Force Rust
doc.to_pdf("output.pdf", renderer="python") # Force Python/ReportLab
```

## License

Apache License 2.0

