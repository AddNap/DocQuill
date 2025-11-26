# Diagnoza problemu z nowym rendererem

## Problem
Nowy renderer renderuje prawie goły tekst - tylko paragrafy i bold. Brakuje kolorów, rozmiarów czcionek, stylów, tabel, obrazów.

## Przyczyna
Stary renderer bezpośrednio używa właściwości z modelu:
- `run.properties.font_size` (half-points)
- `run.properties.bold`
- `run.properties.font_color`
- `run.properties.font_name`
- `para.properties.alignment`
- `para.properties.space_before`
- `para.properties.space_after`

Nowy renderer próbuje używać `run.style` (dict), ale:
1. Nie zawsze ma dostęp do `run.properties`
2. Layout engine może nie być dostosowany do struktury modelu
3. `_get_font_info` nie zawsze prawidłowo pobiera właściwości

## Rozwiązanie
Należy dostosować nowy renderer aby:
1. **Bezpośrednio używał właściwości z modelu** (jak stary renderer)
2. **Pobierał style z dokumentu** przez `document.styles.get_style()`
3. **Fallback do domyślnych wartości** jeśli właściwości nie są dostępne

## Zmiany do wprowadzenia
1. Poprawić `_get_font_info()` aby używał `run.properties` zamiast `run.style`
2. Poprawić renderowanie paragrafów aby używało `para.properties`
3. Upewnić się że layout engine prawidłowo używa struktury modelu
4. Dodać fallback do właściwości dokumentu dla domyślnych wartości

