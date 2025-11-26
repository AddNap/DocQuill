# DocQuill

Zaawansowana biblioteka do manipulacji dokumentami DOCX z funkcjonalnościami Jinja-like i zaawansowanym scalaniem dokumentów.

## ✨ Główne Funkcjonalności

- ✅ **Jinja-like Placeholder System** - 20+ typów placeholderów z automatycznym formatowaniem
- ✅ **Zaawansowane Scalanie Dokumentów** - selektywne łączenie elementów z różnych dokumentów
- ✅ **Obsługa Relacji OPC** - zachowanie wszystkich relacji podczas scalania
- ✅ **Proste API** - intuicyjny interfejs dla użytkowników
- ✅ **Renderowanie** - HTML i PDF (używa istniejących rendererów bez modyfikacji)

## 🚀 Szybki Start

```python
from docx_interpreter import Document

# Otwórz dokument
doc = Document.open("template.docx")

# Wypełnij placeholdery (Jinja-like)
doc.fill_placeholders({
    "TEXT:Name": "Jan Kowalski",
    "DATE:IssueDate": "2025-10-16",
    "CURRENCY:Amount": 1500.50,  # → 1 500,50 PLN
    "PHONE:Contact": "123456789",  # → +48 123 456 789
    "QR:OrderCode": "ORDER-123",
    "TABLE:Items": {
        "headers": ["Product", "Qty", "Price"],
        "rows": [["Laptop", "1", "4500"]]
    }
})

# Renderuj do HTML
doc.render_html("output.html")
```

## 📚 Przykłady

### Tworzenie i Edycja Dokumentów

```python
from docx_interpreter import Document

# Utwórz nowy dokument
doc = Document.create()

# Dodaj paragrafy
doc.add_paragraph("Tytuł dokumentu", style="Heading1")
doc.add_paragraph("Normalny tekst")

# Dodaj paragraf z formatowaniem
para = doc.add_paragraph("Tekst z ")
doc.add_run(para, "pogrubieniem", bold=True)
doc.add_run(para, " i ", italic=False)
doc.add_run(para, "kursywą", italic=True)
doc.add_run(para, " oraz ", underline=False)
doc.add_run(para, "podkreśleniem", underline=True)

# Dodaj kolorowy tekst
para_color = doc.add_paragraph("Kolorowy tekst: ")
doc.add_run(para_color, "zielony", font_color="008000")
doc.add_run(para_color, " i ", font_color=None)
doc.add_run(para_color, "czerwony", font_color="FF0000")

# Zapisz dokument
doc.save("new_document.docx")
```

### Wypełnianie Szablonu

```python
from docx_interpreter import Document

doc = Document.open("template.docx")

# Wypełnij placeholdery (Jinja-like)
doc.fill_placeholders({
    "TEXT:Name": "Jan Kowalski",
    "DATE:IssueDate": "2025-10-16",
    "CURRENCY:Amount": 1500.50,  # → 1 500,50 PLN
    "PHONE:Contact": "123456789",  # → +48 123 456 789
    "QR:OrderCode": "ORDER-123",
    "TABLE:Items": {
        "headers": ["Product", "Qty", "Price"],
        "rows": [
            ["Laptop", "1", "4500"],
            ["Mouse", "2", "50"]
        ]
    },
    "IMAGE:Logo": "logo.png",
    "LIST:Features": ["Feature 1", "Feature 2", "Feature 3"]
})

doc.save("filled.docx")
```

### HTML Workflow (Edycja w Przeglądarce)

```python
from docx_interpreter import Document

# Otwórz dokument
doc = Document.open("template.docx")

# Renderuj do edytowalnego HTML
doc.render_html("editable.html", editable=True)

# ... edycja w przeglądarce (dodawanie tekstu, formatowanie, tabele, obrazy) ...

# Zaktualizuj dokument z edytowanego HTML
doc.update_from_html_file("editable.html", preserve_structure=True)

# Zapisz zaktualizowany dokument
doc.save("updated.docx")
```

### Łączenie Dokumentów

```python
from docx_interpreter import Document

# Pełne scalanie
doc = Document.open("main.docx")
doc.merge("appendix.docx", page_break=True)
doc.save("merged.docx")

# Selektywne scalanie elementów z różnych dokumentów
doc = Document.open("main.docx")
doc.merge_selective({
    "body": Document.open("content.docx"),
    "headers": Document.open("header_template.docx"),
    "footers": Document.open("footer_template.docx"),
    "styles": Document.open("style_template.docx")
})
doc.save("merged_selective.docx")

# Scalanie tylko nagłówków
doc.merge_headers("header_template.docx")

# Scalanie tylko stopek
doc.merge_footers("footer_template.docx")
```

### Renderowanie

```python
from docx_interpreter import Document

doc = Document.open("document.docx")

# Renderuj do HTML (edytowalny)
doc.render_html("output.html", editable=True)

# Renderuj do HTML (tylko do odczytu)
doc.render_html("output_readonly.html", editable=False)

# Renderuj do PDF
doc.render_pdf("output.pdf")
```

### Bloki Warunkowe

```python
from docx_interpreter import Document

doc = Document.open("template.docx")

# Pokaż/ukryj blok warunkowy
# W dokumencie: {{ START_SpecialOffer }}...{{ END_SpecialOffer }}
doc.process_conditional_block("SpecialOffer", show=True)  # Pokaż
doc.process_conditional_block("SpecialOffer", show=False)  # Ukryj

doc.save("processed.docx")
```

### Listy

```python
from docx_interpreter import Document

doc = Document.create()

# Utwórz listę numerowaną
numbered_list = doc.create_numbered_list()
para1 = doc.add_paragraph("Pierwszy element")
para1.set_list(numbered_list, level=0)
para2 = doc.add_paragraph("Drugi element")
para2.set_list(numbered_list, level=0)

# Utwórz listę punktową
bullet_list = doc.create_bullet_list()
para3 = doc.add_paragraph("Element punktowy")
para3.set_list(bullet_list, level=0)

doc.save("lists.docx")
```

### Zastępowanie Tekstu

```python
from docx_interpreter import Document

doc = Document.open("template.docx")

# Zastąp tekst w całym dokumencie
doc.replace_text("Stary tekst", "Nowy tekst")

# Zastąp tylko w body (nie w nagłówkach/stopkach)
doc.replace_text("Stary tekst", "Nowy tekst", scope="body")

# Case-insensitive replacement
doc.replace_text("stary tekst", "Nowy tekst", case_sensitive=False)

doc.save("replaced.docx")
```

### Ekstrakcja Placeholderów

```python
from docx_interpreter import Document

doc = Document.open("template.docx")

# Wyciągnij wszystkie placeholdery z dokumentu
placeholders = doc.extract_placeholders()

for placeholder in placeholders:
    print(f"Typ: {placeholder.type}, Nazwa: {placeholder.name}")
    # Typ: TEXT, Nazwa: Name
    # Typ: DATE, Nazwa: IssueDate
    # ...
```

### Convenience Functions

```python
from docx_interpreter import (
    fill_template, 
    merge_documents, 
    render_to_html,
    render_to_pdf,
    open_document,
    create_document
)

# Wypełnij szablon (jedna linia)
fill_template("template.docx", {"TEXT:Name": "Jan"}, "output.docx")

# Połącz dokumenty (jedna linia)
merge_documents("main.docx", ["appendix1.docx", "appendix2.docx"], "merged.docx")

# Renderuj do HTML (jedna linia)
render_to_html("document.docx", "output.html", editable=True)

# Renderuj do PDF (jedna linia)
render_to_pdf("document.docx", "output.pdf")

# Otwórz dokument (funkcja)
doc = open_document("template.docx")

# Utwórz dokument (funkcja)
doc = create_document()
```

## 🎯 Typy Placeholderów

Biblioteka obsługuje 20+ typów placeholderów z automatycznym formatowaniem:

- **TEXT** - zwykły tekst
- **DATE** - formatowanie dat (16.10.2025)
- **CURRENCY** - formatowanie waluty (1 500,50 PLN)
- **PHONE** - formatowanie telefonów (+48 123 456 789)
- **QR** - generowanie kodów QR
- **TABLE** - wstawianie tabel z nagłówkami i wierszami
- **IMAGE** - wstawianie obrazów
- **LIST** - wstawianie list (numerowanych lub punktowych)
- **CONDITIONAL** - bloki warunkowe (START_/END_)
- ... i wiele innych

### Format Placeholderów

Placeholdery używają formatu: `{{ TYPE:Key }}`

Przykłady:
- `{{ TEXT:Name }}` - zwykły tekst
- `{{ DATE:IssueDate }}` - data
- `{{ CURRENCY:Amount }}` - waluta
- `{{ QR:OrderCode }}` - kod QR
- `{{ TABLE:Items }}` - tabela
- `{{ START_SpecialOffer }}...{{ END_SpecialOffer }}` - blok warunkowy

## 📖 Dokumentacja API

### Główne Metody

#### Tworzenie i Otwieranie
- `Document.open(file_path)` - Otwiera dokument z pliku
- `Document.create()` - Tworzy nowy pusty dokument

#### Dodawanie Zawartości
- `add_paragraph(text, style)` - Dodaje paragraf
- `add_run(paragraph, text, bold, italic, underline, ...)` - Dodaje run z formatowaniem
- `create_numbered_list()` - Tworzy listę numerowaną
- `create_bullet_list()` - Tworzy listę punktową

#### Manipulacja Tekstem
- `replace_text(old, new, scope, case_sensitive)` - Zastępuje tekst
- `fill_placeholders(data, multi_pass)` - Wypełnia placeholdery
- `process_conditional_block(name, show)` - Obsługuje bloki warunkowe

#### Scalanie Dokumentów
- `merge(other, page_break)` - Pełne scalanie dokumentów
- `merge_selective(options)` - Selektywne scalanie elementów
- `merge_headers(source)` - Scalanie nagłówków
- `merge_footers(source)` - Scalanie stopek
- `append(other)` - Dodaje dokument na końcu
- `prepend(other)` - Dodaje dokument na początku

#### Renderowanie
- `render_html(path, editable)` - Renderuje do HTML
- `render_pdf(path)` - Renderuje do PDF
- `update_from_html_file(path, preserve_structure)` - Aktualizuje z HTML

#### Eksport i Zapisywanie
- `save(file_path)` - Zapisuje dokument do DOCX
- `extract_placeholders()` - Wyciąga placeholdery z dokumentu

### Właściwości

- `body` - Dostęp do body dokumentu

## 📖 Dodatkowa Dokumentacja

- [Quick Start Guide](docs/QUICKSTART.md) - Przewodnik szybkiego startu
- [Merger Documentation](docs/MERGER_DOCUMENTATION.md) - Dokumentacja scalania dokumentów
- [Relationships Guide](docs/MERGER_RELATIONSHIPS.md) - Szczegóły obsługi relacji OPC

## 🔧 Instalacja

```bash
pip install docx-interpreter
```

## 📝 Licencja

MIT License

