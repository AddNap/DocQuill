# Rust Renderer - Dostępne Metody Renderowania

## Metody Wysokiego Poziomu (dostępne z Pythona)

### Zarządzanie Stronami
1. **`new_page(width, height)`** - Tworzy nową stronę PDF
2. **`set_total_pages(total)`** - Ustawia całkowitą liczbę stron (dla field codes)
3. **`set_current_page_number(page_num)`** - Ustawia numer bieżącej strony
4. **`save()`** - Zapisuje PDF do pliku

### Rejestracja Zasobów
5. **`register_truetype_font(path)`** - Rejestruje font TrueType/OpenType
6. **`register_image_stream(key, data, mime_type)`** - Rejestruje obraz jako stream (bajty)

### Renderowanie Bloków (z JSON)
7. **`render_paragraph_block(x, y, width, height, content_json)`** - Renderuje paragraf z JSON
8. **`render_table_block(x, y, width, height, content_json)`** - Renderuje tabelę z JSON
9. **`render_image_block(x, y, width, height, image_path, width_emu, height_emu)`** - Renderuje obraz z ścieżki
10. **`render_image_block_stream(x, y, width, height, stream_key, width_emu, height_emu)`** - Renderuje obraz ze stream_key
11. **`render_header_block(x, y, width, height, content_json)`** - Renderuje nagłówek z JSON
12. **`render_footer_block(x, y, width, height, content_json)`** - Renderuje stopkę z JSON
13. **`render_footnotes_block(x, y, width, height, content_json)`** - Renderuje przypisy z JSON
14. **`render_endnotes_block(x, y, width, height, content_json)`** - Renderuje endnotes z JSON
15. **`render_rectangle_block(x, y, width, height, fill_color, stroke_color, line_width)`** - Renderuje prostokąt

## Metody Niskiego Poziomu (w canvas, nie eksponowane do Pythona)

Te metody są dostępne w `PdfCanvas`, ale nie są bezpośrednio dostępne z Pythona. 
Mogą być użyte wewnętrznie przez metody wysokiego poziomu:

### Rysowanie
- **`draw_string(x, y, text)`** - Rysuje tekst
- **`draw_string_justified(x, y, segments)`** - Rysuje tekst z justyfikacją
- **`draw_image(image_name, x, y, width, height)`** - Rysuje obraz
- **`rect(rect, fill, stroke)`** - Rysuje prostokąt
- **`round_rect(rect, radius, fill, stroke)`** - Rysuje zaokrąglony prostokąt
- **`line(x1, y1, x2, y2)`** - Rysuje linię

### Style i Kolory
- **`set_font(font_name, size)`** - Ustawia font
- **`set_fill_color(color)`** - Ustawia kolor wypełnienia
- **`set_stroke_color(color)`** - Ustawia kolor obrysu
- **`set_line_width(width)`** - Ustawia szerokość linii
- **`set_dash(pattern, offset)`** - Ustawia wzór kreskowania
- **`set_opacity(opacity)`** - Ustawia przezroczystość (placeholder)

### Transformacje
- **`translate(x, y)`** - Przesuwa układ współrzędnych
- **`rotate(angle_degrees)`** - Obraca układ współrzędnych
- **`scale(sx, sy)`** - Skaluje układ współrzędnych

### Zarządzanie Stanem
- **`save_state()`** - Zapisuje stan canvas
- **`restore_state()`** - Przywraca stan canvas

## Obecne Użycie w Kompilerze Python

### Używane Metody:
- ✅ `new_page()` - tworzenie stron
- ✅ `set_total_pages()` - ustawianie liczby stron
- ✅ `set_current_page_number()` - ustawianie numeru strony
- ✅ `register_image_stream()` - rejestracja obrazów
- ✅ `render_image_block()` - renderowanie obrazów z ścieżki
- ✅ `render_image_block_stream()` - renderowanie obrazów ze stream
- ✅ `render_paragraph_block()` - renderowanie paragrafów (z JSON)
- ✅ `render_table_block()` - renderowanie tabel (z JSON)
- ✅ `render_header_block()` - renderowanie nagłówków (z JSON)
- ✅ `render_footer_block()` - renderowanie stopek (z JSON)
- ✅ `render_footnotes_block()` - renderowanie przypisów (z JSON)
- ✅ `render_endnotes_block()` - renderowanie endnotes (z JSON)
- ✅ `render_rectangle_block()` - renderowanie prostokątów
- ✅ `save()` - zapisywanie PDF

### Nieużywane (ale dostępne):
- ⚠️ `register_truetype_font()` - dostępne, ale nie używane w match/case
- ⚠️ `render_layout()` - dostępne, ale deprecated (używamy bezpośrednich wywołań)

### Brakujące (wymagane dla pełnej implementacji match/case):
- ❌ `draw_string(x, y, text, font_name, font_size, color)` - potrzebne do renderowania tekstu z lines
- ❌ `draw_image_stream(x, y, width, height, stream_key)` - potrzebne do renderowania inline images
- ❌ `draw_line(x1, y1, x2, y2, color, width)` - potrzebne do renderowania linii (borders, grid)
- ❌ `draw_rect(x, y, width, height, fill_color, stroke_color, line_width)` - alternatywa dla render_rectangle_block

## Rekomendacje

Aby w pełni wykorzystać podejście match/case z bezpośrednimi wywołaniami:

1. **Dodać proste metody niskiego poziomu do Pythona:**
   - `draw_string(x, y, text, font_name, font_size, color)`
   - `draw_image_stream(x, y, width, height, stream_key)`
   - `draw_line(x1, y1, x2, y2, color, width)`
   - `draw_rect(x, y, width, height, fill_color, stroke_color, line_width)`

2. **Użyć ich w metodach match/case:**
   - `_render_paragraph_with_lines()` - używa `draw_string()` dla każdego tekstu
   - `_render_table_with_cells()` - używa `draw_string()` dla tekstu w komórkach, `draw_line()` dla grid
   - `_render_image_direct()` - używa `draw_image_stream()`
   - `_render_overlay()` - używa `draw_image_stream()` lub `draw_string()`

3. **Zachować metody wysokiego poziomu:**
   - Dla prostych przypadków użycia
   - Dla kompatybilności wstecznej
   - Dla renderowania z JSON (jeśli potrzebne)

## Podsumowanie

**Obecnie dostępne:** 15 metod wysokiego poziomu + metody niskiego poziomu w canvas

**Używane w kompilerze:** 13 metod wysokiego poziomu

**Brakujące dla pełnej implementacji match/case:** 4 proste metody niskiego poziomu (draw_string, draw_image_stream, draw_line, draw_rect)

