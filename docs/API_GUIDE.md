# Przewodnik po wysokopoziomowym API DocQuill

Prosty i intuicyjny interfejs do pracy z dokumentami DOCX.

## Szybki start

```python
from docx_interpreter import Document

# Otwórz dokument
doc = Document('plik.docx')

# Pobierz model
model = doc.to_model()

# Przetwórz przez pipeline
layout = doc.pipeline()

# Renderuj do PDF
doc.to_pdf('output.pdf', backend='rust')

# Renderuj do HTML
doc.to_html('output.html')

# Normalizuj dokument
doc_normalized = doc.normalize('normalized.docx')
```

## Główne metody

### `Document(file_path)` / `Document.open(file_path)`

Otwiera dokument z pliku DOCX.

```python
doc = Document('plik.docx')
# lub
doc = Document.open('plik.docx')
```

### `doc.to_model()`

Zwraca model dokumentu (body, headers, footers) z parsera.

```python
model = doc.to_model()
print(model.elements)  # Lista elementów dokumentu
```

### `doc.pipeline(...)`

Przepuszcza dokument przez silnik layoutu i assembler, zwracając `UnifiedLayout`.

**Parametry:**
- `page_size: Tuple[float, float]` - Rozmiar strony (width, height) w punktach. Domyślnie A4 (595, 842)
- `margins: Tuple[float, float, float, float]` - Marginesy (top, bottom, left, right) w punktach. Domyślnie (72, 72, 72, 72)
- `apply_headers_footers: bool` - Czy stosować nagłówki i stopki. Domyślnie `True`
- `validate: bool` - Czy wykonać walidację. Domyślnie `False`
- `target: str` - Cel renderowania ("pdf", "html", "docx"). Domyślnie `"pdf"`

```python
# Podstawowe użycie
layout = doc.pipeline()

# Z custom ustawieniami
layout = doc.pipeline(
    page_size=(842, 595),  # A4 landscape
    margins=(50, 50, 50, 50),
    apply_headers_footers=True,
    validate=False,
    target="pdf"
)
```

### `doc.to_pdf(output_path, ...)`

Renderuje dokument do PDF.

**Parametry:**
- `output_path: Union[str, Path]` - Ścieżka do pliku wyjściowego PDF
- `backend: str` - Silnik renderowania ("rust" lub "reportlab"). Domyślnie `"rust"`
- `page_size: Tuple[float, float]` - Rozmiar strony w punktach
- `margins: Tuple[float, float, float, float]` - Marginesy w punktach
- `parallelism: int` - Liczba procesów (1 = sequential). Domyślnie `1`
- `watermark_opacity: float` - Przezroczystość watermarków (0.0-1.0)
- `apply_headers_footers: bool` - Czy stosować nagłówki i stopki
- `validate: bool` - Czy wykonać walidację

```python
# Podstawowe użycie
doc.to_pdf('output.pdf', backend='rust')

# Z pełnymi opcjami
doc.to_pdf(
    'output.pdf',
    backend='rust',
    page_size=(595, 842),  # A4
    margins=(72, 72, 72, 72),
    parallelism=1,
    watermark_opacity=0.5
)
```

### `doc.to_html(output_path, ...)`

Renderuje dokument do HTML.

**Parametry:**
- `output_path: Union[str, Path]` - Ścieżka do pliku wyjściowego HTML
- `editable: bool` - Czy HTML ma być edytowalny (contenteditable). Domyślnie `False`
- `page_size: Tuple[float, float]` - Rozmiar strony w punktach
- `margins: Tuple[float, float, float, float]` - Marginesy w punktach
- `apply_headers_footers: bool` - Czy stosować nagłówki i stopki. Domyślnie `False`
- `validate: bool` - Czy wykonać walidację
- `embed_images_as_data_uri: bool` - Czy osadzać obrazy jako data URI. Domyślnie `False`
- `page_max_width: float` - Maksymalna szerokość strony w CSS (px). Domyślnie `960.0`

```python
# Podstawowe użycie
doc.to_html('output.html')

# Z opcjami
doc.to_html(
    'output.html',
    editable=True,
    embed_images_as_data_uri=True,
    page_max_width=1200.0
)
```

### `doc.normalize(output_path=None)`

Normalizuje dokument (czyści style, merguje runs, poprawia formatowanie).

**Parametry:**
- `output_path: Optional[Union[str, Path]]` - Ścieżka do zapisu. Jeśli `None`, tworzy plik z sufiksem "_normalized"

**Zwraca:** Nowy `Document` z znormalizowanym dokumentem

```python
# Z automatyczną nazwą pliku
doc_normalized = doc.normalize()

# Z własną nazwą
doc_normalized = doc.normalize('normalized.docx')
```

## Przykłady użycia

### Podstawowy workflow

```python
from docx_interpreter import Document

# 1. Otwórz dokument
doc = Document('input.docx')

# 2. Przetwórz przez pipeline
layout = doc.pipeline()

# 3. Renderuj do PDF
doc.to_pdf('output.pdf', backend='rust')

# 4. Renderuj do HTML
doc.to_html('output.html')
```

### Zaawansowane użycie z custom ustawieniami

```python
from docx_interpreter import Document

doc = Document('input.docx')

# Custom pipeline
layout = doc.pipeline(
    page_size=(842, 595),  # A4 landscape
    margins=(50, 50, 50, 50),
    apply_headers_footers=True,
    validate=True
)

# PDF z opcjami
doc.to_pdf(
    'output.pdf',
    backend='rust',
    page_size=(842, 595),
    margins=(50, 50, 50, 50),
    parallelism=1,
    watermark_opacity=0.5
)

# HTML z opcjami
doc.to_html(
    'output.html',
    editable=False,
    embed_images_as_data_uri=False,
    page_max_width=1200.0
)
```

### Normalizacja dokumentu

```python
from docx_interpreter import Document

doc = Document('input.docx')

# Normalizuj i zapisz
doc_normalized = doc.normalize('normalized.docx')

# Możesz dalej pracować z znormalizowanym dokumentem
doc_normalized.to_pdf('normalized_output.pdf')
```

### Watermarks (Znaki wodne)

```python
from docx_interpreter import Document

doc = Document('input.docx')

# Dodaj watermark
doc.add_watermark("CONFIDENTIAL", angle=45, opacity=0.3)
doc.add_watermark("DRAFT", color="#FF0000", opacity=0.5)

# Pobierz listę watermarków
watermarks = doc.get_watermarks()
```

### Metadata (Metadane)

```python
from docx_interpreter import Document

doc = Document('input.docx')

# Pobierz wszystkie metadane
metadata = doc.get_metadata()
print(metadata['core_properties'])

# Lub użyj getterów
title = doc.get_title()
author = doc.get_author()
subject = doc.get_subject()
keywords = doc.get_keywords()
```

### Walidacja layoutu

```python
from docx_interpreter import Document

doc = Document('input.docx')

# Waliduj layout z wynikami
layout, is_valid, errors, warnings = doc.validate_layout()

if not is_valid:
    print("Błędy:", errors)
    print("Ostrzeżenia:", warnings)
```

### Informacje o dokumencie

```python
from docx_interpreter import Document

doc = Document('input.docx')

# Statystyki
stats = doc.get_stats()
print(f"Paragrafów: {stats['paragraphs']}")
print(f"Tabel: {stats['tables']}")
print(f"Obrazów: {stats['images']}")

# Sekcje
sections = doc.get_sections()
print(f"Liczba sekcji: {len(sections)}")

# Style
styles = doc.get_styles()
print(f"Dostępne style: {list(styles.keys())}")

# Numeracja
numbering = doc.get_numbering()
print(f"Definicje numeracji: {len(numbering.get('abstract_numberings', {}))}")
```

### Dostęp do wewnętrznych obiektów

```python
from docx_interpreter import Document

doc = Document('input.docx')

# Dostęp do pipeline
pipeline = doc.pipeline  # None jeśli jeszcze nie wywołano pipeline()

# Dostęp do parserów
reader = doc.package_reader
parser = doc.xml_parser

# Dostęp do layoutu
layout = doc.layout  # None jeśli jeszcze nie przetworzono
```

### Praca z modelem

```python
from docx_interpreter import Document

doc = Document('input.docx')

# Pobierz model
model = doc.to_model()

# Przejrzyj elementy
for element in model.elements:
    print(f"Element: {type(element).__name__}")
    
    # Jeśli to paragraf
    if hasattr(element, 'runs'):
        for run in element.runs:
            print(f"  Run: {run.get_text()}")
```

## Inne dostępne metody

### Watermarks (Znaki wodne)
- `doc.add_watermark(text, angle, opacity, color, font_size, font_name)` - Dodaje watermark
- `doc.get_watermarks()` - Zwraca listę watermarków
- `doc.watermarks` - Property zwracające watermarky

### Metadata (Metadane)
- `doc.get_metadata()` - Pobiera metadane dokumentu
- `doc.metadata` - Property zwracające metadane
- `doc.get_title()` - Zwraca tytuł dokumentu
- `doc.get_author()` - Zwraca autora dokumentu
- `doc.get_subject()` - Zwraca temat dokumentu
- `doc.get_keywords()` - Zwraca słowa kluczowe
- `doc.get_description()` - Zwraca opis dokumentu

### Walidacja
- `doc.validate_layout(...)` - Waliduje layout i zwraca (layout, is_valid, errors, warnings)

### Zaawansowane merge
- `doc.merge_sections(source, copy_properties)` - Łączy sekcje
- `doc.merge_styles(source)` - Łączy style

### Wewnętrzne obiekty (Properties)
- `doc.pipeline` - Obiekt LayoutPipeline
- `doc.package_reader` - Obiekt PackageReader
- `doc.xml_parser` - Obiekt XMLParser
- `doc.layout` - UnifiedLayout (jeśli przetworzony)

### Informacje o dokumencie
- `doc.get_stats()` - Statystyki dokumentu (paragraphs, tables, images, etc.)
- `doc.get_sections()` - Lista sekcji dokumentu
- `doc.get_styles()` - Lista stylów w dokumencie
- `doc.get_numbering()` - Informacje o numeracji

### Inne metody z DocumentAPI
- `doc.fill_placeholders(data)` - Wypełnia placeholdery
- `doc.replace_text(old, new)` - Zastępuje tekst
- `doc.merge(other)` - Łączy z innym dokumentem
- `doc.append(other)` - Dodaje dokument na koniec
- `doc.save(path)` - Zapisuje do DOCX
- `doc.extract_placeholders()` - Wyciąga placeholdery
- I wiele innych...

Zobacz pełną dokumentację w `docx_interpreter.api.Document`.

## Convenience functions

Dla jeszcze prostszego użycia:

```python
from docx_interpreter import render_to_pdf, render_to_html, open_document

# Renderuj bezpośrednio
render_to_pdf('input.docx', 'output.pdf', backend='rust')
render_to_html('input.docx', 'output.html')

# Otwórz dokument
doc = open_document('input.docx')
```

## Uwagi

- Metoda `pipeline()` automatycznie przetwarza dokument jeśli nie został jeszcze przetworzony
- Metody `to_pdf()` i `to_html()` również automatycznie wywołują `pipeline()` jeśli potrzeba
- Pipeline jest cachowany - kolejne wywołania `to_pdf()`/`to_html()` używają tego samego layoutu
- Aby wymusić ponowne przetworzenie, wywołaj `pipeline()` z nowymi parametrami

