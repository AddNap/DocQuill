# Architecture

This document describes DocQuill's internal architecture, data flow, and key components.

## Overview

DocQuill is designed as a layered system that transforms DOCX files through several stages:

```
┌─────────────────────────────────────────────────────────────────┐
│                         DOCX File                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PARSING LAYER                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Package     │  │ XML         │  │ Specialized Parsers     │  │
│  │ Reader      │──│ Parser      │──│ (styles, numbering,     │  │
│  │ (OPC/ZIP)   │  │ (factory)   │  │  headers, drawings...)  │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DOCUMENT MODEL                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ Body     │ │ Headers  │ │ Footers  │ │ Sections │           │
│  │ ├─Para   │ │ ├─Para   │ │ ├─Para   │ │ ├─Props  │           │
│  │ ├─Table  │ │ ├─Table  │ │ ├─Table  │ │ └─Margins│           │
│  │ ├─Image  │ │ └─Image  │ │ └─Image  │ │          │           │
│  │ └─...    │ │          │ │          │ │          │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LAYOUT PIPELINE                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Page       │  │ Layout      │  │ Text Metrics            │  │
│  │ Engine     │──│ Assembler   │──│ (HarfBuzz, fonts)       │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Paginator  │  │ Line        │  │ Footnote Renderer       │  │
│  │            │──│ Breaker     │──│                         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    UNIFIED LAYOUT                               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Page 1                                                   │   │
│  │  ├─ Block (paragraph) @ [x, y, w, h]                    │   │
│  │  ├─ Block (table)     @ [x, y, w, h]                    │   │
│  │  ├─ Block (image)     @ [x, y, w, h]                    │   │
│  │  └─ Block (footer)    @ [x, y, w, h]                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Page 2...                                                │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   PDF Compiler  │ │  HTML Exporter  │ │  JSON Exporter  │
│  ┌───────────┐  │ │                 │ │                 │
│  │ Rust      │  │ │  Editable or    │ │  AI-ready       │
│  │ Backend   │  │ │  Read-only      │ │  Layout         │
│  ├───────────┤  │ │                 │ │                 │
│  │ ReportLab │  │ │                 │ │                 │
│  │ Fallback  │  │ │                 │ │                 │
│  └───────────┘  │ │                 │ │                 │
└─────────────────┘ └─────────────────┘ └─────────────────┘
        │                   │                   │
        ▼                   ▼                   ▼
     PDF File          HTML File           JSON File
```

## Component Details

### 1. Parsing Layer

#### PackageReader (`parser/package_reader.py`)

Handles OPC (Open Packaging Conventions) format:
- Extracts ZIP archive
- Reads `[Content_Types].xml`
- Resolves relationships (`_rels/*.rels`)
- Provides access to individual XML parts

#### XMLParser (`parser/xml_parser.py`)

Central XML parser using factory pattern:

```python
TAG_MAP = {
    "p": "Paragraph",
    "r": "Run",
    "tbl": "Table",
    "tr": "TableRow",
    "tc": "TableCell",
    "drawing": "Image",
    "hyperlink": "Hyperlink",
    ...
}
```

Handles:
- Paragraphs with full formatting (spacing, indentation, borders)
- Runs with text properties (bold, italic, fonts, colors)
- Tables with grid, borders, cell merging
- Images (inline and anchored)
- Textboxes (AlternateContent, VML, DrawingML)
- Field codes (`fldSimple`, `fldChar`)
- Footnotes and endnotes
- Bookmarks and hyperlinks
- Watermarks (VML shapes)
- Structured Document Tags (SDT)

#### Specialized Parsers

| Parser | File | Purpose |
|--------|------|---------|
| `StyleParser` | `style_parser.py` | Document and character styles |
| `NumberingParser` | `numbering_parser.py` | List definitions |
| `HeaderFooterParser` | `header_footer_parser.py` | Headers/footers per section |
| `DrawingParser` | `drawing_parser.py` | Images and shapes |
| `NotesParser` | `notes_parser.py` | Footnotes and endnotes |
| `FieldParser` | `field_parser.py` | Field codes (PAGE, DATE, etc.) |

### 2. Document Model

Located in `models/`:

```
models/
├── body.py          # Document body container
├── paragraph.py     # Paragraph with runs
├── run.py           # Text run with formatting
├── table.py         # Table, TableRow, TableCell
├── image.py         # Image reference
├── textbox.py       # Textbox container
├── section.py       # Section properties
└── ...
```

Key characteristics:
- Preserves raw XML for lossless round-trip (`raw_xml` attribute)
- Maintains relationships to original DOCX structure
- Supports style inheritance resolution

### 3. Layout Pipeline

#### LayoutPipeline (`engine/layout_pipeline.py`)

Orchestrates document-to-layout conversion:

```python
class LayoutPipeline:
    def __init__(self, page_config: PageConfig):
        self.page_engine = PageEngine(page_config)
        self.layout_assembler = LayoutAssembler()
        self.image_cache = ImageCache()
        
    def process(self, document_model, **options) -> UnifiedLayout:
        # 1. Initialize pages
        # 2. Process elements sequentially
        # 3. Handle pagination
        # 4. Apply headers/footers
        # 5. Return UnifiedLayout
```

#### PageEngine (`engine/page_engine.py`)

Manages page creation and content area calculation:
- Page dimensions and margins
- Content area boundaries
- Page break handling

#### LayoutAssembler (`engine/layout_assembler.py`)

Converts document elements to positioned blocks:
- Calculates block positions
- Handles text wrapping
- Manages footnote placement
- Processes headers/footers

#### Text Metrics (`engine/text_metrics/`)

Precise text measurement using HarfBuzz:

```
text_metrics/
├── text_metrics_engine.py  # Main measurement API
├── font_loader.py          # Font file loading
├── glyph_metrics.py        # Glyph-level metrics
└── harfbuzz_shaper.py      # HarfBuzz integration
```

### 4. Unified Layout

The intermediate representation connecting parsing to rendering:

```python
class UnifiedLayout:
    pages: list[LayoutPage]
    current_page: int

class LayoutPage:
    number: int
    size: Size           # (width, height) in points
    margins: Margins     # (top, bottom, left, right)
    blocks: list[LayoutBlock]

class LayoutBlock:
    frame: Rect          # (x, y, width, height) position
    block_type: str      # "paragraph", "table", "image", etc.
    content: Any         # Type-specific content
    style: dict          # Resolved style properties
    source_uid: str      # Original element ID
    sequence: int        # Order in document
```

### 5. Rendering Layer

#### PDF Compiler (`engine/pdf/pdf_compiler.py`)

```python
class PDFCompiler:
    def __init__(self, output_path, page_size, use_rust=True, ...):
        self.backend = RustBackend() if use_rust else ReportLabBackend()
    
    def compile(self, layout: UnifiedLayout) -> Path:
        for page in layout.pages:
            self.backend.new_page(page.size)
            for block in page.blocks:
                self.render_block(block)
        return self.backend.save()
```

**Rust Backend** (`pdf_renderer_rust/`):
- High-performance native PDF generation
- Uses `pdf-writer` crate
- PyO3 Python bindings
- Handles: text, images, rectangles, borders

**ReportLab Backend** (fallback):
- Pure Python implementation
- Full feature compatibility
- Slower but more portable

#### HTML Exporter (`export/html_exporter.py`)

Generates HTML with CSS styling:
- Preserves visual layout
- Optional `contenteditable` for browser editing
- Image embedding as data URIs
- Page-based structure

#### JSON Exporter (`export/json_exporter.py`)

Exports layout for external processing:

```json
{
  "version": "2.0",
  "format": "optimized_pipeline",
  "metadata": { "total_pages": 9, ... },
  "styles": [ /* deduplicated style definitions */ ],
  "media": [ /* image references */ ],
  "pages": [
    {
      "n": 1,
      "size": [595, 842],
      "margins": [72, 72, 72, 72],
      "blocks": [
        {
          "f": [72, 750, 451, 20],  // frame: [x, y, w, h]
          "t": "paragraph",         // type
          "s": 5,                   // style index
          "c": { "text": "..." }    // content
        }
      ]
    }
  ]
}
```

### 6. Import Pipeline

#### PipelineJSONImporter (`importers/pipeline_json_importer.py`)

Reverse flow: JSON → UnifiedLayout → Document Model → DOCX

```python
class PipelineJSONImporter:
    def to_unified_layout(self) -> UnifiedLayout:
        # Deserialize JSON to layout objects
        
    def to_document_model(self) -> DocumentModel:
        # Convert layout back to document structure
        # Restore headers/footers from original DOCX
        # Rebuild OPC relationships
```

## Data Flow Examples

### Template Filling

```
template.docx
    │
    ▼ PackageReader
    │
    ▼ XMLParser.parse_body()
    │
Document Model (with {{ placeholders }})
    │
    ▼ PlaceholderResolver.fill()
    │
Modified Document Model
    │
    ▼ DOCXExporter.save()
    │
filled.docx
```

### PDF Generation

```
input.docx
    │
    ▼ PackageReader + XMLParser
    │
Document Model
    │
    ▼ LayoutPipeline.process()
    │
UnifiedLayout
    │
    ▼ PDFCompiler.compile()
    │
    ├─► RustBackend (default)
    │       │
    │       ▼ pdf_renderer_rust
    │
    └─► ReportLabBackend (fallback)
            │
            ▼ reportlab
    │
output.pdf
```

### HTML Round-Trip

```
document.docx
    │
    ▼ Parse + Layout
    │
UnifiedLayout
    │
    ▼ HTMLExporter (editable=True)
    │
editable.html
    │
    ▼ [User edits in browser]
    │
modified.html
    │
    ▼ HTMLImporter.update_from_html()
    │
Updated Document Model
    │
    ▼ DOCXExporter.save()
    │
updated.docx
```

## Extension Points

### Custom Renderers

Implement `BaseRenderer` interface:

```python
class CustomRenderer(BaseRenderer):
    def render_paragraph(self, block: LayoutBlock) -> None: ...
    def render_table(self, block: LayoutBlock) -> None: ...
    def render_image(self, block: LayoutBlock) -> None: ...
```

### Custom Placeholder Types

Register in `PlaceholderResolver`:

```python
resolver.register_type("CUSTOM", CustomPlaceholderHandler())
```

### Plugin System

`plugin_system.py` provides hooks for extending functionality without modifying core code.

## Performance Considerations

1. **Image Caching**: WMF/EMF conversion is async with caching
2. **Style Deduplication**: JSON export deduplicates repeated styles
3. **Lazy Parsing**: Headers/footers parsed on demand
4. **Rust Backend**: Native code for PDF rendering hot path
5. **Sequential Rendering**: `parallelism=1` default (thread sync overhead)

## File Organization

```
packages/
├── docquill_core/          # Main Python package
│   └── docquill/
│       ├── __init__.py     # Public API exports
│       ├── api.py          # Document class
│       ├── document_api.py # Extended document operations
│       ├── cli.py          # Command-line interface
│       ├── parser/         # DOCX parsing
│       ├── models/         # Document model classes
│       ├── engine/         # Layout pipeline
│       │   ├── pdf/        # PDF compilation
│       │   ├── html/       # HTML compiler
│       │   └── text_metrics/ # Text measurement
│       ├── renderers/      # Output renderers
│       ├── export/         # JSON/DOCX exporters
│       ├── importers/      # JSON importer
│       ├── styles/         # Style management
│       ├── layout/         # Page/section models
│       ├── utils/          # Utilities
│       └── media/          # Image conversion
│
├── docquill_pdf_rust/      # Rust PDF backend
│   ├── src/
│   │   ├── lib.rs          # PyO3 bindings
│   │   ├── renderer.rs     # PDF generation
│   │   └── canvas.rs       # High-level API
│   └── Cargo.toml
│
└── docquill_pro/           # Future PRO modules
```

