# Analiza DirectPDFRenderer

## Przegląd Ogólny

`DirectPDFRenderer` to zaawansowany renderer konwertujący dokumenty DOCX bezpośrednio do PDF, bez pośrednictwa HTML. Używa biblioteki ReportLab do generowania PDF. Renderer ma ~5600 linii kodu i implementuje kompleksową obsługę formatowania Word.

**Architektura:**
```
DOCX → DocQuill Parser → Direct PDF Interpreter → PDF Binary
```

## Struktura Klas

### TextLine
```python
class TextLine:
    runs: List[Tuple[run, text, font_info]]  # Runy tekstu w linii
    width: float                              # Szerokość linii
    height: float                             # Wysokość linii
    words: List[str]                          # Lista słów (dla justification)
```

### DirectPDFRenderer

Główna klasa renderera z 50+ metodami.

## Architektura Renderowania

### Dwupassowe Renderowanie

Renderer używa **dwupassowego** podejścia:

1. **Pass 1 (Dry Run)**: Liczy faktyczną liczbę stron bez renderowania
   - Metoda: `_dry_run_render()`
   - Symuluje renderowanie i liczy strony
   - Używane do numeracji stron w header/footer

2. **Pass 2 (Rzeczywiste renderowanie)**: Generuje PDF z prawidłową numeracją
   - Główna metoda: `render()`
   - Renderuje header, body, footer

### Główny Przepływ Renderowania

```python
render(document, output_path)
  ├─ _analyze_style_alignments()     # Analiza alignments w stylach
  ├─ Ładowanie właściwości strony z DOCX (marginesy, rozmiar)
  ├─ _calculate_document_spacing()    # Dynamiczne spacing
  ├─ _calculate_footer_height_dynamic() # Wysokość stopki
  ├─ _register_fonts()                 # Rejestracja fontów
  ├─ _dry_run_render()                 # Pass 1: Liczenie stron
  ├─ _render_header()                  # Renderowanie nagłówka
  ├─ Renderowanie zawartości body:
  │   ├─ _render_table_universal()     # Tabele
  │   ├─ _render_paragraph()           # Paragrafy
  │   └─ _render_image_anchored()      # Obrazy zakotwiczone
  └─ _render_footer()                  # Renderowanie stopki
```

## Kluczowe Komponenty

### 1. Renderowanie Paragrafów (`_render_paragraph`)

**Funkcjonalność:**
- Text wrapping z proper word breaking
- Justification (wyjustowanie tekstu)
- Obsługa list (numerycznych i punktowanych)
- Widows/orphans control (kontrola wiszących linii)
- Page breaks
- Multi-page paragraph handling

**Proces:**

```python
_render_paragraph(paragraph, next_paragraph)
  ├─ Analiza alignment (direct → style → default)
  ├─ Sprawdzenie page breaks i keep_together
  ├─ Widows/orphans control dla numbered paragraphs
  ├─ Obliczenie indentacji (left, right, first_line, hanging)
  ├─ _break_paragraph_into_lines()    # Łamanie na linie
  ├─ Renderowanie per-page blocks:
  │   ├─ _render_paragraph_block_decorations()  # Ramki, tła
  │   └─ _render_text_line()                   # Rzeczywisty tekst
  └─ Aktualizacja pozycji Y
```

**Łamanie Paragrafu na Linie:**

Metoda `_break_paragraph_into_lines()` używa **hybrid approach**:

1. **Dla justify/both**: Używa ReportLab Paragraph do obliczenia łamania
   - Zachowuje formatowanie per-run poprzez `char_to_run_map`
   - Mapuje słowa z powrotem do runów

2. **Dla innych alignments**: Standardowe łamanie słów
   - Buduje `char_to_run_map` (pozycja → run)
   - Dzieli tekst na słowa z zachowaniem formatowania

### 2. Renderowanie Linii Tekstu (`_render_text_line`)

**Wyrównanie:**
- `left`: Standardowe (x = margin_left + left_indent)
- `center`: `x += (available_width - line.width) / 2`
- `right`: `x += (available_width - line.width)`
- `justify/both`: Zaawansowana justyfikacja

**Justyfikacja (Wyjustowanie):**

Zaawansowany algorytm z:
- Tokenizacją ponad runami (słowa/spacje)
- Rozkładem wagowym extra_space
- Pomijaniem leading/trailing spaces
- Domknięciem prawego brzegu

```python
if needs_justify and word_spacing > 0:
    # 1. Tokenizacja (word/space z font_info)
    tokens = [...]
    
    # 2. Identyfikacja rozszerzalnych przerw
    gap_indices = [...]  # Pomija leading/trailing/NBSP
    
    # 3. Proporcjonalny rozkład extra_space
    # + reszta do ostatniej luki dla domknięcia brzegu
```

### 3. Renderowanie Tabel (`_render_table_universal`)

**Uniwersalna metoda** dla body, header i footer.

**Proces:**

```python
_render_table_universal(table, x, y, direction)
  ├─ Obliczenie szerokości kolumn (_calculate_table_column_widths)
  │   ├─ Auto-fit do dostępnej szerokości
  │   ├─ Uwzględnienie width z DOCX (pct/dxa/auto)
  │   └─ Rozkład proporcjonalny
  ├─ Obliczenie wysokości wierszy (_calculate_table_row_heights)
  │   ├─ Cache'owanie wysokości (dla footer/header)
  │   ├─ Uwzględnienie height z DOCX (exact/atLeast)
  │   └─ Dynamiczne obliczanie na podstawie contentu
  ├─ Renderowanie komórek:
  │   ├─ Obsługa colspan i rowspan
  │   ├─ Vertical merge (restart/continue)
  │   ├─ Background (shading)
  │   ├─ Borders (_draw_cell_borders)
  │   └─ Content (_render_cell_content)
  └─ Zwrócenie nowej pozycji Y
```

**Cache wysokości wierszy:**
- `_table_row_heights_cache` dla wielokrotnego użycia (np. footer na każdej stronie)
- Klucz: `table_id` (unikalny ID tabeli)

### 4. Renderowanie Obrazów

**Trzy typy obrazów:**

1. **Inline** (`_render_image_inline`):
   - W tekście paragrafu
   - Pozycjonowanie względem tekstu
   - Sprawdzanie czy mieści się na stronie

2. **Anchored** (`_render_image_anchored`):
   - Absolutne pozycjonowanie na stronie
   - Wsparcie dla z-ordering (behind_doc)
   - Pozycjonowanie względem page/margin

3. **Footer** (`_render_image_inline_footer`):
   - Specjalna wersja dla stopek
   - Renderowanie bottom-to-top

**Cache obrazów:**
- `_image_cache`: {hash → PIL Image}
- `_image_conversion_cache`: {hash → converted_bytes}
- `_xobject_cache`: {hash → xobject_name} (ReportLab XObjects)

### 5. Headers i Footers

**Header (`_render_header`):**
- Obsługa różnego headeru dla pierwszej strony
- Placeholders: {PAGE}, {NUMPAGES}, {DATE}, {TIME}, etc.
- Renderowanie tabel, obrazów, textboxów
- Obsługa "behind document" images

**Footer (`_render_footer`):**
- Dynamiczne obliczanie wysokości (`_calculate_footer_height_dynamic`)
- Renderowanie bottom-to-top
- Tabele w stopce (`_render_table_universal` z direction='bottom_to_top')
- Textboxy w stopce

### 6. Dekoracje Paragrafów (`_render_paragraph_block_decorations`)

**Architektura per-page block:**

Paragraf dzielony na bloki per-page (nie cały paragraf naraz):
- Każdy blok ma własne dekoracje
- Umożliwia precyzyjne pozycjonowanie ramek na stronie

**Warstwy dekoracji:**

1. **Shadow** (warstwa 1 - pod wszystkim)
2. **Background** (warstwa 2 - shading/highlight)
3. **Borders** (warstwa 3 - ramki)

**Inteligentne łączenie ramek:**

- Sprawdza czy następny paragraf ma identyczne formatowanie
- Jeśli tak → łączy ramki (usuwa dolną linię)
- Jeśli nie → kończy ramkę na tekście

```python
if _borders_are_identical(current, next):
    should_connect_bottom = True  # Nie rysuj dolnej linii
```

## Zaawansowane Funkcje

### 1. Style Alignment Overrides

Analiza dokumentu (`_analyze_style_alignments`):
- Liczy alignment dla każdego stylu
- Jeśli >50% paragrafów ma inny alignment niż styl → override
- Umożliwia poprawne renderowanie gdy style są błędnie zdefiniowane

### 2. Widows/Orphans Control

Dla numbered paragraphs:
- Wymaga minimum 2 linii na każdej stronie
- Zapobiega wiszącym linii (1 linia na końcu/początku strony)
- Przenosi paragraf na następną stronę jeśli potrzeba

### 3. Keep Together / Keep With Next

- `keep_together`: Nie dzieli paragrafu między stronami
- `keep_with_next`: Trzyma paragraf z następnym razem

### 4. List Numbering

- Obsługa multi-level lists
- Różne formaty: decimal, bullet, roman, etc.
- Cache kontra per numbering ID i level
- `_get_list_marker()`: Generuje marker dla listy

### 5. Font Management

- Rejestracja fontów z polskimi znakami (DejaVu)
- Cache fontów (`font_cache`, `_font_cache`)
- Pobieranie font_info z run properties lub style

## Optymalizacje

### 1. Cache'owanie

- **Table row heights**: `_table_row_heights_cache`
- **Images**: `_image_cache`, `_image_conversion_cache`, `_xobject_cache`
- **Fonts**: `font_cache`, `_font_cache`

### 2. XObjects dla Duplikatów Obrazów

- Używa ReportLab XObjects dla powtarzających się obrazów
- Zmniejsza rozmiar PDF

### 3. Dry Run Renderowania

- Tylko pierwszy pass renderuje rzeczywisty PDF
- Drugi pass używa wyników pierwszego

## Konwersje Jednostek

- **Twips → Points**: `twips / 20.0` (1 point = 20 twips)
- **Twips → Inches**: `twips / 1440.0` (1 inch = 1440 twips)
- **DOCX width → Points**: `width / 914400.0 * inch` (EMU units)

## Obsługiwane Właściwości DOCX

### Paragraf:
- Alignment (left/center/right/justify)
- Indentation (left, right, first_line, hanging)
- Spacing (before, after, line)
- Borders (top, bottom, left, right)
- Background (shading, highlight)
- Shadow
- Numbering (id, level)
- Page breaks
- Keep together/with next

### Run:
- Font (name, size, bold, italic, underline)
- Color
- Small caps
- Hyperlinks

### Table:
- Column widths (auto, pct, dxa)
- Row heights (exact, atLeast, auto)
- Cell spanning (colspan, rowspan)
- Borders (per cell)
- Shading (background)
- Alignment (left/center/right)

### Image:
- Inline positioning
- Anchored positioning
- Z-ordering (behind document)
- Width/height
- Conversion (EMF→PNG, etc.)

## Debug Features

### Flagi Debugowania:

- `debug_borders`: Rysuje czerwone ramki wokół paragrafów
- `debug_spaces`: Loguje szczegółowe info o spacjach/justyfikacji
- `force_justify`: Wymusza justyfikację nawet dla małych spacing
- `ignore_leading_trailing_spaces`: Ignoruje spacje na początku/końcu w justyfikacji

### Debug Margin Lines:

`_draw_debug_margin_lines()`:
- Rysuje linie marginesów na pierwszej stronie
- Pomaga w debugowaniu layoutu

## Problemy i Ograniczenia

### 1. Ograniczenia:

- **Brak obsługi footnotes/endnotes**: Nie renderowane
- **Ograniczona obsługa complex layouts**: Niektóre zaawansowane layouty mogą nie działać
- **Brak obsługi watermarks**: Nie implementowane
- **Ograniczona obsługa smartart**: Podstawowa

### 2. Znane Problemy:

- Justyfikacja może być niedokładna dla bardzo długich linii
- Cache może powodować problemy przy dynamicznych zmianach
- Vertical merge w tabelach może mieć błędy dla złożonych przypadków

## Użycie

```python
from doclingforge import Document
from doclingforge.render.direct_pdf_renderer import DirectPDFRenderer

# Podstawowe użycie
doc = Document.open("input.docx")
renderer = DirectPDFRenderer()
renderer.render(doc, "output.pdf")

# Z opcjami debugowania
renderer = DirectPDFRenderer(
    debug_borders=True,
    debug_spaces=True,
    force_justify=True
)
renderer.render(doc, "output.pdf")

# Convenience function
from doclingforge.render.direct_pdf_renderer import render_pdf_direct
render_pdf_direct(doc, "output.pdf", page_size='A4')
```

## Podsumowanie

`DirectPDFRenderer` to kompleksowy renderer PDF z:
- ✅ Zaawansowanym text wrapping i justification
- ✅ Pełną obsługą tabel z auto-fit
- ✅ Multi-level lists
- ✅ Headers/footers z placeholders
- ✅ Obrazami (inline/anchored)
- ✅ Zaawansowanymi dekoracjami (borders, backgrounds, shadows)
- ✅ Optymalizacjami (cache, XObjects)
- ✅ Debug features

Renderer jest gotowy do produkcji i obsługuje większość typowych przypadków użycia DOCX→PDF.

