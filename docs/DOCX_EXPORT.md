# DOCX Export - Tworzenie Plików DOCX

## 📋 Przegląd

`DOCXExporter` tworzy pliki DOCX z modeli dokumentów. Wykorzystuje istniejący `XMLExporter` do generowania WordML XML i pakuje wszystko do pakietu DOCX (ZIP) z relacjami i [Content_Types].xml.

## 🚀 Szybki Start

```python
from docx_interpreter import Document
from docx_interpreter.export.docx_exporter import DOCXExporter

# Otwórz dokument
doc = Document.open("template.docx")

# Wypełnij placeholdery
doc.fill_placeholders({
    "TEXT:Name": "Jan Kowalski",
    "DATE:IssueDate": "2025-10-16"
})

# Zapisz do DOCX
doc.save("output.docx")

# Lub bezpośrednio używając DOCXExporter
exporter = DOCXExporter(doc._document_model)
exporter.export("output.docx")
```

## ✅ Co Jest Obsługiwane

### 1. Generowanie document.xml
- Używa `XMLExporter` do generowania WordML XML z modeli
- Eksportuje paragrafy, tabele, formatowanie
- Zachowuje strukturę dokumentu

### 2. Generowanie Części z Modeli Dokumentu
- ✅ `styles.xml` - **generowane z modeli** używając `StyleNormalizer` z `normalize.py`
  - Automatyczne wykrywanie i grupowanie identycznych stylów paragrafów i runów
  - Zachowanie podstawowych stylów (Normal, Heading1, etc.)
  - Tworzenie nowych stylów dla unikalnych kombinacji formatowania
- ✅ `numbering.xml` - **generowane z modeli** używając `NumberingNormalizer` z `normalize.py`
  - Automatyczne wykrywanie i normalizacja numeracji list
  - Zachowanie poziomów i formatowania numeracji
  - Tworzenie nowych definicji numeracji dla używanych list
- `settings.xml` - kopiowane z oryginalnego dokumentu (jeśli istnieje)
- Headers i footers z relacjami

### 3. Kopiowanie Media
- Obrazy (PNG, JPG, GIF, BMP)
- Automatyczne wykrywanie typów zawartości
- Zachowanie relacji do obrazów

### 4. Generowanie Relacji
- Główne relacje (`_rels/.rels`)
- Relacje dokumentu (`word/_rels/document.xml.rels`)
- Relacje headers/footers
- Automatyczne generowanie ID relacji

### 5. Generowanie [Content_Types].xml
- Domyślne typy zawartości dla rozszerzeń
- Override dla konkretnych części
- Automatyczne wykrywanie typów

## 📝 Przykłady

### Przykład 1: Podstawowy Eksport

```python
from docx_interpreter import Document

doc = Document.open("template.docx")
doc.fill_placeholders({"TEXT:Name": "Jan"})
doc.save("output.docx")
```

### Przykład 2: Bezpośrednie Użycie DOCXExporter

```python
from docx_interpreter.export.docx_exporter import DOCXExporter

# Masz już model dokumentu
exporter = DOCXExporter(document_model)
exporter.export("output.docx")
```

### Przykład 3: Eksport z Edycją

```python
from docx_interpreter import Document

doc = Document.open("template.docx")

# Edytuj dokument
doc.add_paragraph("Nowy paragraf", style="Heading1")
doc.replace_text("stary", "nowy")

# Zapisz
doc.save("edited.docx")
```

## 🔧 Szczegóły Implementacji

### Struktura Pakietu DOCX

```
output.docx (ZIP)
├── [Content_Types].xml
├── _rels/
│   └── .rels
├── word/
│   ├── document.xml
│   ├── styles.xml
│   ├── numbering.xml
│   ├── settings.xml
│   ├── media/
│   │   └── image1.png
│   ├── header1.xml
│   ├── footer1.xml
│   └── _rels/
│       ├── document.xml.rels
│       ├── header1.xml.rels
│       └── footer1.xml.rels
```

### Proces Eksportu

1. **Przygotowanie części** (`_prepare_parts()`)
   - Generowanie `document.xml` przez XMLExporter
   - Kopiowanie `styles.xml`, `numbering.xml`, `settings.xml`
   - Kopiowanie media (obrazy)
   - Kopiowanie headers/footers

2. **Przygotowanie relacji** (`_prepare_relationships()`)
   - Główne relacje (`_rels/.rels`)
   - Relacje dokumentu (`word/_rels/document.xml.rels`)
   - Relacje headers/footers

3. **Przygotowanie [Content_Types].xml** (`_prepare_content_types()`)
   - Domyślne typy dla rozszerzeń
   - Override dla konkretnych części

4. **Zapis pakietu** (`_write_package()`)
   - Tworzenie ZIP
   - Zapis wszystkich części
   - Zapis relacji
   - Zapis [Content_Types].xml

## ⚠️ Ograniczenia

### Obecne Ograniczenia:
1. **Kopiowanie zamiast generowania**
   - `styles.xml`, `numbering.xml` są kopiowane z oryginalnego dokumentu
   - Nie są generowane z modeli (wymagałoby pełnej implementacji eksportu stylów)

2. **Relacje**
   - Relacje są kopiowane z oryginalnego dokumentu
   - Nowe relacje (np. dla nowych obrazów) wymagają ręcznego dodania

3. **Headers/Footers**
   - Headers/footers są kopiowane z oryginalnego dokumentu
   - Edycja headers/footers wymaga modyfikacji XML bezpośrednio

### Planowane Ulepszenia:
- Generowanie `styles.xml` z modeli stylów
- Generowanie `numbering.xml` z modeli numeracji
- Automatyczne tworzenie relacji dla nowych elementów
- Edycja headers/footers przez API

## 🔗 Związane Moduły

- `docx_interpreter.export.xml_exporter.XMLExporter` - Generowanie WordML XML
- `docx_interpreter.parser.package_reader.PackageReader` - Czytanie pakietów DOCX
- `docx_interpreter.document_api.Document` - Wysokopoziomowe API dokumentu

