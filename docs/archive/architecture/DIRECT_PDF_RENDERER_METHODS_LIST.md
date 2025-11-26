# Lista wszystkich metod i funkcji w DirectPDFRenderer

## 📋 PODZIAŁ NA KATEGORIE

### 🔍 **KATEGORIA 1: PARSOWANIE I ANALIZA** (15 metod)
*Metody odpowiedzialne za analizę dokumentu, parsowanie właściwości i przygotowanie danych*

#### Konwersje i normalizacja:
- `_normalize_alignment(value)` - Normalizuje alignment do standardowych wartości
- `twips_to_points(twips)` - Konwertuje twips na punkty (static)
- `twips_to_inches(twips)` - Konwertuje twips na cale (static)

#### Analiza dokumentu:
- `_analyze_style_alignments(document)` - Analizuje alignment w stylach i tworzy override map
- `_calculate_document_spacing(document)` - Dynamicznie oblicza spacing z DOCX
- `_calculate_footer_height_dynamic(document)` - Oblicza wysokość stopki na podstawie zawartości
- `_calculate_total_pages(document)` - Oblicza całkowitą liczbę stron

#### Parsowanie właściwości:
- `_resolve_effective_indent(paragraph, indent_type)` - Rozwiązuje efektywne wcięcia paragrafu
- `_get_font_info(run)` - Pobiera informacje o foncie z run properties
- `_get_cell_border_style(cell_props, table_props)` - Pobiera styl ramek komórki
- `_get_image_data_with_conversion(image)` - Pobiera dane obrazu z konwersją

#### Znajdowanie elementów:
- `_find_header_by_rid(rel_id)` - Znajduje header po relationship ID
- `_find_footer_by_rid(rel_id)` - Znajduje footer po relationship ID
- `_get_list_marker(paragraph, numbering_id, level)` - Generuje marker listy
- `_to_roman(num)` - Konwertuje liczbę na rzymską

---

### ⚙️ **KATEGORIA 2: SILNIK GEOMETRII I OBLICZEŃ** (18 metod)
*Metody odpowiedzialne za obliczenia pozycji, wymiarów, layoutu i geometrii*

#### Obliczenia wymiarów:
- `_estimate_table_height(table)` - Estymuje wysokość tabeli dla dry-run
- `_estimate_paragraph_height(paragraph)` - Estymuje wysokość paragrafu
- `_estimate_paragraph_height_accurate(paragraph)` - Dokładne obliczenie wysokości paragrafu
- `_calculate_table_column_widths(table, available_width, num_cols)` - Oblicza szerokości kolumn tabeli
- `_calculate_table_row_heights(table, col_widths)` - Oblicza wysokości wierszy tabeli
- `_calculate_cell_content_height(cell, cell_width, total_padding)` - Oblicza wysokość zawartości komórki

#### Geometria i pozycjonowanie:
- `_check_collision(x1, y1, w1, h1, x2, y2, w2, h2)` - Sprawdza kolizję prostokątów
- `_compute_textbox_footer_bbox(textbox)` - Oblicza bounding box textbox w stopce
- `_compute_anchored_image_bbox(image)` - Oblicza bounding box zakotwiczonego obrazu

#### Łamanie tekstu:
- `_break_paragraph_into_lines(paragraph, available_width, first_line_indent, alignment)` - Łamie paragraf na linie z word wrapping

#### Cache i optymalizacje:
- `_get_cached_image_xobject(image_data, width, height)` - Pobiera cached XObject dla obrazu
- `_borders_are_identical(props1, props2)` - Sprawdza czy ramki są identyczne

#### Inicjalizacja i setup:
- `__init__(page_size, debug_borders, debug_spaces, force_justify, ignore_leading_trailing_spaces)` - Konstruktor
- `_register_fonts()` - Rejestruje fonty z obsługą polskich znaków
- `_new_page()` - Tworzy nową stronę PDF
- `_dry_run_render(document)` - Dry-run renderowania do liczenia stron

#### Debug:
- `_draw_debug_margin_lines()` - Rysuje linie marginesów do debugowania

---

### 🎨 **KATEGORIA 3: RENDEROWANIE** (23 metody)
*Metody odpowiedzialne za rzeczywiste rysowanie elementów w PDF*

#### Główny przepływ renderowania:
- `render(document, output_path)` - **GŁÓWNA METODA** - renderuje dokument do PDF
- `render_pdf_direct(document, output_path, page_size)` - Convenience function (standalone)

#### Renderowanie paragrafów:
- `_render_paragraph(paragraph, next_paragraph)` - Renderuje pojedynczy paragraf
- `_render_text_line(line, left_indent, alignment, available_width, is_last_line)` - Renderuje linię tekstu z alignment
- `_draw_text_with_formatting(text, x, y, font_info)` - Rysuje tekst z formatowaniem
- `_render_paragraph_block_decorations(block_start_y, block_height, left_indent, available_width, props, lines_in_block, next_paragraph_props)` - Renderuje dekoracje bloku paragrafu

#### Renderowanie tabel:
- `_render_table_universal(table, x, y, direction)` - **UNIWERSALNA** metoda renderowania tabeli
- `_render_cell_content(cell, cell_x, cell_y, cell_width, cell_height)` - Renderuje zawartość komórki
- `_render_cell_content_footer(cell, cell_x, cell_y, cell_width, cell_height)` - Renderuje zawartość komórki w stopce
- `_render_cell_text_fragment_inline(text, run, x, y, font_info, cell_width)` - Renderuje fragment tekstu w komórce
- `_render_paragraphs_in_bounds(paragraphs, x, y, width, height, direction)` - Renderuje paragrafy w granicach
- `_draw_table_row_borders(table, row_idx, x, y, col_widths, row_height)` - Rysuje ramki wiersza tabeli
- `_draw_cell_borders(x, y, width, height, border_style)` - Rysuje ramki komórki

#### Renderowanie obrazów:
- `_render_image_anchored(image)` - Renderuje zakotwiczony obraz
- `_render_image_inline(image, x, y, skip_page_check)` - Renderuje inline obraz
- `_render_image_inline_footer(image, x, y)` - Renderuje inline obraz w stopce

#### Renderowanie textboxów:
- `_render_textbox_inline(textbox, x, y)` - Renderuje inline textbox
- `_render_textbox_in_header(textbox, x, y)` - Renderuje textbox w nagłówku
- `_render_textbox_in_footer(textbox, x, y)` - Renderuje textbox w stopce
- `_render_textbox_in_footer_inline(textbox, x, y)` - Renderuje inline textbox w stopce

#### Headers i footers:
- `_render_header()` - Renderuje nagłówek strony
- `_render_footer()` - Renderuje stopkę strony

#### Legacy/Deprecated:
- `_render_table_in_footer_OLD(table, x, y)` - **STARA** metoda renderowania tabeli w stopce (zastąpiona przez _render_table_universal)

---

## 📊 **STATYSTYKI**

| Kategoria | Liczba metod | Procent |
|-----------|--------------|---------|
| **Parsowanie i analiza** | 15 | 26.8% |
| **Silnik geometrii i obliczeń** | 18 | 32.1% |
| **Renderowanie** | 23 | 41.1% |
| **RAZEM** | **56** | **100%** |

## 🔗 **ZALEŻNOŚCI MIĘDZY KATEGORIAMI**

```
PARSOWANIE → SILNIK GEOMETRII → RENDEROWANIE
     ↓              ↓                ↓
  Dane DOCX    →  Obliczenia    →  PDF Output
```

**Przykład przepływu:**
1. `_analyze_style_alignments()` (PARSOWANIE) → analizuje dokument
2. `_calculate_table_column_widths()` (SILNIK) → oblicza wymiary
3. `_render_table_universal()` (RENDEROWANIE) → rysuje tabelę

## 🎯 **KLUCZOWE METODY**

### **Najważniejsze metody główne:**
- `render()` - Punkt wejścia całego renderowania
- `_render_table_universal()` - Uniwersalne renderowanie tabel
- `_break_paragraph_into_lines()` - Zaawansowane łamanie tekstu
- `_render_text_line()` - Renderowanie z justyfikacją

### **Najważniejsze obliczeniowe:**
- `_calculate_table_column_widths()` - Auto-fit tabel
- `_calculate_table_row_heights()` - Dynamiczne wysokości wierszy
- `_estimate_paragraph_height()` - Estymacja wysokości

### **Najważniejsze parsujące:**
- `_analyze_style_alignments()` - Analiza stylów
- `_get_font_info()` - Informacje o fontach
- `_resolve_effective_indent()` - Wcięcia paragrafów
