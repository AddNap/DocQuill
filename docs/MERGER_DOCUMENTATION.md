# Document Merger - Zaawansowane Scalanie Dokumentów DOCX

## 📋 Przegląd

`DocumentMerger` to zaawansowany system scalania dokumentów DOCX, który pozwala na:
- ✅ Pełne scalanie dokumentów (jak docx-compose)
- ✅ Selektywne łączenie elementów z różnych dokumentów
- ✅ Rozwiązywanie konfliktów stylów i numeracji
- ✅ Kontrola nad każdym aspektem scalania

## 🚀 Szybki Start

### Podstawowe użycie - Pełne scalanie

```python
from docx_interpreter.document_api import Document
from docx_interpreter.merger import MergeOptions

# Otwórz dokumenty
target_doc = Document.open("template.docx")
source_doc = Document.open("content.docx")

# Scal całe dokumenty
target_doc.merge(source_doc, page_break=True)

# Lub użyj DocumentMerger bezpośrednio
from docx_interpreter.merger import DocumentMerger

merger = DocumentMerger(target_doc)
merger.merge_full(source_doc, MergeOptions(page_break=True))
```

### Zaawansowane użycie - Selektywne scalanie

```python
from docx_interpreter.document_api import Document

# Otwórz główny dokument
doc = Document.open("template.docx")

# Scal elementy z różnych dokumentów
doc.merge_selective({
    "body": "content.docx",           # Body z tego dokumentu
    "headers": "header_template.docx", # Headers z tego dokumentu
    "footers": "footer_template.docx", # Footers z tego dokumentu
    "sections": "layout.docx",        # Sections (marginesy, rozmiar strony) z tego
    "styles": "style_template.docx"   # Styles z tego dokumentu
})
```

## 📚 API Reference

### DocumentMerger

#### `merge_full(source_document, options=None)`

Łączy cały dokument z dokumentem źródłowym.

**Parametry:**
- `source_document`: Dokument źródłowy (Document, ścieżka, lub Path)
- `options`: Opcje scalania (MergeOptions)

**Przykład:**
```python
merger = DocumentMerger(target_doc)
merger.merge_full(source_doc, MergeOptions(page_break=True))
```

#### `merge_body(source_document, options=None, position="append")`

Łączy tylko body (paragrafy, tabele) z dokumentu źródłowego.

**Parametry:**
- `source_document`: Dokument źródłowy
- `options`: Opcje scalania
- `position`: Pozycja dodania ("append", "prepend", "insert")

**Przykład:**
```python
# Dodaj body na koniec
merger.merge_body(source_doc, MergeOptions(page_break=True), position="append")

# Dodaj body na początku
merger.merge_body(source_doc, MergeOptions(), position="prepend")
```

#### `merge_headers(source_document, options=None, header_types=None)`

Łączy nagłówki z dokumentu źródłowego.

**Parametry:**
- `source_document`: Dokument źródłowy
- `options`: Opcje scalania
- `header_types`: Lista typów nagłówków do scalenia (None = wszystkie)
  - Możliwe wartości: `"default"`, `"first"`, `"even"`, `"odd"`

**Przykład:**
```python
# Scal tylko default header
merger.merge_headers(source_doc, header_types=["default"])

# Scal wszystkie nagłówki
merger.merge_headers(source_doc)
```

#### `merge_footers(source_document, options=None, footer_types=None)`

Łączy stopki z dokumentu źródłowego.

**Parametry:**
- `source_document`: Dokument źródłowy
- `options`: Opcje scalania
- `footer_types`: Lista typów stopek do scalenia (None = wszystkie)
  - Możliwe wartości: `"default"`, `"first"`, `"even"`, `"odd"`

**Przykład:**
```python
# Scal tylko default footer
merger.merge_footers(source_doc, footer_types=["default"])

# Scal wszystkie stopki
merger.merge_footers(source_doc)
```

#### `merge_sections(source_document, options=None, copy_properties=True)`

Łączy sekcje z dokumentu źródłowego (właściwości strony, marginesy).

**Parametry:**
- `source_document`: Dokument źródłowy
- `options`: Opcje scalania
- `copy_properties`: Czy kopiować właściwości sekcji (rozmiar strony, marginesy, kolumny)

**Przykład:**
```python
# Skopiuj właściwości sekcji (marginesy, rozmiar strony)
merger.merge_sections(source_doc, copy_properties=True)
```

#### `merge_styles(source_document, options=None)`

Łączy style z dokumentu źródłowego, rozwiązując konflikty.

**Parametry:**
- `source_document`: Dokument źródłowy
- `options`: Opcje scalania

**Przykład:**
```python
merger.merge_styles(source_doc)
```

#### `merge_numbering(source_document, options=None)`

Łączy numerację z dokumentu źródłowego, rozwiązując konflikty.

**Parametry:**
- `source_document`: Dokument źródłowy
- `options`: Opcje scalania

**Przykład:**
```python
merger.merge_numbering(source_doc)
```

#### `merge_selective(sources, options=None)`

Zaawansowane selektywne łączenie elementów z różnych dokumentów.

**Parametry:**
- `sources`: Słownik określający źródła dla każdego elementu:
  ```python
  {
      "body": source_doc1,      # Body z tego dokumentu
      "headers": source_doc2,    # Headers z tego dokumentu
      "footers": source_doc3,    # Footers z tego dokumentu
      "sections": source_doc4,   # Sections z tego dokumentu
      "styles": source_doc5,     # Styles z tego dokumentu
      "numbering": source_doc6,  # Numbering z tego dokumentu
      "media": source_doc7       # Media z tego dokumentu
  }
  ```
- `options`: Opcje scalania

**Przykład:**
```python
merger.merge_selective({
    "body": "content.docx",
    "headers": "header_template.docx",
    "footers": "footer_template.docx",
    "styles": "style_template.docx"
}, MergeOptions(page_break=True))
```

### MergeOptions

Klasa opcji scalania dokumentów.

**Parametry:**
- `page_break`: Czy dodać podział strony przed scalonymi elementami (domyślnie: False)
- `resolve_style_conflicts`: Czy automatycznie rozwiązywać konflikty stylów (domyślnie: True)
- `resolve_numbering_conflicts`: Czy automatycznie rozwiązywać konflikty numeracji (domyślnie: True)
- `preserve_formatting`: Czy zachować formatowanie (domyślnie: True)
- `merge_media`: Czy łączyć media (obrazy, etc.) (domyślnie: True)

**Przykład:**
```python
options = MergeOptions(
    page_break=True,
    resolve_style_conflicts=True,
    resolve_numbering_conflicts=True,
    preserve_formatting=True,
    merge_media=True
)
```

## 💡 Przykłady Użycia

### Przykład 1: Pełne scalanie dokumentów

```python
from docx_interpreter.document_api import Document

# Otwórz dokumenty
main_doc = Document.open("main.docx")
appendix_doc = Document.open("appendix.docx")

# Dodaj appendix na koniec z podziałem strony
main_doc.append(appendix_doc, page_break=True)

# Dodaj cover na początku
cover_doc = Document.open("cover.docx")
main_doc.prepend(cover_doc, page_break=True)
```

### Przykład 2: Selektywne scalanie elementów

```python
from docx_interpreter.document_api import Document

# Otwórz główny dokument
doc = Document.open("template.docx")

# Scal elementy z różnych dokumentów
doc.merge_selective({
    "body": "content.docx",              # Treść z tego dokumentu
    "headers": "corporate_header.docx",  # Nagłówki firmowe
    "footers": "legal_footer.docx",      # Stopki prawne
    "styles": "brand_styles.docx"        # Style marki
})
```

### Przykład 3: Scalanie tylko nagłówków i stopek

```python
from docx_interpreter.document_api import Document

doc = Document.open("content.docx")

# Dodaj nagłówki z template
doc.merge_headers("header_template.docx", header_types=["default", "first"])

# Dodaj stopki z template
doc.merge_footers("footer_template.docx", footer_types=["default"])
```

### Przykład 4: Kopiowanie właściwości sekcji

```python
from docx_interpreter.document_api import Document

doc = Document.open("content.docx")

# Skopiuj marginesy i rozmiar strony z layout template
doc.merge_sections("layout_template.docx", copy_properties=True)
```

### Przykład 5: Zaawansowane scalanie z opcjami

```python
from docx_interpreter.document_api import Document
from docx_interpreter.merger import DocumentMerger, MergeOptions

doc = Document.open("template.docx")
merger = DocumentMerger(doc)

# Utwórz opcje scalania
options = MergeOptions(
    page_break=True,
    resolve_style_conflicts=True,
    resolve_numbering_conflicts=True,
    preserve_formatting=True,
    merge_media=True
)

# Scal body z content.docx
merger.merge_body("content.docx", options, position="append")

# Scal style z style_template.docx
merger.merge_styles("style_template.docx", options)
```

## 🎯 Różnice w stosunku do docx-compose

| Funkcjonalność | docx-compose | DocumentMerger |
|----------------|--------------|----------------|
| Pełne scalanie dokumentów | ✅ | ✅ |
| Selektywne scalanie body | ❌ | ✅ |
| Selektywne scalanie headers | ❌ | ✅ |
| Selektywne scalanie footers | ❌ | ✅ |
| Scalanie sekcji | ❌ | ✅ |
| Scalanie stylów | ⚠️ Podstawowe | ✅ Zaawansowane |
| Scalanie numeracji | ⚠️ Podstawowe | ✅ Zaawansowane |
| Rozwiązywanie konfliktów | ⚠️ Podstawowe | ✅ Zaawansowane |
| Kontrola opcji scalania | ❌ | ✅ |

## 🔗 Obsługa Relacji OPC

DocumentMerger **zachowuje wszystkie relacje OPC** podczas scalania dokumentów:

### ✅ Co jest obsługiwane:

1. **Kopiowanie części (parts)** - Wszystkie części są kopiowane wraz z relacjami
2. **Aktualizacja plików .rels** - Relacje są aktualizowane w plikach `word/_rels/*.rels`
3. **Aktualizacja [Content_Types].xml** - Typy zawartości są automatycznie aktualizowane
4. **Aktualizacja rel_id** - Wszystkie `r:id` w XML są aktualizowane do nowych wartości
5. **Kopiowanie media** - Obrazy i inne media są kopiowane wraz z relacjami
6. **Relacje headers/footers** - Relacje w nagłówkach i stopkach są zachowane

### Przykład z relacjami:

```python
from docx_interpreter.document_api import Document
from docx_interpreter.merger import DocumentMerger, MergeOptions

# Otwórz dokumenty (automatycznie ładuje PackageReader z relacjami)
target_doc = Document.open("template.docx")  # Ma obrazy w header
source_doc = Document.open("content.docx")    # Ma obrazy w body

# Scal dokumenty - wszystkie relacje są automatycznie obsługiwane
merger = DocumentMerger(target_doc)
merger.merge_full(source_doc, MergeOptions(merge_media=True))

# Obrazy z obu dokumentów są skopiowane wraz z relacjami
# Wszystkie r:id są zaktualizowane
# [Content_Types].xml jest zaktualizowany
```

## 📝 Uwagi

1. **Renderery pozostają bez zmian** - DocumentMerger nie modyfikuje istniejących rendererów
2. **Używa istniejących modeli** - Wykorzystuje Paragraph, Run, Table, Header, Footer, Section
3. **Głębokie kopiowanie** - Wszystkie elementy są głęboko kopiowane, aby uniknąć problemów z referencjami
4. **Rozwiązywanie konfliktów** - Automatyczne rozwiązywanie konfliktów stylów i numeracji
5. **Zachowanie relacji OPC** - Wszystkie relacje są zachowane i aktualizowane podczas scalania
6. **Kopiowanie części** - Wszystkie części (XML, obrazy, etc.) są kopiowane wraz z relacjami

## 🔗 Związane Moduły

- `docx_interpreter.document_api.Document` - Wysokopoziomowe API dokumentu
- `docx_interpreter.models` - Modele dokumentów
- `docx_interpreter.layout` - Layout (sections, headers, footers)

