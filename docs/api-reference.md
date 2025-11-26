# API Reference

Complete documentation of DocQuill's public API.

## Document Class

The main entry point for all document operations.

### Constructor & Factory Methods

```python
Document(file_path: str | Path)
Document.open(file_path: str | Path) -> Document
Document.create() -> Document
```

| Method | Description |
|--------|-------------|
| `Document(path)` | Open existing DOCX file |
| `Document.open(path)` | Alias for constructor |
| `Document.create()` | Create new empty document |

### Core Methods

#### Document Model

```python
doc.to_model() -> DocumentModel
```

Returns the parsed document model with body, headers, footers, and metadata.

#### Layout Pipeline

```python
doc.pipeline(
    page_size: tuple[float, float] = (595, 842),  # A4 in points
    margins: tuple[float, float, float, float] = (72, 72, 72, 72),
    apply_headers_footers: bool = True,
    validate: bool = False,
    target: str = "pdf"
) -> UnifiedLayout
```

Process document through layout engine, returning positioned blocks.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page_size` | `tuple[float, float]` | `(595, 842)` | Width, height in points |
| `margins` | `tuple[float, float, float, float]` | `(72, 72, 72, 72)` | Top, bottom, left, right |
| `apply_headers_footers` | `bool` | `True` | Include headers/footers |
| `validate` | `bool` | `False` | Run layout validation |
| `target` | `str` | `"pdf"` | Target format hint |

### Rendering

#### PDF Output

```python
doc.to_pdf(
    output_path: str | Path,
    backend: str = "rust",
    page_size: tuple[float, float] = None,
    margins: tuple[float, float, float, float] = None,
    parallelism: int = 1,
    watermark_opacity: float = None,
    apply_headers_footers: bool = True,
    validate: bool = False
) -> Path
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `output_path` | `str \| Path` | required | Output file path |
| `backend` | `str` | `"rust"` | `"rust"` or `"reportlab"` |
| `page_size` | `tuple` | `None` | Override page dimensions |
| `margins` | `tuple` | `None` | Override margins |
| `parallelism` | `int` | `1` | Parallel rendering (experimental) |
| `watermark_opacity` | `float` | `None` | Global watermark opacity (0.0-1.0) |

#### HTML Output

```python
doc.to_html(
    output_path: str | Path,
    editable: bool = False,
    page_size: tuple[float, float] = None,
    margins: tuple[float, float, float, float] = None,
    apply_headers_footers: bool = False,
    validate: bool = False,
    embed_images_as_data_uri: bool = False,
    page_max_width: float = 960.0
) -> Path
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `editable` | `bool` | `False` | Enable contenteditable |
| `embed_images_as_data_uri` | `bool` | `False` | Inline images as base64 |
| `page_max_width` | `float` | `960.0` | Max width in CSS pixels |

#### HTML Import

```python
doc.update_from_html_file(
    html_path: str | Path,
    preserve_structure: bool = True
) -> None
```

Import changes from edited HTML back into document model.

### Template Operations

#### Fill Placeholders

```python
doc.fill_placeholders(
    data: dict[str, Any],
    multi_pass: bool = False
) -> None
```

Fill template placeholders with provided data.

**Supported placeholder types:**

| Type | Key Format | Value Type | Example |
|------|------------|------------|---------|
| `TEXT` | `TEXT:Key` | `str` | `{"TEXT:Name": "John"}` |
| `DATE` | `DATE:Key` | `str` | `{"DATE:Due": "2025-01-15"}` |
| `CURRENCY` | `CURRENCY:Key` | `float` | `{"CURRENCY:Total": 1234.56}` |
| `PHONE` | `PHONE:Key` | `str` | `{"PHONE:Tel": "1234567890"}` |
| `QR` | `QR:Key` | `str` | `{"QR:Code": "https://..."}` |
| `TABLE` | `TABLE:Key` | `dict` | `{"TABLE:Items": {"headers": [...], "rows": [...]}}` |
| `IMAGE` | `IMAGE:Key` | `str` | `{"IMAGE:Logo": "logo.png"}` |
| `LIST` | `LIST:Key` | `list[str]` | `{"LIST:Items": ["a", "b", "c"]}` |

#### Conditional Blocks

```python
doc.process_conditional_block(
    name: str,
    show: bool
) -> None
```

Show or hide conditional block marked with `{{ START_name }}...{{ END_name }}`.

#### Extract Placeholders

```python
doc.extract_placeholders() -> list[Placeholder]
```

Returns list of all placeholders found in document.

### Text Operations

#### Replace Text

```python
doc.replace_text(
    old: str,
    new: str,
    scope: str = "all",
    case_sensitive: bool = True
) -> int
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `old` | `str` | required | Text to find |
| `new` | `str` | required | Replacement text |
| `scope` | `str` | `"all"` | `"all"`, `"body"`, `"headers"`, `"footers"` |
| `case_sensitive` | `bool` | `True` | Case-sensitive matching |

Returns number of replacements made.

### Content Creation

#### Paragraphs

```python
doc.add_paragraph(
    text: str,
    style: str = None
) -> Paragraph
```

#### Runs (Formatted Text)

```python
doc.add_run(
    paragraph: Paragraph,
    text: str,
    bold: bool = False,
    italic: bool = False,
    underline: bool = False,
    font_color: str = None,
    font_name: str = None,
    font_size: int = None
) -> Run
```

#### Lists

```python
doc.create_numbered_list() -> NumberingDefinition
doc.create_bullet_list() -> NumberingDefinition

# Usage:
para = doc.add_paragraph("Item text")
para.set_list(numbering_def, level=0)
```

### Document Merging

#### Full Merge

```python
doc.merge(
    other: str | Path | Document,
    page_break: bool = False
) -> None
```

Append entire document content.

#### Selective Merge

```python
doc.merge_selective(
    options: dict[str, Document]
) -> None
```

Merge specific parts from different documents:

```python
doc.merge_selective({
    "body": Document.open("content.docx"),
    "headers": Document.open("header.docx"),
    "footers": Document.open("footer.docx"),
    "styles": Document.open("styles.docx")
})
```

#### Component Merge

```python
doc.merge_headers(source: str | Path | Document) -> None
doc.merge_footers(source: str | Path | Document) -> None
doc.merge_styles(source: str | Path | Document) -> None
doc.merge_sections(source: str | Path | Document, copy_properties: bool = True) -> None
```

#### Append/Prepend

```python
doc.append(other: str | Path | Document) -> None
doc.prepend(other: str | Path | Document) -> None
```

### Metadata & Info

```python
doc.get_metadata() -> dict
doc.get_title() -> str | None
doc.get_author() -> str | None
doc.get_subject() -> str | None
doc.get_keywords() -> str | None
doc.get_description() -> str | None

doc.get_stats() -> dict  # paragraphs, tables, images counts
doc.get_sections() -> list[Section]
doc.get_styles() -> dict[str, Style]
doc.get_numbering() -> dict
```

### Watermarks

```python
doc.add_watermark(
    text: str,
    angle: float = 45,
    opacity: float = 0.3,
    color: str = "#000000",
    font_size: float = 72,
    font_name: str = "Arial"
) -> None

doc.get_watermarks() -> list[Watermark]
```

### Normalization

```python
doc.normalize(
    output_path: str | Path = None
) -> Document
```

Clean document structure (merge runs, normalize styles). Returns new Document instance.

### Validation

```python
doc.validate_layout(
    **pipeline_kwargs
) -> tuple[UnifiedLayout, bool, list[str], list[str]]
```

Returns `(layout, is_valid, errors, warnings)`.

### Save

```python
doc.save(file_path: str | Path) -> Path
```

Save document to DOCX file.

### Properties

```python
doc.body -> Body                    # Document body
doc.package_reader -> PackageReader # Low-level DOCX access
doc.xml_parser -> XMLParser         # XML parser instance
doc.layout -> UnifiedLayout | None  # Cached layout (after pipeline())
doc.metadata -> dict                # Document metadata
doc.watermarks -> list[Watermark]   # Watermark list
```

---

## Convenience Functions

Module-level functions for common operations:

```python
from docx_interpreter import (
    open_document,
    create_document,
    fill_template,
    merge_documents,
    render_to_pdf,
    render_to_html
)
```

### open_document

```python
open_document(file_path: str | Path) -> Document
```

### create_document

```python
create_document() -> Document
```

### fill_template

```python
fill_template(
    template_path: str | Path,
    data: dict[str, Any],
    output_path: str | Path
) -> Path
```

### merge_documents

```python
merge_documents(
    main_path: str | Path,
    others: list[str | Path],
    output_path: str | Path,
    page_breaks: bool = True
) -> Path
```

### render_to_pdf

```python
render_to_pdf(
    input_path: str | Path,
    output_path: str | Path,
    **kwargs
) -> Path
```

### render_to_html

```python
render_to_html(
    input_path: str | Path,
    output_path: str | Path,
    editable: bool = False,
    **kwargs
) -> Path
```

---

## Data Classes

### UnifiedLayout

```python
class UnifiedLayout:
    pages: list[LayoutPage]
    current_page: int
    
    def export_json(path: str, format: str = "optimized_pipeline") -> None
```

### LayoutPage

```python
class LayoutPage:
    number: int
    size: Size
    margins: Margins
    blocks: list[LayoutBlock]
    skip_headers_footers: bool
```

### LayoutBlock

```python
class LayoutBlock:
    frame: Rect           # Position and size
    block_type: str       # "paragraph", "table", "image", etc.
    content: Any          # Block content
    style: dict           # Style properties
    page_number: int
    source_uid: str
    sequence: int
```

### Geometry

```python
class Size:
    width: float
    height: float

class Margins:
    top: float
    bottom: float
    left: float
    right: float

class Rect:
    x: float
    y: float
    width: float
    height: float
```

---

## Exceptions

```python
from docx_interpreter.exceptions import (
    DocxError,      # Base exception
    ParseError,     # Document parsing failed
    RenderError,    # Rendering failed
    ValidationError # Layout validation failed
)
```

