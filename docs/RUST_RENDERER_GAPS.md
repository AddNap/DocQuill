# Luki w Rust Rendererze w porównaniu do ReportLab

## Przegląd

Ten dokument identyfikuje funkcjonalności, które są zaimplementowane w ReportLab rendererze, ale brakuje ich lub są niekompletne w Rust rendererze.

## 1. Formatowanie Tekstu

### ✅ Zaimplementowane
- **Bold/Italic** - ✅ Działa (przez warianty fontów: `-Bold`, `-Oblique`, `-BoldOblique`)
- **Superscript/Subscript** - ✅ Struktura w `text_formatting.rs`, ale **nie używane** w `render_paragraph_from_layout`
- **Strikethrough** - ✅ Struktura w `text_formatting.rs`, ale **nie używane** w `render_paragraph_from_layout`
- **Highlight** - ✅ Struktura w `text_formatting.rs`, ale **nie używane** w `render_paragraph_from_layout`

### ❌ Brakuje
- **Underline** - ❌ Jest TODO w `renderer.rs:2286`, struktura w `text_formatting.rs`, ale **nie zaimplementowane**
- **Double Strikethrough** - ❌ Brak implementacji
- **Overline** - ❌ Brak implementacji
- **Hyperlinki** - ❌ Brak implementacji (ReportLab używa `c.linkURL()`)
- **Footnote/Endnote References** - ❌ Brak implementacji (ReportLab renderuje numery jako superscript)

### 📝 Szczegóły

#### Underline
**ReportLab (pdf_compiler.py:1900-1908):**
```python
if run_style.get("underline"):
    c.saveState()
    try:
        c.setStrokeColor(fill_color)
        c.setLineWidth(max(font_size * 0.055, 0.4))
        underline_y = run_baseline - max(font_size * 0.15, 0.6)
        c.line(item_x, underline_y, item_x + effective_width, underline_y)
    finally:
        c.restoreState()
```

**Rust (renderer.rs:2286):**
```rust
// TODO: Handle underline if text_style.underline == Some(true)
```

**Status:** Struktura w `text_formatting.rs`, ale nie używana w renderowaniu.

#### Strikethrough
**ReportLab (pdf_compiler.py:1910-1918):**
```python
if run_style.get("strike_through") or run_style.get("strikethrough"):
    c.saveState()
    try:
        c.setStrokeColor(fill_color)
        c.setLineWidth(max(font_size * 0.05, 0.4))
        strike_y = run_baseline + max(font_size * 0.3, 0.6)
        c.line(item_x, strike_y, item_x + effective_width, strike_y)
    finally:
        c.restoreState()
```

**Rust:** Struktura w `text_formatting.rs:145-155`, ale **nie używana** w `render_paragraph_from_layout`.

#### Highlight
**ReportLab (pdf_compiler.py:1862-1877):**
```python
highlight_value = data.get("highlight") or run_style.get("highlight")
highlight_color = self._resolve_highlight_color(highlight_value)
if highlight_color:
    c.saveState()
    try:
        c.setFillColor(self._color_to_reportlab(highlight_color, highlight_color))
        c.rect(
            item_x,
            run_baseline - inline.descent,
            effective_width,
            inline.ascent + inline.descent,
            fill=1,
            stroke=0,
        )
    finally:
        c.restoreState()
```

**Rust:** Struktura w `text_formatting.rs:114-128`, ale **nie używana** w `render_paragraph_from_layout`.

#### Hyperlinki
**ReportLab (pdf_compiler.py:1887-1898):**
```python
hyperlink_url = self._resolve_hyperlink_url(run_style.get("hyperlink"), text)
if hyperlink_url and effective_width > 0.0:
    link_rect = (
        item_x,
        run_baseline - inline.descent,
        item_x + effective_width,
        run_baseline + inline.ascent,
    )
    try:
        c.linkURL(hyperlink_url, link_rect, relative=0)
    except Exception:
        logger.debug(f"Nie udało się zarejestrować linkURL: {hyperlink_url}")
```

**Rust:** ❌ Brak implementacji. `pdf-writer` wymaga użycia `Annotation::link()`.

#### Footnote/Endnote References
**ReportLab (pdf_compiler.py:1920-1987):**
```python
footnote_refs = data.get("footnote_refs") or run_style.get("footnote_refs", [])
endnote_refs = data.get("endnote_refs") or run_style.get("endnote_refs", [])

if footnote_refs or endnote_refs:
    # Renderuj numery jako superscript
    ref_font_size = font_size * 0.58
    superscript_baseline_shift = font_size * 0.33
    # ... renderowanie numerów ...
```

**Rust:** ❌ Brak implementacji. Powinno renderować numery jako superscript po tekście.

## 2. Shadow/Background/Border

### ✅ Zaimplementowane
- **Shadow** - ✅ `draw_shadow()` w `renderer.rs:2540-2558`
- **Background** - ✅ Obsługiwane w `render_paragraph()` i `render_table()`
- **Border** - ✅ `draw_border()` i `draw_borders()` w `renderer.rs:2560-2647`

### 📝 Szczegóły

Wszystkie te funkcjonalności są zaimplementowane i działają poprawnie.

## 3. Watermarks

### ⚠️ Częściowo zaimplementowane
- **Watermark rendering** - ✅ `render_watermark()` w `renderer.rs:1128-1245`
- **Opacity** - ❌ Jest TODO w `canvas.rs:92-96`, ale **nie zaimplementowane**

### 📝 Szczegóły

#### Opacity
**ReportLab:** Używa `c.setFillAlpha()` i `c.setStrokeAlpha()` dla watermarks.

**Rust (canvas.rs:88-96):**
```rust
/// Set graphics state with opacity (for watermarks, etc.)
/// Note: pdf-writer doesn't directly support opacity, but we can use ExtGState
/// For now, this is a placeholder - full implementation requires ExtGState dictionary
#[allow(dead_code)]
pub fn set_opacity(&mut self, _opacity: f64) {
    // TODO: Implement ExtGState with opacity when pdf-writer API supports it
    // For now, we'll use a workaround by adjusting color alpha
    // This is a limitation - we can't set global opacity easily
}
```

**Status:** Wymaga implementacji ExtGState dictionary w PDF.

## 4. Inline Elements

### ✅ Zaimplementowane
- **Inline text** - ✅ Renderowane w `render_paragraph_from_layout`
- **Inline images** - ✅ Renderowane w `render_paragraph_from_layout:2306-2376`

### ❌ Brakuje
- **Inline textboxes** - ❌ Jest TODO w `renderer.rs:2379-2380`

### 📝 Szczegóły

#### Inline Textboxes
**ReportLab:** Renderuje inline textboxes jako osobne bloki z własnym układem.

**Rust (renderer.rs:2378-2381):**
```rust
"inline_textbox" => {
    // TODO: Implement inline textboxes
    // For now, skip
},
```

## 5. Advanced Text Features

### ⚠️ Częściowo zaimplementowane
- **Line breaking** - ✅ Podstawowe word-based w `text_layout.rs:LineBreaker`
- **Justification** - ✅ `Justifier` w `text_layout.rs`
- **Kerning** - ❌ Jest TODO w `text_layout.rs:270-287`, ale **nie zaimplementowane**

### 📝 Szczegóły

#### Kerning
**ReportLab:** Używa `KerningEngine` do obliczania kerningu między znakami.

**Rust (text_layout.rs:270-287):**
```rust
// TODO: Implement full kerning table parsing

// TODO: Implement actual kerning lookup
// This would require:
// 1. Convert chars to glyph IDs
// 2. Look up (left_glyph, right_glyph) in kern_pairs
// 3. Scale kern value to font_size
0.0
```

**Status:** Struktura `Kerning` istnieje, ale `get_kern()` zawsze zwraca `0.0`.

#### Line Breaking
**ReportLab:** Używa zaawansowanego line breakingu z uwzględnieniem Unicode.

**Rust (text_layout.rs:53):**
```rust
// TODO: Implement UAX-14 Unicode line breaking

let words: Vec<&str> = text.split_whitespace().collect();
```

**Status:** Podstawowe word-based line breaking działa, ale brakuje UAX-14 Unicode line breaking.

## 6. Table Features

### ✅ Zaimplementowane
- **Cell borders** - ✅ Obsługiwane
- **Cell backgrounds** - ✅ Obsługiwane
- **Cell content** - ✅ Paragrafy i obrazy w komórkach

### 📝 Szczegóły

Tabele są w pełni zaimplementowane i działają poprawnie.

## 7. Image Features

### ✅ Zaimplementowane
- **Raster images** - ✅ PNG, JPEG, etc.
- **WMF/EMF conversion** - ✅ Konwersja do SVG, potem do PNG
- **Image positioning** - ✅ Inline i block images
- **Image dimensions** - ✅ Używa wymiarów z DOCX dla SVG conversion

### 📝 Szczegóły

Obrazy są w pełni zaimplementowane, w tym konwersja WMF/EMF do SVG.

## 8. Header/Footer Features

### ✅ Zaimplementowane
- **Header rendering** - ✅ `render_header()` w `renderer.rs:1247-1468`
- **Footer rendering** - ✅ `render_footer()` w `renderer.rs:1469-1484`
- **Images in headers/footers** - ✅ Obsługiwane
- **Overlays in headers/footers** - ✅ Obsługiwane

### 📝 Szczegóły

Header/footer są w pełni zaimplementowane.

## 9. Footnotes/Endnotes

### ✅ Zaimplementowane
- **Footnotes rendering** - ✅ `render_footnotes()` w `renderer.rs:1485-1597`
- **Endnotes rendering** - ✅ `render_endnotes()` w `renderer.rs:1601-1611`

### ❌ Brakuje
- **Footnote/Endnote references in text** - ❌ Brak implementacji (patrz sekcja 1)

### 📝 Szczegóły

Renderowanie footnotes/endnotes działa, ale brakuje renderowania referencji w tekście (numery jako superscript).

## 10. Field Codes

### ✅ Zaimplementowane
- **PAGE** - ✅ `resolve_field_text()` w `field.rs`
- **NUMPAGES** - ✅ `resolve_field_text()` w `field.rs`
- **DATE** - ✅ `resolve_field_text()` w `field.rs` (podstawowa implementacja)
- **TIME** - ✅ `resolve_field_text()` w `field.rs` (podstawowa implementacja)

### 📝 Szczegóły

Field codes są zaimplementowane, ale DATE/TIME używają prostego formatowania (można ulepszyć używając `chrono`).

## 11. List Markers / Paragraph Numbering

### ✅ Zaimplementowane
- **List markers** - ✅ `render_marker()` w `markers.rs`
- **Paragraph numbering** - ✅ Obsługiwane przez `render_marker()`
- **Marker override text** - ✅ Obsługiwane (`marker_override_text`)

### 📝 Szczegóły

Markery są w pełni zaimplementowane i działają poprawnie.

## Podsumowanie

### Priorytet Wysoki (Krytyczne)
1. **Underline** - TODO w kodzie, struktura istnieje, ale nie używana
2. **Strikethrough** - Struktura istnieje, ale nie używana w renderowaniu
3. **Highlight** - Struktura istnieje, ale nie używana w renderowaniu
4. **Hyperlinki** - Brak implementacji, wymaga `pdf-writer::Annotation::link()`
5. **Footnote/Endnote references** - Brak implementacji, ważne dla dokumentów akademickich

### Priorytet Średni
6. **Opacity dla watermarks** - Wymaga ExtGState dictionary
7. **Inline textboxes** - TODO w kodzie
8. **Kerning** - Struktura istnieje, ale nie zaimplementowana

### Priorytet Niski
9. **Double strikethrough** - Rzadko używane
10. **Overline** - Rzadko używane
11. **UAX-14 Unicode line breaking** - Ulepszenie, ale podstawowe line breaking działa

## Rekomendacje

1. **Integracja `text_formatting.rs`** - Struktury już istnieją, ale nie są używane w `render_paragraph_from_layout`. Należy zintegrować `TextFormatting` z renderowaniem tekstu.

2. **Implementacja hyperlinków** - Wymaga użycia `pdf-writer::Annotation::link()` do tworzenia linków w PDF.

3. **Implementacja footnote/endnote references** - Renderować numery jako superscript po tekście, podobnie jak w ReportLab.

4. **Implementacja opacity** - Wymaga utworzenia ExtGState dictionary w PDF dla watermarks.

5. **Implementacja kerningu** - Parsowanie tabeli kerningu z TTF i zastosowanie podczas renderowania.

