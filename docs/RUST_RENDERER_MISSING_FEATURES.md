# Brakujące funkcjonalności w Rust PDF Renderer

## 📋 Porównanie z Python Rendererem (ReportLab)

### ✅ Zaimplementowane w Rust

1. **Paragrafy** (`paragraph`)
   - ✅ Renderowanie z pre-calculated `ParagraphLayout`
   - ✅ Multi-line text z wrappingiem
   - ✅ Text alignment (left, center, right, justify)
   - ✅ Font loading (podstawowe)
   - ✅ Kolor tekstu
   - ✅ Rozmiar czcionki

2. **Tabele** (`table`)
   - ✅ Renderowanie komórek
   - ✅ Colspan/rowspan (merged cells)
   - ✅ Cell borders
   - ✅ Cell backgrounds
   - ✅ Cell margins
   - ✅ Paragraphs w komórkach

3. **Obrazy** (`image`)
   - ✅ Ładowanie PNG/JPEG
   - ✅ Skalowanie z zachowaniem proporcji
   - ✅ Pozycjonowanie
   - ✅ Placeholder przy błędzie

4. **Textboxy** (`textbox`)
   - ✅ Podstawowe renderowanie
   - ✅ Paragraphs w textboxach

5. **Style i dekoracje**
   - ✅ Background colors
   - ✅ Borders (solid, dashed, dotted, double)
   - ✅ Rounded rectangles
   - ✅ Shadows
   - ✅ Padding

### ❌ Brakujące funkcjonalności

#### 1. **Watermarks (Znaki wodne)** 🔴 WYSOKI PRIORYTET
- **Status**: Wykrywane, ale nie renderowane specjalnie
- **Python**: `_draw_watermark()` - pełna obsługa z rotacją, przezroczystością
- **Potrzebne**:
  - Renderowanie watermarks jako pierwsze (pod wszystkimi elementami)
  - Rotacja tekstu/obrazu (zwykle 45°)
  - Przezroczystość (opacity)
  - Pozycjonowanie na środku strony
  - Obsługa VML shapes jako watermarks

#### 2. **Headers i Footers** 🔴 WYSOKI PRIORYTET
- **Status**: Wykrywane (`header_blocks`, `footer_blocks`), ale renderowane jak zwykłe bloki
- **Python**: `_draw_header()`, `_draw_footer()` - specjalne renderowanie
- **Potrzebne**:
  - Renderowanie na każdej stronie (jeśli zdefiniowane)
  - Obsługa różnych headers/footers dla różnych sekcji
  - Pozycjonowanie względem marginesów strony
  - Pomijanie na pierwszej stronie (jeśli ustawione)

#### 3. **Footnotes i Endnotes** 🟡 ŚREDNI PRIORYTET
- **Status**: Wykrywane (`footnote_blocks`), ale nie renderowane
- **Python**: `_draw_footnotes()`, `_draw_endnotes()` - pełna obsługa
- **Potrzebne**:
  - Renderowanie separator line nad footnotes
  - Numeracja footnotes
  - Wyrównanie tekstu z numerem
  - Automatyczne łamanie linii
  - Pozycjonowanie na dole strony

#### 4. **Overlays (Nakładki)** 🟡 ŚREDNI PRIORYTET
- **Status**: Brak implementacji
- **Python**: `_draw_overlays()` - renderowanie nakładek
- **Potrzebne**:
  - Renderowanie overlay images
  - Renderowanie overlay textboxes
  - Pozycjonowanie absolutne
  - Obsługa w headerach/footerach

#### 5. **Pełne TTF/OTF Font Embedding** 🔴 WYSOKI PRIORYTET
- **Status**: Tylko walidacja fontów, brak embeddingu
- **Python**: Pełne embedowanie fontów TTF/OTF
- **Potrzebne**:
  - Implementacja `add_truetype_font()` w `font_utils.rs`
  - Embedowanie fontów do PDF
  - Subsetting fontów (tylko używane znaki)
  - Obsługa różnych wag fontów (bold, italic, bold-italic)

#### 6. **Inline Images w tekście** 🟡 ŚREDNI PRIORYTET
- **Status**: TODO w kodzie
- **Python**: Pełna obsługa inline images w ParagraphLayout
- **Potrzebne**:
  - Renderowanie obrazów jako inline items w liniach tekstu
  - Pozycjonowanie względem baseline
  - Skalowanie z zachowaniem proporcji

#### 7. **Inline Textboxes w tekście** 🟢 NISKI PRIORYTET
- **Status**: TODO w kodzie
- **Python**: Obsługa inline textboxes
- **Potrzebne**:
  - Renderowanie textboxów jako inline items
  - Pozycjonowanie w linii tekstu

#### 8. **Zaawansowane style tekstu** 🟡 ŚREDNI PRIORYTET
- **Status**: Podstawowe style (bold, italic)
- **Python**: Pełna obsługa wszystkich stylów
- **Potrzebne**:
  - Underline (podkreślenie)
  - Strikethrough (przekreślenie)
  - Superscript/Subscript (indeksy)
  - Text effects (shadow, outline)

#### 9. **Zaawansowane style borders** 🟢 NISKI PRIORYTET
- **Status**: Podstawowe style (solid, dashed, dotted, double)
- **Python**: Więcej opcji
- **Potrzebne**:
  - Różne szerokości dla każdej strony bordera
  - Różne kolory dla każdej strony bordera
  - 3D borders
  - Gradient borders

#### 10. **Zaawansowane tła** 🟢 NISKI PRIORYTET
- **Status**: Tylko solid colors
- **Python**: Gradient backgrounds
- **Potrzebne**:
  - Gradient fills (linear, radial)
  - Pattern fills
  - Image backgrounds

#### 11. **Hyperlinks** 🟡 ŚREDNI PRIORYTET
- **Status**: Brak implementacji
- **Python**: Obsługa linków w tekście
- **Potrzebne**:
  - Linki URL
  - Linki wewnętrzne (do innych stron w PDF)
  - Linki do zakładek (bookmarks)

#### 12. **Bookmarks (Zakładki)** 🟢 NISKI PRIORYTET
- **Status**: Brak implementacji
- **Python**: Generowanie zakładek PDF
- **Potrzebne**:
  - Hierarchiczna struktura zakładek
  - Linki do stron

## 🎯 Rekomendowany plan implementacji

### Faza 1: Krytyczne funkcjonalności (1-2 tygodnie)
1. **Watermarks** - potrzebne dla dokumentów firmowych
2. **Headers/Footers** - podstawowa funkcjonalność dokumentów
3. **TTF/OTF Font Embedding** - poprawa jakości tekstu

### Faza 2: Ważne funkcjonalności (2-3 tygodnie)
4. **Footnotes/Endnotes** - potrzebne dla dokumentów akademickich
5. **Overlays** - potrzebne dla złożonych layoutów
6. **Inline Images** - poprawa jakości dokumentów z obrazami

### Faza 3: Ulepszenia (1-2 tygodnie)
7. **Zaawansowane style tekstu** - underline, strikethrough
8. **Hyperlinks** - interaktywność PDF
9. **Inline Textboxes** - zaawansowane layouty

### Faza 4: Opcjonalne (według potrzeb)
10. **Zaawansowane borders i tła** - gradienty, wzory
11. **Bookmarks** - nawigacja w PDF

## 📝 Uwagi techniczne

### Watermarks
- Renderować jako pierwsze (najniższa warstwa)
- Używać `canvas.save_state()` i `canvas.restore_state()` dla transformacji
- Implementować rotację przez `canvas.transform()`

### Headers/Footers
- Renderować przed/po body blocks
- Sprawdzać `skip_headers_footers` na stronie
- Obsługiwać różne headers/footers dla różnych sekcji

### Font Embedding
- Użyć `pdf-writer` API do embedowania fontów
- Rozważyć użycie biblioteki pomocniczej (np. `printpdf` jako referencja)
- Implementować subsetting dla mniejszych plików PDF

### Footnotes
- Renderować na dole strony przed footerami
- Obliczać dostępną przestrzeń dynamicznie
- Obsługiwać overflow (przenoszenie na następną stronę)

## 🔗 Powiązane pliki

- `pdf_renderer_rust/src/renderer.rs` - główny kod renderera
- `pdf_renderer_rust/src/font_utils.rs` - funkcje fontów (TODO: embedding)
- `pdf_renderer_rust/src/canvas.rs` - canvas API
- `docx_interpreter/engine/pdf/pdf_compiler.py` - Python renderer (referencja)

