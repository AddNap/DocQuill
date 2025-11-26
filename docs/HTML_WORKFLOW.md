# HTML Workflow - Dwukierunkowa Konwersja DOCX ↔ HTML

## Przegląd

Biblioteka obsługuje pełną dwukierunkową konwersję między DOCX a HTML z możliwością edycji w przeglądarce.

## Funkcjonalności

### 1. Renderowanie DOCX → HTML (edytowalne)

```python
from docx_interpreter import Document

# Otwórz dokument
doc = Document.open("template.docx")

# Renderuj do HTML z możliwością edycji
doc.render_html("editable.html", editable=True)
```

**Funkcje:**
- ✅ Contenteditable paragrafy
- ✅ Zachowanie formatowania (bold, italic, underline)
- ✅ Automatyczne zapisywanie do localStorage
- ✅ Skróty klawiszowe (Ctrl+B, Ctrl+I, Ctrl+U)
- ✅ Wizualne wskaźniki edycji

### 2. Aktualizacja DOCX z HTML

```python
# Po edycji w przeglądarce, zaktualizuj dokument
doc.update_from_html_file("editable.html")
doc.save("updated.docx")
```

**Opcje:**
- `preserve_structure=True` (domyślnie) - zachowuje tabele, obrazy i inne elementy
- `preserve_structure=False` - zastępuje całą zawartość body

## Przykład użycia

### Pełny workflow

```python
from docx_interpreter import Document

# 1. Otwórz dokument DOCX
doc = Document.open("template.docx")

# 2. Renderuj do edytowalnego HTML
doc.render_html("editable.html", editable=True)

# 3. Użytkownik edytuje w przeglądarce
# - Może używać Ctrl+B/I/U do formatowania
# - Zmiany są automatycznie zapisywane w localStorage
# - Po zakończeniu edycji, zapisuje plik HTML

# 4. Zaktualizuj dokument z edytowanego HTML
doc.update_from_html_file("editable.html", preserve_structure=True)

# 5. Zapisz zaktualizowany dokument
doc.save("updated.docx")
```

## Format HTML

### Struktura edytowalnego HTML

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Document</title>
    <style>
        /* Style dla contenteditable */
    </style>
</head>
<body>
    <p contenteditable="true" data-para-id="0">
        <strong>Bold text</strong> and <em>italic</em> and <u>underlined</u>
    </p>
    <p contenteditable="true" data-para-id="1">
        Normal text
    </p>
    <script>
        /* JavaScript do zapisywania zmian */
    </script>
</body>
</html>
```

### Obsługiwane tagi formatowania

- `<strong>` lub `<b>` - **bold**
- `<em>` lub `<i>` - *italic*
- `<u>` - <u>underline</u>

## Parser HTML

### HTMLParser

```python
from docx_interpreter.parser.html_parser import HTMLParser

# Parsuj HTML z pliku
paragraphs = HTMLParser.parse_file("editable.html")

# Parsuj HTML z stringa
parser = HTMLParser(html_content)
paragraphs = parser.parse()
```

**Zwraca:**
```python
[
    {
        'text': 'Full paragraph text',
        'runs': [
            {'text': 'Bold text', 'bold': True},
            {'text': ' and ', 'bold': False},
            {'text': 'italic', 'italic': True},
        ]
    },
    # ...
]
```

## Zachowanie formatowania

### Podczas renderowania DOCX → HTML

- Bold runs → `<strong>` lub `<b>`
- Italic runs → `<em>` lub `<i>`
- Underline runs → `<u>`
- Kombinacje formatowania są zachowane

### Podczas parsowania HTML → DOCX

- `<strong>`/`<b>` → `run.bold = True`
- `<em>`/`<i>` → `run.italic = True`
- `<u>` → `run.underline = True`
- Tekst bez tagów → zwykły run

## Ograniczenia

### Obecne ograniczenia

- ⚠️ Obsługuje tylko podstawowe formatowanie (bold, italic, underline)
- ⚠️ Nie obsługuje kolorów, rozmiarów czcionek, stylów paragrafów
- ⚠️ Nie obsługuje tabel i obrazów w edytowalnym HTML
- ⚠️ Nie obsługuje list numerowanych/punktowanych

### Planowane ulepszenia

- [ ] Obsługa kolorów tekstu
- [ ] Obsługa rozmiarów czcionek
- [ ] Obsługa stylów paragrafów (wyrównanie, wcięcia)
- [ ] Obsługa tabel w edytowalnym HTML
- [ ] Obsługa obrazów w edytowalnym HTML
- [ ] Obsługa list

## API Reference

### Document.render_html()

```python
def render_html(
    self,
    output_path: Union[str, Path],
    editable: bool = False
) -> None
```

Renderuje dokument do HTML.

**Parametry:**
- `output_path`: Ścieżka do pliku wyjściowego HTML
- `editable`: Czy HTML ma być edytowalny (contenteditable)

### Document.update_from_html_file()

```python
def update_from_html_file(
    self,
    html_path: Union[str, Path],
    preserve_structure: bool = True
) -> None
```

Aktualizuje dokument na podstawie edytowanego pliku HTML.

**Parametry:**
- `html_path`: Ścieżka do pliku HTML z edytowaną zawartością
- `preserve_structure`: Czy zachować strukturę dokumentu (tabele, obrazy, etc.)

## Przykłady

### Przykład 1: Prosta edycja tekstu

```python
from docx_interpreter import Document

doc = Document.open("letter.docx")
doc.render_html("letter_editable.html", editable=True)
# Edytuj w przeglądarce...
doc.update_from_html_file("letter_editable.html")
doc.save("letter_updated.docx")
```

### Przykład 2: Edycja z zachowaniem struktury

```python
from docx_interpreter import Document

doc = Document.open("report.docx")
# Dokument zawiera tabele i obrazy
doc.render_html("report_editable.html", editable=True)
# Edytuj tylko tekst, tabele i obrazy pozostaną
doc.update_from_html_file("report_editable.html", preserve_structure=True)
doc.save("report_updated.docx")
```

### Przykład 3: Pełna zamiana zawartości

```python
from docx_interpreter import Document

doc = Document.open("template.docx")
doc.render_html("new_content.html", editable=True)
# Zastąp całą zawartość nowym HTML
doc.update_from_html_file("new_content.html", preserve_structure=False)
doc.save("new_document.docx")
```

