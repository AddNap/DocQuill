# Relationship Merger - Obsługa Relacji OPC podczas Scalania

## 📋 Przegląd

`RelationshipMerger` zarządza wszystkimi relacjami OPC podczas scalania dokumentów DOCX. Zapewnia, że wszystkie zależności są zachowane i poprawnie zaktualizowane.

## 🔗 Co to są Relacje OPC?

W formacie DOCX (OOXML), dokumenty są pakietami ZIP zawierającymi:
- **Części (Parts)** - pliki XML i binarne (document.xml, styles.xml, obrazy, etc.)
- **Relacje (Relationships)** - pliki `.rels` określające zależności między częściami
- **[Content_Types].xml** - określa typy zawartości dla każdej części

### Przykład Relacji:

```xml
<!-- word/_rels/document.xml.rels -->
<Relationships>
  <Relationship 
    Id="rId1" 
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
    Target="media/image1.png"/>
  <Relationship 
    Id="rId2" 
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header"
    Target="header1.xml"/>
</Relationships>
```

W `document.xml` obrazy są referencowane przez `r:id`:
```xml
<w:drawing>
  <wp:inline>
    <a:graphic>
      <a:graphicData>
        <pic:pic>
          <pic:blipFill>
            <a:blip r:embed="rId1"/>  <!-- Relacja do obrazu -->
          </pic:blipFill>
        </pic:pic>
      </a:graphicData>
    </a:graphic>
  </wp:inline>
</w:drawing>
```

## ✅ Co RelationshipMerger Obsługuje

### 1. Kopiowanie Części z Relacjami

```python
from docx_interpreter.merger.relationship_merger import RelationshipMerger

merger = RelationshipMerger(target_reader, source_reader)

# Skopiuj część wraz z wszystkimi relacjami
new_path, rel_mapping = merger.copy_part_with_relationships(
    "word/media/image1.png",
    "word/media/image1.png"  # Ta sama ścieżka lub nowa
)

# rel_mapping zawiera: {"rId1": "rId5"} - mapping stary_id -> nowy_id
```

### 2. Kopiowanie Media z Relacjami

```python
# Skopiuj obraz wraz z relacjami i zwróć nowy rel_id
new_rel_id = merger.copy_media_with_relationships(
    "rId1",  # Stary rel_id w dokumencie źródłowym
    "document"  # Część źródłowa
)
# Zwraca nowy rel_id w dokumencie docelowym
```

### 3. Aktualizacja rel_id w XML

```python
# Aktualizuj rel_id w zawartości XML
updated_xml = merger.update_relationship_ids_in_xml(
    xml_content,
    "document",
    {"rId1": "rId5", "rId2": "rId6"}  # Mapping relacji
)
```

### 4. Aktualizacja [Content_Types].xml

```python
# Automatycznie aktualizuje [Content_Types].xml dla wszystkich skopiowanych części
merger.update_content_types()
```

## 🔄 Przepływ Scalania z Relacjami

```
1. DocumentMerger.merge_full()
   ↓
2. RelationshipMerger inicjalizacja
   ↓
3. Kopiowanie części (parts):
   - document.xml
   - styles.xml
   - media/image1.png
   - header1.xml
   ↓
4. Kopiowanie relacji:
   - word/_rels/document.xml.rels
   - word/_rels/header1.xml.rels
   ↓
5. Aktualizacja rel_id w XML:
   - rId1 → rId5 (nowy ID)
   - rId2 → rId6 (nowy ID)
   ↓
6. Aktualizacja [Content_Types].xml
   ↓
7. Zapisanie zaktualizowanych części do pakietu docelowego
```

## 💡 Przykłady Użycia

### Przykład 1: Scalanie Dokumentów z Obrazami

```python
from docx_interpreter.document_api import Document
from docx_interpreter.merger import DocumentMerger, MergeOptions

# Otwórz dokumenty
target_doc = Document.open("template.docx")  # Ma logo w header
source_doc = Document.open("content.docx")   # Ma obrazy w body

# Scal dokumenty - RelationshipMerger automatycznie:
# 1. Kopiuje obrazy z obu dokumentów
# 2. Aktualizuje rel_id w document.xml
# 3. Aktualizuje pliki .rels
# 4. Aktualizuje [Content_Types].xml
merger = DocumentMerger(target_doc)
merger.merge_full(source_doc, MergeOptions(merge_media=True))
```

### Przykład 2: Selektywne Scalanie z Relacjami

```python
doc = Document.open("template.docx")

# Scal body z obrazami - RelationshipMerger kopiuje obrazy wraz z relacjami
doc.merge_selective({
    "body": "content_with_images.docx",  # Ma obrazy
    "headers": "header_with_logo.docx"   # Ma logo w header
})

# Wszystkie obrazy są skopiowane wraz z relacjami
# Wszystkie r:id są zaktualizowane
```

### Przykład 3: Bezpośrednie Użycie RelationshipMerger

```python
from docx_interpreter.parser.package_reader import PackageReader
from docx_interpreter.merger.relationship_merger import RelationshipMerger

target_reader = PackageReader("target.docx")
source_reader = PackageReader("source.docx")

merger = RelationshipMerger(target_reader, source_reader)

# Skopiuj obraz wraz z relacjami
new_rel_id = merger.copy_media_with_relationships("rId1", "document")

# Zaktualizuj [Content_Types].xml
merger.update_content_types()
```

## 🔧 Szczegóły Implementacji

### Mapping Relacji

RelationshipMerger utrzymuje mappingi:
- `relationship_id_mapping`: `{source_part: {old_id: new_id}}`
- `part_path_mapping`: `{old_path: new_path}`
- `copied_parts`: Set skopiowanych części

### Generowanie Nowych ID

Nowe ID relacji są generowane sekwencyjnie:
- `rId1`, `rId2`, `rId3`, etc.
- Dla każdego źródła (document, header1, etc.) osobny licznik

### Aktualizacja XML

Relacje są aktualizowane w:
- `r:embed` - embedded content (obrazy)
- `r:link` - linked content
- `r:id` - general relationship ID
- `w:anchor` - anchored elements

## ⚠️ Uwagi

1. **Wymaga PackageReader** - RelationshipMerger wymaga dostępu do PackageReader dla obu dokumentów
2. **Zapis do pakietu** - Pełna implementacja wymaga PackageWriter do zapisu części do pakietu docelowego
3. **Relacje zewnętrzne** - Relacje zewnętrzne (TargetMode="External") są kopiowane bez zmian
4. **Konflikty ścieżek** - Jeśli część już istnieje w dokumencie docelowym, może być nadpisana lub zmieniona ścieżka

## 📚 Związane Moduły

- `docx_interpreter.parser.package_reader.PackageReader` - Czytanie pakietów DOCX
- `docx_interpreter.parser.relationships.RelationshipManager` - Zarządzanie relacjami
- `docx_interpreter.merger.DocumentMerger` - Główny merger dokumentów

