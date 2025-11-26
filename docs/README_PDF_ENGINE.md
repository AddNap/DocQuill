# Silnik PDF dla DOCX Interpreter

Kompletny silnik renderowania PDF dla DOCX Interpreter, zaprojektowany na podstawie analizy DirectPDFRenderer i zintegrowany z istniejącym parserem DOCX.

## 🚀 Szybki Start

```python
from docx_interpreter import Document, render_docx_file_to_pdf, PageSize

# Najprostsze użycie
render_docx_file_to_pdf("document.docx", "output.pdf")

# Z custom ustawieniami
render_docx_file_to_pdf("document.docx", "output.pdf", 
                       page_size=PageSize.A4, debug=True)

# Użycie rozszerzonej klasy Document
doc = Document.open("document.docx")
doc.render_to_pdf("output.pdf")
```

## 📋 Funkcje

### ✅ Zaimplementowane
- **Modularna architektura** - 3 główne silniki (Parsing, Geometry, Rendering)
- **Integracja z parserem DOCX** - Płynna integracja z istniejącym kodem
- **Zaawansowane łamanie tekstu** - Hybrid approach z ReportLab Paragraph
- **Justyfikacja tekstu** - Tokenizacja, rozkład wagowy, domknięcie brzegu
- **Obsługa tabel** - Auto-fit, cache wysokości, colspan/rowspan
- **Różne rozmiary stron** - A4, A3, A5, Letter, Legal
- **Fonty z polskimi znakami** - DejaVu fonts
- **Debug mode** - Szczegółowe logi i informacje
- **Adaptery modeli** - Konwersja między formatami
- **Convenience functions** - Proste API
- **Error handling** - Obsługa błędów
- **Batch processing** - Przetwarzanie wsadowe

### 🔄 W Trakcie
- Headers i footers
- Obrazy (inline/anchored)
- Dekoracje paragrafów (borders, backgrounds)
- Watermarks
- Plugin system

## 🏗️ Architektura

```
DOCX → Parser → Engine_Parsing → Engine_Geometry → Engine_Rendering → PDF
```

### Silniki (56 metod łącznie)

1. **Engine_Parsing** (15 metod - 26.8%)
   - Analiza dokumentu DOCX
   - Parsowanie właściwości paragrafów, runów, tabel
   - Konwersje jednostek (twips → points)
   - Normalizacja alignment

2. **Engine_Geometry** (18 metod - 32.1%)
   - Obliczenia wymiarów i pozycjonowania
   - Łamanie tekstu na linie
   - Geometria tabel i komórek
   - Estymacja wysokości elementów

3. **Engine_Rendering** (23 metody - 41.1%)
   - Rzeczywiste renderowanie do PDF
   - Obsługa paragrafów, tabel, obrazów
   - Headers i footers
   - Zarządzanie stronami

## 📦 Instalacja

```bash
# Wymagane zależności
pip install reportlab pillow

# Fonty DejaVu (opcjonalne, dla polskich znaków)
# Ubuntu/Debian:
sudo apt-get install fonts-dejavu-core

# macOS:
brew install font-dejavu

# Windows: Pobierz z https://dejavu-fonts.github.io/
```

## 📖 Przykłady Użycia

### Podstawowe

```python
# Metoda 1: Convenience function
from docx_interpreter import render_docx_file_to_pdf, PageSize

render_docx_file_to_pdf("input.docx", "output.pdf", 
                       page_size=PageSize.A4, debug=True)

# Metoda 2: Custom renderer
from docx_interpreter import create_pdf_renderer

renderer = create_pdf_renderer(page_size=PageSize.A4, debug=True)
renderer.render_file("input.docx", "output.pdf")

# Metoda 3: Rozszerzona klasa Document
from docx_interpreter import Document

doc = Document.open("input.docx")
doc.render_to_pdf("output.pdf", page_size=PageSize.A4, debug=True)

# Metoda 4: Bezpośrednie użycie silnika
from docx_interpreter import create_pdf_engine

doc = Document.open("input.docx")
pdf_engine = create_pdf_engine(page_size=PageSize.A4, debug=True)
pdf_engine.render_document(doc, "output.pdf")
```

### Zaawansowane

```python
# Przetwarzanie wsadowe
from pathlib import Path
from docx_interpreter import create_pdf_renderer

renderer = create_pdf_renderer(debug=False)

docx_files = ["doc1.docx", "doc2.docx", "doc3.docx"]
for i, docx_file in enumerate(docx_files, 1):
    if Path(docx_file).exists():
        output_file = f"output_{i}.pdf"
        renderer.render_file(docx_file, output_file)
        print(f"✅ {docx_file} → {output_file}")

# Różne rozmiary stron
from docx_interpreter import Document, PageSize

doc = Document.open("input.docx")
page_sizes = [PageSize.A4, PageSize.A3, PageSize.LETTER, PageSize.LEGAL]

for page_size in page_sizes:
    output_file = f"output_{page_size.value.lower()}.pdf"
    doc.render_to_pdf(output_file, page_size=page_size)

# Użycie adapterów
from docx_interpreter import Document, ParagraphAdapter, TableAdapter

doc = Document.open("input.docx")

# Analiza paragrafów
for paragraph in doc.body.paragraphs:
    adapted = ParagraphAdapter.adapt_paragraph(paragraph)
    print(f"Tekst: {adapted['text'][:50]}...")
    print(f"Alignment: {adapted['alignment']}")
    print(f"Runy: {len(adapted['runs'])}")

# Analiza tabel
for table in doc.body.tables:
    adapted = TableAdapter.adapt_table(table)
    print(f"Wiersze: {len(adapted['rows'])}")
    print(f"Szerokość: {adapted['width']}")
```

### Obsługa błędów

```python
import logging
from docx_interpreter import render_docx_file_to_pdf

logging.basicConfig(level=logging.INFO)

try:
    render_docx_file_to_pdf("input.docx", "output.pdf")
    print("✅ Renderowanie zakończone pomyślnie")
    
except FileNotFoundError:
    print("❌ Plik DOCX nie istnieje")
    
except PermissionError:
    print("❌ Brak uprawnień do zapisu pliku PDF")
    
except Exception as e:
    print(f"❌ Nieoczekiwany błąd: {e}")
    logging.exception("Szczegóły błędu:")
```

## 🔧 API Reference

### Główne Klasy

#### `PDFEngine`
Główny silnik PDF łączący wszystkie komponenty.

```python
from docx_interpreter import PDFEngine, PageSize

engine = PDFEngine(page_size=PageSize.A4, debug=True)
engine.render_document(document, "output.pdf")
info = engine.get_engine_info()
```

#### `DOCXInterpreterPDFRenderer`
Integracja z parserem DOCX.

```python
from docx_interpreter import create_pdf_renderer

renderer = create_pdf_renderer(page_size=PageSize.A4, debug=True)
renderer.render_file("input.docx", "output.pdf")
renderer.render_document(document, "output.pdf")
```

### Enums

```python
from docx_interpreter import PageSize, Alignment, FontWeight, FontStyle

# Rozmiary stron
PageSize.A4      # 595.28 x 841.89 pt
PageSize.A3      # 841.89 x 1190.55 pt
PageSize.A5      # 419.53 x 595.28 pt
PageSize.LETTER  # 612.0 x 792.0 pt
PageSize.LEGAL   # 612.0 x 1008.0 pt

# Wyrównanie tekstu
Alignment.LEFT     # "left"
Alignment.CENTER   # "center"
Alignment.RIGHT    # "right"
Alignment.JUSTIFY  # "justify"
Alignment.BOTH     # "both"

# Font
FontWeight.NORMAL  # "normal"
FontWeight.BOLD    # "bold"
FontStyle.NORMAL   # "normal"
FontStyle.ITALIC   # "italic"
```

### Dataclasses

```python
from docx_interpreter import FontInfo, TextLine, PageGeometry, TableGeometry

# Informacje o foncie
font_info = FontInfo(
    name="DejaVuSans",
    size=12.0,
    weight=FontWeight.BOLD,
    style=FontStyle.ITALIC,
    color="#000000",
    underline=True
)

# Linia tekstu
text_line = TextLine(
    runs=[(run, "Hello", font_info)],
    width=50.0,
    height=14.4,
    words=["Hello"]
)

# Geometria strony
page_geometry = PageGeometry(
    width=595.28,
    height=841.89,
    margin_top=72.0,
    margin_bottom=72.0,
    margin_left=72.0,
    margin_right=72.0
)
```

### Convenience Functions

```python
from docx_interpreter import (
    render_docx_file_to_pdf,
    create_pdf_renderer,
    create_pdf_engine
)

# Renderowanie pliku
render_docx_file_to_pdf("input.docx", "output.pdf", 
                       page_size=PageSize.A4, debug=True)

# Tworzenie renderera
renderer = create_pdf_renderer(page_size=PageSize.A4, debug=True)

# Tworzenie silnika
engine = create_pdf_engine(page_size=PageSize.A4, debug=True)
```

## 🐛 Troubleshooting

### Częste problemy

**Problem**: "Font not found" lub "DejaVuSans not registered"
```python
# Sprawdź czy fonty DejaVu są zainstalowane
from pathlib import Path

font_paths = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/DejaVuSans.ttf",  # macOS
    "C:/Windows/Fonts/dejavu-sans.ttf"      # Windows
]

for font_path in font_paths:
    if Path(font_path).exists():
        print(f"✅ Font znaleziony: {font_path}")
        break
else:
    print("❌ Fonty DejaVu nie znalezione - zainstaluj je")
```

**Problem**: "Permission denied" przy zapisie PDF
```python
# Sprawdź uprawnienia do katalogu wyjściowego
from pathlib import Path

output_dir = Path("output")
if not output_dir.exists():
    output_dir.mkdir(parents=True, exist_ok=True)

# Sprawdź czy można zapisać plik
test_file = output_dir / "test.txt"
try:
    test_file.write_text("test")
    test_file.unlink()
    print("✅ Uprawnienia OK")
except PermissionError:
    print("❌ Brak uprawnień do zapisu")
```

**Problem**: "Empty PDF" lub "Blank pages"
```python
# Sprawdź czy dokument ma zawartość
from docx_interpreter import Document

doc = Document.open("input.docx")

# Sprawdź body content
if hasattr(doc, 'body') and hasattr(doc.body, 'paragraphs'):
    print(f"Paragrafy: {len(doc.body.paragraphs)}")
    for i, para in enumerate(doc.body.paragraphs):
        text = getattr(para, 'text', '')
        print(f"  Para {i}: '{text[:50]}...'")

# Sprawdź tabele
if hasattr(doc, 'body') and hasattr(doc.body, 'tables'):
    print(f"Tabele: {len(doc.body.tables)}")
```

### Debugowanie

```python
import logging

# Włącz szczegółowe logowanie
logging.basicConfig(level=logging.DEBUG)

# Użyj debug=True w rendererze
from docx_interpreter import create_pdf_renderer

renderer = create_pdf_renderer(debug=True)

# Sprawdź informacje o silniku
info = renderer.get_engine_info()
print("Engine info:", info)
```

## 🧪 Testowanie

```python
# Uruchom przykłady
from docx_interpreter.pdf_examples import PDFRendererExamples

examples = PDFRendererExamples()
examples.run_all_examples()

# Lub uruchom konkretny przykład
examples.example_1_basic_file_rendering()
examples.example_6_batch_processing()
```

## 📚 Dokumentacja

- **Kompletna dokumentacja**: `pdf_documentation.py`
- **Przykłady użycia**: `pdf_examples.py`
- **Integracja**: `pdf_integration.py`
- **Silnik główny**: `pdf_engine.py`

## 🤝 Rozwój

### Rozszerzanie funkcjonalności

```python
# Custom Parsing Engine
from docx_interpreter.pdf_engine import ParsingEngine

class CustomParsingEngine(ParsingEngine):
    def analyze_document(self, document):
        metadata = super().analyze_document(document)
        metadata['custom_field'] = 'custom_value'
        return metadata

# Custom Geometry Engine
from docx_interpreter.pdf_engine import GeometryEngine

class CustomGeometryEngine(GeometryEngine):
    def calculate_table_dimensions(self, table, available_width):
        geometry = super().calculate_table_dimensions(table, available_width)
        geometry.custom_width = geometry.width * 1.1  # 10% większa
        return geometry

# Custom PDF Engine
from docx_interpreter.pdf_engine import PDFEngine

class CustomPDFEngine(PDFEngine):
    def __init__(self, page_size=None, debug=False, custom_param=None):
        super().__init__(page_size, debug)
        self.custom_param = custom_param
        
        # Zastąp silniki custom wersjami
        self.parsing_engine = CustomParsingEngine()
        self.geometry_engine = CustomGeometryEngine(self.parsing_engine)
```

### Plugin System

```python
from abc import ABC, abstractmethod

class PDFPlugin(ABC):
    @abstractmethod
    def before_render(self, document, engine):
        pass
    
    @abstractmethod
    def after_render(self, document, engine, output_path):
        pass

class WatermarkPlugin(PDFPlugin):
    def __init__(self, watermark_text="DRAFT"):
        self.watermark_text = watermark_text
    
    def after_render(self, document, engine, output_path):
        # Dodaj watermark do PDF
        pass
```

## 📄 Licencja

MIT License - zobacz plik LICENSE dla szczegółów.

## 🙏 Podziękowania

- **DirectPDFRenderer** - Inspiracja dla architektury
- **ReportLab** - Biblioteka PDF
- **DejaVu Fonts** - Fonty z polskimi znakami
- **DOCX Interpreter Team** - Parser DOCX

## 📞 Wsparcie

- **GitHub Issues**: https://github.com/your-repo/issues
- **Dokumentacja**: https://your-docs.com/pdf-engine
- **Email**: support@docx-interpreter.com

---

**Silnik PDF dla DOCX Interpreter** - Kompletne rozwiązanie do renderowania DOCX → PDF 🚀
