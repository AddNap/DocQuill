# Brakujące funkcjonalności w nowym PDF rendererze

## Główne kategorie brakujących metod:

### 1. **Renderowanie tabel (Zaawansowane)**
- ❌ `_render_table_universal` - uniwersalne renderowanie tabel
- ❌ `_calculate_table_column_widths` - obliczanie szerokości kolumn
- ❌ `_calculate_table_row_heights` - obliczanie wysokości wierszy
- ❌ `_calculate_cell_content_height` - wysokość zawartości komórki
- ❌ `_render_cell_content` - renderowanie zawartości komórki
- ❌ `_render_cell_content_footer` - komórki w stopce
- ❌ `_render_cell_text_fragment_inline` - fragmenty tekstu w komórkach
- ❌ `_get_cell_border_style` - style obramowań komórek
- ❌ `_draw_table_row_borders` - obramowania wierszy
- ❌ `_draw_cell_borders` - obramowania komórek
- ❌ `_render_table_in_footer_OLD` - tabele w stopce

### 2. **Tekst i paragrafy**
- ✅ `_break_paragraph_into_lines` - częściowo (w pdf_text_breaking.py)
- ❌ `_render_paragraph` - główna metoda renderowania paragrafów
- ❌ `_render_paragraph_block_decorations` - dekoracje bloków paragrafów
- ❌ `_render_paragraphs_in_bounds` - paragrafy w określonych granicach
- ❌ `_resolve_effective_indent` - rozwiązywanie efektów indentacji (częściowo w PositionCalculator)
- ❌ `_estimate_paragraph_height` - szacowanie wysokości paragrafu
- ❌ `_estimate_paragraph_height_accurate` - dokładne szacowanie

### 3. **Obrazy**
- ❌ `_render_image_anchored` - obraz zakotwiczony (floating)
- ❌ `_render_image_inline_footer` - obrazy inline w stopce
- ❌ `_get_image_data_with_conversion` - konwersja obrazów (EMF/WMF)
- ❌ `_get_cached_image_xobject` - cache obrazów jako XObject

### 4. **Header/Footer**
- ❌ `_find_header_by_rid` - znajdowanie nagłówka po rId
- ❌ `_find_footer_by_rid` - znajdowanie stopki po rId
- ❌ `_calculate_footer_height_dynamic` - dynamiczna wysokość stopki
- ❌ `_render_textbox_in_header` - textboxy w nagłówku
- ❌ `_render_textbox_in_footer` - textboxy w stopce
- ❌ `_render_textbox_in_footer_inline` - textboxy inline w stopce
- ❌ `_render_textbox_inline` - textboxy inline w treści
- ❌ `_compute_textbox_footer_bbox` - obliczanie bounding box textboxów
- ❌ `_compute_anchored_image_bbox` - obliczanie bounding box obrazów zakotwiczonych

### 5. **Dekoracje i style**
- ❌ `_render_paragraph_block_decorations` - dekoracje bloków (shadow, background, borders)
- ❌ `_borders_are_identical` - porównywanie obramowań
- ❌ `_analyze_style_alignments` - analiza wyrównań stylów

### 6. **Paginacja i layout**
- ❌ `_new_page` - tworzenie nowej strony
- ❌ `_dry_run_render` - dry-run renderowania (obliczanie liczby stron)
- ❌ `_calculate_total_pages` - obliczanie całkowitej liczby stron
- ❌ `_estimate_table_height` - szacowanie wysokości tabeli
- ❌ `_calculate_document_spacing` - obliczanie odstępów dokumentu
- ❌ `_draw_debug_margin_lines` - linie debug marginesów

### 7. **Narzędzia pomocnicze**
- ❌ `_check_collision` - sprawdzanie kolizji elementów
- ❌ `_normalize_alignment` - normalizacja wyrównania
- ❌ `twips_to_inches` - konwersja twips na cale

## Co jest już zaimplementowane:
- ✅ Podstawowe renderowanie tekstu (`_render_text_line`)
- ✅ Font info (`_get_font_info`)
- ✅ Formatowanie tekstu (`_draw_text_with_formatting`)
- ✅ List markers (`_get_list_marker`)
- ✅ Podstawowe renderowanie tabel (`_render_table_basic`)
- ✅ Podstawowe renderowanie obrazów inline (`_render_image_inline`)
- ✅ Podstawowe header/footer (`_render_header`, `_render_footer`)
- ✅ Dekoracje paragrafów (`_render_paragraph_decorations`)
- ✅ Text breaking (`pdf_text_breaking.py`)

## Priorytety implementacji:

### Wysoki priorytet:
1. `_render_table_universal` + wszystkie metody pomocnicze tabel
2. `_render_paragraph_block_decorations` - pełne dekoracje bloków
3. `_render_image_anchored` - floating images
4. `_estimate_paragraph_height_accurate` - dla paginacji
5. `_new_page` + `_dry_run_render` - poprawna paginacja

### Średni priorytet:
6. `_render_textbox_*` - textboxy wszędzie
7. `_find_header_by_rid` / `_find_footer_by_rid` - poprawne header/footer
8. `_resolve_effective_indent` - pełna logika indentacji

### Niski priorytet:
9. Debug helpers (`_draw_debug_margin_lines`)
10. `twips_to_inches`
11. `_check_collision`

