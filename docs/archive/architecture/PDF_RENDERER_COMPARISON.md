# Porównanie PDF Rendererów

## Przegląd

Ten dokument porównuje stary renderer PDF (`DirectPDFRenderer`) z nową implementacją (`PDFRenderer`) w projekcie DocQuill 2.0.

---

## 1. Architektura

### Stary Renderer (`DirectPDFRenderer`)
- **Monolityczny**: Wszystko w jednej klasie (~5665 linii kodu)
- **Samowystarczalny**: Wszystkie obliczenia i renderowanie w jednym miejscu
- **Bezpośredni**: Renderuje DOCX → PDF bezpośrednio bez dodatkowych warstw abstrakcji

```python
class DirectPDFRenderer:
    def __init__(self, page_size='A4', ...):
        # Wszystkie komponenty wewnątrz klasy
        self.pdf = None
        self._list_counters = {}
        self._image_cache = {}
        # ...
    
    def render(self, document, output_path):
        # Cała logika renderowania w jednej metodzie
        # + wszystkie metody pomocnicze w tej samej klasie
```

### Nowy Renderer (`PDFRenderer`)
- **Modularny**: Dziedziczy z `BaseRenderer`, używa dedykowanych komponentów
- **Separacja odpowiedzialności**: Renderowanie i obliczenia geometryczne rozdzielone
- **Ekstensywny**: Wykorzystuje istniejącą infrastrukturę projektu

```python
class PDFRenderer(BaseRenderer):
    def __init__(self, document, output_path, render_options):
        super().__init__(document, output_path, render_options)
        
        # Używa dedykowanych silników
        self.position_calculator = PositionCalculator(dpi=96)
        self.pagination_engine = PaginationEngine(...)
        self.table_layout_engine = TableLayoutEngine(...)
        self.text_breaker = PDFTextBreaker(...)
```

**Różnice kluczowe:**
- ✅ Nowy: Rozdzielenie responsywności zgodnie z zasadą Single Responsibility
- ✅ Nowy: Łatwiejsze testowanie poszczególnych komponentów
- ⚠️ Stary: Szybszy development (wszystko w jednym miejscu)
- ⚠️ Stary: Trudniejszy w utrzymaniu przy dużym kodzie

---

## 2. Łamanie Tekstu i Justyfikacja

### Stary Renderer
- **Własna implementacja**: Metoda `_break_paragraph_into_lines()` (linie 1694-2072)
- **Logika wbudowana**: Cała logika łamania linii w klasie renderera
- **Hybrydowe podejście**: Wykorzystuje ReportLab Paragraph dla justification

```python
def _break_paragraph_into_lines(self, paragraph, available_width, 
                               first_line_indent, alignment='left'):
    # ~378 linii kodu łamania tekstu
    # Mapowanie znaków → runs
    # Justification z ReportLab Paragraph
    # Fallback dla innych alignmentów
```

### Nowy Renderer
- **Oddzielny moduł**: Klasa `PDFTextBreaker` w `pdf_text_breaking.py`
- **Reużywalny**: Może być używany przez inne renderery
- **Podobne podejście**: Również używa ReportLab Paragraph dla justification

```python
class PDFTextBreaker:
    def break_paragraph_into_lines(self, paragraph, available_width, 
                                   first_line_indent, alignment='left'):
        # Podobna logika, ale w oddzielnym module
        # Mapowanie char_to_run_map
        # Hybrydowe podejście z ReportLab
```

**Różnice:**
- ✅ Nowy: Kod reużywalny w innych kontekstach
- ✅ Nowy: Łatwiejsze testowanie logiki łamania tekstu
- ⚠️ Oba: Podobna jakość i podejście do justification

---

## 3. Obliczenia Geometryczne i Layout

### Stary Renderer
- **Na bieżąco**: Wszystkie obliczenia podczas renderowania
- **Inline**: Metody pomocnicze w klasie renderera
- **Przykłady metod:**
  - `_estimate_table_height()` - linia 257
  - `_calculate_document_spacing()` - linia 266
  - `_calculate_footer_height_dynamic()` - linia 294
  - `_estimate_paragraph_height()` - linia 2661
  - `_estimate_paragraph_height_accurate()` - linia 2678

```python
def _estimate_table_height(self, table):
    # Obliczenia w klasie renderera
    # Bezpośredni dostęp do self.pdf, self.margin_*
    # Jednoznaczne obliczenia na bieżąco
```

### Nowy Renderer
- **Dedykowane silniki**: Używa `PositionCalculator`, `PaginationEngine`, `TableLayoutEngine`
- **Wcześniejsze obliczenia**: Geometria może być obliczona przed renderowaniem
- **Cache'owanie**: Możliwość cache'owania wyników przez Layout Engine

```python
# W PDFRenderer.__init__
self.position_calculator = PositionCalculator(dpi=96)
self.pagination_engine = PaginationEngine(...)
self.table_layout_engine = TableLayoutEngine(...)

# Użycie
table_height_mm = self.position_calculator.estimate_table_height(item)
para_height_mm = self.position_calculator.estimate_paragraph_height_accurate(...)
```

**Różnice:**
- ✅ Nowy: Możliwość optymalizacji (cache, wielowątkowość)
- ✅ Nowy: Jednolity interfejs dla różnych rendererów (HTML, PDF)
- ⚠️ Stary: Prostsze w debugowaniu (wszystko w jednym miejscu)
- ⚠️ Stary: Mniej overhead (bezpośrednie obliczenia)

---

## 4. Struktura Kodu i Organizacja

### Stary Renderer
```
direct_pdf_renderer.py (5665 linii)
├── TextLine (klasa pomocnicza)
├── DirectPDFRenderer
│   ├── __init__()
│   ├── render()
│   ├── _break_paragraph_into_lines()
│   ├── _render_paragraph()
│   ├── _render_table_universal()
│   ├── _render_image_anchored()
│   ├── _render_image_inline()
│   ├── _render_header()
│   ├── _render_footer()
│   └── ... ~50 innych metod
```

### Nowy Renderer
```
docx_interpreter/renderers/
├── base_renderer.py (BaseRenderer - abstrakcja)
├── pdf_renderer.py (PDFRenderer - główna klasa)
├── pdf_text_breaking.py (PDFTextBreaker - łamanie tekstu)
└── ...

docx_interpreter/Layout_engine/
├── position_calculator.py (PositionCalculator)
├── pagination_engine.py (PaginationEngine)
├── table_layout_engine.py (TableLayoutEngine)
└── layout_helpers.py (LayoutHelpers)
```

**Różnice:**
- ✅ Nowy: Lepsza organizacja, łatwiejsze znalezienie funkcjonalności
- ✅ Nowy: Zgodność z architekturą projektu (innymi rendererami)
- ⚠️ Stary: Wszystko w jednym miejscu (łatwiejsze dla prostych przypadków)

---

## 5. Obsługa Elementów

### Paragrafy

**Stary:**
```python
def _render_paragraph(self, paragraph, next_paragraph=None):
    # ~479 linii kodu
    # Pełna obsługa: indenty, numbering, borders, alignment
    # Wbudowana logika łamania linii
```

**Nowy:**
```python
def _render_paragraph_advanced(self, paragraph, y_position, canvas):
    # Używa PDFTextBreaker do łamania
    # Używa PositionCalculator do obliczeń
    # Prostszy kod, deleguje odpowiedzialności
```

### Tabele

**Stary:**
```python
def _render_table_universal(self, table, x, y, direction='top_to_bottom'):
    # ~445 linii kodu
    # Pełna obsługa: borders, cells, content, alignment
    # Obliczenia szerokości kolumn wbudowane
```

**Nowy:**
```python
def _render_table_basic(self, table, y_position, canvas):
    # Używa TableLayoutEngine do obliczeń
    # Deleguje obliczenia do dedykowanego silnika
```

### Obrazy

**Stary:**
```python
def _render_image_inline(self, image, x, y, skip_page_check=False):
    # ~93 linii
    # Pełna obsługa: inline i anchored images
    # Konwersja formatów (EMF → PNG)
```

**Nowy:**
```python
def _render_image_inline(self, image, x, y, canvas):
    # Podobna logika
    # Wykorzystuje cache i konwertery z projektu
```

**Różnice:**
- ⚠️ Stary: Bardziej szczegółowa implementacja (wiele edge cases)
- ✅ Nowy: Czystszy kod dzięki delegacji
- ⚠️ Potencjalnie: Nowy może mieć mniej funkcji (work in progress)

---

## 6. Obsługa Fontów

### Stary Renderer
```python
def _register_fonts(self):
    # Rejestracja DejaVuSans (wsparcie polskich znaków)
    # Cache fontów: self.font_cache, self._font_cache
    
def _get_font_info(self, run):
    # ~132 linie kodu
    # Pełna obsługa: bold, italic, underline, color, size
```

### Nowy Renderer
```python
def _register_fonts(self):
    # Podobna rejestracja
    # Wykorzystuje istniejące mechanizmy projektu
    
def _get_font_info(self, run):
    # Podobna funkcjonalność
    # Może korzystać z font_manager.py z projektu
```

**Różnice:**
- ⚠️ Podobna funkcjonalność
- ✅ Nowy: Może korzystać z centralnego zarządzania fontami

---

## 7. Headers i Footers

### Stary Renderer
```python
def _render_header(self):
    # ~138 linii
    # Pełna obsługa: tekst, tabele, textboxy, obrazy
    
def _render_footer(self):
    # ~399 linii
    # Pełna obsługa z tabelami w footerze
```

### Nowy Renderer
```python
def _render_header(self, canvas, document):
    # Uproszczona implementacja
    # Używa istniejących metod renderowania
    
def _render_footer(self, canvas, document):
    # Podobnie
```

**Różnice:**
- ⚠️ Stary: Bardziej szczegółowa implementacja
- ✅ Nowy: Kod bardziej zwięzły
- ⚠️ Potencjalnie: Stary może mieć więcej funkcji

---

## 8. Paginacja i Page Breaks

### Stary Renderer
```python
def _dry_run_render(self, document):
    # ~78 linii
    # Pełny dry-run dla obliczenia liczby stron
    
def _new_page(self):
    # Reset pozycji Y, renderowanie header/footer
```

### Nowy Renderer
```python
def _dry_run_render(self, document):
    # ~122 linie
    # Podobna funkcjonalność
    
def _new_page(self, canvas_obj):
    # Podobnie, ale przyjmuje canvas jako parametr
```

**Różnice:**
- ⚠️ Podobna funkcjonalność
- ✅ Nowy: Może korzystać z PaginationEngine do optymalizacji

---

## 9. Interfejs i Użycie

### Stary Renderer
```python
renderer = DirectPDFRenderer(page_size='A4', debug_borders=False)
renderer.render(document, output_path='output.pdf')
```

### Nowy Renderer
```python
renderer = PDFRenderer(document, output_path='output.pdf', 
                      render_options={'page_size': 'A4'})
pdf_bytes = renderer.render(document)
renderer.save_to_file(pdf_bytes, 'output.pdf')
```

**Różnice:**
- ✅ Nowy: Spójny interfejs z innymi rendererami (HTML, Markdown)
- ✅ Nowy: Zwraca bytes (możliwość dalszego przetwarzania)
- ⚠️ Stary: Prostszy dla prostych przypadków użycia

---

## 10. Debugowanie i Opcje

### Stary Renderer
```python
DirectPDFRenderer(
    page_size='A4',
    debug_borders=True,      # Rysuje czerwone ramki
    debug_spaces=True,       # Loguje spacje
    force_justify=False,     # Wymusza justyfikację
    ignore_leading_trailing_spaces=False
)
```

### Nowy Renderer
```python
PDFRenderer(
    document,
    output_path,
    render_options={
        'page_size': 'A4',
        'margins': {...},
        'font_family': 'Helvetica',
        'font_size': 12,
        'line_height': 1.2,
        'include_images': True,
        'image_quality': 95,
        'table_style': 'default'
    }
)
```

**Różnice:**
- ✅ Stary: Bardziej szczegółowe opcje debugowania
- ✅ Nowy: Bardziej rozbudowane opcje renderowania

---

## 11. Obsługa Edge Cases

### Stary Renderer
- **Bardzo szczegółowy**: ~5665 linii sugeruje obsługę wielu edge cases
- **Przykłady:**
  - `_borders_are_identical()` - porównywanie borderów
  - `_check_collision()` - wykrywanie kolizji elementów
  - `_compute_textbox_footer_bbox()` - obliczanie bounding box
  - `_compute_anchored_image_bbox()` - pozycjonowanie anchored images
  - Różne warianty renderowania tabel w footerze

### Nowy Renderer
- **W trakcie rozwoju**: Może mieć mniej edge cases obecnie
- **Lepsza architektura**: Łatwiejsze dodawanie nowych funkcji

**Różnice:**
- ⚠️ Stary: Prawdopodobnie bardziej kompletny obecnie
- ✅ Nowy: Lepsza architektura do rozwoju

---

## 12. Wydajność

### Stary Renderer
- **Bezpośredni**: Mniej overhead, bezpośrednie obliczenia
- **Cache**: Cache obrazów, fontów, heights
- **Dry-run**: Pełny dry-run dla liczby stron

### Nowy Renderer
- **Modularny**: Może być wolniejszy (wiele warstw)
- **Cache**: Wykorzystuje cache z Layout Engine
- **Optymalizacje**: Możliwość równoległego przetwarzania

**Różnice:**
- ⚠️ Stary: Prawdopodobnie szybszy dla prostych dokumentów
- ✅ Nowy: Potencjalnie lepszy dla złożonych dokumentów (cache, optymalizacje)

---

## Podsumowanie

### Kiedy użyć Starego Renderera?
- ✅ Gdy potrzebujesz pełnej funkcjonalności od razu
- ✅ Gdy pracujesz nad prostymi dokumentami
- ✅ Gdy zależy Ci na czasie implementacji

### Kiedy użyć Nowego Renderera?
- ✅ Gdy chcesz zgodności z architekturą projektu
- ✅ Gdy planujesz rozwój i rozszerzenia
- ✅ Gdy potrzebujesz spójnego interfejsu z innymi rendererami
- ✅ Gdy zależy Ci na testowalności i utrzymaniu kodu

### Główne Zalety Starego Renderera
1. **Kompletność**: Pełna implementacja z wieloma edge cases
2. **Prostota**: Wszystko w jednym miejscu
3. **Dojrzałość**: Przetestowany w wielu scenariuszach

### Główne Zalety Nowego Renderera
1. **Architektura**: Modularny, zgodny z resztą projektu
2. **Rozwój**: Łatwiejsze dodawanie nowych funkcji
3. **Testowanie**: Łatwiejsze testowanie komponentów
4. **Reużywalność**: Komponenty mogą być używane przez inne renderery

### Rekomendacja
**Faza przejściowa**: Używać starego renderera dla produkcji, stopniowo migrować funkcjonalności do nowego.

**Długoterminowo**: Nowy renderer jest lepszym wyborem ze względu na architekturę i możliwości rozwoju.

---

## Szczegółowe Porównanie Implementacji

### 1. Widows i Orphans Control

**Stary Renderer** - Bardzo szczegółowa implementacja:
```python
# Linie 1223-1256
if props and hasattr(props, 'numbering_id') and props.numbering_id:
    available_space = self.y - self.margin_bottom
    lines = self._break_paragraph_into_lines(paragraph, ...)
    
    if len(lines) >= 2:
        first_two_lines_height = lines[0].height + lines[1].height
        last_two_lines_height = lines[-2].height + lines[-1].height
        
        # Sprawdza zarówno pierwsze jak i ostatnie 2 linie
        if available_space < first_two_lines_height or available_space < last_two_lines_height:
            self._new_page()
            self._numbered_continuation = True
```

**Nowy Renderer** - Uproszczona implementacja:
```python
# Linie 1878-1897
if props and hasattr(props, 'numbering_id') and props.numbering_id:
    paragraph_height = self._mm_to_pt(paragraph_height_mm)
    available_space = y_position - self.margins['bottom']
    min_height = self.default_font_size * self.line_spacing_multiplier * 2
    
    # Sprawdza tylko czy mieści się minimum 2 linie
    if available_space < min_height and paragraph_height > available_space:
        canvas.showPage()
```

**Różnica**: Stary renderer ma bardziej precyzyjną kontrolę (sprawdza pierwszą i ostatnią linię osobno).

---

### 2. Style Alignment Overrides

**Stary Renderer** - Zaawansowana analiza stylów:
```python
# Linie 174-256: _analyze_style_alignments()
def _analyze_style_alignments(self, document):
    """
    Analizuje wszystkie paragrafy i tworzy mapowanie:
    style_id → najczęstszy alignment (jeśli różni się od domyślnego)
    """
    # Zlicza alignmenty dla każdego stylu
    # Jeśli >50% paragrafów ma inny alignment niż w definicji stylu,
    # tworzy override w _style_alignment_overrides
```

**Nowy Renderer** - Brak takiej funkcjonalności:
```python
# Używa tylko alignment z właściwości paragrafu
alignment = props.alignment if props and hasattr(props, 'alignment') else 'left'
```

**Różnica**: Stary renderer ma zaawansowaną logikę wykrywania domyślnych alignmentów w stylach dokumentu.

---

### 3. Empty Paragraphs Handling

**Stary Renderer** - Bardzo szczegółowa obsługa:
```python
# Linie 1308-1335
if not paragraph.runs or all(not run.text for run in paragraph.runs):
    # Empty paragraph - obsługa różnych przypadków line_spacing
    # auto spacing, exact spacing, itp.
    line_spacing_multiplier = self.line_spacing_multiplier
    if props and hasattr(props, 'line_spacing'):
        if props.line_spacing_rule == 'auto':
            line_spacing_multiplier = props.line_spacing
        elif props.line_spacing_rule == 'exact':
            line_spacing_points = self.twips_to_points(props.line_spacing)
            line_spacing_multiplier = line_spacing_points / font_size
    self.y -= self.default_font_size * line_spacing_multiplier
```

**Nowy Renderer** - Uproszczona obsługa:
```python
# Linie 1912-1920
if not has_text and not has_drawing:
    if props:
        space_after = self._twips_to_points(getattr(props, 'space_after', 0))
        y_position -= max(space_after, self.default_font_size * self.line_spacing_multiplier)
    else:
        y_position -= self.default_font_size * self.line_spacing_multiplier
```

**Różnica**: Stary renderer obsługuje więcej przypadków line_spacing dla pustych paragrafów.

---

### 4. Border Rendering

**Stary Renderer** - Pełna implementacja borders:
```python
# Linie 802-1135: _render_paragraph_block_decorations()
def _render_paragraph_block_decorations(self, block_start_y, block_height, 
                                       left_indent, available_width, props, 
                                       lines_in_block=None, next_paragraph_props=None):
    """
    Renderuje borders, background, shading dla bloku paragrafów.
    Obsługuje różne style borderów, kolory, szerokości.
    """
    # ~333 linie kodu dla borderów
    # Obsługa top, bottom, left, right borders osobno
    # Merging borderów z sąsiednimi paragrafami
```

**Nowy Renderer** - Uproszczona implementacja:
```python
# Linie 2667-2703: _render_paragraph_decorations()
def _render_paragraph_decorations(self, props, start_y, height, 
                                 left_indent, width):
    """
    Podstawowa obsługa dekoracji paragrafu.
    """
    # Podstawowa implementacja borders
```

**Różnica**: Stary renderer ma znacznie bardziej szczegółową obsługę borderów i ich merging.

---

### 5. Table Rendering

**Stary Renderer** - Uniwersalna metoda:
```python
# Linie 4013-4257: _render_table_universal()
def _render_table_universal(self, table, x, y, direction='top_to_bottom'):
    """
    Uniwersalna metoda renderowania tabel - działa w body, header, footer.
    Obsługuje różne kierunki renderowania.
    """
    # ~445 linii kodu
    # Pełna obsługa: cells, borders, content, nested tables
```

**Nowy Renderer** - Podstawowa implementacja:
```python
# Linie 2226-2452: _render_table_basic()
def _render_table_basic(self, table, y_position, canvas):
    """
    Podstawowa implementacja renderowania tabel.
    """
    # Używa TableLayoutEngine do obliczeń
    # Prostsza implementacja
```

**Różnica**: Stary renderer ma bardziej kompletną implementację z obsługą różnych kontekstów.

---

## Lista Funkcjonalności do Migracji

### Wysokiej Priorytet
1. ✅ Style alignment overrides (`_analyze_style_alignments`)
2. ✅ Zaawansowana kontrola widows/orphans
3. ✅ Pełna obsługa borderów paragrafów z merging
4. ✅ Obsługa różnych typów line_spacing dla pustych paragrafów
5. ✅ Uniwersalna metoda renderowania tabel

### Średniej Priorytet
1. ⚠️ Obsługa anchored images w różnych kontekstach
2. ⚠️ Renderowanie textboxów w header/footer
3. ⚠️ Cache'owanie heights tabel
4. ⚠️ Debug mode z debug_borders, debug_spaces

### Niskiej Priorytet
1. ⬜ Opcjonalne: force_justify
2. ⬜ Opcjonalne: ignore_leading_trailing_spaces

---

## Metryki Kodowe

| Metryka | Stary Renderer | Nowy Renderer |
|---------|---------------|---------------|
| **Liczba linii** | ~5665 | ~2770 |
| **Liczba metod** | ~55 | ~25 |
| **Liczba klas** | 2 (TextLine + DirectPDFRenderer) | 1 (PDFRenderer) + współdzielone komponenty |
| **Długość _render_paragraph** | ~479 linii | ~425 linii |
| **Długość _break_paragraph_into_lines** | ~378 linii | ~388 linii (w PDFTextBreaker) |
| **Długość _render_table** | ~445 linii | ~226 linii |

---

## Następne Kroki

1. **Audyt funkcjonalności**: Sprawdzić, które funkcje starego renderera brakują w nowym
2. **Migracja**: Stopniowa migracja najważniejszych funkcji (wysokiej priorytet)
3. **Testy porównawcze**: Testy jakości i wydajności obu rendererów na tym samym dokumencie
4. **Dokumentacja**: Dokumentacja brakujących funkcji w nowym rendererze
5. **Feature parity**: Dążenie do pełnej parzystości funkcjonalnej
