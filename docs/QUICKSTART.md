# Quick Start Guide - DocQuill

## 🚀 Szybki Start

### Instalacja

```bash
pip install docx-interpreter
```

### Podstawowe Użycie

```python
from docx_interpreter import Document

# Otwórz dokument
doc = Document.open("template.docx")

# Wypełnij placeholdery (Jinja-like)
doc.fill_placeholders({
    "TEXT:Name": "Jan Kowalski",
    "DATE:IssueDate": "2025-10-16",
    "CURRENCY:Amount": 1500.50
})

# Renderuj do HTML
doc.render_html("output.html")
```

## 📚 Przykłady Użycia

### 1. Otwieranie i Edycja Dokumentu

```python
from docx_interpreter import Document

# Otwórz dokument
doc = Document.open("raport.docx")

# Dodaj paragraf
para = doc.add_paragraph("Nowy tytuł", style="Heading1")

# Dodaj runy z formatowaniem
doc.add_run(para, "bold", bold=True)
doc.add_run(para, " italic", italic=True)
doc.add_run(para, " green", font_color="008000")

# Zastąp tekst
doc.replace_text("2024", "2025")

# Renderuj do HTML
doc.render_html("raport.html")
```

### 2. Wypełnianie Szablonu (Jinja-like)

```python
from docx_interpreter import Document

# Otwórz szablon
doc = Document.open("template.docx")

# Wypełnij placeholdery
doc.fill_placeholders({
    # Podstawowe typy
    "TEXT:Name": "Jan Kowalski",
    "DATE:IssueDate": "2025-10-16",  # → 16.10.2025
    "CURRENCY:Amount": 1500.50,       # → 1 500,50 PLN
    "PHONE:Contact": "123456789",    # → +48 123 456 789
    "EMAIL:Email": "jan@example.com",
    
    # Custom blocks
    "QR:OrderCode": "ORDER-123",      # Generuje QR code
    "TABLE:Items": {
        "headers": ["Product", "Qty", "Price"],
        "rows": [
            ["Laptop", "1", "4500"],
            ["Mouse", "2", "150"]
        ]
    },
    "IMAGE:Logo": "logo.png",
    "LIST:Features": ["Fast", "Reliable", "Secure"]
})

# Conditional blocks
doc.process_conditional_block("SpecialOffer", show=True)
doc.process_conditional_block("Discount", show=False)

# Zapisz
doc.save("filled.docx")
```

### 3. Łączenie Dokumentów

```python
from docx_interpreter import Document

# Pełne scalanie
doc = Document.open("main.docx")
doc.merge("appendix.docx", page_break=True)
doc.save("merged.docx")

# Dodawanie na koniec/początek
doc.append("appendix.docx", page_break=True)
doc.prepend("cover.docx", page_break=True)

# Selektywne scalanie elementów z różnych dokumentów
doc.merge_selective({
    "body": "content.docx",           # Body z tego dokumentu
    "headers": "header_template.docx", # Headers z tego dokumentu
    "footers": "footer_template.docx", # Footers z tego dokumentu
    "styles": "style_template.docx"   # Styles z tego dokumentu
})
```

### 4. Convenience Functions

```python
from docx_interpreter import (
    open_document,
    create_document,
    fill_template,
    merge_documents,
    render_to_html,
    render_to_pdf
)

# Otwórz dokument
doc = open_document("template.docx")

# Utwórz nowy dokument
doc = create_document()
doc.add_paragraph("Tytuł", style="Heading1")

# Wypełnij szablon (jedna linia)
fill_template(
    "template.docx",
    {"TEXT:Name": "Jan Kowalski"},
    "output.docx"
)

# Połącz dokumenty (jedna linia)
merge_documents(
    "main.docx",
    ["appendix1.docx", "appendix2.docx"],
    "merged.docx"
)

# Renderuj do HTML/PDF (jedna linia)
render_to_html("document.docx", "output.html", editable=True)
render_to_pdf("document.docx", "output.pdf")
```

### 5. Tworzenie Dokumentu od Zera

```python
from docx_interpreter import Document

# Utwórz nowy dokument
doc = Document.create()

# Dodaj tytuł
doc.add_paragraph("Raport roczny 2024", style="Heading1")

# Dodaj treść z formatowaniem
para = doc.add_paragraph("Kluczowe metryki: ")
doc.add_run(para, "przychody", bold=True)
doc.add_run(para, " wzrosły o ", italic=True)
doc.add_run(para, "25%", bold=True, font_color="008000")

# Utwórz listę numerowaną
numbered_list = doc.create_numbered_list()
p1 = doc.add_paragraph("Pierwszy punkt")
# TODO: Ustaw numbering na paragrafie

# Utwórz listę punktową
bullet_list = doc.create_bullet_list()
p2 = doc.add_paragraph("Element listy")
# TODO: Ustaw numbering na paragrafie

# Zapisz
doc.save("raport.docx")
```

### 6. Wyciąganie Placeholderów

```python
from docx_interpreter import Document

doc = Document.open("template.docx")

# Wyciągnij wszystkie placeholdery
placeholders = doc.extract_placeholders()

for ph in placeholders:
    print(f"{ph.name} ({ph.type}): {ph.count} wystąpień")
    print(f"  Pozycje: {ph.positions}")
```

### 7. Zaawansowane Scalanie

```python
from docx_interpreter import Document

doc = Document.open("template.docx")

# Scal tylko nagłówki
doc.merge_headers("header_template.docx", header_types=["default", "first"])

# Scal tylko stopki
doc.merge_footers("footer_template.docx", footer_types=["default"])

# Skopiuj właściwości sekcji (marginesy, rozmiar strony)
doc.merge_sections("layout_template.docx", copy_properties=True)

# Scal style
doc.merge_styles("style_template.docx")
```

## 🎯 Typy Placeholderów

| Typ | Przykład | Formatowanie |
|-----|----------|--------------|
| TEXT | `"TEXT:Name"` | Zwykły tekst |
| DATE | `"DATE:IssueDate"` | `16.10.2025` |
| TIME | `"TIME:StartTime"` | `14:30` |
| DATETIME | `"DATETIME:Created"` | `16.10.2025 14:30` |
| CURRENCY | `"CURRENCY:Amount"` | `1 500,50 PLN` |
| NUMBER | `"NUMBER:Count"` | `1 234,56` |
| PERCENT | `"PERCENT:Discount"` | `25.5%` |
| PHONE | `"PHONE:Contact"` | `+48 123 456 789` |
| EMAIL | `"EMAIL:Email"` | `jan@example.com` |
| BOOLEAN | `"BOOLEAN:Active"` | `Tak` / `Nie` |
| QR | `"QR:OrderCode"` | Generuje QR code |
| TABLE | `"TABLE:Items"` | Wstawia tabelę |
| IMAGE | `"IMAGE:Logo"` | Wstawia obraz |
| LIST | `"LIST:Features"` | Wstawia listę |

## 📖 Więcej Informacji

- `docs/MERGER_DOCUMENTATION.md` - Dokumentacja scalania dokumentów
- `docs/MERGER_RELATIONSHIPS.md` - Szczegóły obsługi relacji OPC
- `docs/IMPLEMENTATION_SUMMARY.md` - Pełna lista funkcjonalności

