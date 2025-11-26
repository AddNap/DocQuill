# Plan Napraw Problemów PDF Rendering

## Problemy do Naprawienia

1. **Złe marginesy** - Marginesy nie są poprawnie stosowane w renderowaniu
2. **Brak justowania** - Tekst justify nie używa word spacing
3. **Rozstrzelenie polskich znaków** - Problem z spacing przy CID fontach
4. **Brak grafiki w nagłówku** - Obrazy w header nie są renderowane
5. **Brak borders w paragrafach** - Borders nie są renderowane dla paragrafów
6. **Nieprawidłowa kolejność paragrafów w stopkach** - Footer paragraphs są w złej kolejności
7. **Brak grafik w stopce** - Obrazy w footer nie są renderowane
8. **Brak textboxów w stopce** - Textboxy w footer nie są renderowane

## Plan Napraw

### 1. Marginesy
- Sprawdzić jak layout engine oblicza pozycje z marginesami
- Zweryfikować czy marginesy są poprawnie przekazywane do renderowania
- Upewnić się że marginesy są uwzględniane w pozycjonowaniu bloków

### 2. Justowanie
- Zaimplementować word spacing dla justify alignment
- Użyć operatora PDF `TJ` (array format) dla word spacing
- Obliczyć word spacing na podstawie różnicy między content_width a line_width

### 3. Rozstrzelenie polskich znaków
- Poprawić /Widths array w CID fontach
- Upewnić się że wszystkie znaki mają poprawne szerokości
- Zweryfikować czy CIDToGIDMap jest poprawnie zbudowany

### 4. Grafika w nagłówku
- Sprawdzić czy header blocks zawierają Image objects
- Upewnić się że header blocks są renderowane z obrazami
- Sprawdzić czy Image objects są poprawnie wykrywane w header blocks

### 5. Borders w paragrafach
- Poprawić `_extract_border` żeby obsługiwał borders dict (top, right, bottom, left)
- Dodać renderowanie borders dla paragrafów osobno (nie tylko jako stroke na rect)
- Użyć `_render_borders` dla renderowania borders na każdej stronie

### 6. Kolejność paragrafów w stopkach
- Sprawdzić kolejność w `_render_footers_bottom_to_top`
- Upewnić się że paragrafy są renderowane w poprawnej kolejności (z layout engine)
- Poprawić sortowanie footer blocks

### 7. Grafika w stopce
- Sprawdzić czy footer blocks zawierają Image objects
- Upewnić się że footer blocks są renderowane z obrazami
- Dodać obsługę Image objects w footer rendering

### 8. Textboxy w stopce
- Sprawdzić czy textboxy są poprawnie wykrywane w footer
- Upewnić się że textboxy są renderowane z absolute positioning
- Dodać obsługę textboxów w footer rendering

