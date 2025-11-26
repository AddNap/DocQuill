# Porównanie funkcji: ReportLab vs Rust Renderer

Ten dokument porównuje funkcjonalności implementacji ReportLab (`pdf_compiler.py`) z implementacją Rust (`pdf_renderer_rust`).

## ✅ Zaimplementowane w Rust

### Podstawowe funkcje
- ✅ Tworzenie PDF z `pdf-writer`
- ✅ Tworzenie stron (`new_page`)
- ✅ Renderowanie podstawowych bloków:
  - ✅ Paragrafy (podstawowe)
  - ✅ Tabele (podstawowe)
  - ✅ Obrazy (placeholder)
  - ✅ Textboxy (podstawowe)
  - ✅ Dekoratory (podstawowe)
- ✅ Obsługa kolorów (RGB)
- ✅ Podstawowe obramowania (borders)
- ✅ Tło (background) dla bloków
- ✅ Podstawowe fonty (Helvetica, Times-Roman, Courier)

### Canvas API
- ✅ `save_state` / `restore_state`
- ✅ `set_fill_color` / `set_stroke_color`
- ✅ `rect` (prostokąty)
- ✅ `line` (linie)
- ✅ `draw_string` (tekst)
- ✅ `translate`, `rotate`, `scale` (transformacje)
- ✅ `set_line_width`
- ✅ `set_dash` (wzory kreskowania)

---

## ❌ Brakujące funkcje w Rust

### 1. Renderowanie Paragrafów

#### Zaawansowane layoutowanie tekstu
- ❌ **ParagraphLayout** - renderowanie z gotowego layoutu (linie z baseline, offset_x, etc.)
- ❌ **TextMetricsEngine** - pomiar szerokości tekstu
- ❌ **TextAlignmentEngine** - wyrównanie tekstu (left, center, right, justify)
- ❌ **KerningEngine** - kerning (odstępy między znakami)
- ❌ **LigatureEngine** - ligatury
- ❌ **Multi-line text** - prawidłowe renderowanie wielu linii z właściwym line spacing
- ❌ **Text wrapping** - zawijanie tekstu do szerokości kolumny
- ❌ **Justification** - wyrównanie do obu marginesów z rozłożeniem odstępów między słowami

#### Inline elements
- ❌ **Inline images** - obrazy w tekście (inline_image)
- ❌ **Inline textboxes** - textboxy w tekście
- ❌ **Text runs** - różne style w jednej linii (bold, italic, color, font_size)
- ❌ **Fields** - pola formularzy (field codes)
- ❌ **Hyperlinks** - linki w tekście
- ❌ **Highlighting** - podświetlanie tekstu (background color dla fragmentów)

#### Markery list
- ❌ **List markers** - numery, bullet points, custom markers
- ❌ **Marker positioning** - pozycjonowanie markerów względem tekstu
- ❌ **Marker styling** - style markerów (font, color, size)

#### Inne
- ❌ **Paragraph padding** - padding wewnętrzny paragrafu
- ❌ **Line spacing** - kontrola odstępów między liniami (line_spacing_factor)
- ❌ **Baseline adjustment** - dostosowanie baseline dla różnych fontów
- ❌ **Paragraph alignment** - left, center, right, justify
- ❌ **Border between paragraphs** - linie między paragrafami (_border_between_top)

### 2. Renderowanie Tabel

#### Zaawansowane funkcje
- ❌ **Cell padding** - padding w komórkach
- ❌ **Cell margins** - marginesy komórek (z parsowaniem twips → points)
- ❌ **Cell spacing** - odstępy między komórkami
- ❌ **Row heights** - dynamiczne obliczanie wysokości wierszy na podstawie zawartości
- ❌ **Column widths** - dynamiczne szerokości kolumn
- ❌ **Cell colspan** - łączenie komórek w poziomie (grid_span)
- ❌ **Cell rowspan** - łączenie komórek w pionie (vertical_merge)
- ❌ **Vertical merge tracking** - śledzenie vertical merge (restart/continue)
- ❌ **Inside borders** - wewnętrzne obramowania (insideH, insideV)
- ❌ **Cell background** - tło dla pojedynczych komórek
- ❌ **Cell borders** - obramowania dla pojedynczych komórek
- ❌ **Cell content rendering** - renderowanie paragrafów w komórkach (_render_cell_paragraphs)
- ❌ **Cell alignment** - wyrównanie zawartości komórek (horizontal, vertical)
- ❌ **Table header/footer** - nagłówki i stopki tabeli (header_footer_context)

#### Parsowanie stylów
- ❌ **Border normalization** - normalizacja specyfikacji obramowań (_normalize_inside_spec)
- ❌ **Border visibility check** - sprawdzanie czy border jest widoczny (_border_spec_visible)
- ❌ **Border style parsing** - parsowanie stylów obramowań (solid, dashed, dotted, etc.)
- ❌ **Border width parsing** - parsowanie szerokości (sz, width, val)

### 3. Renderowanie Obrazów

#### Podstawowe funkcje
- ❌ **Image loading** - ładowanie obrazów z plików (PNG, JPEG)
- ❌ **Image path resolution** - rozwiązywanie ścieżek obrazów (_resolve_image_path)
- ❌ **Image caching** - cache obrazów (image_cache)
- ❌ **Image scaling** - skalowanie obrazów do rozmiaru ramki
- ❌ **Preserve aspect ratio** - zachowanie proporcji obrazu
- ❌ **Image masks** - maski dla obrazów (mask="auto")
- ❌ **EMF/WMF support** - obsługa obrazów EMF/WMF (konwersja przez Java daemon)

#### Zaawansowane
- ❌ **Image DPI handling** - obsługa różnych DPI (_IMAGE_TARGET_DPI = 192.0)
- ❌ **Image error handling** - obsługa błędów z placeholderami
- ❌ **Image in paragraphs** - obrazy w paragrafach (inline images)
- ❌ **Image positioning** - pozycjonowanie obrazów w paragrafach
- ❌ **Image size calculation** - obliczanie rozmiaru obrazu (EMU → points)

### 4. Renderowanie Textboxów

- ❌ **Textbox content** - renderowanie zawartości textboxa
- ❌ **Textbox styling** - style textboxa
- ❌ **Textbox with ParagraphLayout** - textboxy z ParagraphLayout payload
- ❌ **Textbox overlays** - textboxy jako overlay (_draw_overlays)

### 5. Renderowanie Headerów/Footerów

- ❌ **Header rendering** - renderowanie headerów (_draw_header)
- ❌ **Footer rendering** - renderowanie footerów (_draw_footer)
- ❌ **Header/footer images** - obrazy w headerach/footerach
- ❌ **Header/footer context** - kontekst header/footer dla stylowania

### 6. Renderowanie Watermarków

- ❌ **Watermark rendering** - renderowanie watermarków (_draw_watermark)
- ❌ **VML shape watermarks** - watermarki jako VML shapes
- ❌ **Watermark rotation** - rotacja watermarków
- ❌ **Watermark transparency** - przezroczystość watermarków
- ❌ **Watermark positioning** - pozycjonowanie watermarków (środek strony)

### 7. Renderowanie Footnotes/Endnotes

- ❌ **Footnotes rendering** - renderowanie przypisów (_draw_footnotes)
- ❌ **Endnotes rendering** - renderowanie endnotes (_draw_endnotes)
- ❌ **Footnote references** - referencje do przypisów w tekście
- ❌ **Footnote positioning** - pozycjonowanie przypisów na stronie

### 8. Zaawansowane Style

#### Background
- ❌ **Shading** - cieniowanie tła (shading.fill, shading.color)
- ❌ **Background color parsing** - parsowanie różnych formatów kolorów tła
- ❌ **Background for groups** - tło dla grup paragrafów

#### Borders
- ❌ **Rounded rectangles** - zaokrąglone prostokąty (radius > 0)
- ❌ **Border styles** - różne style obramowań (solid, dashed, dotted, double, etc.)
- ❌ **Border width parsing** - parsowanie szerokości obramowań (sz, width)
- ❌ **Border color parsing** - parsowanie kolorów obramowań
- ❌ **Border group drawing** - grupowanie obramowań (_border_group_draw)
- ❌ **Borders override** - nadpisywanie obramowań (_borders_to_draw)

#### Shadow
- ❌ **Shadow rendering** - renderowanie cieni (draw_shadow)
- ❌ **Shadow offset** - offset cienia (offset_x, offset_y)
- ❌ **Shadow color** - kolor cienia

### 9. Fonty

- ❌ **TTF/OTF font loading** - ładowanie niestandardowych fontów
- ❌ **Font embedding** - osadzanie fontów w PDF
- ❌ **Font fallback** - fallback do innych fontów
- ❌ **Font metrics** - metryki fontów (ascent, descent, etc.)
- ❌ **Font subsetting** - subsetting fontów (tylko używane znaki)

### 10. Kolory

- ❌ **Color parsing** - parsowanie różnych formatów kolorów (_color_to_reportlab, _hex_to_rgb)
- ❌ **CMYK colors** - obsługa kolorów CMYK
- ❌ **Named colors** - nazwane kolory
- ❌ **Color fallback** - fallback do domyślnych kolorów

### 11. Content Resolution

- ❌ **Content resolution** - rozwiązywanie zawartości bloków (_resolve_content)
- ❌ **Payload extraction** - ekstrakcja payload (ParagraphLayout, etc.)
- ❌ **Content value extraction** - ekstrakcja wartości content (text, images, etc.)

### 12. Overlays

- ❌ **Overlay rendering** - renderowanie overlay (_draw_overlays)
- ❌ **Overlay images** - obrazy jako overlay
- ❌ **Overlay textboxes** - textboxy jako overlay

### 13. Error Handling

- ❌ **Error placeholders** - placeholdery dla błędów (_draw_error_placeholder)
- ❌ **Error logging** - logowanie błędów renderowania
- ❌ **Fallback rendering** - fallback do prostszych metod renderowania

### 14. Performance Features

- ❌ **Parallel rendering** - równoległe renderowanie (_render_parallel)
- ❌ **Sequential rendering** - sekwencyjne renderowanie (_render_sequential)
- ❌ **Timings** - zbieranie czasów operacji (timings dict)
- ❌ **Page number tracking** - śledzenie numerów stron (start_page_number)

### 15. Inne

- ❌ **Generic block rendering** - renderowanie generycznych bloków (_draw_generic)
- ❌ **Block sorting** - sortowanie bloków (watermarks, headers, body, footnotes, footers)
- ❌ **Page margins** - obsługa marginesów stron
- ❌ **Page size handling** - obsługa różnych rozmiarów stron

---

## 📊 Podsumowanie

### Status implementacji:
- **Podstawowe funkcje**: ~30% ✅
- **Zaawansowane funkcje**: ~5% ✅
- **Brakujące funkcje**: ~95% ❌

### Priorytet implementacji:

#### Wysoki priorytet (krytyczne dla podstawowej funkcjonalności):
1. **Image loading** - bez tego obrazy nie będą renderowane
2. **Multi-line text** - bez tego tekst nie będzie prawidłowo wyświetlany
3. **Text wrapping** - bez tego tekst nie będzie zawijany
4. **Cell content rendering** - bez tego tabele nie będą miały tekstu
5. **Font loading (TTF/OTF)** - bez tego niestandardowe fonty nie będą działać

#### Średni priorytet (ważne dla jakości):
6. **ParagraphLayout rendering** - lepsze renderowanie paragrafów
7. **Text runs** - różne style w jednej linii
8. **Cell colspan/rowspan** - zaawansowane tabele
9. **Border styles** - lepsze obramowania
10. **Shadow rendering** - efekty wizualne

#### Niski priorytet (nice to have):
11. **Watermarks** - znaki wodne
12. **Footnotes/Endnotes** - przypisy
13. **Inline images** - obrazy w tekście
14. **Hyperlinks** - linki w tekście
15. **Parallel rendering** - optymalizacja wydajności

---

## 🔧 Następne kroki

1. **Implementacja Image loading** - użyj biblioteki `image` do ładowania PNG/JPEG
2. **Implementacja Multi-line text** - dodaj logikę zawijania tekstu
3. **Implementacja Font loading** - użyj `ttf-parser` do parsowania TTF/OTF
4. **Implementacja ParagraphLayout** - dodaj wsparcie dla ParagraphLayout payload
5. **Implementacja Cell content** - dodaj renderowanie paragrafów w komórkach

