# DocQuill PDF Rust Backend

[![PyPI version](https://badge.fury.io/py/docquill-pdf-rust.svg)](https://badge.fury.io/py/docquill-pdf-rust)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

**High-performance Rust-based PDF renderer for DocQuill.**

This package provides a native Rust extension for PDF generation, offering significant performance improvements over the pure Python (ReportLab) backend.

## Installation

```bash
pip install docquill-pdf-rust
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

## Usage

Once installed, DocQuill automatically detects and uses the Rust backend:

```python
from docquill import Document

doc = Document.open("document.docx")

# Use Rust backend (automatically detected)
doc.to_pdf("output.pdf", use_rust=True)

# Force Python backend
doc.to_pdf("output.pdf", use_rust=False)
```

## Performance

The Rust backend typically provides:
- **2-5x faster** PDF generation for complex documents
- **Lower memory usage** for large documents
- **Better parallelization** for batch processing

## Building from Source

If you need to build from source (e.g., for unsupported platforms):

```bash
# Install Rust (if not already installed)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Install maturin
pip install maturin

# Build and install
cd packages/docquill_pdf_rust
maturin develop --release
```

## License

Apache License 2.0
