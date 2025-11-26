# Plan Migracji Renderera PDF do Rusta

## 🎯 Cel

Przeniesienie tylko **renderowania PDF** (najcięższej części) do Rusta, zachowując resztę projektu w Pythonie.

## 📊 Obecna Architektura

### Obecny Stack Renderowania
- **ReportLab Canvas** - główny interfejs renderowania
- **Python** - cała logika renderowania
- **Operacje Canvas używane**:
  - `canvas.rect()` - prostokąty (tło, ramki)
  - `canvas.roundRect()` - zaokrąglone prostokąty
  - `canvas.line()` - linie (borders)
  - `canvas.drawImage()` - obrazy
  - `canvas.drawString()` - tekst prosty
  - `canvas.saveState()` / `canvas.restoreState()` - stan grafiki
  - `canvas.setFillColor()` / `canvas.setStrokeColor()` - kolory
  - `canvas.setLineWidth()` / `canvas.setDash()` - style linii
  - `canvas.translate()` - transformacje
  - `canvas.setFont()` - fonty

### Główne Komponenty Renderowania

1. **PDFCompiler** (`docx_interpreter/engine/pdf/pdf_compiler.py`)
   - Główna klasa renderująca UnifiedLayout → PDF
   - ~4300 linii kodu
   - Używa ReportLab Canvas

2. **Metody Renderowania**:
   - `_render_page()` - renderuje pojedynczą stronę
   - `_draw_paragraph()` - renderuje paragrafy tekstu
   - `_draw_table()` - renderuje tabele
   - `_draw_image()` - renderuje obrazy
   - `_draw_textbox()` - renderuje textboxy
   - `_draw_decorator()` - renderuje dekoracje
   - `_draw_watermark()` - renderuje watermarks
   - `_draw_footnotes()` / `_draw_endnotes()` - renderuje notatki

3. **Helpery** (`docx_interpreter/renderers/render_utils.py`):
   - `draw_background()` - tło
   - `draw_border()` - ramki
   - `draw_shadow()` - cienie
   - `to_color()` - konwersja kolorów

## 🦀 Biblioteka Rust: `pdf-writer` ⭐

### Wybór: `pdf-writer`
- **GitHub**: https://github.com/typst/pdf-writer
- **Crates.io**: https://crates.io/crates/pdf-writer
- **Status**: Aktywnie rozwijane przez zespół Typst
- **Użycie**: Używane w produkcyjnym projekcie Typst (profesjonalny typesetter)

### Funkcje `pdf-writer`
- ✅ Niskopoziomowe generowanie PDF (pełna kontrola)
- ✅ Bardzo szybkie (używane przez Typst w produkcji)
- ✅ Obsługa wszystkich operacji PDF (tekst, grafika, obrazy, fonty)
- ✅ Bezpieczne API (Rust type system)
- ✅ Minimalne zależności
- ✅ Dobrze przetestowane (używane przez Typst)

### Zalety `pdf-writer`
- ✅ **Wydajność**: Najszybsza opcja (używana przez Typst)
- ✅ **Kontrola**: Pełna kontrola nad generowaniem PDF
- ✅ **Stabilność**: Sprawdzona w produkcyjnym projekcie
- ✅ **Jakość**: Generuje wysokiej jakości PDF
- ✅ **Aktywny rozwój**: Rozwijane przez profesjonalny zespół

### Wyzwania `pdf-writer`
- ⚠️ **Niskopoziomowe API**: Wymaga więcej pracy niż wysokopoziomowe biblioteki
- ⚠️ **Dokumentacja**: Mniej przykładów niż `printpdf`
- ⚠️ **Krzywa uczenia**: Trzeba zrozumieć strukturę PDF

### Dlaczego `pdf-writer` jest dobrym wyborem
- ✅ Najszybsza opcja (używana przez Typst)
- ✅ Pełna kontrola nad generowaniem PDF
- ✅ Sprawdzona w produkcji
- ✅ Warto zainwestować czas w niskopoziomowe API dla maksymalnej wydajności

## 📋 Plan Migracji

### Faza 1: Proof of Concept (2-3 tygodnie)

#### 1.1 Setup Rust Project
```bash
# Utwórz nowy crate dla renderera PDF
cargo new --lib pdf_renderer_rust
cd pdf_renderer_rust

# Dodaj zależności do Cargo.toml
[dependencies]
pdf-writer = "0.9"  # Główna biblioteka PDF
pyo3 = { version = "0.20", features = ["extension-module"] }
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
image = "0.24"  # Do przetwarzania obrazów
ttf-parser = "0.20"  # Do parsowania fontów TTF
fontdue = "0.7"  # Opcjonalnie: rasteryzacja fontów
```

#### 1.2 Stwórz Python Bindings (PyO3)
```rust
// src/lib.rs
use pyo3::prelude::*;

#[pyclass]
pub struct PdfRenderer {
    // Stan renderera
}

#[pymethods]
impl PdfRenderer {
    #[new]
    fn new(output_path: String, page_size: (f64, f64)) -> Self {
        // Inicjalizacja
    }
    
    fn render_page(&mut self, page_data: &PyDict) -> PyResult<()> {
        // Renderowanie strony
    }
    
    fn finish(&mut self) -> PyResult<()> {
        // Zakończenie i zapis PDF
    }
}

#[pymodule]
fn pdf_renderer_rust(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<PdfRenderer>()?;
    Ok(())
}
```

#### 1.3 Migruj Podstawowe Operacje
- Renderowanie prostokątów (tło)
- Renderowanie tekstu (prosty)
- Renderowanie obrazów
- Podstawowe kolory i style

#### 1.4 Testy Porównawcze
- Renderuj ten sam dokument w Pythonie i Rust
- Porównaj wydajność
- Porównaj jakość wyjściową

### Faza 2: Migracja Głównych Komponentów (4-6 tygodni)

#### 2.1 Renderowanie Paragrafów
- Migracja `_draw_paragraph()`
- Obsługa fontów i stylów tekstu
- Justyfikacja tekstu
- Line breaking

#### 2.2 Renderowanie Tabel
- Migracja `_draw_table()`
- Obsługa borders i cell padding
- Colspan/rowspan
- Cell alignment

#### 2.3 Renderowanie Obrazów
- Migracja `_draw_image()`
- Obsługa różnych formatów
- Scaling i positioning

#### 2.4 Renderowanie Dekoracji
- Migracja `_draw_decorator()`
- Borders (wszystkie style)
- Shadows
- Backgrounds

### Faza 3: Integracja z Pythonem (2-3 tygodnie)

#### 3.1 Python Wrapper
```python
# docx_interpreter/engine/pdf/pdf_compiler_rust.py
import pdf_renderer_rust  # Rust module via PyO3

class PDFCompilerRust:
    def __init__(self, output_path, page_size, ...):
        self.rust_renderer = pdf_renderer_rust.PdfRenderer(
            output_path, page_size
        )
    
    def compile(self, unified_layout):
        # Konwertuj UnifiedLayout do formatu dla Rust
        for page in unified_layout.pages:
            page_data = self._convert_page(page)
            self.rust_renderer.render_page(page_data)
        self.rust_renderer.finish()
```

#### 3.2 Konwersja Danych
- UnifiedLayout → JSON/struct dla Rust
- Konwersja kolorów, fontów, geometry
- Obsługa wszystkich typów bloków

#### 3.3 Fallback do ReportLab
- Jeśli Rust renderer nie obsługuje jakiejś funkcji
- Fallback do starego ReportLab renderera
- Logowanie brakujących funkcji

### Faza 4: Optymalizacja i Testy (2-3 tygodnie)

#### 4.1 Benchmarking
- Porównanie wydajności
- Testy na różnych dokumentach
- Profiling i optymalizacja

#### 4.2 Testy Jakości
- Porównanie wyjściowych PDF
- Testy regresyjne
- Weryfikacja wszystkich funkcji

#### 4.3 Dokumentacja
- Dokumentacja Rust API
- Przykłady użycia
- Migration guide

## 🔧 Szczegóły Techniczne

### Mapowanie ReportLab → pdf-writer

**Uwaga**: `pdf-writer` ma niskopoziomowe API. Poniżej są przykłady podstawowych operacji. W praktyce warto stworzyć wrapper/high-level API, który uprości te operacje.

#### Przydatne Zasoby
- **Typst source code**: https://github.com/typst/typst - możesz zobaczyć jak używają pdf-writer
- **pdf-writer docs**: https://docs.rs/pdf-writer
- **Przykłady**: Sprawdź przykłady w repozytorium Typst

#### Wskazówki
- Stwórz helper functions dla częstych operacji (rect, text, image)
- Użyj struct do zarządzania stanem PDF (fonts, colors, etc.)
- Rozważ stworzenie Canvas-like wrapper API dla łatwiejszej migracji z ReportLab
- **Wzoruj się na Typst**: Sprawdź jak Typst używa pdf-writer w swoim kodzie źródłowym
- **Font Registry**: Stwórz system zarządzania fontami (TTF/OTF loading, caching)
- **Content Builder**: Rozważ stworzenie ContentBuilder helper class dla łatwiejszego budowania content streams

#### Przykład High-Level Wrapper (Pomysł)
```rust
// Wrapper dla łatwiejszego użycia pdf-writer
pub struct PdfCanvas {
    pdf: Pdf,
    content: Content,
    font_registry: FontRegistry,
    current_font: Option<FontRef>,
    current_color: Color,
}

impl PdfCanvas {
    pub fn rect(&mut self, x: f64, y: f64, w: f64, h: f64, fill: bool) {
        self.content.rect(x, y, w, h);
        if fill {
            self.content.fill();
        } else {
            self.content.stroke();
        }
    }
    
    pub fn text(&mut self, x: f64, y: f64, text: &str, size: f64) {
        let font = self.current_font.unwrap_or_default();
        self.content.begin_text();
        self.content.set_font(font.name(), size);
        self.content.next_line(x, y);
        self.content.show(TextStr(text));
        self.content.end_text();
    }
    
    // ... więcej metod ...
}
```

### Struktura Danych

#### UnifiedLayout → Rust Struct
```rust
#[derive(Serialize, Deserialize)]
pub struct Page {
    pub number: u32,
    pub size: Size,
    pub blocks: Vec<Block>,
}

#[derive(Serialize, Deserialize)]
pub struct Block {
    pub block_type: String,  // "paragraph", "table", "image", etc.
    pub frame: Rect,
    pub style: Style,
    pub content: BlockContent,
}

#[derive(Serialize, Deserialize)]
pub struct Rect {
    pub x: f64,
    pub y: f64,
    pub width: f64,
    pub height: f64,
}
```

### Python → Rust Bridge

#### Opcja 1: JSON Serialization (Prostsze)
```python
# Python
import json
page_json = json.dumps(page.to_dict())
rust_renderer.render_page_json(page_json)
```

```rust
// Rust
pub fn render_page_json(&mut self, json: &str) -> PyResult<()> {
    let page: Page = serde_json::from_str(json)?;
    self.render_page(&page)
}
```

#### Opcja 2: Direct Structs (Szybsze)
```python
# Python - użyj PyO3 do bezpośredniego przekazania
rust_renderer.render_page(page_dict)  # PyDict → Rust struct
```

```rust
// Rust
pub fn render_page(&mut self, page: &PyDict) -> PyResult<()> {
    // Konwertuj PyDict do Page struct
    let page_struct = convert_pydict_to_page(page)?;
    self.render_page_internal(&page_struct)
}
```

## 📈 Szacowany Zysk Wydajnościowy

### Obecna Wydajność
- Renderowanie PDF: ~2.1s na dokument
- Najcięższa część: operacje canvas (drawing)

### Oczekiwany Zysk z Rust
- **Renderowanie canvas**: 3-5x szybsze
- **Obsługa fontów**: 2-3x szybsze
- **Przetwarzanie obrazów**: 2-4x szybsze
- **Całkowity zysk**: **2-4x** (z ~2.1s do ~0.5-1.0s)

### Dlaczego Nie Więcej?
- Parsowanie i layout pozostają w Pythonie
- Konwersja danych Python → Rust ma overhead
- ReportLab już ma C extensions (nie jest czysty Python)

## ⚠️ Wyzwania i Rozwiązania

### Wyzwanie 1: Niskopoziomowe API
**Problem**: `pdf-writer` ma niskopoziomowe API - trzeba ręcznie zarządzać wszystkimi obiektami PDF

**Rozwiązanie**:
- Stwórz wrapper/high-level API w Rust, który ukrywa szczegóły
- Wzoruj się na kodzie Typst (open source)
- Użyj helper functions dla częstych operacji

### Wyzwanie 2: Konwersja Danych
**Problem**: Overhead konwersji Python → Rust

**Rozwiązanie**:
- Użyj efektywnej serializacji (MessagePack zamiast JSON)
- Cache konwersji gdzie możliwe
- Batch processing wielu stron

### Wyzwanie 3: Fonty
**Problem**: `pdf-writer` wymaga ręcznego dodawania fontów (TTF/OTF data)

**Rozwiązanie**:
- Użyj `ttf-parser` do parsowania fontów
- Załaduj fonty z systemu lub z wbudowanych zasobów
- Stwórz font registry w Rust
- Cache fontów między wywołaniami
- Fallback do systemowych fontów (DejaVu, Arial, etc.)

### Wyzwanie 4: Debugging
**Problem**: Trudniejsze debugowanie Rust z Pythonem

**Rozwiązanie**:
- Szczegółowe logowanie
- Testy jednostkowe w Rust
- Porównanie wyjściowych PDF

## 🚀 Quick Start Guide

### 1. Setup
```bash
# Zainstaluj Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Zainstaluj maturin (build tool dla PyO3)
pip install maturin

# Utwórz nowy projekt
maturin new pdf_renderer_rust
cd pdf_renderer_rust
```

### 2. Podstawowy Przykład z pdf-writer
```rust
// src/lib.rs
use pyo3::prelude::*;
use pdf_writer::{Pdf, Content, Rect, Name, TextStr};
use std::fs::File;
use std::io::BufWriter;

#[pyclass]
pub struct PdfRenderer {
    pdf: Pdf,
    pages: Vec<(u32, Content)>, // (page_id, content)
    current_page: Option<(u32, Content)>,
    output_path: String,
}

#[pymethods]
impl PdfRenderer {
    #[new]
    fn new(output_path: String, width: f64, height: f64) -> Self {
        let mut pdf = Pdf::new();
        
        // Dodaj stronę
        let page_id = pdf.add_page();
        let content_id = pdf.add_stream();
        
        // Ustaw rozmiar strony (A4 = 595x842 points)
        pdf.set_page_media_box(page_id, Rect::new(0.0, 0.0, width, height));
        pdf.set_page_contents(page_id, content_id);
        
        let content = Content::new();
        
        Self {
            pdf,
            pages: vec![(page_id, content)],
            current_page: Some((page_id, content)),
            output_path,
        }
    }
    
    fn add_rect(&mut self, x: f64, y: f64, width: f64, height: f64, fill: bool) -> PyResult<()> {
        if let Some((_, ref mut content)) = self.current_page {
            content.rect(x, y, width, height);
            if fill {
                content.fill();
            } else {
                content.stroke();
            }
            Ok(())
        } else {
            Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No page"))
        }
    }
    
    fn add_text(&mut self, x: f64, y: f64, text: String, font_size: f64) -> PyResult<()> {
        if let Some((_, ref mut content)) = self.current_page {
            // Użyj domyślnego fontu (musisz wcześniej dodać font)
            // To jest uproszczony przykład
            content.begin_text();
            content.set_font(Name(b"F1"), font_size);
            content.next_line(x, y);
            content.show(TextStr(text.as_str()));
            content.end_text();
            Ok(())
        } else {
            Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>("No page"))
        }
    }
    
    fn save(&mut self) -> PyResult<()> {
        // Zapisz content do streamów
        for (page_id, content) in &self.pages {
            let content_id = self.pdf.stream_for(*page_id);
            self.pdf.write(content_id, content.finish());
        }
        
        // Zapisz PDF do pliku
        let file = File::create(&self.output_path)?;
        let mut writer = BufWriter::new(file);
        self.pdf.finish(&mut writer)?;
        Ok(())
    }
}

#[pymodule]
fn pdf_renderer_rust(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<PdfRenderer>()?;
    Ok(())
}
```

### 3. Build i Install
```bash
# Development build
maturin develop

# Release build
maturin build --release

# Install
pip install target/wheels/pdf_renderer_rust-*.whl
```

### 4. Użycie w Pythonie
```python
import pdf_renderer_rust

renderer = pdf_renderer_rust.PdfRenderer("output.pdf", 595, 842)
renderer.add_rect(0, 0, 100, 100)
renderer.save("output.pdf")
```

## 📝 Checklist Migracji

### Faza 1: PoC
- [ ] Setup Rust project z pdf-writer
- [ ] Podstawowe Python bindings (PyO3)
- [ ] Renderowanie prostokątów
- [ ] Renderowanie tekstu (z podstawowymi fontami)
- [ ] Renderowanie obrazów
- [ ] Testy porównawcze z ReportLab
- [ ] Stworzenie high-level wrapper API dla pdf-writer

### Faza 2: Główne Komponenty
- [ ] Renderowanie paragrafów
- [ ] Renderowanie tabel
- [ ] Renderowanie dekoracji (borders, shadows)
- [ ] Obsługa fontów
- [ ] Obsługa kolorów

### Faza 3: Integracja
- [ ] Python wrapper dla PDFCompiler
- [ ] Konwersja UnifiedLayout → Rust structs
- [ ] Fallback do ReportLab
- [ ] Testy integracyjne

### Faza 4: Finalizacja
- [ ] Benchmarking
- [ ] Testy jakości
- [ ] Dokumentacja
- [ ] Deployment

## 🎯 Podsumowanie

**Migracja tylko renderera PDF do Rusta** to dobry kompromis:
- ✅ Najcięższa część (renderowanie) w Rust
- ✅ Reszta projektu pozostaje w Pythonie
- ✅ Łatwiejsza migracja niż pełna
- ✅ Szacowany zysk: 2-4x wydajności
- ✅ Czas: 10-15 tygodni

**Następne kroki**:
1. Stwórz PoC z podstawowym renderowaniem
2. Porównaj wydajność z obecnym rozwiązaniem
3. Jeśli zysk >2x → kontynuuj migrację
4. Jeśli zysk <2x → rozważ alternatywy

