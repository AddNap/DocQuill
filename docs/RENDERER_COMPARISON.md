# Porównanie Rendererów: ReportLab vs Rust

## Przegląd

Oba renderery (ReportLab i Rust) korzystają z tego samego pipeline (`LayoutPipeline` → `LayoutAssembler` → `UnifiedLayout`), ale różnią się w sposobie obsługi danych:

- **ReportLab**: Otrzymuje obiekty Python (`BlockContent`, `ParagraphLayout`, etc.)
- **Rust**: Otrzymuje zserializowany JSON z tych samych danych

## 1. Rozpakowywanie Contentu

### ReportLab (`pdf_compiler.py`)
```python
@staticmethod
def _resolve_content(content: Any) -> tuple[Any, Optional[Any]]:
    """Rozpakowuje BlockContent do surowego słownika lub payloadu."""
    if isinstance(content, BlockContent):
        raw = content.raw
        payload = content.payload
        if raw is not None:
            return raw, payload
        return payload, payload
    return content, None
```

**Użycie:**
```python
content_value, payload_candidate = self._resolve_content(block.content)
marker = content_value.get("marker") if isinstance(content_value, dict) else None
```

### Rust (`renderer.rs`)
```rust
// Content jest już dict (JSON), więc nie ma potrzeby rozpakowywania
let content = block.get("content")
    .and_then(|c| c.as_object())
    .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Missing content"))?;

let marker = content.get("marker")
    .and_then(|m| m.as_object());
```

**Różnica**: ReportLab rozpakowuje `BlockContent` obiekt, Rust otrzymuje już zserializowany JSON.

---

## 2. Extrakcja ParagraphLayout

### ReportLab
```python
paragraph_payload: Optional[ParagraphLayout] = None
if isinstance(block.content, BlockContent) and isinstance(block.content.payload, ParagraphLayout):
    paragraph_payload = block.content.payload
elif isinstance(payload_candidate, ParagraphLayout):
    paragraph_payload = payload_candidate
elif isinstance(content_value, dict):
    candidate = content_value.get("layout_payload") or content_value.get("_layout_payload")
    if isinstance(candidate, ParagraphLayout):
        paragraph_payload = candidate
```

**Używa bezpośrednio obiektu Python `ParagraphLayout`** z atrybutami:
- `payload.lines` - lista obiektów `Line`
- `payload.style` - obiekt `ParagraphStyle`
- `payload.metadata` - dict z metadanymi

### Rust
```rust
let layout_payload = content.get("layout_payload")
    .or_else(|| content.get("_layout_payload"))
    .and_then(|l| l.as_object());

// Następnie parsuje JSON:
let lines = layout_payload
    .and_then(|l| l.get("lines"))
    .and_then(|l| l.as_array())?;
```

**Parsuje zserializowany JSON** i musi ręcznie wyciągać:
- `layout_payload.lines` - array JSON
- `layout_payload.style` - object JSON
- `layout_payload.metadata` - object JSON

**Różnica**: ReportLab ma dostęp do typowanych obiektów Python, Rust musi parsować JSON.

---

## 3. Obsługa Markerów

### ReportLab
```python
# Marker jest przekazywany jako parametr do _draw_paragraph_from_layout
marker = content_value.get("marker") if isinstance(content_value, dict) else None

if marker:
    marker_text = (
        marker.get("text")
        or marker.get("label")
        or marker.get("display")
        or marker.get("bullet")
        or ""
    )
    marker_x = marker.get("x")
    marker_baseline = first_line_baseline if first_line_baseline is not None else ...
    # Renderuje bezpośrednio
    c.drawString(float(marker_x), marker_baseline, marker_text)
```

**Sprawdza tylko `content.marker`** (po rozpakowaniu `_resolve_content`).

### Rust
```rust
// Sprawdza wiele miejsc:
let marker = content.get("marker")
    .and_then(|m| m.as_object())
    .or_else(|| {
        content.get("meta")
            .and_then(|m| m.as_object())
            .and_then(|m| m.get("marker"))
            .and_then(|m| m.as_object())
    })
    .or_else(|| {
        content.get("payload")
            .and_then(|p| p.as_object())
            .and_then(|p| p.get("marker"))
            .and_then(|m| m.as_object())
    })
    .or_else(|| {
        layout.get("marker").and_then(|m| m.as_object())
    });

// Sprawdza też marker_override_text
let marker_override_text = metadata
    .and_then(|m| m.get("marker_override_text"))
    .and_then(|v| v.as_str())
    .or_else(|| {
        content.get("meta")
            .and_then(|m| m.as_object())
            .and_then(|m| m.get("marker_override_text"))
            .and_then(|v| v.as_str())
    });
```

**Sprawdza wiele miejsc** (`content.marker`, `content.meta.marker`, `content.payload.marker`, `layout.marker`, `content.raw.marker`) i obsługuje `marker_override_text`.

**Różnica**: Rust jest bardziej elastyczny i sprawdza więcej lokalizacji, co jest potrzebne ze względu na serializację JSON.

---

## 4. Renderowanie Linii i Inline Items

### ReportLab
```python
for line_index, line in enumerate(payload.lines):
    baseline_y = text_top - line.baseline_y
    line_start_x = text_left + line.offset_x
    
    for inline_idx, inline in enumerate(line.items):
        item_x = line_start_x + inline.x + cumulative_extra
        
        if inline.kind in ("text_run", "field"):
            data = inline.data or {}
            text = data.get("text") or data.get("display") or ""
            
            # Bezpośredni dostęp do atrybutów obiektu
            run_style = data.get("style") or {}
            font_name = run_style.get("font_name") or default_font_name
            font_size = float(run_style.get("font_size") or default_font_size)
            
            c.drawString(item_x, run_baseline, text)
```

**Bezpośredni dostęp do atrybutów obiektu** (`inline.kind`, `inline.data`, `inline.x`, `inline.width`).

### Rust
```rust
let lines = layout_payload
    .and_then(|l| l.get("lines"))
    .and_then(|l| l.as_array())?;

for line_obj in lines {
    let baseline_y = line_obj.get("baseline_y")
        .and_then(|v| v.as_f64())
        .unwrap_or(0.0);
    let offset_x = line_obj.get("offset_x")
        .and_then(|v| v.as_f64())
        .unwrap_or(0.0);
    
    let items = line_obj.get("items")
        .and_then(|i| i.as_array())?;
    
    for item_obj in items {
        let item_kind = item_obj.get("kind")
            .and_then(|k| k.as_str())
            .unwrap_or("text_run");
        
        let item_x = item_obj.get("x")
            .and_then(|v| v.as_f64())
            .unwrap_or(0.0);
        
        let data = item_obj.get("data")
            .and_then(|d| d.as_object())?;
        
        let text = data.get("text")
            .or_else(|| data.get("display"))
            .and_then(|v| v.as_str())
            .unwrap_or("");
        
        // Parsowanie style z JSON
        let run_style = data.get("style")
            .and_then(|s| s.as_object())
            .unwrap_or(&serde_json::Map::new());
        
        let font_name = run_style.get("font_name")
            .and_then(|v| v.as_str())
            .unwrap_or(default_font_name);
        
        let font_size = run_style.get("font_size")
            .and_then(|v| v.as_f64())
            .unwrap_or(default_font_size);
        
        canvas.draw_string(item_x, run_baseline, text, font_name, font_size, color)?;
    }
}
```

**Musi parsować każdy element z JSON** używając `get()`, `as_f64()`, `as_str()`, etc.

**Różnica**: ReportLab ma typowane obiekty, Rust musi parsować JSON ręcznie.

---

## 5. Field Codes

### ReportLab
```python
def _resolve_field_text(self, field_info: Optional[Dict[str, Any]]) -> str:
    field_type = str(field_info.get("field_type") or field_info.get("type") or "").upper()
    current_page = self._current_page_number if self._current_page_number > 0 else 1
    total_pages = self._total_pages if self._total_pages > 0 else 1
    
    context = {
        "current_page": current_page,
        "total_pages": total_pages,
    }
    
    instruction = (
        field_info.get("instruction")
        or field_info.get("instr")
        or field_info.get("code")
        or ""
    )
    
    try:
        field_model = Field()
        if instruction:
            field_model.set_instr(instruction)
        field_model.update_context(context)
        calculated = field_model.calculate_value(context)
        if calculated:
            return str(calculated)
    except Exception:
        pass
    
    # Fallback
    fallback = field_info.get("result") or field_info.get("value") or ...
    if field_type == "PAGE" and not fallback:
        return str(context["current_page"])
    if field_type == "NUMPAGES" and not fallback:
        return str(context["total_pages"])
    return str(fallback)
```

**Używa obiektu `Field` z Python** do obliczania wartości.

### Rust
```rust
pub fn resolve_field_text(
    field_info: Option<&serde_json::Map<String, serde_json::Value>>,
    current_page: u32,
    total_pages: u32,
) -> String {
    let field = field_info?;
    
    // Get field type - try multiple keys
    let field_type = field.get("field_type")
        .or_else(|| field.get("type"))
        .or_else(|| field.get("fieldType"))
        .or_else(|| field.get("name"))
        .and_then(|v| v.as_str())
        .map(|s| s.to_uppercase())
        .unwrap_or_else(|| String::new());
    
    // Get instruction - try multiple keys
    let instruction = field.get("instruction")
        .or_else(|| field.get("instr"))
        .or_else(|| field.get("code"))
        .or_else(|| field.get("field_code"))
        .and_then(|v| v.as_str())
        .map(|s| s.to_uppercase())
        .unwrap_or_else(|| String::new());
    
    // Detect field type from instruction if not set
    let detected_type = if field_type.is_empty() && !instruction.is_empty() {
        if instruction.contains("PAGE") {
            "PAGE"
        } else if instruction.contains("NUMPAGES") {
            "NUMPAGES"
        } else {
            ""
        }
    } else {
        field_type.as_str()
    };
    
    // Resolve field value based on type
    match detected_type {
        "PAGE" => format!("{}", current_page.max(1)),
        "NUMPAGES" => format!("{}", total_pages.max(1)),
        "DATE" => { /* simple date formatting */ },
        "TIME" => { /* simple time formatting */ },
        _ => {
            field.get("result")
                .or_else(|| field.get("value"))
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string()
        }
    }
}
```

**Implementuje logikę bezpośrednio w Rust** (nie używa obiektu Python).

**Różnica**: ReportLab używa modelu `Field` z Python, Rust ma własną implementację.

---

## 6. Obrazy

### ReportLab
```python
def _resolve_image_path(self, image: Any) -> Optional[str]:
    if isinstance(image, dict):
        initial_path = image.get("path") or image.get("src") or image.get("image_path")
    else:
        initial_path = getattr(image, "path", None) or getattr(image, "image_path", None)
    
    resolved = self._ensure_bitmap_path(image, initial_path)
    # Konwersja WMF/EMF do PNG przez MediaConverter
    return resolved

def _ensure_bitmap_path(self, image: Any, initial_path: Optional[str]) -> Optional[str]:
    # Sprawdza cache prekonwertowanych obrazów
    if self.image_cache and rel_id:
        cached_path = self.image_cache.get(rel_id, wait=True)
        if cached_path and cached_path.exists():
            return str(cached_path)
    
    # Konwersja WMF/EMF do PNG
    if suffix in {".wmf", ".emf"}:
        png_bytes = self.media_converter.convert_emf_to_png(
            image_bytes,
            width=width_px,
            height=height_px,
        )
        # Zapisuje do pliku tymczasowego
        temp_png = self._register_temp_file(png_bytes, ".png")
        return str(temp_png)
```

**Używa `MediaConverter` z Python** do konwersji WMF/EMF.

### Rust
```rust
pub fn load_image(
    path: &str,
    target_width_emu: Option<f64>,
    target_height_emu: Option<f64>,
) -> PyResult<ImageData> {
    // Wykrywa WMF/EMF
    if path.ends_with(".wmf") || path.ends_with(".emf") {
        let bytes = std::fs::read(path)?;
        // Konwersja do SVG
        let svg_content = emf_converter::convert_emf_bytes_to_svg(&bytes)?;
        return Ok(ImageData::Svg(svg_content));
    }
    
    // Dla innych formatów używa biblioteki `image`
    let img = image::open(path)?;
    Ok(ImageData::Image(img))
}

pub fn add_image_to_pdf(
    pdf: &mut Pdf,
    image_data: &ImageData,
    width_emu: Option<f64>,
    height_emu: Option<f64>,
) -> PyResult<Name<'static>> {
    // Jeśli SVG, konwertuje do PNG
    let image = match image_data {
        ImageData::Svg(svg_content) => {
            convert_svg_to_png(svg_content, width_emu, height_emu)?
        }
        ImageData::Image(img) => img.clone(),
    };
    // Dodaje do PDF
}
```

**Używa biblioteki Rust `emf-converter`** do konwersji WMF/EMF → SVG, a następnie `resvg` do SVG → PNG.

**Różnica**: ReportLab używa konwertera Python, Rust używa bibliotek Rust.

---

## 7. Tabele

### ReportLab
```python
def _draw_table(self, c: canvas.Canvas, block: LayoutBlock) -> None:
    content_value, _payload = self._resolve_content(block.content)
    content = content_value if isinstance(content_value, dict) else {}
    
    rows = content.get("rows", [])
    
    # Renderuje komórki
    for row_idx, row in enumerate(rows):
        cells = row if isinstance(row, list) else [row]
        for cell_idx, cell in enumerate(cells):
            # Pobiera content komórki
            cell_content_items = self._extract_cell_content(cell)
            
            # Renderuje paragrafy w komórce
            if self._render_cell_paragraphs(
                c,
                cell_content_items,
                cell_rect,
                cell_margins,
                header_footer_context,
                style_override,
                vertical_align,
            ):
                continue
            
            # Renderuje obrazy w komórce
            cell_images = []
            if hasattr(cell, 'get_images'):
                for img in cell.get_images() or []:
                    cell_images.append(img)
            
            for img in cell_images:
                img_path = self._resolve_image_path(img)
                c.drawImage(img_path, img_x, img_y, width=render_width, height=render_height)
```

**Bezpośredni dostęp do obiektów** (`cell.get_images()`, `cell.content`).

### Rust
```rust
pub fn render_table(
    canvas: &mut PdfCanvas,
    pdf: &mut Pdf,
    fonts_registry: &mut FontRegistry,
    images_registry: &mut ImageRegistry,
    block: &serde_json::Map<String, serde_json::Value>,
    current_page: u32,
    total_pages: u32,
) -> PyResult<()> {
    let content = block.get("content")
        .and_then(|c| c.as_object())?;
    
    let rows = content.get("rows")
        .and_then(|r| r.as_array())?;
    
    for row_obj in rows {
        let cells = row_obj.get("cells")
            .and_then(|c| c.as_array())?;
        
        for cell_obj in cells {
            // Parsuje content komórki z JSON
            let cell_content = cell_obj.get("content")
                .and_then(|c| c.as_array());
            
            // Renderuje paragrafy w komórce
            if let Some(content_array) = cell_content {
                for item_obj in content_array {
                    // Sprawdza czy to paragraf
                    if item_obj.get("type")
                        .and_then(|t| t.as_str()) == Some("paragraph") {
                        render_paragraph(...)?;
                    }
                    
                    // Sprawdza obrazy
                    if let Some(images) = item_obj.get("images")
                        .and_then(|i| i.as_array()) {
                        for img_obj in images {
                            render_image(...)?;
                        }
                    }
                }
            }
        }
    }
}
```

**Parsuje wszystko z JSON** (`get()`, `as_array()`, `as_object()`).

**Różnica**: ReportLab ma dostęp do obiektów Python, Rust parsuje JSON.

---

## 8. Header/Footer

### ReportLab
```python
def _draw_header(self, c: canvas.Canvas, block: LayoutBlock) -> None:
    content_value, _payload = self._resolve_content(block.content)
    images = []
    text = ""
    
    if isinstance(content_value, dict):
        text = content_value.get("text", content_value.get("content", ""))
        images = content_value.get("images", [])
    
    # Renderuje obrazy
    if images:
        for img in images:
            img_path = self._resolve_image_path(img)
            c.drawImage(img_path, x, y, width=calc_width, height=calc_height)
    
    # Renderuje tekst
    if text:
        self._draw_paragraph(c, block)
```

**Bezpośredni dostęp do `content.images`**.

### Rust
```rust
pub fn render_header(
    canvas: &mut PdfCanvas,
    pdf: &mut Pdf,
    fonts_registry: &mut FontRegistry,
    images_registry: &mut ImageRegistry,
    block: &serde_json::Map<String, serde_json::Value>,
    current_page: u32,
    total_pages: u32,
) -> PyResult<()> {
    let content = block.get("content")
        .and_then(|c| c.as_object())?;
    
    // Sprawdza obrazy w różnych miejscach
    let images = content.get("images")
        .and_then(|i| i.as_array())
        .or_else(|| {
            content.get("payload")
                .and_then(|p| p.as_object())
                .and_then(|p| p.get("images"))
                .and_then(|i| i.as_array())
        });
    
    // Renderuje obrazy
    if let Some(images_array) = images {
        for img_obj in images_array {
            // Sprawdza anchor_type (pomija "anchor" - są w overlays)
            let anchor_type = img_obj.get("anchor_type")
                .and_then(|a| a.as_str());
            if anchor_type == Some("anchor") {
                continue;
            }
            
            render_image(...)?;
        }
    }
    
    // Sprawdza overlays
    let overlays = content.get("payload")
        .and_then(|p| p.as_object())
        .and_then(|p| p.get("overlays"))
        .and_then(|o| o.as_array())
        .or_else(|| {
            content.get("overlays")
                .and_then(|o| o.as_array())
        });
    
    if let Some(overlays_array) = overlays {
        render_overlays(...)?;
    }
}
```

**Sprawdza wiele miejsc** (`content.images`, `payload.images`, `payload.overlays`, `content.overlays`) i obsługuje deduplikację.

**Różnica**: Rust jest bardziej defensywny i sprawdza więcej lokalizacji.

---

## Podsumowanie Kluczowych Różnic

| Aspekt | ReportLab | Rust |
|--------|-----------|------|
| **Typ danych** | Obiekty Python (`BlockContent`, `ParagraphLayout`) | Zserializowany JSON |
| **Rozpakowywanie** | `_resolve_content()` rozpakowuje `BlockContent` | Content jest już dict (JSON) |
| **ParagraphLayout** | Bezpośredni dostęp do obiektu (`payload.lines`, `payload.style`) | Parsuje JSON (`layout_payload.lines`, `layout_payload.style`) |
| **Marker** | Sprawdza tylko `content.marker` | Sprawdza wiele miejsc (`content.marker`, `meta.marker`, `payload.marker`, `raw.marker`, `layout.marker`) |
| **Inline Items** | Bezpośredni dostęp (`inline.kind`, `inline.data`) | Parsuje JSON (`item.get("kind")`, `item.get("data")`) |
| **Field Codes** | Używa obiektu Python `Field` | Własna implementacja w Rust |
| **Obrazy** | Używa `MediaConverter` (Python) | Używa `emf-converter` + `resvg` (Rust) |
| **Tabele** | Bezpośredni dostęp (`cell.get_images()`, `cell.content`) | Parsuje JSON (`cell.get("images")`, `cell.get("content")`) |
| **Header/Footer** | Sprawdza `content.images` | Sprawdza wiele miejsc + deduplikacja |

## Mapowanie 1:1: Obiekty Python → JSON

### BlockContent

**Python (ReportLab):**
```python
@dataclass(slots=True)
class BlockContent:
    payload: BlockPayload  # ParagraphLayout, TableLayout, etc.
    raw: Dict[str, Any]     # Oryginalny słownik źródłowy
```

**Serializacja do JSON (Rust):**
```python
# W _content_to_dict():
if is_dataclass(content):  # BlockContent
    for field in fields(content):
        if field_name == 'payload':
            result['payload'] = serialized_payload
            # Jeśli payload ma layout_payload, dodaj go też na top level
            if hasattr(field_value, 'layout_payload'):
                result['layout_payload'] = serialized_layout
        elif field_name == 'raw':
            # raw jest merge'owany do głównego dict
            result.update(serialized_raw)
```

**JSON (Rust renderer otrzymuje):**
```json
{
  "payload": { /* ParagraphLayout lub inny BlockPayload */ },
  "layout_payload": { /* jeśli payload to ParagraphLayout */ },
  "raw": { /* zawartość raw jest merge'owana tutaj */ },
  "marker": { /* z raw */ },
  "images": [ /* z raw */ ],
  "text": "/* z raw */",
  ...
}
```

**Mapowanie:**
- `BlockContent.payload` → `content.payload` (JSON)
- `BlockContent.raw` → merge'owane do głównego `content` (JSON)
- `BlockContent.raw.marker` → `content.marker` (JSON)
- `BlockContent.raw.images` → `content.images` (JSON)

### ParagraphLayout

**Python (ReportLab):**
```python
@dataclass(slots=True)
class ParagraphLayout:
    lines: List[ParagraphLine]
    overlays: List[OverlayBox]
    style: BoxStyle
    metadata: Dict[str, Any]
```

**Serializacja do JSON:**
```python
# W _serialize_layout_payload_optimized():
result = {
    'lines': [
        {
            'baseline_y': line.baseline_y,
            'offset_x': line.offset_x,
            'available_width': line.available_width,
            'items': [ /* InlineBox items */ ]
        }
    ],
    'style': { /* BoxStyle */ }
}
```

**JSON (Rust renderer otrzymuje):**
```json
{
  "layout_payload": {
    "lines": [
      {
        "baseline_y": 12.5,
        "offset_x": 0.0,
        "available_width": 500.0,
        "items": [ /* ... */ ]
      }
    ],
    "style": { /* ... */ }
  }
}
```

**Mapowanie:**
- `ParagraphLayout.lines` → `layout_payload.lines` (JSON)
- `ParagraphLayout.style` → `layout_payload.style` (JSON)
- `ParagraphLayout.metadata` → `payload.metadata` (JSON) - **UWAGA**: metadata jest w `payload`, nie w `layout_payload`!

### ParagraphLine

**Python (ReportLab):**
```python
@dataclass(slots=True)
class ParagraphLine:
    baseline_y: float
    height: float
    items: List[InlineBox]
    offset_x: float = 0.0
    available_width: float = 0.0
```

**JSON:**
```json
{
  "baseline_y": 12.5,
  "height": 14.4,
  "offset_x": 0.0,
  "available_width": 500.0,
  "items": [ /* InlineBox items */ ]
}
```

**Mapowanie 1:1:**
- `ParagraphLine.baseline_y` → `line.baseline_y`
- `ParagraphLine.height` → `line.height`
- `ParagraphLine.items` → `line.items`
- `ParagraphLine.offset_x` → `line.offset_x`
- `ParagraphLine.available_width` → `line.available_width`

### InlineBox

**Python (ReportLab):**
```python
@dataclass(slots=True)
class InlineBox:
    kind: InlineKind  # "text_run", "field", "inline_image", "inline_textbox"
    x: float
    width: float
    ascent: float
    descent: float
    data: Dict[str, Any]
```

**Serializacja do JSON:**
```python
# W _serialize_layout_payload_optimized():
item_dict = {
    'kind': item.kind,
    'x': item.x,
    'width': item.width,
    'ascent': item.ascent,
    'descent': item.descent,
    'data': {
        'text': data.get('text'),
        'display': data.get('display'),
        'font': data.get('font'),
        'size': data.get('size'),
        'color': data.get('color'),
        'image': data.get('image'),  # dla inline_image
        'style': data.get('style'),  # jeśli istnieje
        ...
    }
}
```

**JSON:**
```json
{
  "kind": "text_run",
  "x": 0.0,
  "width": 50.5,
  "ascent": 8.5,
  "descent": 2.1,
  "data": {
    "text": "Hello",
    "style": {
      "font_name": "Helvetica",
      "font_size": 11.0,
      "color": "#000000"
    }
  }
}
```

**Mapowanie 1:1:**
- `InlineBox.kind` → `item.kind`
- `InlineBox.x` → `item.x`
- `InlineBox.width` → `item.width`
- `InlineBox.ascent` → `item.ascent`
- `InlineBox.descent` → `item.descent`
- `InlineBox.data` → `item.data`

### Marker

**Python (ReportLab):**
```python
# Marker jest w BlockContent.raw
marker = content_value.get("marker")  # po _resolve_content()
```

**Serializacja:**
```python
# W _content_to_dict():
# raw jest merge'owany do głównego dict
if field_name == 'raw':
    result.update(serialized_raw)  # marker z raw trafia do content.marker
```

**JSON:**
```json
{
  "content": {
    "marker": {
      "text": "1.",
      "x": 50.0,
      "baseline_offset": 0.0,
      "number_position": 50.0,
      "indent_left": 72.0,
      "indent_hanging": 22.0
    }
  }
}
```

**Mapowanie:**
- `BlockContent.raw.marker` → `content.marker` (JSON)
- **UWAGA**: Rust renderer sprawdza też `content.meta.marker`, `content.payload.marker`, `content.raw.marker`, `layout.marker` (defensywny)

### Metadata i marker_override_text

**Python:**
```python
# W layout_engine.py:
marker_override = meta.get("marker_override_text")
if marker_override is not None:
    marker_dict = block.get("marker")
    marker_dict["text"] = marker_override
    block["marker"] = marker_dict
```

**Serializacja:**
```python
# W _content_to_dict():
# metadata z ParagraphLayout.metadata trafia do payload.metadata
# ale raw.meta też może być merge'owany
```

**JSON:**
```json
{
  "content": {
    "payload": {
      "metadata": {
        "marker_override_text": "1.1"
      }
    },
    "meta": {  // z raw
      "marker_override_text": "1.1"
    }
  }
}
```

**Mapowanie:**
- `ParagraphLayout.metadata.marker_override_text` → `payload.metadata.marker_override_text` (JSON)
- `BlockContent.raw.meta.marker_override_text` → `content.meta.marker_override_text` (JSON)
- **Rust renderer** sprawdza oba miejsca

## Kluczowe Różnice w Dostępie

### ReportLab Renderer

```python
# 1. Rozpakowuje BlockContent
content_value, payload_candidate = self._resolve_content(block.content)
# content_value = BlockContent.raw (dict)
# payload_candidate = BlockContent.payload (ParagraphLayout)

# 2. Pobiera marker z raw
marker = content_value.get("marker")  # z BlockContent.raw

# 3. Pobiera ParagraphLayout
if isinstance(block.content, BlockContent):
    paragraph_payload = block.content.payload  # Bezpośredni dostęp
elif isinstance(payload_candidate, ParagraphLayout):
    paragraph_payload = payload_candidate

# 4. Używa obiektu ParagraphLayout
for line in paragraph_payload.lines:  # Bezpośredni dostęp do atrybutu
    for inline in line.items:
        text = inline.data.get("text")  # inline.data jest dict
```

### Rust Renderer

```rust
// 1. Content jest już dict (JSON)
let content = block.get("content")
    .and_then(|c| c.as_object())?;

// 2. Pobiera marker (sprawdza wiele miejsc)
let marker = content.get("marker")  // z BlockContent.raw (merge'owany)
    .or_else(|| content.get("meta").and_then(|m| m.get("marker")))
    .or_else(|| content.get("payload").and_then(|p| p.get("marker")));

// 3. Pobiera layout_payload
let layout_payload = content.get("layout_payload")
    .or_else(|| content.get("_layout_payload"))
    .and_then(|l| l.as_object())?;

// 4. Parsuje JSON
let lines = layout_payload.get("lines")
    .and_then(|l| l.as_array())?;

for line_obj in lines {
    let baseline_y = line_obj.get("baseline_y")
        .and_then(|v| v.as_f64())?;  // Ręczne parsowanie
    
    let items = line_obj.get("items")
        .and_then(|i| i.as_array())?;
    
    for item_obj in items {
        let text = item_obj.get("data")
            .and_then(|d| d.as_object())?
            .get("text")
            .and_then(|t| t.as_str())?;  // Wielopoziomowe parsowanie
    }
}
```

## Mapowanie Struktur - Tabela

| Python (ReportLab) | JSON (Rust) | Uwagi |
|-------------------|-------------|-------|
| `BlockContent.raw` | `content.*` (merge'owany) | Wszystkie pola z `raw` są na top level `content` |
| `BlockContent.raw.marker` | `content.marker` | Rust sprawdza też `meta.marker`, `payload.marker` |
| `BlockContent.payload` | `content.payload` | |
| `BlockContent.payload.layout_payload` | `content.layout_payload` | Dodatkowo na top level dla łatwego dostępu |
| `ParagraphLayout.lines` | `layout_payload.lines` | |
| `ParagraphLayout.style` | `layout_payload.style` | |
| `ParagraphLayout.metadata` | `payload.metadata` | **UWAGA**: Nie w `layout_payload`! |
| `ParagraphLine.baseline_y` | `line.baseline_y` | Mapowanie 1:1 |
| `ParagraphLine.items` | `line.items` | Mapowanie 1:1 |
| `InlineBox.kind` | `item.kind` | Mapowanie 1:1 |
| `InlineBox.data` | `item.data` | Mapowanie 1:1 |
| `InlineBox.data.text` | `item.data.text` | Mapowanie 1:1 |
| `InlineBox.data.style` | `item.data.style` | Mapowanie 1:1 |

## Wnioski

1. **ReportLab renderer** ma prostszą implementację dzięki typowanym obiektom Python, ale jest mniej elastyczny.

2. **Rust renderer** jest bardziej defensywny i sprawdza więcej lokalizacji w JSON, co jest konieczne ze względu na serializację. Jest też bardziej odporny na różne struktury JSON.

3. **Oba renderery** korzystają z tego samego pipeline, ale:
   - ReportLab otrzymuje obiekty Python bezpośrednio
   - Rust otrzymuje zserializowany JSON tych samych danych

4. **Rust renderer** ma lepszą obsługę edge cases (np. `marker_override_text`, deduplikacja obrazów, sprawdzanie wielu lokalizacji dla markerów).

5. **Główne wyzwanie w Rust**: Parsowanie JSON jest bardziej verbose i podatne na błędy, ale jednocześnie bardziej elastyczne (może obsługiwać różne struktury).

6. **Mapowanie 1:1 istnieje**: Struktury JSON są bezpośrednim odzwierciedleniem obiektów Python, ale:
   - `BlockContent.raw` jest merge'owany do głównego `content` (JSON)
   - `layout_payload` jest dodawany na top level dla łatwego dostępu
   - `metadata` jest w `payload.metadata`, nie w `layout_payload.metadata`

