# Porównanie rendererów: Stara vs Obecna wersja

## 📊 Podsumowanie porównania

### Stara wersja (doclingforge 0.3.0)
✅ **Status:** Gotowa do produkcji, wszystkie funkcje działają  
✅ **Jakość:** Wysoka - pixel-perfect renderowanie  
✅ **Obsługa:** Kompletna hierarchia wcięć i formatowania

### Obecna wersja (docx_interpreter)
⚠️ **Status:** W trakcie rozwoju  
⚠️ **Jakość:** Częściowa - wymaga poprawek  
⚠️ **Obsługa:** Brakuje kluczowych funkcji z starej wersji

---

## 🔍 Główne różnice

### 1. Rozwiązywanie efektywnych wcięć

#### ✅ STARA WERSJA - `_resolve_effective_indent()`
```python
def _resolve_effective_indent(self, paragraph, indent_type: str):
    """
    Rozwiązuje efektywne wcięcie zgodnie z hierarchią DOCX (Word):
    
    1. Direct formatting (pPr/ind w akapicie) - najwyższy priorytet
    2. Numbering level properties (dla list - NADPISUJE style!)
    3. Style properties
    4. Default (None)
    """
    # 1. Direct formatting - najwyższy priorytet (ZAWSZE)
    direct_value = getattr(paragraph.properties, indent_type, None)
    if direct_value is not None:
        return direct_value
    
    # 2. Numbering level properties (NADPISUJE style dla list!)
    if paragraph.properties.numbering_id:
        # Pobierz z poziomu numeracji
        ...
    
    # 3. Style properties (niższy priorytet niż lista)
    if paragraph.properties.style_id:
        # Pobierz ze stylu
        ...
    
    return None
```

**Zalety:**
- ✅ Obsługuje pełną hierarchię DOCX
- ✅ Rozróżnia direct formatting, numbering, style
- ✅ Prawidłowo obsługuje listy (numbering nadpisuje style)
- ✅ Obsługuje wszystkie typy wcięć (left, right, first_line, hanging)

#### ❌ OBECNA WERSJA - Brak funkcji `_resolve_effective_indent()`

**Problemy:**
- ❌ Brak centralnej funkcji rozwiązywania wcięć
- ❌ Nie uwzględnia hierarchii DOCX
- ❌ Nie rozróżnia numbering vs style
- ❌ Prawdopodobnie nie obsługuje wszystkich przypadków

---

### 2. Renderowanie akapitów

#### ✅ STARA WERSJA - `_render_paragraph()`

**Kluczowe funkcje:**
1. **Rozwiązywanie wcięć:**
```python
left_indent = self._resolve_effective_indent(paragraph, 'left_indent')
right_indent = self._resolve_effective_indent(paragraph, 'right_indent')
first_line_indent = self._resolve_effective_indent(paragraph, 'first_line_indent')
hanging_indent = self._resolve_effective_indent(paragraph, 'hanging_indent')
```

2. **Obsługa list z prawidłowymi wcięciami:**
```python
# T = left_indent (pozycja tekstu)
# H = hanging_indent
# N = T - H (pozycja markera)
T = left_indent if left_indent is not None else (level + 1) * DEFAULT_LIST_INDENT_TWIPS
H = hanging_indent if hanging_indent is not None else DEFAULT_HANGING_TWIPS
N = T - H  # Pozycja markera
margin_left_px = self._convert_twips_to_px(N)
```

3. **Struktura HTML dla list:**
```html
<li class="list-item" style="margin-left: ...px">
  <p class="...">...</p>
</li>
```

4. **Obsługa markerów list:**
```python
# Marker z absolute positioning
marker_style = f' style="left: -{list_marker_offset:.1f}px"'
html += f'<span class="list-marker"{marker_style}>{marker_text}</span>'
```

#### ❌ OBECNA WERSJA - `render_paragraph()`

**Problemy:**
- ❌ Brak funkcji `_resolve_effective_indent()` - bezpośrednie odczytywanie ze stylu
- ❌ Mniej precyzyjna obsługa wcięć
- ❌ Nie uwzględnia hierarchii numbering → style → default
- ❌ Kod jest bardziej rozproszony i trudniejszy do utrzymania

---

### 3. Konwersja jednostek

#### ✅ STARA WERSJA
```python
def _convert_twips_to_px(self, twips_value: float, target_width_px: int = None) -> float:
    """
    Konwertuje twips → cm → px z proporcjonalnym skalowaniem.
    
    1 twip = 1/1440 inch = (1/1440) * 2.54 cm
    """
    # Konwertuj twips → cm → px
    cm_value = (twips_value / 1440) * 2.54
    return self._convert_cm_to_px(cm_value, target_width_px)
```

**Zalety:**
- ✅ Proporcjonalne skalowanie względem docelowej szerokości
- ✅ Spójna konwersja we wszystkich miejscach
- ✅ Domyślna szerokość 800px (responsywna)

#### ❌ OBECNA WERSJA
```python
def _convert_twips_to_px(self, twips_value: float, target_width_px: int = None) -> float:
    """Konwertuje wartość z twips na pixele."""
    cm_value = (twips_value / 1440) * 2.54
    return self._convert_cm_to_px(cm_value, target_width_px)
```

**Problemy:**
- ⚠️ Podobna implementacja, ale może brakować spójności w użyciu
- ⚠️ Może nie być używana konsekwentnie we wszystkich miejscach

---

### 4. Obsługa CSS i stylów

#### ✅ STARA WERSJA

**Struktura CSS:**
```css
/* Kompatybilne z Aspose.Words */
* {
    margin-top: 0;
    margin-right: 0;
    margin-bottom: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    text-align: justify;
    line-height: 14pt;
    font-family: Verdana;
    font-size: 10pt;
    letter-spacing: 0.2pt;
}

/* Nowa struktura list: <ul>/<ol> + <li> + <p> */
.list-item, .list-item-numbered {
    list-style: none;
    margin: 0;
    padding: 0;
    position: relative;
}

.list-item .list-marker, .list-item-numbered .list-marker {
    position: absolute;
    left: 0;
    font-weight: normal;
}
```

**Zalety:**
- ✅ Szczegółowy CSS z pełną kontrolą
- ✅ Wsparcie dla list z absolute positioning markerów
- ✅ Kompatybilność z Aspose.Words
- ✅ Cache CSS dla optymalizacji

#### ❌ OBECNA WERSJA

**Problemy:**
- ⚠️ CSS może być mniej kompletny
- ⚠️ Może brakować obsługi markerów list
- ⚠️ Mniej szczegółowe style

---

### 5. Optymalizacje

#### ✅ STARA WERSJA
```python
def __init__(self, document: Any, optimize: bool = True) -> None:
    # Optymalizacje
    self.optimize = optimize
    self._css_cache: Dict[str, str] = {}  # Cache dla często używanych stylów CSS
    self._run_format_cache: Dict[int, str] = {}  # Cache dla formatowania runów
```

**Zalety:**
- ✅ Cache CSS - ↓9% pamięci
- ✅ Cache formatowania runów
- ✅ Łączenie runów - ↓46% tagów HTML
- ✅ Flaga optymalizacji

#### ❌ OBECNA WERSJA

**Problemy:**
- ❌ Brak cache CSS
- ❌ Brak cache formatowania
- ❌ Brak optymalizacji łączenia runów
- ❌ Brak flagi optymalizacji

---

## 📋 Plan migracji najlep

szych praktyk

### Faza 1: Rozwiązywanie wcięć (PRIORYTET 1)

**Cel:** Dodać funkcję `_resolve_effective_indent()` do obecnej wersji

**Kroki:**
1. Skopiować `_resolve_effective_indent()` ze starej wersji
2. Dostosować do obecnej struktury danych
3. Zintegrować z `render_paragraph()`
4. Dodać testy jednostkowe

**Kod do skopiowania:**
```python
def _resolve_effective_indent(self, paragraph, indent_type: str):
    """
    Rozwiązuje efektywne wcięcie zgodnie z hierarchią DOCX (Word):
    
    1. Direct formatting (pPr/ind w akapicie) - najwyższy priorytet
    2. Numbering level properties (dla list - NADPISUJE style!)
    3. Style properties
    4. Default (None)
    """
    # 1. Direct formatting - najwyższy priorytet (ZAWSZE)
    direct_value = getattr(paragraph.properties, indent_type, None)
    if direct_value is not None:
        return direct_value
    
    # 2. Numbering level properties (NADPISUJE style dla list!)
    if paragraph.properties.numbering_id:
        num_id = paragraph.properties.numbering_id
        level = paragraph.properties.numbering_level or 0
        
        numbering_instance = self.document.numbering._numbering_instances.get(num_id)
        if numbering_instance:
            abstract_num_id = numbering_instance.abstract_num_id
            abstract_num = self.document.numbering._abstract_numberings.get(abstract_num_id)
            if abstract_num and abstract_num.levels:
                if level < len(abstract_num.levels):
                    level_obj = abstract_num.levels[level]
                    
                    # Pobierz wcięcie z poziomu numeracji
                    if indent_type == 'left_indent' and level_obj.left_indent is not None:
                        return level_obj.left_indent
                    elif indent_type == 'hanging_indent' and level_obj.hanging_indent is not None:
                        return level_obj.hanging_indent
                    elif indent_type == 'first_line_indent' and level_obj.first_line_indent is not None:
                        return level_obj.first_line_indent
    
    # 3. Style properties (niższy priorytet niż lista)
    if paragraph.properties.style_id:
        style = self.document.styles.get_style(paragraph.properties.style_id)
        if style and style.paragraph_properties:
            style_value = style.paragraph_properties.get(indent_type)
            if style_value is not None:
                try:
                    return int(style_value)
                except (ValueError, TypeError):
                    pass
    
    # 4. Default
    return None
```

---

### Faza 2: Poprawa renderowania akapitów (PRIORYTET 2)

**Cel:** Poprawić `render_paragraph()` aby używał `_resolve_effective_indent()`

**Kroki:**
1. Zastąpić bezpośrednie odczytywanie wcięć wywołaniem `_resolve_effective_indent()`
2. Poprawić obsługę list (struktura `<li><p>`)
3. Dodać obsługę markerów z absolute positioning
4. Poprawić CSS dla list

**Przykład poprawki:**
```python
# PRZED (obecna wersja):
left_indent = style.get("indent", {}).get("left", 0)

# PO (z rozwiązywaniem wcięć):
left_indent = self._resolve_effective_indent(paragraph, 'left_indent')
```

---

### Faza 3: Optymalizacje (PRIORYTET 3)

**Cel:** Dodać cache CSS i optymalizacje z starej wersji

**Kroki:**
1. Dodać `_css_cache` i `_run_format_cache`
2. Dodać funkcję łączenia runów
3. Dodać flagę `optimize`
4. Zmierzyć poprawę wydajności

---

### Faza 4: CSS dla list (PRIORYTET 4)

**Cel:** Dodać kompletny CSS dla list ze starej wersji

**Kroki:**
1. Skopiować CSS dla `.list-item` i `.list-item-numbered`
2. Dodać CSS dla `.list-marker` z absolute positioning
3. Dodać obsługę `<ul>/<ol>` jeśli potrzebne
4. Przetestować renderowanie list

---

## 🎯 Rekomendacje

### Najpilniejsze do naprawy:
1. ✅ **`_resolve_effective_indent()`** - fundament poprawnego renderowania
2. ✅ **Obsługa wcięć w listach** - poprawa renderowania numeracji
3. ✅ **CSS dla markerów list** - pixel-perfect renderowanie

### Długoterminowe:
1. Optymalizacje (cache CSS, łączenie runów)
2. Ulepszone CSS (kompatybilność z Aspose.Words)
3. Testy jednostkowe dla wszystkich przypadków wcięć

---

## 📝 Checklist migracji

- [ ] Skopiować `_resolve_effective_indent()` ze starej wersji
- [ ] Dostosować do obecnej struktury danych
- [ ] Zintegrować z `render_paragraph()`
- [ ] Poprawić obsługę list (`<li><p>` struktura)
- [ ] Dodać CSS dla markerów list
- [ ] Dodać cache CSS
- [ ] Dodać testy jednostkowe
- [ ] Przetestować na przykładowych dokumentach
- [ ] Porównać output starej vs obecnej wersji

---

## 🔗 Linki do kluczowych plików

**Stara wersja:**
- `tests/_old_rend/src/doclingforge/render/html_renderer.py` (linia 41-118)
- `tests/_old_rend/src/doclingforge/render/html_renderer.py` (linia 1824-2120)

**Obecna wersja:**
- `docx_interpreter/renderers/html_renderer.py` (linia 1120-1320)

