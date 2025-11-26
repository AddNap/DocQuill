# Porównanie funkcjonalności: PDFCompiler (Python/ReportLab) vs PDFCompilerRust

## Status: Rust Renderer NIE JEST GOTOWY do użycia produkcyjnego

### ❌ Krytyczne braki (blokujące użycie produkcyjne)

#### 1. **Numbering / Markery listy** ❌ BRAK
- **PDFCompiler (Python)**: ✅ Pełna obsługa markerów
  - Renderuje markery z `marker.text`, `marker.label`, `marker.display`, `marker.bullet`
  - Obsługuje `marker.suffix` (tab, space, none)
  - Pozycjonowanie markerów (`marker.x`, `marker.baseline_adjust`)
  - Stylowanie markerów (font, size, color)
  - Kod: `pdf_compiler.py:1576-1632`
  
- **PDFCompilerRust**: ❌ **BRAK IMPLEMENTACJI**
  - Komentarz w kodzie: "markers, overlays, justification modules are ready for use" - **NIE PRAWDZIWE**
  - Funkcja `render_paragraph_from_layout` nie obsługuje parametru `marker`
  - Markery nie są renderowane w ogóle

#### 2. **Polskie znaki / Unicode** ❌ NIE DZIAŁA POPRAWNIE
- **PDFCompiler (Python)**: ✅ Pełna obsługa Unicode
  - ReportLab używa UTF-8 natywnie
  - Rejestracja fontów Unicode (DejaVu, Arial)
  - Polskie znaki (ą, ć, ę, ł, ń, ó, ś, ź, ż) działają poprawnie
  - Kod: `pdf_compiler.py` używa `c.drawString()` z UTF-8
  
- **PDFCompilerRust**: ❌ **PROBLEM Z KODOWANIEM**
  - Używa `Str(text.as_bytes())` - konwertuje string na bajty bezpośrednio
  - Standardowe fonty Type1 (Helvetica) nie obsługują Unicode bezpośrednio
  - Potrzebne są fonty CID lub TrueType z Unicode encoding
  - Kod: `canvas.rs:205` - `self.content.show(Str(text.as_bytes()));`
  - **Efekt**: Polskie znaki mogą być wyświetlane jako "?" lub w ogóle nie renderowane

#### 3. **Wyrównania tekstu** ⚠️ CZĘŚCIOWO DZIAŁA
- **PDFCompiler (Python)**: ✅ Pełna obsługa
  - `left`, `center`, `right`, `justify` (both)
  - Zaawansowana justyfikacja z tokenization
  - Weighted space distribution
  - Kod: `pdf_compiler.py:1642-1660`
  
- **PDFCompilerRust**: ⚠️ **PODSTAWOWA IMPLEMENTACJA**
  - Obsługuje `left`, `center`, `right`, `justify`
  - **BRAK** zaawansowanej justyfikacji (tokenization, weighted distribution)
  - Kod: `renderer.rs:1342-1347` - tylko podstawowe przesunięcie X

#### 4. **Tabele** ⚠️ ZAIMPLEMENTOWANE, ALE MOŻE NIE DZIAŁAĆ
- **PDFCompiler (Python)**: ✅ Pełna obsługa
  - Renderowanie komórek z marginesami
  - Obsługa `grid_span` (colspan) i `vertical_merge_type` (rowspan)
  - Renderowanie paragrafów w komórkach z markerami
  - Obsługa stylów komórek (background, borders)
  - Kod: `pdf_compiler.py:_render_cell_paragraphs()`
  
- **PDFCompilerRust**: ⚠️ **ZAIMPLEMENTOWANE, ALE NIE TESTOWANE**
  - Funkcja `render_table()` istnieje (`renderer.rs:412`)
  - Obsługuje `grid_span` i `vertical_merge_type`
  - Renderuje komórki z paragrafami
  - **BRAK** obsługi markerów w komórkach tabeli
  - **NIE TESTOWANE** na rzeczywistych dokumentach

#### 5. **Nagłówki i stopki** ⚠️ ZAIMPLEMENTOWANE, ALE MOŻE NIE DZIAŁAĆ
- **PDFCompiler (Python)**: ✅ Pełna obsługa
  - Renderowanie headerów/footerów na każdej stronie
  - Obsługa field codes (PAGE, NUMPAGES)
  - Renderowanie obrazów w headerach
  - Renderowanie paragrafów z markerami
  - Kod: `pdf_compiler.py:_render_header()`, `_render_footer()`
  
- **PDFCompilerRust**: ⚠️ **ZAIMPLEMENTOWANE, ALE NIE TESTOWANE**
  - Funkcje `render_header()` i `render_footer()` istnieją (`renderer.rs:913, 988`)
  - Renderują tekst i obrazy
  - **BRAK** obsługi markerów w headerach/footerach
  - **NIE TESTOWANE** na rzeczywistych dokumentach

#### 6. **Obrazy** ⚠️ ZAIMPLEMENTOWANE, ALE MOŻE NIE DZIAŁAĆ
- **PDFCompiler (Python)**: ✅ Pełna obsługa
  - Rozwiązywanie ścieżek obrazów (relationship_id, part_path)
  - Konwersja WMF/EMF do PNG (preconversion)
  - Renderowanie inline images w paragrafach
  - Renderowanie overlay images
  - Obsługa `image_cache` dla prekonwertowanych obrazów
  - Kod: `pdf_compiler.py:_resolve_image_path()`, `_draw_overlays()`
  
- **PDFCompilerRust**: ⚠️ **ZAIMPLEMENTOWANE, ALE NIE TESTOWANE**
  - Funkcja `render_image()` istnieje (`renderer.rs:623`)
  - Obsługuje ścieżki obrazów i cached image references
  - **BRAK** obsługi inline images w paragrafach
  - **BRAK** obsługi overlay images
  - **NIE TESTOWANE** na rzeczywistych dokumentach

---

## ✅ Co działa w Rust Rendererze

1. **Podstawowe paragrafy** ✅
   - Renderowanie tekstu z różnymi fontami i rozmiarami
   - Podstawowe kolory tekstu
   - Podstawowe wyrównania (left, center, right)

2. **Dekoratory** ✅
   - Renderowanie prostokątów, linii, tła

3. **Watermarki** ✅
   - Renderowanie z rotacją i przezroczystością

4. **Footnotes/Endnotes** ⚠️ Częściowo
   - Funkcje istnieją, ale nie testowane

---

## 📊 Podsumowanie

| Funkcjonalność | PDFCompiler (Python) | PDFCompilerRust | Status |
|----------------|----------------------|-----------------|--------|
| **Paragrafy podstawowe** | ✅ | ✅ | OK |
| **Numbering / Markery** | ✅ | ❌ | **BRAK** |
| **Polskie znaki / Unicode** | ✅ | ❌ | **NIE DZIAŁA** |
| **Wyrównania (zaawansowane)** | ✅ | ⚠️ | **PODSTAWOWE** |
| **Tabele** | ✅ | ⚠️ | **NIE TESTOWANE** |
| **Nagłówki** | ✅ | ⚠️ | **NIE TESTOWANE** |
| **Stopki** | ✅ | ⚠️ | **NIE TESTOWANE** |
| **Obrazy** | ✅ | ⚠️ | **NIE TESTOWANE** |
| **Dekoratory** | ✅ | ✅ | OK |
| **Watermarki** | ✅ | ✅ | OK |

---

## 🔧 Co trzeba naprawić w Rust Rendererze

### Priorytet 1 (KRYTYCZNE - blokujące użycie):
1. **Numbering / Markery** ❌
   - Dodać obsługę parametru `marker` w `render_paragraph_from_layout`
   - Renderować markery przed tekstem paragrafu
   - Obsługiwać `marker.text`, `marker.x`, `marker.baseline_adjust`, `marker.suffix`

2. **Polskie znaki / Unicode** ❌
   - Zmienić kodowanie z `Str(text.as_bytes())` na Unicode-aware encoding
   - Użyć fontów CID lub TrueType z Unicode support
   - Lub użyć `/ToUnicode` CMap dla standardowych fontów

### Priorytet 2 (WAŻNE - brakuje funkcjonalności):
3. **Zaawansowana justyfikacja** ⚠️
   - Dodać tokenization tekstu
   - Dodać weighted space distribution
   - Obsługiwać NBSP (non-breaking spaces)

4. **Tabele - testowanie** ⚠️
   - Przetestować na rzeczywistych dokumentach
   - Dodać obsługę markerów w komórkach tabeli

5. **Nagłówki/Stopki - testowanie** ⚠️
   - Przetestować na rzeczywistych dokumentach
   - Dodać obsługę markerów w headerach/footerach

6. **Obrazy - rozszerzenie** ⚠️
   - Dodać obsługę inline images w paragrafach
   - Dodać obsługę overlay images

---

## 📝 Uwagi techniczne

### Problem z Unicode w Rust Rendererze

Kod w `canvas.rs:205`:
```rust
pub fn draw_string(&mut self, x: f64, y: f64, text: &str) {
    self.content.begin_text();
    self.content.set_font(self.state.font_name, self.state.font_size as f32);
    self.content.next_line(x as f32, y as f32);
    self.content.show(Str(text.as_bytes()));  // ❌ PROBLEM: bezpośrednia konwersja na bajty
    self.content.end_text();
}
```

**Problem**: Standardowe fonty Type1 (Helvetica, Arial) w PDF używają encoding `StandardEncoding` lub `WinAnsiEncoding`, które nie obsługują pełnego Unicode. Polskie znaki (ą, ć, ę, ł, ń, ó, ś, ź, ż) nie są w tych encodingach.

**Rozwiązanie**: 
- Użyć fontów CID z Unicode CMap
- Lub użyć TrueType fontów z Unicode support
- Lub dodać `/ToUnicode` CMap do standardowych fontów

### Problem z markerami

Kod w `renderer.rs:1152` - funkcja `render_paragraph_from_layout`:
- **BRAK** parametru `marker`
- **BRAK** kodu renderującego markery przed tekstem

**Rozwiązanie**: Dodać obsługę markerów podobnie jak w `pdf_compiler.py:1576-1632`.

---

## ✅ Wniosek

**Rust Renderer NIE JEST GOTOWY do użycia produkcyjnego** z powodu:
1. ❌ Brak obsługi markerów/numbering
2. ❌ Niepoprawne renderowanie polskich znaków
3. ⚠️ Brak testów na rzeczywistych dokumentach dla tabel, headerów, footerów, obrazów

**Rekomendacja**: 
- Naprawić krytyczne problemy (markery, Unicode) przed użyciem produkcyjnym
- Przetestować wszystkie funkcjonalności na rzeczywistych dokumentach
- Porównać wyniki z PDFCompiler (Python) dla każdego typu bloku
