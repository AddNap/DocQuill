# 📋 Brakujące Funkcje w Rendererach

## Analiza stanu rendererów - co jest sparsowane, ale nie renderowane

**Data analizy:** 2025-01-XX  
**Wersja:** DocQuill 2.0

---

## 🔍 Metodologia

Przeanalizowano:
- ✅ Modele w `docx_interpreter/models/` - co jest sparsowane
- ✅ Parsery w `docx_interpreter/parser/` - co jest parsowane
- ❌ Renderery w `docx_interpreter/renderers/` - co jest renderowane

---

## 📊 Podsumowanie

| Kategoria | Sparsowane | Renderowane HTML | Renderowane PDF | Status |
|----------|-----------|------------------|-----------------|--------|
| **Paragrafy** | ✅ | ✅ | ✅ | ✅ Pełna obsługa |
| **Tabele** | ✅ | ✅ | ⚠️ Podstawowe | ⚠️ Częściowo |
| **Obrazy** | ✅ | ✅ | ⚠️ Inline tylko | ⚠️ Częściowo |
| **Listy** | ✅ | ✅ | ✅ | ✅ Pełna obsługa |
| **Footnotes** | ✅ | ❌ | ❌ | ❌ Brak |
| **Endnotes** | ✅ | ❌ | ❌ | ❌ Brak |
| **Comments** | ✅ | ❌ | ❌ | ❌ Brak |
| **Fields** | ✅ | ❌ | ❌ | ❌ Brak |
| **Hyperlinks** | ✅ | ⚠️ Częściowo | ⚠️ Częściowo | ⚠️ Częściowo |
| **Bookmarks** | ✅ | ❌ | ❌ | ❌ Brak |
| **SmartArt** | ✅ | ❌ | ❌ | ❌ Brak |
| **Watermarks** | ⚠️ Częściowo | ❌ | ❌ | ❌ Brak |
| **Track Changes** | ⚠️ Częściowo | ❌ | ❌ | ❌ Brak |

---

## ❌ HTML Renderer - Brakujące Funkcje

### 1. Footnotes i Endnotes 🔴 WYSOKI PRIORYTET

**Status:** Model istnieje (`models/footnote.py`), parser istnieje (`parser/notes_parser.py`), **brak renderowania**

**Brakujące funkcje:**
- ❌ Renderowanie przypisów dolnych na końcu strony/sekcji
- ❌ Renderowanie przypisów końcowych na końcu dokumentu
- ❌ Linki do przypisów w tekście (superskrypty z numerami)
- ❌ Separatory przypisów
- ❌ Kontynuacja przypisów na następnej stronie

**Przykład użycia:**
```python
# Model istnieje:
footnote = Footnote(footnote_id="1", content="To jest przypis")

# Parser istnieje:
notes_parser = NotesParser(package_reader)
footnotes = notes_parser.parse_footnotes()

# Renderer NIE ISTNIEJE:
# HTMLRenderer powinien mieć:
# def _render_footnote(self, footnote: Footnote) -> str
# def _render_footnote_reference(self, footnote_id: str) -> str
```

---

### 2. Comments (Komentarze) 🟡 ŚREDNI PRIORYTET

**Status:** Model istnieje (`models/comment.py`), **brak renderowania**

**Brakujące funkcje:**
- ❌ Renderowanie komentarzy jako tooltip/popup
- ❌ Wizualizacja zakresu komentarza w tekście
- ❌ Panel komentarzy obok dokumentu
- ❌ Autor i data komentarza

**Model:**
```python
class Comment(Models):
    comment_id: str
    author: str
    date: datetime
    content: str
    range_start: int
    range_end: int
```

---

### 3. Fields (Pola) 🔴 WYSOKI PRIORYTET

**Status:** Model istnieje (`models/field.py`), **brak renderowania**

**Brakujące funkcje:**
- ❌ Renderowanie kodów pola (PAGE, NUMPAGES, DATE, TIME)
- ❌ Renderowanie pól formularzy
- ❌ Renderowanie pól równań
- ❌ Renderowanie TOC (Table of Contents)
- ❌ Renderowanie cross-references (REF)

**Obsługiwane typy pól:**
- `PAGE` - numer strony
- `NUMPAGES` - całkowita liczba stron
- `DATE` - data
- `TIME` - czas
- `REF` - odwołanie krzyżowe
- `TOC` - spis treści
- `AUTHOR` - autor dokumentu
- `TITLE` - tytuł dokumentu

**Model:**
```python
class Field(Models):
    instr: str  # "PAGE", "DATE", "REF bookmark"
    value: str  # Wynik pola
    field_type: str
```

---

### 4. Hyperlinks (Hiperłącza) ⚠️ CZĘŚCIOWO

**Status:** Model istnieje (`models/hyperlink.py`), **częściowa obsługa**

**Zaimplementowane:**
- ✅ Podstawowe hiperłącza w PDF (TextRenderer)

**Brakujące:**
- ❌ Pełna obsługa w HTML (bookmark links, cross-references)
- ❌ Tooltip dla hiperłączy
- ❌ Wizualizacja visited/unvisited links
- ❌ Anchor links (bookmarks)

---

### 5. Bookmarks (Zakładki) 🟡 ŚREDNI PRIORYTET

**Status:** Model istnieje (`models/bookmark.py`), **brak renderowania**

**Brakujące funkcje:**
- ❌ Renderowanie zakładek jako anchorów HTML (`<a name="bookmark">`)
- ❌ Linki do zakładek (`<a href="#bookmark">`)
- ❌ Panel nawigacji z zakładkami

---

### 6. Track Changes (Śledzenie zmian) 🟡 ŚREDNI PRIORYTET

**Status:** Częściowo sparsowane, **brak renderowania**

**Brakujące funkcje:**
- ❌ Wizualizacja wstawionych fragmentów (podkreślenie)
- ❌ Wizualizacja usuniętych fragmentów (przekreślenie)
- ❌ Panel zmian z autorami i datami
- ❌ Akceptacja/odrzucenie zmian

---

### 7. Watermarks (Znaki wodne) 🟡 ŚREDNI PRIORYTET

**Status:** Częściowo sparsowane, **brak renderowania**

**Brakujące funkcje:**
- ❌ Renderowanie znaków wodnych jako tła
- ❌ Pozycjonowanie znaków wodnych (poziomo/pionowo)
- ❌ Przezroczystość znaków wodnych
- ❌ Obrót znaków wodnych

---

### 8. SmartArt i Diagramy 🟢 NISKI PRIORYTET

**Status:** Model istnieje (`models/smartart.py`), **brak renderowania**

**Brakujące funkcje:**
- ❌ Renderowanie SmartArt jako SVG/Canvas
- ❌ Konwersja SmartArt do obrazów
- ❌ Renderowanie diagramów

---

### 9. Zaawansowane Formatowanie Tekstu 🟡 ŚREDNI PRIORYTET

**Status:** Częściowo zaimplementowane

**Zaimplementowane:**
- ✅ Bold, italic, underline
- ✅ Kolory tekstu
- ✅ Rozmiary czcionek
- ✅ Nazwy czcionek

**Brakujące:**
- ❌ Double strikethrough
- ❌ Emboss / Engrave effects
- ❌ Outline text
- ❌ Shadow effects dla tekstu
- ❌ Small caps
- ❌ All caps

---

## ❌ PDF Renderer - Brakujące Funkcje

### 1. Renderowanie Tabel (Zaawansowane) 🔴 WYSOKI PRIORYTET

**Status:** Podstawowe renderowanie istnieje, **brak zaawansowanych funkcji**

**Brakujące funkcje:**
- ❌ Auto-fit column widths (obliczanie szerokości kolumn)
- ❌ Dynamiczne obliczanie wysokości wierszy
- ❌ Cell padding
- ❌ Merged cells (colspan/rowspan)
- ❌ Zaawansowane style obramowań komórek
- ❌ Tabele w headerach/footerach
- ❌ Tabele z podwójnymi obramowaniami

**Metody do zaimplementowania:**
```python
def _calculate_table_column_widths(self, table, available_width) -> List[float]
def _calculate_table_row_heights(self, table, column_widths) -> List[float]
def _calculate_cell_content_height(self, cell, cell_width) -> float
def _render_cell_content(self, cell, x, y, width, height)
def _render_merged_cell(self, cell, x, y, width, height, colspan, rowspan)
```

---

### 2. Renderowanie Obrazów (Zaawansowane) 🔴 WYSOKI PRIORYTET

**Status:** Podstawowe renderowanie inline istnieje, **brak floating images**

**Brakujące funkcje:**
- ❌ Floating/anchored images (obrazy zakotwiczone)
- ❌ Konwersja EMF/WMF do PNG
- ❌ Image caching jako XObject (dla wydajności)
- ❌ Obrazy w headerach/footerach
- ❌ Obrazy z tekstem dookoła (text wrapping)

**Metody do zaimplementowania:**
```python
def _render_image_anchored(self, image, x, y, available_width, available_height)
def _get_image_data_with_conversion(self, image_path) -> bytes
def _get_cached_image_xobject(self, image_path) -> XObject
def _compute_anchored_image_bbox(self, image, page_width, page_height) -> Rect
```

---

### 3. Headers i Footers (Zaawansowane) 🟡 ŚREDNI PRIORYTET

**Status:** Podstawowe renderowanie istnieje, **brak field codes**

**Brakujące funkcje:**
- ❌ Field code replacement (PAGE, NUMPAGES, DATE, TIME)
- ❌ Textboxy w headerach/footerach
- ❌ Obrazy w headerach/footerach
- ❌ Collision detection (zapobieganie nakładaniu się)
- ❌ Różne headery/footery dla pierwszej strony

**Metody do zaimplementowania:**
```python
def _replace_field_codes(self, text: str, page_num: int, total_pages: int) -> str
def _render_textbox_in_header(self, textbox, header_rect)
def _render_textbox_in_footer(self, textbox, footer_rect)
def _check_collision(self, element1, element2) -> bool
```

---

### 4. Dekoracje Paragrafów (Zaawansowane) 🟡 ŚREDNI PRIORYTET

**Status:** Podstawowe dekoracje istnieją, **brak pełnych block decorations**

**Brakujące funkcje:**
- ❌ Pełne block decorations (borders, background, shadows)
- ❌ Zaawansowane style obramowań (różne style dla każdej strony)
- ❌ Gradient backgrounds
- ❌ Pattern fills

**Metody do zaimplementowania:**
```python
def _render_paragraph_block_decorations(self, paragraph, frame, style)
def _borders_are_identical(self, border1, border2) -> bool
def _analyze_style_alignments(self, styles) -> Dict
```

---

### 5. Paginacja (Zaawansowana) 🔴 WYSOKI PRIORYTET

**Status:** Podstawowa paginacja istnieje, **brak dry-run i szacowań**

**Brakujące funkcje:**
- ❌ Dry-run renderowanie (obliczanie liczby stron bez renderowania)
- ❌ Dynamiczne tworzenie nowych stron
- ❌ Szacowanie wysokości paragrafów
- ❌ Szacowanie wysokości tabel
- ❌ Optymalizacja podziału stron (unikanie orphan lines)

**Metody do zaimplementowania:**
```python
def _dry_run_render(self, document) -> int  # Zwraca liczbę stron
def _calculate_total_pages(self, document) -> int
def _estimate_paragraph_height(self, paragraph, available_width) -> float
def _estimate_paragraph_height_accurate(self, paragraph, available_width) -> float
def _estimate_table_height(self, table, available_width) -> float
```

---

### 6. Footnotes i Endnotes 🔴 WYSOKI PRIORYTET

**Status:** Model i parser istnieją, **brak renderowania**

**Brakujące funkcje:**
- ❌ Renderowanie przypisów dolnych na dole strony
- ❌ Renderowanie przypisów końcowych na końcu dokumentu
- ❌ Linki do przypisów (superskrypty)
- ❌ Separatory przypisów
- ❌ Kontynuacja przypisów na następnej stronie

---

### 7. Watermarks 🟡 ŚREDNI PRIORYTET

**Status:** Częściowo sparsowane, **brak renderowania**

**Brakujące funkcje:**
- ❌ Renderowanie znaków wodnych jako tła PDF
- ❌ Pozycjonowanie znaków wodnych
- ❌ Przezroczystość znaków wodnych
- ❌ Obrót znaków wodnych

---

## 📈 Priorytety Implementacji

### 🔴 WYSOKI PRIORYTET (Krytyczne dla podstawowej funkcjonalności)

1. **Footnotes/Endnotes** - Model i parser istnieją, brakuje tylko renderowania
2. **Field codes** - PAGE, NUMPAGES, DATE - krytyczne dla headerów/footerów
3. **Floating images** - Często używane w dokumentach
4. **Paginacja (dry-run)** - Potrzebne do poprawnego renderowania
5. **Zaawansowane tabele** - Auto-fit, merged cells

### 🟡 ŚREDNI PRIORYTET (Ważne dla pełnej funkcjonalności)

6. **Track Changes** - Ważne dla dokumentów biznesowych
7. **Comments** - Ważne dla współpracy
8. **Watermarks** - Często używane w dokumentach oficjalnych
9. **Bookmarks** - Ułatwiają nawigację
10. **Zaawansowane formatowanie** - Double strikethrough, effects

### 🟢 NISKI PRIORYTET (Nice to have)

11. **SmartArt** - Rzadko używane, można konwertować do obrazów
12. **OLE objects** - Bardzo rzadko używane
13. **Advanced effects** - Emboss, Engrave - rzadko używane

---

## 📝 Uwagi Techniczne

### Modele już istniejące (gotowe do użycia):
- ✅ `models/footnote.py` - Footnote, Endnote
- ✅ `models/comment.py` - Comment
- ✅ `models/field.py` - Field
- ✅ `models/bookmark.py` - Bookmark
- ✅ `models/hyperlink.py` - Hyperlink
- ✅ `models/smartart.py` - SmartArt

### Parsery już istniejące:
- ✅ `parser/notes_parser.py` - NotesParser (footnotes/endnotes)
- ✅ `parser/header_footer_parser.py` - HeaderFooterParser
- ✅ `parser/drawing_parser.py` - DrawingParser (obrazy)

### Co trzeba zrobić:
1. Dodać metody renderowania w `HTMLRenderer` i `PDFRenderer`
2. Zintegrować istniejące parsery z rendererami
3. Dodać obsługę field codes w headerach/footerach
4. Zaimplementować floating images w PDF

---

## 🎯 Rekomendacje

1. **Zacząć od Footnotes/Endnotes** - Model i parser już istnieją, tylko renderowanie
2. **Field codes** - Krytyczne dla headerów/footerów
3. **Floating images** - Często używane
4. **Zaawansowane tabele** - Auto-fit i merged cells

---

**Ostatnia aktualizacja:** 2025-01-XX

