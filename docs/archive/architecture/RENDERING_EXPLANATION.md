# Jak Działa Renderowanie PDF - Wyjaśnienie

## 📋 Przepływ Renderowania

### Ogólny Przepływ
```
DOCX File
    ↓
Document.parse()           # Parsowanie DOCX
    ↓
PdfCompiler.compile()       # Główny pipeline
    ↓
Preprocessor.process()     # Preprocessing (placeholderów, etc.)
    ↓
DocumentEngine.build_layout()  # Obliczenie layoutu
    ↓
List[LayoutPage]           # LayoutPages z LayoutBlocks
    ↓
PdfBackend.render()        # Renderowanie do PDF ⭐
    ↓
PDF File
```

### Krok Kluczowy: PdfBackend.render()

`PdfBackend` jest odpowiedzialny za zamianę `LayoutPages` na plik PDF. Wybiera między dwoma trybami:

```python
# compiler/backends/pdf_backend.py
class PdfBackend:
    def __init__(self, output_path, options, context):
        # Wybór trybu renderowania
        self.mode = options.get("backend") or options.get("renderer") or "reportlab"
        
        if self.mode == "direct":
            # Tryb direct - własny generator PDF
            self.direct_writer = None  # Zostanie utworzony w render()
        else:
            # Tryb reportlab - używa biblioteki ReportLab
            self.reportlab_renderer = PdfRenderer(...)
    
    def render(self, layout_pages):
        if self.mode == "direct":
            self._render_direct(pages)    # ⭐ Direct mode
        else:
            self.reportlab_renderer.render(pages, self.output_path)  # ⭐ ReportLab mode
```

---

## 🔄 Tryb ReportLab (`reportlab`)

### Jak Działa

**ReportLab mode** używa biblioteki `reportlab` do generowania PDF. Jest to wysokopoziomowa biblioteka, która obsługuje:
- Canvas API (podobny do HTML5 Canvas)
- Automatyczne zarządzanie fontami
- Zaawansowane funkcje PDF (zakładki, linki, itp.)

### Architektura

```
PdfBackend (mode="reportlab")
    ↓
PdfRenderer (docx_interpreter/renderers/pdf_renderer.py)
    ↓
ReportLab Canvas API
    ├── TextRenderer      # Renderowanie tekstu
    ├── TableRenderer     # Renderowanie tabel
    ├── ImageRenderer     # Renderowanie obrazów
    └── HeaderFooterRenderer  # Renderowanie header/footer
    ↓
PDF File (via ReportLab)
```

### Przykład Kodu

```python
# docx_interpreter/renderers/pdf_renderer.py
class PdfRenderer(BaseRenderer):
    def __init__(self, page_size=A4, margins=(50, 50, 50, 50), dpi=72.0):
        self.canvas = None  # ReportLab Canvas
    
    def _init_canvas(self, output):
        from reportlab.pdfgen import canvas
        self.canvas = canvas.Canvas(output, pagesize=self.page_size)
    
    def _render_page(self, layout_page):
        # Renderowanie na ReportLab Canvas
        for block in layout_page.blocks:
            if block.block_type == "paragraph":
                self.text_renderer.draw(block)  # Używa canvas.drawString()
            elif block.block_type == "table":
                self.table_renderer.draw(block)  # Używa canvas.table()
            # ...
        self.canvas.showPage()  # Zakończenie strony
```

### Zalety ReportLab Mode
✅ **Wysokopoziomowa API** - łatwe w użyciu
✅ **Bogate funkcje** - zakładki, linki, formularze
✅ **Automatyczne zarządzanie** - fonty, strony, streamy
✅ **Dojrzała biblioteka** - szeroko używana, dobrze przetestowana

### Wady ReportLab Mode
❌ **Zależność zewnętrzna** - wymaga instalacji `reportlab`
❌ **Ograniczenia fontów** - tylko fonty zarejestrowane w ReportLab
❌ **Większy rozmiar PDF** - bardziej skomplikowane struktury
❌ **Problemy z fontami** - np. Verdana nie jest dostępna domyślnie

---

## ⚡ Tryb Direct (`direct`)

### Jak Działa

**Direct mode** generuje PDF **bezpośrednio**, pisząc surowy format PDF (PDF specification). To oznacza:
- Generowanie niskopoziomowych komend PDF
- Bezpośrednie pisanie do pliku PDF
- Większa kontrola nad formatem

### Architektura

```
PdfBackend (mode="direct")
    ↓
DirectPdfWriter (compiler/backends/pdf/direct_writer.py)
    ↓
PDF Commands (surowy format PDF)
    ├── TextCommand      # Komendy tekstowe (BT, ET)
    ├── RectCommand       # Komendy prostokątów
    └── LinkCommand       # Komendy linków
    ↓
PDF File (bezpośrednio pisany)
```

### Przykład Kodu

```python
# compiler/backends/pdf/direct_writer.py
class DirectPdfWriter:
    def __init__(self, output_path, dpi=72.0):
        self.output_path = Path(output_path)
        self.pages = []
        self.fonts = {}
    
    def add_page(self, width, height):
        """Dodaje nową stronę."""
        page = DirectPdfPage(width=width, height=height)
        self.pages.append(page)
        return page
    
    def add_text(self, page, x, y, text, font_size, font_resource):
        """Dodaje tekst do strony."""
        # Escapowanie tekstu dla PDF
        escaped_text = _escape_text(text)
        payload = f"(BT /{font_resource} {font_size} Tf {x} {y} Td ({escaped_text}) Tj ET)"
        page.add_text(x, y, payload.encode(), font_size, font_resource, unicode=True)
    
    def write(self):
        """Zapisuje PDF do pliku."""
        with open(self.output_path, 'wb') as f:
            f.write(b"%PDF-1.4\n")  # Header PDF
            # ... zapisanie obiektów PDF
            f.write(b"%%EOF\n")  # Footer PDF
```

### Komendy PDF (Przykład)

Direct mode pisze surowe komendy PDF:

```pdf
BT                          % Begin Text
/F1 12 Tf                   % Ustaw font F1, rozmiar 12
100 700 Td                  % Pozycja (100, 700)
(Hello World) Tj            % Tekst
ET                          % End Text
```

### Zalety Direct Mode
✅ **Brak zależności zewnętrznych** - tylko Python standard library
✅ **Pełna kontrola** - dokładnie jak PDF jest generowany
✅ **Lżejsze pliki** - mniej overhead
✅ **Własne fonty** - można użyć dowolnych fontów (TTF, OTF)
✅ **Szybsze** - bez pośrednich warstw

### Wady Direct Mode
❌ **Niskopoziomowe** - trzeba ręcznie pisać komendy PDF
❌ **Bardziej skomplikowane** - więcej kodu do zarządzania
❌ **Mniej funkcji** - brak niektórych zaawansowanych funkcji (formularze, itp.)
❌ **Więcej bugów potencjalnych** - trzeba ręcznie zarządzać wszystkimi aspektami

---

## 🔀 Różnice Kluczowe

### 1. Generowanie PDF

**ReportLab:**
```python
# ReportLab generuje PDF przez swoje API
canvas = Canvas("output.pdf")
canvas.drawString(100, 700, "Hello")
canvas.save()  # ReportLab sam zapisuje PDF
```

**Direct:**
```python
# Direct pisze surowy PDF
writer = DirectPdfWriter("output.pdf")
writer.add_text(page, 100, 700, "Hello", 12, "F1")
writer.write()  # Bezpośrednio do pliku PDF
```

### 2. Fonty

**ReportLab:**
```python
# ReportLab wymaga zarejestrowanych fontów
from reportlab.pdfbase import pdfmetrics
pdfmetrics.registerFont(...)  # Musisz zarejestrować font
canvas.setFont("Verdana", 12)  # ❌ Błąd jeśli font nie zarejestrowany
```

**Direct:**
```python
# Direct może użyć dowolnego fontu TTF/OTF
font_path = resolve_font_path("Verdana")  # ✅ Znajdzie font TTF
writer.register_font("F1", font_path)  # ✅ Działa z dowolnym fontem
```

### 3. Struktura Kodu

**ReportLab:**
```python
# Wysokopoziomowa, abstrakcyjna
class PdfRenderer:
    def _render_block(self, block):
        if block.block_type == "paragraph":
            self.text_renderer.draw(block)  # ReportLab robi resztę
```

**Direct:**
```python
# Niskopoziomowa, konkretna
class DirectPdfWriter:
    def add_text(self, page, x, y, text, font_size, font_resource):
        # Musisz ręcznie zarządzać wszystkimi detalami
        escaped_text = _escape_text(text)
        payload = f"(BT /{font_resource} {font_size} Tf {x} {y} Td ({escaped_text}) Tj ET)"
        page.add_text(x, y, payload.encode(), font_size, font_resource, unicode=True)
```

### 4. Obsługa Błędów

**ReportLab:**
```python
# ReportLab zgłasza błędy, jeśli font nie jest dostępny
canvas.setFont("Verdana", 12)  # ❌ KeyError: 'Verdana'
```

**Direct:**
```python
# Direct może użyć fallback fontów
font_path = resolve_font_path("Verdana")
if font_path:
    writer.register_font("F1", font_path)  # ✅ Używa Verdana
else:
    writer.register_font("F1", default_font)  # ✅ Fallback
```

---

## 📊 Porównanie

| Aspekt | ReportLab Mode | Direct Mode |
|--------|---------------|-------------|
| **Zależności** | Wymaga `reportlab` | Tylko Python stdlib |
| **Poziom API** | Wysoki (abstrakcyjny) | Niski (bezpośredni) |
| **Fonty** | Tylko zarejestrowane | Dowolne TTF/OTF |
| **Rozmiar PDF** | Większy (overhead) | Mniejszy (bezpośredni) |
| **Szybkość** | Wolniejszy (warstwy) | Szybszy (bezpośredni) |
| **Funkcje** | Bogate (formularze, itp.) | Podstawowe (tekst, grafika) |
| **Złożoność** | Prostsza (API) | Bardziej skomplikowana |
| **Debugowanie** | Trudniejsze (warstwy) | Łatwiejsze (bezpośrednie) |
| **Błędy fontów** | Częste (np. Verdana) | Rzadkie (fallback) |

---

## 🎯 Kiedy Używać Jakiego Trybu?

### Użyj ReportLab Mode gdy:
- ✅ Potrzebujesz zaawansowanych funkcji PDF (formularze, zakładki)
- ✅ Masz zarejestrowane fonty w ReportLab
- ✅ Chcesz prostszą API
- ✅ Nie masz problemów z dostępnością fontów

### Użyj Direct Mode gdy:
- ✅ Chcesz uniknąć zależności zewnętrznych
- ✅ Potrzebujesz użyć niestandardowych fontów (Verdana, itp.)
- ✅ Chcesz mniejsze pliki PDF
- ✅ Chcesz pełną kontrolę nad generowaniem PDF
- ✅ Masz problemy z fontami w ReportLab (jak w przypadku Verdana)

---

## 🔧 Przykład Użycia

### ReportLab Mode (domyślny)
```python
from compiler import PdfCompiler
from docx_interpreter import Document

doc = Document("input.docx")
doc.parse()

# Domyślnie używa ReportLab
compiler = PdfCompiler(doc, "output.pdf")  # mode="reportlab"
compiler.compile()
```

### Direct Mode (zalecany dla Verdana)
```python
from compiler.pdf_compiler import PdfCompiler, CompilerOptions
from docx_interpreter import Document

doc = Document("input.docx")
doc.parse()

# Używa Direct mode
options = CompilerOptions(renderer="direct")
compiler = PdfCompiler(doc, "output.pdf", options)
compiler.compile()
```

### Przez CLI
```bash
# ReportLab (domyślny)
python -m compiler input.docx -o output.pdf

# Direct
python -m compiler input.docx -o output.pdf --backend direct
```

---

## 📝 Podsumowanie

**Renderowanie** to proces zamiany `LayoutPages` (obiektów Python z pozycjami i stylami) na plik PDF.

**ReportLab mode** używa biblioteki `reportlab` do generowania PDF przez wysokopoziomowe API. Jest prostszy, ale wymaga zewnętrznej biblioteki i ma ograniczenia fontów.

**Direct mode** generuje PDF bezpośrednio, pisząc surowy format PDF. Jest bardziej skomplikowany, ale daje pełną kontrolę i pozwala używać dowolnych fontów.

Dla dokumentów z niestandardowymi fontami (np. Verdana) **Direct mode** jest lepszym wyborem, bo może użyć dowolnych fontów TTF/OTF bez konieczności rejestrowania ich w ReportLab.

---

*Wyjaśnienie przygotowane: $(date)*

