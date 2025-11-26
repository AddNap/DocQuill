# Architektura Rust PDF Renderera

## 🎯 Założenia Architektury

Rust PDF renderer jest **rendererem "głupim"** (dumb renderer) - nie wykonuje żadnych obliczeń layoutu. Wszystkie obliczenia i układanie dokumentu są wykonywane przez:

1. **LayoutEngine** - konwertuje model dokumentu na strukturę logiczną layoutu
2. **LayoutAssembler** - przelicza wymiary, spacing, pozycje elementów i przygotowuje gotowe bloki

Rust renderer **tylko renderuje** gotowe bloki, które otrzymuje z assemblera.

## 📊 Przepływ Danych

```
DOCX → Parser → LayoutEngine → LayoutAssembler → PDFCompilerRust → Rust Renderer → PDF
                                    ↓
                            Wszystkie obliczenia:
                            - Pozycje (x, y)
                            - Wymiary (width, height)
                            - Zawijanie tekstu (line breaking)
                            - Layout paragrafów (ParagraphLayout)
                            - Layout tabel (TableLayout)
                            - Pozycjonowanie obrazów
```

## ✅ Co Rust Renderer Otrzymuje

### 1. UnifiedLayout
- `pages: List[LayoutPage]` - lista stron
- Każda strona ma `blocks: List[LayoutBlock]`

### 2. LayoutBlock
- `frame: Rect` - **już obliczona** pozycja i wymiary (x, y, width, height)
- `block_type: str` - typ bloku ("paragraph", "table", "image", "textbox", "decorator")
- `content: BlockContent` - zawartość bloku z gotowym payloadem
- `style: Dict` - style bloku

### 3. BlockContent dla Paragraph
- `payload: ParagraphLayout` - **już obliczony** layout paragrafu:
  - `lines: List[ParagraphLine]` - linie z już obliczonymi pozycjami:
    - `baseline_y: float` - pozycja Y linii bazowej
    - `height: float` - wysokość linii
    - `offset_x: float` - offset X linii
    - `available_width: float` - dostępna szerokość
    - `items: List[InlineBox]` - elementy inline z już obliczonymi pozycjami:
      - `x: float` - pozycja X względem początku linii
      - `width: float` - szerokość elementu
      - `ascent: float`, `descent: float` - metryki czcionki
      - `kind: str` - typ ("text_run", "field", "inline_image", "inline_textbox")
      - `data: Dict` - dane elementu (tekst, style, etc.)
  - `overlays: List[OverlayBox]` - overlay boxes z już obliczonymi pozycjami
  - `style: BoxStyle` - style paragrafu (background, borders, padding)
  - `metadata: Dict` - metadane

### 4. BlockContent dla Table
- `payload: TableLayout` - **już obliczony** layout tabeli:
  - `frame: Rect` - pozycja i wymiary tabeli
  - `rows: List[List[TableCellLayout]]` - komórki z już obliczonymi pozycjami
  - `grid_lines: List[BorderSpec]` - linie siatki
  - `style: BoxStyle` - style tabeli

### 5. BlockContent dla Image
- `payload: ImageLayout` - **już obliczony** layout obrazu:
  - `frame: Rect` - pozycja i wymiary obrazu
  - `path: str` - ścieżka do obrazu
  - `preserve_aspect: bool` - zachowanie proporcji

## ❌ Czego Rust Renderer NIE Powinien Robić

Rust renderer **NIE powinien** wykonywać następujących obliczeń:

1. ❌ **Zawijanie tekstu** (`wrap_text_simple`) - tekst jest już podzielony na linie w `ParagraphLayout.lines`
2. ❌ **Obliczanie pozycji X** (`calculate_text_x_position`) - pozycje są już obliczone w `ParagraphLine.offset_x` i `InlineBox.x`
3. ❌ **Obliczanie pozycji Y** - pozycje są już obliczone w `ParagraphLine.baseline_y`
4. ❌ **Obliczanie wymiarów** - wymiary są już obliczone w `frame` (Rect)
5. ❌ **Layout tabeli** - layout jest już obliczony w `TableLayout`
6. ❌ **Pozycjonowanie obrazów** - pozycje są już obliczone w `ImageLayout.frame`

## ✅ Co Rust Renderer Powinien Robić

Rust renderer **tylko renderuje**:

1. ✅ **Renderowanie linii** - rysuje linie z `ParagraphLayout.lines` używając już obliczonych pozycji
2. ✅ **Renderowanie inline items** - rysuje elementy inline z `InlineBox` używając już obliczonych pozycji
3. ✅ **Renderowanie tła** - rysuje tło z `BoxStyle.background`
4. ✅ **Renderowanie ramek** - rysuje ramki z `BoxStyle.borders`
5. ✅ **Renderowanie cieni** - rysuje cienie z `style.shadow`
6. ✅ **Renderowanie obrazów** - rysuje obrazy w obliczonych pozycjach
7. ✅ **Renderowanie tabel** - rysuje tabele z obliczonymi pozycjami komórek

## 🔧 Aktualna Implementacja

### Problem: Fallback z Obliczeniami

Obecna implementacja ma funkcję `draw_text`, która wykonuje obliczenia layoutu jako fallback, gdy nie ma `ParagraphLayout`:

```rust
// ❌ TO NIE POWINNO ISTNIEĆ - obliczenia powinny być w assemblerze
fn draw_text(...) {
    let layout = wrap_text_simple(text, rect.width, font_size, line_spacing_factor); // ❌
    let x = calculate_text_x_position(rect.x, rect.width, text_width, alignment); // ❌
    // ...
}
```

### Rozwiązanie

1. **Usunąć lub oznaczyć jako deprecated** funkcje obliczeniowe:
   - `wrap_text_simple` - powinno być tylko w assemblerze
   - `calculate_text_x_position` - powinno być tylko w assemblerze
   - `draw_text` - fallback, który wykonuje obliczenia

2. **Upewnić się, że zawsze używamy ParagraphLayout**:
   - Jeśli `ParagraphLayout` nie istnieje, to znaczy, że assembler nie działa poprawnie
   - Zamiast fallback, powinien być błąd lub warning

3. **Dodać walidację**:
   - Sprawdzać, czy bloki mają gotowe payloady przed renderowaniem
   - Logować warningi, gdy brakuje gotowych payloadów

## 📝 Przykład Poprawnego Renderowania

### Paragraph z ParagraphLayout

```rust
fn render_paragraph_from_layout(...) {
    // ParagraphLayout jest już gotowy z obliczonymi liniami
    let lines = layout_payload.get("lines").unwrap();
    
    for line in lines {
        let baseline_y = line.get("baseline_y").unwrap(); // ✅ Już obliczone
        let offset_x = line.get("offset_x").unwrap(); // ✅ Już obliczone
        let items = line.get("items").unwrap();
        
        for item in items {
            let x = item.get("x").unwrap(); // ✅ Już obliczone
            let text = item.get("data").unwrap().get("text").unwrap();
            
            // Tylko renderujemy - nie obliczamy!
            canvas.draw_string(
                rect.x + offset_x + x, // ✅ Używamy obliczonych pozycji
                rect.y + baseline_y,   // ✅ Używamy obliczonych pozycji
                text
            );
        }
    }
}
```

## 🎯 Podsumowanie

- **Engine/Assembler**: Wykonują wszystkie obliczenia i przygotowują gotowe bloki
- **Rust Renderer**: Tylko renderuje gotowe bloki bez wykonywania obliczeń

To zapewnia:
- ✅ Separację odpowiedzialności
- ✅ Łatwiejsze testowanie
- ✅ Możliwość użycia tego samego layoutu dla różnych rendererów (PDF, HTML, etc.)
- ✅ Lepsze performance (obliczenia raz, renderowanie wiele razy)

