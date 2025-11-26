# Fonty dla Rust PDF Canvas

Ten folder zawiera pliki fontów TTF używane przez renderer PDF.

## Wymagane fonty

Aby zapewnić pełną obsługę polskich znaków i znaków specjalnych, umieść tutaj następujące pliki:

- `DejaVuSans.ttf` - podstawowa wersja fontu
- `DejaVuSans-Bold.ttf` - wersja pogrubiona
- `DejaVuSans-Oblique.ttf` - wersja kursywa
- `DejaVuSans-BoldOblique.ttf` - wersja pogrubiona + kursywa

## Pobieranie fontów

Fonty DejaVu Sans są dostępne na licencji open source (Bitstream Vera License):

- **Oficjalna strona**: https://dejavu-fonts.github.io/
- **GitHub**: https://github.com/dejavu-fonts/dejavu-fonts
- **Pobierz**: https://github.com/dejavu-fonts/dejavu-fonts/releases

## Instalacja

1. Pobierz pliki TTF z powyższych źródeł
2. Skopiuj wymienione pliki do tego folderu (`assets/fonts/`)
3. Renderer automatycznie znajdzie i użyje tych fontów

## Fallback

Jeśli fonty nie zostaną znalezione w tym folderze, renderer spróbuje znaleźć je w systemowych lokalizacjach:
- Linux: `/usr/share/fonts/truetype/dejavu/`
- macOS: `/System/Library/Fonts/Supplemental/`
- Windows: `C:/Windows/Fonts/`

## Licencja

DejaVu Sans jest dostępny na licencji Bitstream Vera License, która pozwala na:
- Użycie komercyjne i niekomercyjne
- Modyfikację
- Dystrybucję

Więcej informacji: https://dejavu-fonts.github.io/License.html

