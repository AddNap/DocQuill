# Build Instructions

## Prerequisites

1. **Install Rust**:
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
```

2. **Install maturin** (Python build tool for PyO3):
```bash
pip install maturin
```

## Build

### Development Build (Recommended for testing)

```bash
cd pdf_renderer_rust
maturin develop
```

This will:
- Compile the Rust code
- Create a Python extension module
- Install it in your current Python environment

### Release Build (For production)

```bash
cd pdf_renderer_rust
maturin build --release
```

This creates a wheel file in `target/wheels/` that can be installed with pip.

### Install from wheel

```bash
pip install target/wheels/pdf_renderer_rust-*.whl
```

## Usage

```python
import pdf_renderer_rust

# Create renderer
renderer = pdf_renderer_rust.PdfRenderer("output.pdf", 595.0, 842.0)

# Render layout from JSON
import json
layout_json = json.dumps({...})
renderer.render_layout(layout_json)
renderer.save()
```

## Troubleshooting

### Error: "cargo: command not found"
- Install Rust: `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`

### Error: "maturin: command not found"
- Install maturin: `pip install maturin`

### Compilation errors
- Make sure you have Rust 1.70+ installed
- Run `rustup update` to update Rust

