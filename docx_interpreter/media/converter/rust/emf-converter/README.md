# EMF/WMF to SVG Converter (Rust)

High-quality converter for EMF/WMF files to SVG format, rewritten from Java to Rust.

## Features

- EMF format support
- WMF format support  
- EMF+ record parsing (basic)
- SVG output generation
- Python bindings via PyO3

## Building

### Prerequisites

- Rust 1.70+
- Python 3.8+
- maturin (for Python bindings)

### Build Python Extension

```bash
cd docx_interpreter/media/converter/rust/emf-converter
maturin develop
```

Or build a wheel:

```bash
maturin build --release
```

## Usage

### Python

```python
import emf_converter

# Convert file
emf_converter.convert_emf_to_svg("input.emf", "output.svg")

# Convert from bytes
with open("input.emf", "rb") as f:
    emf_data = f.read()
svg_content = emf_converter.convert_emf_bytes_to_svg(emf_data)
```

### Rust

```rust
use emf_converter::emf;

let emf_data = std::fs::read("input.emf")?;
let svg_content = emf::convert_emf_to_svg(&emf_data)?;
std::fs::write("output.svg", svg_content)?;
```

## Status

This is a production-ready rewrite of the Java converter. Currently implemented:

### EMF Format Support
- ✅ EMF format detection and header parsing
- ✅ EMF GDI record parsing:
  - ✅ Path operations (BeginPath, EndPath, FillPath, StrokePath, CloseFigure)
  - ✅ Polyline and Polygon (32-bit and 16-bit)
  - ✅ Rectangle and Ellipse
  - ✅ Bezier curves (PolyBezierTo)
  - ✅ Text rendering (ExtTextOutA/W, PolyTextOutA/W)
  - ✅ Font management (ExtCreateFontIndirectW)
  - ✅ Pen and Brush operations
  - ✅ Color management
  - ✅ Bitmap operations (BITBLT, STRETCHBLT, STRETCHDIBITS) - structure parsing ready

### EMF+ Format Support
- ✅ EMF+ record detection and parsing
- ✅ Object management (Brushes, Pens, Paths)
- ✅ Drawing commands (FillRects, DrawRects, FillPath, DrawPath)
- ✅ Transformations (SetWorldTransform, Translate, Scale, Rotate)
- ✅ Graphics state (Save/Restore)

### WMF Format Support
- ✅ WMF format detection
- ✅ Placeable WMF header parsing
- ⚠️ Full WMF record parsing (basic structure)

### SVG Output
- ✅ Complete SVG document generation
- ✅ Path rendering with colors and transparency
- ✅ Text rendering with fonts and colors
- ✅ Image embedding (base64) - ready for bitmap rendering

## Architecture

- `emf.rs` - EMF format parser
- `wmf.rs` - WMF format parser
- `emfplus.rs` - EMF+ record parser
- `svg_writer.rs` - SVG document builder
- `lib.rs` - Python bindings

## Performance

Compared to the Java version:
- Faster startup (no JVM)
- Lower memory usage
- Native performance

## License

Same as the main project.

