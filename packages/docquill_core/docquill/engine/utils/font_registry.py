from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from reportlab.pdfbase import pdfmetrics  # type: ignore
from reportlab.pdfbase.ttfonts import TTFont  # type: ignore

logger = logging.getLogger(__name__)

# Cache for ReportLab font parsing to avoid repeated AFM parsing
_FONT_PARSING_CACHE: Dict[str, any] = {}
_FONT_PARSING_CACHE_ENABLED = False


def enable_font_parsing_cache() -> None:
    """
    Enable caching for ReportLab font parsing (parseAFMFile).
    This significantly speeds up PDF generation by avoiding repeated AFM file parsing.
    """
    global _FONT_PARSING_CACHE_ENABLED
    
    if _FONT_PARSING_CACHE_ENABLED:
        return  # Already enabled
    
    try:
        from reportlab.pdfbase import pdfmetrics as rl_pdfmetrics
        
        # Store original function
        if not hasattr(rl_pdfmetrics, '_original_parseAFMFile'):
            rl_pdfmetrics._original_parseAFMFile = rl_pdfmetrics.parseAFMFile
        
        # Create cached version
        def cached_parseAFMFile(filename):
            """Cached version of parseAFMFile."""
            if filename in _FONT_PARSING_CACHE:
                return _FONT_PARSING_CACHE[filename]
            
            # Call original and cache result
            result = rl_pdfmetrics._original_parseAFMFile(filename)
            _FONT_PARSING_CACHE[filename] = result
            return result
        
        # Replace with cached version
        rl_pdfmetrics.parseAFMFile = cached_parseAFMFile
        _FONT_PARSING_CACHE_ENABLED = True
        logger.debug("Font parsing cache enabled")
        
    except Exception as e:
        logger.warning(f"Failed to enable font parsing cache: {e}")


def clear_font_parsing_cache() -> None:
    """Clear the font parsing cache."""
    global _FONT_PARSING_CACHE
    _FONT_PARSING_CACHE.clear()
    logger.debug("Font parsing cache cleared")

# Bundled fonts directory (shipped with package) - HIGHEST PRIORITY
_BUNDLED_FONTS_DIR = Path(__file__).resolve().parent.parent.parent / "fonts"

SEARCH_DIRECTORIES: List[Path] = [
    # Bundled fonts first - ensures consistency between Python and Rust
    _BUNDLED_FONTS_DIR,
    # Then system fonts as fallback
    Path("/usr/share/fonts"),
    Path("/usr/share/fonts/truetype"),
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/local/share/fonts"),
    Path.home() / ".fonts",
    Path.home() / ".local/share/fonts",
    # Windows fonts
    Path("C:/Windows/Fonts"),
    # macOS fonts
    Path("/System/Library/Fonts"),
    Path("/Library/Fonts"),
]

FONT_VARIANTS: Dict[str, Dict[str, Iterable[str]]] = {
    "DejaVuSans": {
        "": ("DejaVuSans.ttf", "DejaVuSans-Regular.ttf"),
        "-Bold": ("DejaVuSans-Bold.ttf",),
        "-Oblique": ("DejaVuSans-Oblique.ttf", "DejaVuSans-Italic.ttf"),
        "-BoldOblique": ("DejaVuSans-BoldOblique.ttf", "DejaVuSans-BoldItalic.ttf"),
    },
    "DejaVuSerif": {
        "": ("DejaVuSerif.ttf", "DejaVuSerif-Regular.ttf"),
        "-Bold": ("DejaVuSerif-Bold.ttf",),
        "-Italic": ("DejaVuSerif-Italic.ttf",),
        "-BoldItalic": ("DejaVuSerif-BoldItalic.ttf",),
    },
    "LiberationSans": {
        "": ("LiberationSans-Regular.ttf", "LiberationSans.ttf"),
        "-Bold": ("LiberationSans-Bold.ttf",),
        "-Italic": ("LiberationSans-Italic.ttf",),
        "-BoldItalic": ("LiberationSans-BoldItalic.ttf",),
    },
    "LiberationSerif": {
        "": ("LiberationSerif-Regular.ttf", "LiberationSerif.ttf"),
        "-Bold": ("LiberationSerif-Bold.ttf",),
        "-Italic": ("LiberationSerif-Italic.ttf",),
        "-BoldItalic": ("LiberationSerif-BoldItalic.ttf",),
    },
}


@lru_cache()
def _build_font_index() -> Dict[str, Path]:
    index: Dict[str, Path] = {}
    for root in SEARCH_DIRECTORIES:
        if not root or not root.exists():
            continue
        try:
            for candidate in root.rglob("*.ttf"):
                index.setdefault(candidate.name.lower(), candidate)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Nie udało się przeskanować katalogu fontów %s: %s", root, exc)
    return index


def _locate_font_file(candidates: Iterable[str]) -> Optional[Path]:
    index = _build_font_index()
    for name in candidates:
        path = index.get(name.lower())
        if path:
            return path
    return None


_REGISTERED: set[str] = set()


def get_bundled_fonts_dir() -> Path:
    """
    Returns path to bundled fonts directory.
    This is the canonical location for fonts used by both Python and Rust.
    """
    return _BUNDLED_FONTS_DIR


def get_bundled_font_path(font_filename: str) -> Optional[Path]:
    """
    Get path to a specific bundled font file.
    
    Args:
        font_filename: Font filename (e.g., "DejaVuSans.ttf")
        
    Returns:
        Path to font file if exists, None otherwise
    """
    font_path = _BUNDLED_FONTS_DIR / font_filename
    if font_path.exists():
        return font_path
    return None


def register_default_fonts() -> None:
    """

    Registers selected font families (DejaVuSans/Serif) needed for proper
    rendering of diacritical characters in PDF, if corresponding *.ttf files
    exist in system or project directory.

    """
    for family, variants in FONT_VARIANTS.items():
        for suffix, candidate_names in variants.items():
            font_id = f"{family}{suffix}"
            if font_id in _REGISTERED:
                continue
            font_path = _locate_font_file(candidate_names)
            if not font_path:
                logger.debug("Brak pliku fontu %s (szukano %s)", font_id, candidate_names)
                continue
            try:
                pdfmetrics.registerFont(TTFont(font_id, str(font_path)))
                _REGISTERED.add(font_id)
                logger.debug("Zarejestrowano font %s (%s)", font_id, font_path)
            except Exception as exc:  # pragma: no cover - defensively guard reportlab failures
                logger.warning("Nie udało się zarejestrować fontu %s: %s", font_id, exc)

