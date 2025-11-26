# ROZBIJENIE IMPLEMENTACJI: PARSER → ENGINE → RENDERER

## Zasady podziału:
- **PARSER**: Ekstrakcja i parsowanie danych z DOCX (czytanie, transformacja)
- **ENGINE**: Obliczenia geometryczne, layout logic, pozycjonowanie (nie rysuje!)
- **RENDERER**: Rysowanie na canvas (wszystko co dotyczy ReportLab/PDF)

---

## 🔵 PARSER (docx_interpreter/parser/)

### Metody do parsowania danych z DOCX:

1. ✅ **Parsowanie fontów** - już istnieje w `font_parser.py`
2. ✅ **Parsowanie stylów** - już istnieje w `style_parser.py`
3. ✅ **Parsowanie tabel** - już istnieje w `table_parser.py`
4. ✅ **Parsowanie obrazów** - już istnieje w `drawing_parser.py`
5. ✅ **Parsowanie header/footer** - już istnieje w `header_footer_parser.py`

**Brakuje (optional - jeśli wymagane):**
- ❌ Parsowanie relationship IDs dla header/footer (może być w `relationships_parser.py`)
- ❌ Parsowanie textboxów (może być w `drawing_parser.py`)

**Status parsera:** ✅ Parser jest wystarczająco kompletny!

---

## 🟢 ENGINE (docx_interpreter/Layout_engine/)

### Obliczenia geometryczne i layout logic:

#### PositionCalculator (rozszerzenie):
1. ✅ `twips_to_points` - już istnieje
2. ✅ `twips_to_inches` - **DODAJ**
3. ✅ `resolve_effective_indent` - **ROZSZERZ** (obecnie podstawowa wersja)
4. ✅ `estimate_paragraph_height` - **ROZSZERZ** (obecnie podstawowa wersja)
5. ❌ `estimate_paragraph_height_accurate` - **DODAJ NOWĄ**
6. ❌ `estimate_table_height` - **DODAJ NOWĄ**
7. ❌ `calculate_document_spacing` - **DODAJ NOWĄ**
8. ❌ `normalize_alignment` - **DODAJ NOWĄ**

#### TableLayoutEngine (NOWY moduł):
9. ❌ `calculate_table_column_widths` - **DODAJ NOWĄ**
10. ❌ `calculate_table_row_heights` - **DODAJ NOWĄ**
11. ❌ `calculate_cell_content_height` - **DODAJ NOWĄ**
12. ❌ `get_cell_border_style` - **DODAJ NOWĄ** (style logic, nie rysowanie)

#### LayoutEngine (rozszerzenie):
13. ❌ `analyze_style_alignments` - **DODAJ NOWĄ**
14. ❌ `check_collision` - **DODAJ NOWĄ** (geometria kolizji)
15. ❌ `compute_anchored_image_bbox` - **DODAJ NOWĄ** (obliczanie bounding box)
16. ❌ `compute_textbox_footer_bbox` - **DODAJ NOWĄ**

#### PaginationEngine (NOWY moduł):
17. ❌ `calculate_total_pages` - **DODAJ NOWĄ** (logika, nie renderowanie)
18. ❌ `calculate_footer_height_dynamic` - **DODAJ NOWĄ**

---

## 🔴 RENDERER (docx_interpreter/renderers/pdf_renderer.py)

### Rysowanie na canvas PDF:

#### Podstawowe renderowanie:
1. ✅ `_get_font_info` - już istnieje
2. ✅ `_draw_text_with_formatting` - już istnieje
3. ✅ `_register_fonts` - już istnieje
4. ✅ `_to_roman` - już istnieje
5. ⚠️ `_render_text_line` - **ROZSZERZ** (ulepszona justyfikacja)
6. ⚠️ `_render_image_inline` - **ROZSZERZ** (bardziej zaawansowane)

#### Renderowanie paragrafów:
7. ❌ `_render_paragraph` - **DODAJ NOWĄ** (479 linii - główna metoda)
8. ⚠️ `_break_paragraph_into_lines` - **ROZSZERZ** (w pdf_text_breaking.py)
9. ❌ `_render_paragraph_block_decorations` - **DODAJ NOWĄ** (334 linii)
10. ❌ `_render_paragraphs_in_bounds` - **DODAJ NOWĄ**

#### Renderowanie tabel:
11. ⚠️ `_render_table_basic` - **ZAMIEŃ** na `_render_table_universal`
12. ❌ `_render_table_universal` - **DODAJ NOWĄ** (245 linii)
13. ❌ `_render_cell_content` - **DODAJ NOWĄ** (243 linii)
14. ❌ `_render_cell_content_footer` - **DODAJ NOWĄ**
15. ❌ `_render_cell_text_fragment_inline` - **DODAJ NOWĄ**
16. ❌ `_draw_table_row_borders` - **DODAJ NOWĄ** (rysowanie obramowań)
17. ❌ `_draw_cell_borders` - **DODAJ NOWĄ** (rysowanie obramowań)

#### Renderowanie obrazów:
18. ❌ `_render_image_anchored` - **DODAJ NOWĄ** (137 linii)
19. ❌ `_render_image_inline_footer` - **DODAJ NOWĄ**
20. ⚠️ `_get_image_data` - **ROZSZERZ** do `_get_image_data_with_conversion`
21. ❌ `_get_cached_image_xobject` - **DODAJ NOWĄ**

#### Renderowanie header/footer:
22. ⚠️ `_render_header` - **ROZSZERZ** (pełna wersja)
23. ⚠️ `_render_footer` - **ROZSZERZ** (399 linii - pełna wersja)
24. ❌ `_render_table_in_footer_OLD` - **DODAJ NOWĄ**

#### Renderowanie textboxów:
25. ❌ `_render_textbox_in_header` - **DODAJ NOWĄ**
26. ❌ `_render_textbox_in_footer` - **DODAJ NOWĄ**
27. ❌ `_render_textbox_in_footer_inline` - **DODAJ NOWĄ**
28. ❌ `_render_textbox_inline` - **DODAJ NOWĄ**

#### Paginacja i zarządzanie stronami:
29. ❌ `_new_page` - **DODAJ NOWĄ**
30. ❌ `_dry_run_render` - **DODAJ NOWĄ** (269 linii)
31. ❌ `_find_header_by_rid` - **DODAJ NOWĄ** (wrapper, używa parsowania)
32. ❌ `_find_footer_by_rid` - **DODAJ NOWĄ** (wrapper, używa parsowania)

#### Pomocnicze:
33. ❌ `_borders_are_identical` - **DODAJ NOWĄ** (porównywanie obramowań)
34. ❌ `_draw_debug_margin_lines` - **DODAJ NOWĄ** (opcjonalne - debug)

---

## 📊 STATYSTYKI PODZIAŁU

### ENGINE (Layout_engine/):
- **PositionCalculator (rozszerzenie):** 8 metod (~400 linii)
- **TableLayoutEngine (nowy):** 4 metody (~300 linii)
- **LayoutEngine (rozszerzenie):** 4 metody (~200 linii)
- **PaginationEngine (nowy):** 2 metody (~100 linii)
- **RAZEM ENGINE:** ~18 metod, ~1000 linii

### RENDERER (renderers/pdf_renderer.py):
- **Podstawowe:** 3 metody (~200 linii)
- **Paragrafy:** 4 metody (~1200 linii)
- **Tabele:** 7 metod (~900 linii)
- **Obrazy:** 4 metody (~300 linii)
- **Header/Footer:** 3 metody (~600 linii)
- **Textboxy:** 4 metody (~200 linii)
- **Paginacja:** 4 metody (~350 linii)
- **Pomocnicze:** 2 metody (~100 linii)
- **RAZEM RENDERER:** ~31 metod, ~3850 linii

### PARSER:
- ✅ **Gotowe** - parser jest kompletny

---

## 🎯 PLAN IMPLEMENTACJI Z PODZIAŁEM

### FAZA 1: Engine - Fundamenty geometryczne

#### PositionCalculator (rozszerzenie):
```python
# docx_interpreter/Layout_engine/position_calculator.py
- twips_to_inches()  # NOWA
- resolve_effective_indent()  # ROZSZERZ
- estimate_paragraph_height()  # ROZSZERZ
- estimate_paragraph_height_accurate()  # NOWA (używa text breaking)
- estimate_table_height()  # NOWA
- calculate_document_spacing()  # NOWA
- normalize_alignment()  # NOWA
```

#### PaginationEngine (nowy moduł):
```python
# docx_interpreter/Layout_engine/pagination_engine.py
- calculate_total_pages(document)  # NOWA
- calculate_footer_height_dynamic(document)  # NOWA
```

### FAZA 2: Engine - Tabele

#### TableLayoutEngine (nowy moduł):
```python
# docx_interpreter/Layout_engine/table_layout_engine.py
- calculate_table_column_widths(table, available_width, num_cols)  # NOWA
- calculate_table_row_heights(table, col_widths)  # NOWA
- calculate_cell_content_height(cell, cell_width, padding)  # NOWA
- get_cell_border_style(cell_props, table_props)  # NOWA (zwraca dict, nie rysuje!)
```

### FAZA 3: Engine - Layout i kolizje

#### LayoutEngine (rozszerzenie):
```python
# docx_interpreter/Layout_engine/layout_engine.py
- analyze_style_alignments(document)  # NOWA
- check_collision(x1, y1, w1, h1, x2, y2, w2, h2)  # NOWA
- compute_anchored_image_bbox(image)  # NOWA
- compute_textbox_footer_bbox(textbox)  # NOWA
```

### FAZA 4: Renderer - Paginacja i fundamenty

```python
# docx_interpreter/renderers/pdf_renderer.py
- _new_page()  # NOWA
- _dry_run_render(document)  # NOWA (używa engine do obliczeń)
- _find_header_by_rid(rel_id)  # NOWA (wrapper)
- _find_footer_by_rid(rel_id)  # NOWA (wrapper)
```

### FAZA 5: Renderer - Paragrafy

```python
# docx_interpreter/renderers/pdf_renderer.py
- _render_paragraph(paragraph, next_paragraph)  # NOWA (479 linii)
- _render_paragraph_block_decorations(...)  # NOWA (334 linii)
- _render_paragraphs_in_bounds(...)  # NOWA
- _break_paragraph_into_lines()  # ROZSZERZ w pdf_text_breaking.py
- _render_text_line()  # ROZSZERZ (ulepszona justyfikacja)
```

### FAZA 6: Renderer - Tabele

```python
# docx_interpreter/renderers/pdf_renderer.py
- _render_table_universal(table, x, y, direction)  # NOWA (245 linii)
- _render_cell_content(cell, x, y, width, height)  # NOWA (243 linii)
- _render_cell_content_footer(...)  # NOWA
- _render_cell_text_fragment_inline(...)  # NOWA
- _draw_table_row_borders(...)  # NOWA (rysowanie)
- _draw_cell_borders(...)  # NOWA (rysowanie)
```

### FAZA 7: Renderer - Obrazy i textboxy

```python
# docx_interpreter/renderers/pdf_renderer.py
- _render_image_anchored(image)  # NOWA (137 linii)
- _render_image_inline_footer(...)  # NOWA
- _get_image_data_with_conversion(image)  # ROZSZERZ
- _get_cached_image_xobject(...)  # NOWA
- _render_textbox_in_header(...)  # NOWA
- _render_textbox_in_footer(...)  # NOWA
- _render_textbox_in_footer_inline(...)  # NOWA
- _render_textbox_inline(...)  # NOWA
```

### FAZA 8: Renderer - Header/Footer

```python
# docx_interpreter/renderers/pdf_renderer.py
- _render_header()  # ROZSZERZ (pełna wersja)
- _render_footer()  # ROZSZERZ (399 linii - pełna wersja)
- _render_table_in_footer_OLD(...)  # NOWA
```

### FAZA 9: Renderer - Pomocnicze

```python
# docx_interpreter/renderers/pdf_renderer.py
- _borders_are_identical(props1, props2)  # NOWA
- _draw_debug_margin_lines()  # NOWA (opcjonalne)
```

---

## 🔗 ZALEŻNOŚCI MIĘDZY MODUŁAMI

```
PARSER → ENGINE → RENDERER
         ↓         ↓
    [dane]    [obliczenia] → [rysowanie]
```

### Przykład przepływu:

1. **PARSER** ekstraktuje paragraf z DOCX
2. **ENGINE** oblicza:
   - Indentację (`resolve_effective_indent`)
   - Wysokość (`estimate_paragraph_height_accurate`)
   - Layout (`analyze_style_alignments`)
3. **RENDERER** rysuje:
   - Wywołuje metody engine do obliczeń
   - Używa wyników do rysowania na canvas

### Zasada:
- **Engine NIE rysuje** - tylko oblicza i zwraca wartości
- **Renderer NIE oblicza geometrii** - używa engine
- **Parser NIE renderuje** - tylko ekstraktuje dane

---

## 📝 NOWE PLIKI DO UTWORZENIA

### Layout Engine:
1. `docx_interpreter/Layout_engine/pagination_engine.py` - NOWY
2. `docx_interpreter/Layout_engine/table_layout_engine.py` - NOWY
3. `docx_interpreter/Layout_engine/position_calculator.py` - ROZSZERZ
4. `docx_interpreter/Layout_engine/layout_engine.py` - ROZSZERZ

### Renderer:
5. `docx_interpreter/renderers/pdf_renderer.py` - ROZSZERZ (główny plik)
6. `docx_interpreter/renderers/pdf_text_breaking.py` - ROZSZERZ (już istnieje)

---

## ✅ CHECKLIST IMPLEMENTACJI

### ENGINE (18 metod):
- [ ] PositionCalculator: 8 metod
- [ ] TableLayoutEngine: 4 metody (nowy moduł)
- [ ] LayoutEngine: 4 metody (rozszerzenie)
- [ ] PaginationEngine: 2 metody (nowy moduł)

### RENDERER (31 metod):
- [ ] Podstawowe: 3 metody
- [ ] Paragrafy: 4 metody
- [ ] Tabele: 7 metod
- [ ] Obrazy: 4 metody
- [ ] Header/Footer: 3 metody
- [ ] Textboxy: 4 metody
- [ ] Paginacja: 4 metody
- [ ] Pomocnicze: 2 metody

**RAZEM:** ~49 metod, ~4850 linii kodu

