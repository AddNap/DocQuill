# PDF Renderer Rust

High-performance PDF renderer for DocQuill using `pdf-writer`.

## 🚀 Quick Start

### Build

```bash
# Install Rust if not already installed
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Install maturin (Python build tool for PyO3)
pip install maturin

# Build in development mode
cd pdf_renderer_rust
maturin develop

# Or build release wheel
maturin build --release
```

### Usage in Python

```python
import pdf_renderer_rust
import json

# Create renderer
renderer = pdf_renderer_rust.PdfRenderer("output.pdf", 595.0, 842.0)  # A4

# Render UnifiedLayout from JSON
layout_json = json.dumps({
    "pages": [{
        "number": 1,
        "size": {"width": 595.0, "height": 842.0},
        "margins": {"top": 72.0, "bottom": 72.0, "left": 72.0, "right": 72.0},
        "blocks": [{
            "frame": {"x": 100.0, "y": 700.0, "width": 400.0, "height": 50.0},
            "block_type": "paragraph",
            "content": {"text": "Hello, World!"},
            "style": {
                "font_name": "Helvetica",
                "font_size": 12.0,
                "color": "#000000"
            }
        }]
    }]
})

renderer.render_layout(layout_json)
renderer.save()
```

## 📋 Features

- ✅ Basic PDF rendering (rectangles, text, images)
- ✅ Paragraph rendering
- ✅ Table rendering
- ✅ Image rendering (placeholder)
- ✅ Border and background rendering
- ✅ Python bindings via PyO3

## 🔧 Architecture

- `src/lib.rs` - Main module and Python bindings
- `src/renderer.rs` - Main PDF renderer implementation
- `src/canvas.rs` - High-level Canvas-like API wrapper
- `src/types.rs` - Type definitions (Rect, Size, Color, etc.)
- `src/geometry.rs` - Geometry utilities

## 📝 TODO

- [ ] Implement proper font loading (TTF/OTF)
- [ ] Implement image rendering
- [ ] Implement rounded rectangles with bezier curves
- [ ] Implement multi-line text with proper alignment
- [ ] Add more text formatting options
- [ ] Optimize performance

## 🐛 Known Issues

- Font loading is currently limited to built-in fonts
- Image rendering is placeholder only
- Rounded rectangles use simple rectangles

