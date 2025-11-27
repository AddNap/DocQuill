# DocQuill Rust Components

[![PyPI version](https://badge.fury.io/py/docquill-rust.svg)](https://badge.fury.io/py/docquill-rust)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**High-performance Rust components for DocQuill:**

- 🖨️ **PDF Renderer** - Fast PDF generation using pdf-writer
- 🖼️ **EMF/WMF Converter** - Convert Windows metafiles to SVG

## Installation

```bash
pip install docquill-rust
```

Or install with the main package:

```bash
pip install docquill[rust]
```

## Requirements

- Python 3.9+
- **No Rust compiler required** - pre-built wheels are available for:
  - Linux (x86_64, aarch64)
  - macOS (Intel x86_64, Apple Silicon arm64)
  - Windows (x86_64)

## Features

### PDF Renderer

High-performance PDF generation as an alternative to ReportLab:

```python
from docquill import Document

doc = Document.open("document.docx")

# Use Rust backend (automatically detected when installed)
doc.to_pdf("output.pdf", use_rust=True)
```

**Benefits:**
- 2-5x faster PDF generation
- Lower memory usage
- Full Unicode support (DejaVu Sans embedded)

### EMF/WMF Converter

Convert Windows Enhanced Metafile (EMF) and Windows Metafile (WMF) to SVG:

```python
import docquill_rust

# Convert file
docquill_rust.convert_emf_to_svg("input.emf", "output.svg")

# Convert bytes to SVG string
svg_content = docquill_rust.convert_emf_bytes_to_svg(emf_bytes)
```

**Supported formats:**
- EMF (Enhanced Metafile)
- WMF (Windows Metafile)

## Building from Source

If you need to build from source (e.g., for unsupported platforms):

```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Install maturin
pip install maturin

# Build and install
cd packages/docquill_rust
maturin develop --release
```

## License

Apache License 2.0

