# Analiza Funkcjonalności Engine vs Rust Renderer

## 📋 Typy Bloków Obsługiwane przez Engine

### 1. **Paragraph** (Paragraf)
Engine generuje następujące funkcjonalności dla paragrafów:

#### ✅ Funkcjonalności generowane przez Engine:
- **Tekst podstawowy** - tekst z paragrafu
- **Runs** (`runs_payload`) - lista runów z indywidualnym formatowaniem:
  - `text` - tekst runu
  - `style` - style runu (bold, italic, underline, font_name, font_size, color, highlight)
  - `has_break`, `has_tab`, `has_drawing` - flagi specjalne
  - `footnote_refs` / `endnote_refs` - referencje do przypisów
  - `fields` - pola (PAGE, NUMPAGES, DATE, TIME, REF, TOC)
- **ParagraphLayout** (`layout_payload` / `_layout_payload`) - zaawansowany layout:
  - `lines` - lista linii z `baseline_y`, `height`, `offset_x`, `available_width`
  - `items` (w każdej linii) - lista `InlineBox` z:
    - `kind`: "text_run", "field", "inline_image", "inline_textbox"
    - `x`, `width`, `ascent`, `descent` - pozycja i wymiary
    - `data` - dane inline elementu (tekst, obraz, textbox, field)
  - `overlays` - lista `OverlayBox` (obrazy, textboxy pozycjonowane absolutnie)
  - `style` - `BoxStyle` (background, borders, padding)
  - `metadata` - metadane paragrafu
- **Numbering** (`numbering`, `marker`) - numeracja list:
  - `marker` - marker listy z `text`, `counter`, pozycjami (`number_position`, `text_position`)
  - `indent` - wcięcia (`left_pt`, `right_pt`, `first_line_pt`, `hanging_pt`, `text_position_pt`, `number_position_pt`)
- **Images** (`images`) - obrazy w paragrafie
- **Textboxes** (`textboxes`) - textboxy w paragrafie
- **VML Shapes** (`vml_shapes`) - watermarks
- **Fields** (`fields`) - pola na poziomie paragrafu
- **Spacing** (`spacing`, `spacing_metrics`) - spacing przed/po paragrafie, line spacing
- **Indent** (`indent`, `inline_indent`) - wcięcia paragrafu
- **Style** (`style`) - style paragrafu:
  - `background_color`, `background`, `shading`
  - `borders`, `border`
  - `shadow` (color, offset_x, offset_y)
  - `alignment` (left, center, right, justify)
  - `font_name`, `font_size`
  - `line_spacing`, `line_spacing_rule`
  - `keep_with_next`, `keep_together`
  - `page_break_before`, `page_break_after`

#### ✅ Zaimplementowane w Rust Rendererze:
- ✅ Podstawowy tekst (`text`)
- ✅ ParagraphLayout (`layout_payload`) - renderowanie z linii i inline items
- ✅ Multi-line text z wrapping
- ✅ Font loading (TTF/OTF) - częściowo (fallback do built-in)
- ✅ Background color
- ✅ Borders (solid, dashed, dotted, double)
- ✅ Shadow rendering
- ✅ Rounded rectangles (radius)
- ✅ Text alignment (left, center, right, justify)
- ✅ Line spacing
- ✅ Indent (podstawowy)

#### ❌ Brakujące w Rust Rendererze:
- ❌ **Runs** (`runs_payload`) - indywidualne formatowanie runów (bold, italic, underline, color per run)
- ❌ **Fields** - pola (PAGE, NUMPAGES, DATE, TIME, REF, TOC)
- ❌ **Footnotes/Endnotes** - referencje i renderowanie przypisów
- ❌ **Numbering markers** - markery list (numery, bullet points)
- ❌ **Inline images** - obrazy w linii tekstu (w `InlineBox` z `kind="inline_image"`)
- ❌ **Inline textboxes** - textboxy w linii tekstu (w `InlineBox` z `kind="inline_textbox"`)
- ❌ **Overlays** - overlay boxes (obrazy/textboxy pozycjonowane absolutnie)
- ❌ **VML Shapes** - watermarks
- ❌ **Highlight** - podświetlanie tekstu
- ❌ **Strikethrough** - przekreślenie tekstu
- ❌ **Superscript/Subscript** - indeksy górne/dolne
- ❌ **Tab stops** - tabulatory
- ❌ **Keep with next/together** - kontrola paginacji
- ❌ **Page breaks** - wymuszone łamanie stron

---

### 2. **Table** (Tabela)
Engine generuje następujące funkcjonalności dla tabel:

#### ✅ Funkcjonalności generowane przez Engine:
- **Rows** (`rows`) - wiersze tabeli
- **Grid** (`grid`) - szerokości kolumn
- **Cells** - komórki z:
  - `blocks` - lista bloków w komórce (paragrafy, tabele zagnieżdżone, obrazy)
  - `style` - style komórki (background, borders, padding, vertical_alignment)
  - `frame` - pozycja i wymiary komórki
- **Cell spanning**:
  - `grid_span` (colspan) - łączenie kolumn
  - `vertical_merge_type` (rowspan) - łączenie wierszy
- **Table style** (`style`):
  - `background_color`, `background`
  - `borders` - ramki tabeli
  - `cell_spacing` - odstępy między komórkami
  - `alignment` (left, center, right)
  - `width` - szerokość tabeli
- **TableLayout** - zaawansowany layout:
  - `frame` - pozycja i wymiary tabeli
  - `rows` - lista wierszy z `TableCellLayout`
  - `grid_lines` - linie siatki (`BorderSpec`)
  - `style` - `BoxStyle`
  - `metadata` - metadane tabeli

#### ✅ Zaimplementowane w Rust Rendererze:
- ✅ Podstawowe renderowanie tabeli
- ✅ Cell content rendering - paragrafy w komórkach
- ✅ Colspan (`grid_span`)
- ✅ Rowspan (`vertical_merge_type`)
- ✅ Cell margins
- ✅ Background color komórek
- ✅ Borders komórek (solid, dashed, dotted, double)
- ✅ Rounded rectangles dla komórek

#### ❌ Brakujące w Rust Rendererze:
- ❌ **Nested tables** - tabele zagnieżdżone w komórkach
- ❌ **Images in cells** - obrazy w komórkach
- ❌ **Textboxes in cells** - textboxy w komórkach
- ❌ **Vertical alignment** - wyrównanie pionowe w komórkach (top, center, bottom)
- ❌ **Cell spacing** - odstępy między komórkami
- ❌ **Table width/alignment** - szerokość i wyrównanie całej tabeli
- ❌ **Grid lines** - linie siatki z `TableLayout`
- ❌ **TableLayout** - zaawansowany layout z pre-calculated wymiarami

---

### 3. **Image** (Obraz)
Engine generuje następujące funkcjonalności dla obrazów:

#### ✅ Funkcjonalności generowane przez Engine:
- **Path** (`path`, `image_path`) - ścieżka do pliku obrazu
- **Relationship ID** (`relationship_id`) - ID relacji w DOCX
- **Dimensions** (`width`, `height`) - wymiary obrazu
- **Style** (`style`):
  - `alignment` (left, center, right, inline)
  - `wrap` - zawijanie tekstu wokół obrazu
  - `anchor_type` - typ kotwicy (inline, anchor)
- **ImageLayout** - zaawansowany layout:
  - `frame` - pozycja i wymiary
  - `path` - ścieżka do obrazu
  - `preserve_aspect` - zachowanie proporcji
  - `metadata` - metadane obrazu
- **Inline images** - obrazy w linii tekstu (w `InlineBox`)

#### ✅ Zaimplementowane w Rust Rendererze:
- ✅ Image loading (PNG, JPEG)
- ✅ Image embedding w PDF
- ✅ Image positioning i sizing
- ✅ Placeholder dla brakujących obrazów

#### ❌ Brakujące w Rust Rendererze:
- ❌ **Image alignment** - wyrównanie obrazu (left, center, right)
- ❌ **Text wrapping** - zawijanie tekstu wokół obrazu
- ❌ **Anchor positioning** - pozycjonowanie absolutne (anchor mode)
- ❌ **Preserve aspect ratio** - zachowanie proporcji
- ❌ **Inline images** - obrazy w linii tekstu
- ❌ **EMF/WMF conversion** - konwersja formatów Windows
- ❌ **Image cropping** - przycinanie obrazów

---

### 4. **Textbox** (Pole tekstowe)
Engine generuje następujące funkcjonalności dla textboxów:

#### ✅ Funkcjonalności generowane przez Engine:
- **Content** (`content`) - zawartość textboxa (paragrafy, tekst)
- **Text** (`text`) - tekst textboxa
- **Anchor info** (`anchor_info`, `anchor_type`):
  - `anchor_type` - "inline" lub "anchor"
  - `position` - pozycja absolutna
  - `width`, `height` - wymiary textboxa
- **Style** (`style`) - style textboxa (background, borders, padding)
- **TextboxLayout** - zaawansowany layout:
  - `rect` - pozycja i wymiary
  - `content` - `ParagraphLayout` z zawartością
  - `style` - `BoxStyle`
  - `anchor_mode` - "inline" lub "anchor"
  - `metadata` - metadane textboxa
- **Inline textboxes** - textboxy w linii tekstu (w `InlineBox`)

#### ✅ Zaimplementowane w Rust Rendererze:
- ✅ Podstawowe renderowanie textboxa
- ✅ Content rendering (paragrafy w textboxie)

#### ❌ Brakujące w Rust Rendererze:
- ❌ **Anchor positioning** - pozycjonowanie absolutne (anchor mode)
- ❌ **Inline textboxes** - textboxy w linii tekstu
- ❌ **TextboxLayout** - zaawansowany layout
- ❌ **Background/borders** - tło i ramki textboxa
- ❌ **Padding** - padding textboxa

---

### 5. **Decorator** (Dekorator)
Engine generuje następujące funkcjonalności dla dekoratorów:

#### ✅ Funkcjonalności generowane przez Engine:
- **Type** (`type`) - typ dekoratora
- **Style** (`style`) - style dekoratora (background, borders, shadow)
- **Content** - zawartość dekoratora

#### ✅ Zaimplementowane w Rust Rendererze:
- ✅ Podstawowe renderowanie dekoratora (background, borders)

#### ❌ Brakujące w Rust Rendererze:
- ❌ **Shadow** - cienie dla dekoratorów
- ❌ **Advanced borders** - zaawansowane ramki

---

### 6. **Header/Footer** (Nagłówek/Stopka)
Engine generuje następujące funkcjonalności dla headerów/footerów:

#### ✅ Funkcjonalności generowane przez Engine:
- **Header/Footer types** - "default", "first", "even"
- **Content** - paragrafy, tabele, obrazy, textboxy w headerze/footerze
- **Fields** - pola (PAGE, NUMPAGES, DATE, TIME)
- **Images** - obrazy w headerze/footerze
- **Textboxes** - textboxy w headerze/footerze
- **Context** (`header_footer_context`) - kontekst (header/footer)

#### ✅ Zaimplementowane w Rust Rendererze:
- ✅ Rozpoznawanie headerów/footerów
- ✅ Renderowanie zawartości (paragrafy, tabele, obrazy)

#### ❌ Brakujące w Rust Rendererze:
- ❌ **Header/Footer types** - różne headery/footery dla first/even pages
- ❌ **Fields** - pola (PAGE, NUMPAGES, DATE, TIME) w headerach/footerach
- ❌ **Watermarks** - znaki wodne

---

### 7. **Footnotes/Endnotes** (Przypisy)
Engine generuje następujące funkcjonalności dla przypisów:

#### ✅ Funkcjonalności generowane przez Engine:
- **Footnote references** (`footnote_refs`) - referencje w runach
- **Endnote references** (`endnote_refs`) - referencje w runach
- **Footnote blocks** (`block_type="footnotes"`) - bloki przypisów
- **Endnote blocks** (`block_type="endnotes"`) - bloki przypisów końcowych

#### ❌ Brakujące w Rust Rendererze:
- ❌ **Footnotes** - renderowanie przypisów
- ❌ **Endnotes** - renderowanie przypisów końcowych
- ❌ **Footnote references** - referencje do przypisów w tekście

---

## 📊 Podsumowanie

### Typy Bloków:
| Typ | Engine | Rust Renderer | Status |
|-----|--------|---------------|--------|
| Paragraph | ✅ Pełne wsparcie | ⚠️ Częściowe | 60% |
| Table | ✅ Pełne wsparcie | ⚠️ Częściowe | 70% |
| Image | ✅ Pełne wsparcie | ⚠️ Częściowe | 50% |
| Textbox | ✅ Pełne wsparcie | ⚠️ Częściowe | 40% |
| Decorator | ✅ Pełne wsparcie | ⚠️ Częściowe | 50% |
| Header/Footer | ✅ Pełne wsparcie | ⚠️ Częściowe | 60% |
| Footnotes | ✅ Pełne wsparcie | ❌ Brak | 0% |

### Kluczowe Brakujące Funkcjonalności:

#### Wysoki Priorytet:
1. **Runs formatting** - indywidualne formatowanie runów (bold, italic, underline, color)
2. **Numbering markers** - markery list (numery, bullet points)
3. **Fields** - pola (PAGE, NUMPAGES, DATE, TIME)
4. **Inline images/textboxes** - obrazy/textboxy w linii tekstu
5. **Footnotes/Endnotes** - przypisy

#### Średni Priorytet:
6. **Vertical alignment** - wyrównanie pionowe w komórkach tabeli
7. **Nested tables** - tabele zagnieżdżone
8. **Text wrapping** - zawijanie tekstu wokół obrazów
9. **Anchor positioning** - pozycjonowanie absolutne
10. **Tab stops** - tabulatory

#### Niski Priorytet:
11. **Strikethrough/Superscript/Subscript** - zaawansowane formatowanie tekstu
12. **Highlight** - podświetlanie
13. **VML Shapes** - watermarks
14. **EMF/WMF conversion** - konwersja formatów
15. **Keep with next/together** - kontrola paginacji

---

## 🔍 Szczegółowa Analiza ParagraphLayout

Engine generuje `ParagraphLayout` z następującą strukturą:

```python
ParagraphLayout:
  lines: List[ParagraphLine]
    - baseline_y: float
    - height: float
    - offset_x: float
    - available_width: float
    - items: List[InlineBox]
      - kind: "text_run" | "field" | "inline_image" | "inline_textbox"
      - x: float
      - width: float
      - ascent: float
      - descent: float
      - data: Dict[str, Any]
        - text: str (dla text_run)
        - field: Dict (dla field)
        - image: Dict (dla inline_image)
        - textbox: Dict (dla inline_textbox)
  overlays: List[OverlayBox]
    - kind: "image" | "textbox" | "shape"
    - frame: Rect
    - payload: Dict[str, Any]
  style: BoxStyle
    - background: ColorSpec
    - borders: List[BorderSpec]
    - padding: Tuple[float, float, float, float]
  metadata: Dict[str, Any]
```

### ✅ Zaimplementowane w Rust Rendererze:
- ✅ Renderowanie linii z `baseline_y`, `offset_x`, `available_width`
- ✅ Renderowanie `InlineBox` z `kind="text_run"` (podstawowy tekst)
- ✅ Style per inline item (font, size, color)

### ❌ Brakujące w Rust Rendererze:
- ❌ `kind="field"` - pola w inline items
- ❌ `kind="inline_image"` - obrazy w linii tekstu
- ❌ `kind="inline_textbox"` - textboxy w linii tekstu
- ❌ `overlays` - overlay boxes
- ❌ `style.padding` - padding paragrafu
- ❌ Zaawansowane `data` w inline items (formatowanie runów)

---

## 📝 Rekomendacje

1. **Priorytet 1**: Implementacja runs formatting (bold, italic, underline, color per run)
2. **Priorytet 2**: Implementacja numbering markers (list markers)
3. **Priorytet 3**: Implementacja fields (PAGE, NUMPAGES, DATE, TIME)
4. **Priorytet 4**: Implementacja inline images/textboxes
5. **Priorytet 5**: Implementacja footnotes/endnotes

