# Kod migracyjny - Funkcja `_resolve_effective_indent()`

## 📝 Funkcja do dodania do obecnej wersji

Poniżej znajduje się funkcja `_resolve_effective_indent()` ze starej wersji, dostosowana do obecnej struktury danych:

```python
def _resolve_effective_indent(self, paragraph, indent_type: str):
    """
    Rozwiązuje efektywne wcięcie zgodnie z hierarchią DOCX (Word):
    
    1. Direct formatting (pPr/ind w akapicie) - najwyższy priorytet
    2. Numbering level properties (dla list - NADPISUJE style!)
    3. Style properties
    4. Default (None)
    
    Args:
        paragraph: Akapit
        indent_type: Typ wcięcia ('left_indent', 'right_indent', 'first_line_indent', 'hanging_indent')
        
    Returns:
        Wartość wcięcia w twips lub None
    """
    # Mapowanie nazw dla różnych formatów danych
    indent_map = {
        'left_indent': 'left',
        'right_indent': 'right',
        'first_line_indent': 'firstLine',
        'hanging_indent': 'hanging'
    }
    
    style_key = indent_map.get(indent_type, indent_type)
    
    # 1. Direct formatting - najwyższy priorytet (ZAWSZE)
    # Sprawdź properties bezpośrednio w akapicie
    if hasattr(paragraph, 'properties') and paragraph.properties:
        direct_value = getattr(paragraph.properties, indent_type, None)
        if direct_value is not None:
            return direct_value
    
    # Alternatywnie sprawdź style dict jeśli properties nie istnieje
    if hasattr(paragraph, 'get_style'):
        style = paragraph.get_style() or {}
        if "indent" in style and style["indent"]:
            indent = style["indent"]
            if style_key in indent:
                value = indent[style_key]
                if value:
                    try:
                        return int(value)
                    except (ValueError, TypeError):
                        pass
    
    # 2. Numbering level properties (NADPISUJE style dla list!)
    # Word: jeśli akapit ma numerację, wcięcia z poziomu listy nadpisują styl
    has_numbering = False
    numbering_id = None
    numbering_level = 0
    
    # Sprawdź czy akapit ma numerację
    if hasattr(paragraph, 'get_style'):
        style = paragraph.get_style() or {}
        if "numbering" in style and style["numbering"]:
            numbering = style["numbering"]
            if "id" in numbering and numbering["id"] != "0":
                has_numbering = True
                numbering_id = numbering["id"]
                numbering_level = int(numbering.get("level", "0"))
    elif hasattr(paragraph, 'properties') and paragraph.properties:
        if hasattr(paragraph.properties, 'numbering_id') and paragraph.properties.numbering_id:
            has_numbering = True
            numbering_id = paragraph.properties.numbering_id
            numbering_level = getattr(paragraph.properties, 'numbering_level', 0) or 0
    
    if has_numbering and numbering_id:
        # Pobierz instancję numeracji z dokumentu
        try:
            # Różne sposoby dostępu do numbering w zależności od struktury dokumentu
            if hasattr(self.document, 'numbering'):
                numbering_obj = self.document.numbering
                if hasattr(numbering_obj, '_numbering_instances'):
                    numbering_instance = numbering_obj._numbering_instances.get(int(numbering_id))
                    if numbering_instance:
                        abstract_num_id = getattr(numbering_instance, 'abstract_num_id', None)
                        if abstract_num_id and hasattr(numbering_obj, '_abstract_numberings'):
                            abstract_num = numbering_obj._abstract_numberings.get(abstract_num_id)
                            if abstract_num and hasattr(abstract_num, 'levels') and abstract_num.levels:
                                if numbering_level < len(abstract_num.levels):
                                    level_obj = abstract_num.levels[numbering_level]
                                    
                                    # Pobierz wcięcie z poziomu numeracji
                                    if indent_type == 'left_indent' and hasattr(level_obj, 'left_indent'):
                                        if level_obj.left_indent is not None:
                                            return level_obj.left_indent
                                    elif indent_type == 'hanging_indent' and hasattr(level_obj, 'hanging_indent'):
                                        if level_obj.hanging_indent is not None:
                                            return level_obj.hanging_indent
                                    elif indent_type == 'first_line_indent' and hasattr(level_obj, 'first_line_indent'):
                                        if level_obj.first_line_indent is not None:
                                            return level_obj.first_line_indent
        except (AttributeError, KeyError, TypeError):
            # Jeśli nie można pobrać z numbering, kontynuuj do stylów
            pass
    
    # 3. Style properties (niższy priorytet niż lista)
    if hasattr(paragraph, 'get_style'):
        style = paragraph.get_style() or {}
        if "indent" in style and style["indent"]:
            indent = style["indent"]
            if style_key in indent:
                value = indent[style_key]
                if value:
                    try:
                        return int(value)
                    except (ValueError, TypeError):
                        pass
    
    # Alternatywnie sprawdź przez properties.style_id
    if hasattr(paragraph, 'properties') and paragraph.properties:
        if hasattr(paragraph.properties, 'style_id') and paragraph.properties.style_id:
            try:
                if hasattr(self.document, 'styles'):
                    style_obj = self.document.styles.get_style(paragraph.properties.style_id)
                    if style_obj and hasattr(style_obj, 'paragraph_properties'):
                        if style_obj.paragraph_properties:
                            # Sprawdź czy styl ma wcięcie jako osobny klucz
                            style_value = style_obj.paragraph_properties.get(indent_type)
                            if style_value is not None:
                                try:
                                    return int(style_value)
                                except (ValueError, TypeError):
                                    pass
                            
                            # Fallback: sprawdź czy styl ma ind jako dict
                            ind_props = style_obj.paragraph_properties.get('ind')
                            if isinstance(ind_props, dict):
                                if indent_type == 'left_indent':
                                    style_value = ind_props.get('left')
                                elif indent_type == 'right_indent':
                                    style_value = ind_props.get('right')
                                elif indent_type == 'first_line_indent':
                                    style_value = ind_props.get('firstLine')
                                elif indent_type == 'hanging_indent':
                                    style_value = ind_props.get('hanging')
                                
                                if style_value is not None:
                                    try:
                                        return int(style_value)
                                    except (ValueError, TypeError):
                                        pass
            except (AttributeError, KeyError):
                pass
    
    # 4. Default
    return None
```

## 🔧 Instrukcja implementacji

### Krok 1: Dodaj funkcję do klasy HTMLRenderer

Otwórz plik `docx_interpreter/renderers/html_renderer.py` i dodaj funkcję `_resolve_effective_indent()` zaraz po metodzie `_convert_twips_to_px()` (około linii 114):

```python
def _convert_twips_to_px(self, twips_value: float, target_width_px: int = None) -> float:
    # ... istniejący kod ...

def _resolve_effective_indent(self, paragraph, indent_type: str):
    """
    Rozwiązuje efektywne wcięcie zgodnie z hierarchią DOCX (Word).
    """
    # ... wklej kod z powyżej ...
```

### Krok 2: Zaktualizuj `render_paragraph()` aby używał nowej funkcji

Znajdź sekcję w `render_paragraph()` gdzie obsługiwane są wcięcia (około linii 1252-1310) i zastąp:

**PRZED:**
```python
if "indent" in style and style["indent"]:
    indent = style["indent"]
    left_indent = int(indent.get("left", "0")) if indent.get("left") else None
    hanging_indent = int(indent.get("hanging", "0")) if indent.get("hanging") else None
    first_line_indent = int(indent.get("firstLine", "0")) if indent.get("firstLine") else None
```

**PO:**
```python
# Użyj _resolve_effective_indent() dla prawidłowej hierarchii DOCX
left_indent = self._resolve_effective_indent(paragraph, 'left_indent')
right_indent = self._resolve_effective_indent(paragraph, 'right_indent')
hanging_indent = self._resolve_effective_indent(paragraph, 'hanging_indent')
first_line_indent = self._resolve_effective_indent(paragraph, 'first_line_indent')
```

### Krok 3: Popraw obsługę list

Zaktualizuj sekcję dla list (około linii 1260-1290) aby używała rozwiązywania wcięć:

**PRZED:**
```python
if "indent" in style and style["indent"]:
    indent = style["indent"]
    left_indent = int(indent.get("left", "0")) if indent.get("left") else None
    hanging_indent = int(indent.get("hanging", "0")) if indent.get("hanging") else None
```

**PO:**
```python
# Użyj _resolve_effective_indent() - automatycznie uwzględnia numbering
left_indent = self._resolve_effective_indent(paragraph, 'left_indent')
hanging_indent = self._resolve_effective_indent(paragraph, 'hanging_indent')
first_line_indent = self._resolve_effective_indent(paragraph, 'first_line_indent')
```

### Krok 4: Testowanie

Po implementacji przetestuj na przykładowych dokumentach:

```python
from docx_interpreter import Document
from docx_interpreter.renderers import HTMLRenderer

# Otwórz dokument z listami
doc = Document.open("test_document.docx")

# Renderuj do HTML
renderer = HTMLRenderer(doc)
html = renderer.render(output_path="test_output.html")

# Sprawdź czy wcięcia są poprawne
```

## ✅ Oczekiwane rezultaty

Po implementacji:
- ✅ Wcięcia będą zgodne z hierarchią DOCX (direct → numbering → style)
- ✅ Listy będą mieć poprawne wcięcia z poziomów numeracji
- ✅ Style będą prawidłowo dziedziczone
- ✅ Renderowanie będzie pixel-perfect jak w starej wersji

## 🔍 Debugging

Jeśli coś nie działa:

1. **Sprawdź strukturę danych:**
```python
# Dodaj debug logging
print(f"Paragraph properties: {paragraph.properties}")
print(f"Paragraph style: {paragraph.get_style()}")
print(f"Document numbering: {self.document.numbering}")
```

2. **Sprawdź co zwraca `_resolve_effective_indent()`:**
```python
left = self._resolve_effective_indent(paragraph, 'left_indent')
print(f"Resolved left_indent: {left}")
```

3. **Porównaj ze starą wersją:**
   - Uruchom starą wersję na tym samym dokumencie
   - Porównaj wygenerowany HTML
   - Znajdź różnice w wcięciach

## 📚 Dodatkowe zasoby

- Stara wersja: `tests/_old_rend/src/doclingforge/render/html_renderer.py` (linia 41-118)
- Obecna wersja: `docx_interpreter/renderers/html_renderer.py` (linia 1120-1320)
- Dokumentacja porównania: `RENDERER_COMPARISON.md`

