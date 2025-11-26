# PEŁNA LISTA IMPLEMENTACJI PDF RENDERERA

## Analiza: Stary renderer ma 5664 linii, nowy ma 2086 linii
**Brakuje: ~3578 linii kodu w ~47 metodach**

---

## 🔴 KRYTYCZNE - PRIORYTET 1 (największe metody, kluczowe funkcjonalności)

### 1. `_render_paragraph` (479 linii) ⚠️ NAJWIĘKSZA METODA
**Status:** ❌ Brak  
**Odpowiedzialność:** Główna metoda renderowania paragrafów
- Renderowanie paragrafów z pełnym formatowaniem
- Obsługa `keep_together`, `keep_with_next`, `widows/orphans`
- Paginacja na poziomie paragrafu
- Renderowanie bloków (dekoracje per-page)
- Integracja z list markers
- Spacing before/after

**Zależności:**
- `_break_paragraph_into_lines` ✅ (częściowo w pdf_text_breaking.py)
- `_render_paragraph_block_decorations` ❌
- `_estimate_paragraph_height_accurate` ❌
- `_resolve_effective_indent` ⚠️ (częściowo w PositionCalculator)
- `_get_list_marker` ✅ (zaimplementowane)

---

### 2. `_render_footer` (399 linii)
**Status:** ⚠️ Podstawowa wersja istnieje, brakuje zaawansowanych funkcji  
**Brakuje:**
- Dynamiczna wysokość stopki (`_calculate_footer_height_dynamic`)
- Tabele w stopce (`_render_table_in_footer_OLD`)
- Textboxy w stopce (`_render_textbox_in_footer`, `_render_textbox_in_footer_inline`)
- Obrazy inline w stopce (`_render_image_inline_footer`)
- Renderowanie w określonych granicach (`_render_paragraphs_in_bounds`)
- Wyszukiwanie po rId (`_find_footer_by_rid`)

---

### 3. `_break_paragraph_into_lines` (379 linii)
**Status:** ⚠️ Częściowo w `pdf_text_breaking.py`  
**Brakuje:**
- Pełna obsługa inline images w liniach
- Obsługa textboxów w liniach
- Line breaks (soft enters)
- Tabs w tekście
- Special items (line breaks, images) na końcu

---

### 4. `_render_paragraph_block_decorations` (334 linii)
**Status:** ❌ Brak  
**Odpowiedzialność:** Dekoracje bloków paragrafów (shadow, background, borders)
- Renderowanie per-page block (nie dla całego paragrafu)
- Precyzyjne pozycjonowanie względem tekstu
- Padding handling
- Line spacing consideration
- Border merging między paragrafami
- Shadow rendering
- Background rendering z uwzględnieniem descent/ascent

**Zależności:**
- `_borders_are_identical` ❌

---

### 5. `_dry_run_render` (269 linii)
**Status:** ❌ Brak  
**Odpowiedzialność:** Dry-run renderowania aby policzyć faktyczną liczbę stron
- FAKTYCZNE renderowanie całego dokumentu na tymczasowym canvas
- Liczenie stron bez zapisywania
- Reset stanu po dry-run
- Obsługa wszystkich elementów (paragrafy, tabele, obrazy)

**Zależności:**
- `_render_paragraph` ❌
- `_render_table_universal` ❌
- `_render_image_anchored` ❌
- `_new_page` ❌

---

### 6. `_render_table_universal` (245 linii)
**Status:** ⚠️ Tylko `_render_table_basic` istnieje  
**Brakuje:**
- Uniwersalne renderowanie (top_to_bottom, bottom_to_top)
- Obliczanie szerokości kolumn (`_calculate_table_column_widths`)
- Obliczanie wysokości wierszy (`_calculate_table_row_heights`)
- Renderowanie zawartości komórek (`_render_cell_content`)
- Style obramowań (`_get_cell_border_style`)
- Obramowania wierszy (`_draw_table_row_borders`)
- Obramowania komórek (`_draw_cell_borders`)
- Wysokość zawartości komórki (`_calculate_cell_content_height`)

**Zależności:**
- `_calculate_table_column_widths` ❌
- `_calculate_table_row_heights` ❌
- `_render_cell_content` ❌
- `_get_cell_border_style` ❌
- `_draw_table_row_borders` ❌
- `_draw_cell_borders` ❌
- `_calculate_cell_content_height` ❌

---

## 🟠 WAŻNE - PRIORYTET 2

### 7. `_render_cell_content` (243 linii)
**Status:** ❌ Brak  
**Odpowiedzialność:** Renderowanie zawartości komórki tabeli
- Paragrafy w komórkach
- Tekst z formatowaniem
- Obrazy inline
- Textboxy inline
- Fragmenty tekstu (`_render_cell_text_fragment_inline`)

**Zależności:**
- `_render_cell_text_fragment_inline` ❌
- `_render_paragraphs_in_bounds` ❌

---

### 8. `_render_table_in_footer_OLD` (232 linii)
**Status:** ❌ Brak  
**Odpowiedzialność:** Renderowanie tabel w stopce
- Tabele w stopce z pełnym formatowaniem
- Specjalne pozycjonowanie
- Komórki w stopce (`_render_cell_content_footer`)

**Zależności:**
- `_render_cell_content_footer` ❌

---

### 9. `_render_text_line` (185 linii)
**Status:** ⚠️ Podstawowa wersja istnieje  
**Brakuje:**
- Ulepszona justyfikacja (tokenizacja ponad runami, rozkład wagowy)
- Dokładne domknięcie prawego brzegu
- Obsługa line breaks w linii
- Obsługa obrazów inline w linii
- Obsługa textboxów w linii

---

### 10. `_get_list_marker` (175 linii)
**Status:** ✅ Zaimplementowane (ale może wymagać sprawdzenia)

---

### 11. `_render_paragraphs_in_bounds` (145 linii)
**Status:** ❌ Brak  
**Odpowiedzialność:** Renderowanie paragrafów w określonych granicach
- Używane w komórkach tabeli i stopkach
- Ograniczenie szerokości i wysokości
- Word wrapping w granicach

---

### 12. `_render_header` (138 linii)
**Status:** ⚠️ Podstawowa wersja istnieje  
**Brakuje:**
- Wyszukiwanie po rId (`_find_header_by_rid`)
- Textboxy w nagłówku (`_render_textbox_in_header`)
- Anchored images
- Tabele w nagłówku
- Renderowanie w określonych granicach

---

### 13. `_render_image_anchored` (137 linii)
**Status:** ❌ Brak  
**Odpowiedzialność:** Renderowanie obrazów zakotwiczonych (floating)
- Absolute positioning
- Bounding box calculation (`_compute_anchored_image_bbox`)
- Collision detection (`_check_collision`)
- Behind document vs front of document
- Wrapping text around image

**Zależności:**
- `_compute_anchored_image_bbox` ❌
- `_check_collision` ❌

---

### 14. `_get_font_info` (132 linii)
**Status:** ✅ Zaimplementowane (wymaga sprawdzenia zgodności)

---

### 15. `_get_image_data_with_conversion` (108 linii)
**Status:** ⚠️ Tylko `_get_image_data` istnieje  
**Brakuje:**
- Konwersja EMF/WMF do PNG
- Cache konwersji
- Obsługa różnych formatów obrazów

---

## 🟡 ŚREDNIE - PRIORYTET 3

### 16. `_render_textbox_in_footer` (104 linii)
**Status:** ❌ Brak

### 17. `_draw_cell_borders` (101 linii)
**Status:** ❌ Brak

### 18. `_render_image_inline` (93 linii)
**Status:** ⚠️ Podstawowa wersja istnieje

### 19. `_calculate_cell_content_height` (92 linii)
**Status:** ❌ Brak

### 20. `_calculate_table_column_widths` (91 linii)
**Status:** ❌ Brak

### 21. `_render_cell_content_footer` (88 linii)
**Status:** ❌ Brak

### 22. `_analyze_style_alignments` (83 linii)
**Status:** ❌ Brak  
**Odpowiedzialność:** Analiza wyrównań stylów w dokumencie

### 23. `_get_cell_border_style` (81 linii)
**Status:** ❌ Brak

### 24. `_draw_text_with_formatting` (80 linii)
**Status:** ✅ Zaimplementowane

### 25. `_resolve_effective_indent` (79 linii)
**Status:** ⚠️ Częściowo w PositionCalculator  
**Brakuje:** Pełna logika hierarchii indentacji

### 26. `_render_textbox_in_footer_inline` (74 linii)
**Status:** ❌ Brak

### 27. `_calculate_table_row_heights` (72 linii)
**Status:** ❌ Brak

### 28. `_register_fonts` (67 linii)
**Status:** ✅ Zaimplementowane

### 29. `_draw_debug_margin_lines` (63 linii)
**Status:** ❌ Brak (opcjonalne - tylko debug)

### 30. `_calculate_footer_height_dynamic` (58 linii)
**Status:** ❌ Brak

### 31. `_render_cell_text_fragment_inline` (58 linii)
**Status:** ❌ Brak

### 32. `_render_image_inline_footer` (55 linii)
**Status:** ❌ Brak

### 33. `_borders_are_identical` (51 linii)
**Status:** ❌ Brak

---

## 🟢 MAŁE - PRIORYTET 4

### 34. `_calculate_total_pages` (48 linii)
**Status:** ❌ Brak

### 35. `_render_textbox_in_header` (47 linii)
**Status:** ❌ Brak

### 36. `_render_textbox_inline` (47 linii)
**Status:** ❌ Brak

### 37. `_compute_anchored_image_bbox` (45 linii)
**Status:** ❌ Brak

### 38. `_draw_table_row_borders` (43 linii)
**Status:** ❌ Brak

### 39. `_estimate_paragraph_height_accurate` (37 linii)
**Status:** ❌ Brak

### 40. `_get_cached_image_xobject` (36 linii)
**Status:** ❌ Brak

### 41. `_normalize_alignment` (31 linii)
**Status:** ❌ Brak

### 42. `_calculate_document_spacing` (28 linii)
**Status:** ❌ Brak

### 43. `_find_footer_by_rid` (28 linii)
**Status:** ❌ Brak

### 44. `_new_page` (26 linii)
**Status:** ❌ Brak

### 45. `_find_header_by_rid` (25 linii)
**Status:** ❌ Brak

### 46. `_check_collision` (25 linii)
**Status:** ❌ Brak

### 47. `_compute_textbox_footer_bbox` (24 linii)
**Status:** ❌ Brak

### 48. `_estimate_paragraph_height` (17 linii)
**Status:** ❌ Brak

### 49. `_to_roman` (16 linii)
**Status:** ✅ Zaimplementowane

### 50. `_estimate_table_height` (9 linii)
**Status:** ❌ Brak

---

## PODSUMOWANIE STATYSTYK

### Status implementacji:
- ✅ **Zaimplementowane:** 5 metod (~500 linii)
- ⚠️ **Częściowo:** 8 metod (~800 linii)
- ❌ **Brakuje:** 37 metod (~2278 linii)

### Rozkład według priorytetów:
- 🔴 **Priorytet 1 (Krytyczne):** 6 metod, ~2100 linii
- 🟠 **Priorytet 2 (Ważne):** 9 metod, ~1200 linii
- 🟡 **Priorytet 3 (Średnie):** 20 metod, ~900 linii
- 🟢 **Priorytet 4 (Małe):** 15 metod, ~350 linii

### Największe luki:
1. Renderowanie paragrafów (479 linii)
2. Renderowanie stopki (399 linii)
3. Breaking paragrafów (379 linii)
4. Dekoracje bloków (334 linii)
5. Dry-run renderowania (269 linii)
6. Tabele uniwersalne (245 linii)

---

## PLAN IMPLEMENTACJI (sugerowany)

### Faza 1: Fundamenty (Priorytet 1)
1. `_dry_run_render` + `_new_page` - paginacja
2. `_estimate_paragraph_height_accurate` - dokładne szacowanie
3. `_resolve_effective_indent` - pełna logika indentacji
4. `_render_paragraph_block_decorations` - dekoracje bloków
5. `_render_paragraph` - główna metoda paragrafów

### Faza 2: Tabele (Priorytet 1)
6. `_calculate_table_column_widths`
7. `_calculate_table_row_heights`
8. `_calculate_cell_content_height`
9. `_render_cell_content` + helpery
10. `_render_table_universal` + wszystkie metody obramowań

### Faza 3: Obrazy i Content (Priorytet 2)
11. `_render_image_anchored` + bbox helpers
12. `_get_image_data_with_conversion`
13. `_render_textbox_*` metody
14. `_render_paragraphs_in_bounds`

### Faza 4: Header/Footer (Priorytet 2)
15. `_find_header_by_rid` / `_find_footer_by_rid`
16. `_calculate_footer_height_dynamic`
17. `_render_footer` - pełna wersja
18. `_render_header` - pełna wersja

### Faza 5: Polish (Priorytet 3-4)
19. Wszystkie pozostałe metody pomocnicze
20. Debug helpers
21. Optymalizacje

