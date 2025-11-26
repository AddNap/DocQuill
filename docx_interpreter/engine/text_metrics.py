"""

TextMetricsEngine - calculating actual text width and height.

Uses ReportLab for font metrics and calculates:
- text width
- text height (accounting for line spacing)
- number of lines
- line structure

"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple

try:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    pdfmetrics = None  # type: ignore

from .utils.font_utils import resolve_font_variant
from .utils.font_registry import register_default_fonts


@dataclass(slots=True)
class Glyph:
    """Represents single glyph in text."""
    glyph_id: int
    cluster: int
    x: float
    y: float
    x_advance: float
    y_advance: float


@dataclass(slots=True)
class TextLayout:
    """Result structure for text layout."""
    width: float
    height: float
    line_count: int = 1
    lines: List[str] = field(default_factory=list)
    glyphs: List[Glyph] = field(default_factory=list)
    font_size: float = 11.0
    direction: str = "ltr"  # ltr or rtl


class TextMetricsEngine:
    """

    Engine for calculating text metrics.

    Uses ReportLab for width measurements and calculates height
    based on line spacing and number of lines.

    """
    
    def __init__(self):
        """Inicjalizacja silnika metryk."""
        self._font_cache: Dict[str, bool] = {}
        register_default_fonts()
        self._ensure_default_fonts()
    
    def _ensure_default_fonts(self) -> None:
        """Ensures default fonts are registered."""
        if not REPORTLAB_AVAILABLE:
            return
        
        # Default ReportLab fonts are always available
        default_fonts = [
            "Helvetica",
            "Helvetica-Bold",
            "Helvetica-Oblique",
            "Helvetica-BoldOblique",
            "Times-Roman",
            "Times-Bold",
            "Times-Italic",
            "Times-BoldItalic",
            "Courier",
            "Courier-Bold",
            "Courier-Oblique",
            "Courier-BoldOblique",
        ]
        for font_name in default_fonts:
            if font_name in pdfmetrics.getRegisteredFontNames():
                self._font_cache[font_name] = True
    
    def _get_font_name(self, style: Dict[str, Any]) -> str:
        """

        Gets font name from style.

        Args:
        style: Dictionary with styles

        Returns:
        Font name to use in ReportLab

        """
        font_candidate = (
            style.get("font_name")
            or style.get("font_pdf_name")
            or style.get("font_family")
            or style.get("font_ascii")
            or style.get("font_hAnsi")
            or "Helvetica"
        )
        bold = bool(style.get("bold") or style.get("font_weight") == "bold")
        italic = bool(style.get("italic") or style.get("font_style") == "italic")
        return resolve_font_variant(font_candidate, bold, italic)
    
    def measure_text(self, text: str, style: Dict[str, Any]) -> Dict[str, float]:
        """

        Measures text width and height.

        Args:
        text: Text to measure
        style: Dictionary with styles (font_name, font_size, line_spacing, etc.)

        Returns:
        Dict with metrics: {"width": float, "height": float, "line_count": int}

        """
        if not text:
            font_size = float(style.get("font_size", 11))
            line_spacing = float(style.get("line_spacing", 1.2))
            return {
                "width": 0.0,
                "height": font_size * line_spacing,
                "line_count": 1
            }
        
        font_name = self._get_font_name(style)
        font_size = float(style.get("font_size", 11))
        line_spacing = float(style.get("line_spacing", 1.2))
        
        if REPORTLAB_AVAILABLE:
            try:
                # Measure width of entire text
                width = pdfmetrics.stringWidth(text, font_name, font_size)
                
                # Calculate height (one line)
                height = font_size * line_spacing
                
                return {
                    "width": width,
                    "height": height,
                    "line_count": 1
                }
            except Exception:
                # Fallback if font not available
                pass
        
        # Fallback: proste szacowanie
        char_width = font_size * 0.6 # Approximate character width
        width = len(text) * char_width
        height = font_size * line_spacing
        
        return {
            "width": width,
            "height": height,
            "line_count": 1
        }
    
    def layout_text(
        self,
        text: str,
        style: Optional[Dict[str, Any]] = None,
        max_width: Optional[float] = None
    ) -> TextLayout:
        """

        Lays out text into lines and calculates metrics.

        Args:
        text: Text to lay out
        style: Dictionary with styles
        max_width: Maximum width (optional, for line breaking)

        Returns:
        TextLayout with metrics and lines

        """
        if style is None:
            style = {}
        
        if not text:
            font_size = float(style.get("font_size", 11))
            line_spacing = float(style.get("line_spacing", 1.2))
            return TextLayout(
                width=0.0,
                height=font_size * line_spacing,
                line_count=1,
                lines=[],
                font_size=font_size
            )
        
        font_name = self._get_font_name(style)
        font_size = float(style.get("font_size", 11))
        line_spacing = float(style.get("line_spacing", 1.2))
        
        # If no max_width, just measure text
        if max_width is None:
            metrics = self.measure_text(text, style)
            return TextLayout(
                width=metrics["width"],
                height=metrics["height"],
                line_count=1,
                lines=[text],
                font_size=font_size
            )
        
        # Line breaking
        lines = self._break_text_into_lines(text, font_name, font_size, max_width)
        
        # Calculate width of widest line
        max_line_width = 0.0
        if REPORTLAB_AVAILABLE:
            try:
                for line in lines:
                    line_width = pdfmetrics.stringWidth(line, font_name, font_size)
                    max_line_width = max(max_line_width, line_width)
            except Exception:
                # Fallback
                char_width = font_size * 0.6
                max_line_width = max(len(line) * char_width for line in lines)
        else:
            # Fallback
            char_width = font_size * 0.6
            max_line_width = max(len(line) * char_width for line in lines)
        
        # Calculate total height
        total_height = len(lines) * font_size * line_spacing
        
        return TextLayout(
            width=max_line_width,
            height=total_height,
            line_count=len(lines),
            lines=lines,
            font_size=font_size
        )
    
    def _break_text_into_lines(
        self,
        text: str,
        font_name: str,
        font_size: float,
        max_width: float
    ) -> List[str]:
        """

        Breaks text into lines according to max_width.

        Args:
        text: Text to break
        font_name: Font name
        font_size: Font size
        max_width: Maximum line width

        Returns:
        List of text lines

        """
        if not text.strip():
            return [""]
        
        # Split into words
        words = text.split()
        if not words:
            return [""]
        
        lines: List[str] = []
        current_line = ""
        
        if REPORTLAB_AVAILABLE:
            try:
                for word in words:
                    # Try to add word to current line
                    candidate = f"{current_line} {word}".strip() if current_line else word
                    candidate_width = pdfmetrics.stringWidth(candidate, font_name, font_size)
                    
                    if candidate_width <= max_width:
                        # Word fits
                        current_line = candidate
                    else:
                        # Word doesn't fit - add current line and start new
                        if current_line:
                            lines.append(current_line)
                            current_line = word
                        else:
                            # Word is too long - add it anyway
                            lines.append(word)
                            current_line = ""
                
                # Add last line
                if current_line:
                    lines.append(current_line)
                
                return lines if lines else [""]
            except Exception:
                # Fallback na prostszy algorytm
                pass
        
        # Fallback: simple line breaking
        char_width = font_size * 0.6
        chars_per_line = max(1, int(max_width / char_width))
        
        current_line_length = 0
        current_line_words = []
        
        for word in words:
            word_length = len(word) + 1  # +1 dla spacji
            if current_line_length + word_length > chars_per_line:
                if current_line_words:
                    lines.append(" ".join(current_line_words))
                    current_line_words = [word]
                    current_line_length = word_length
                else:
                    # Word is too long
                    lines.append(word)
                    current_line_length = 0
            else:
                current_line_words.append(word)
                current_line_length += word_length
        
        if current_line_words:
            lines.append(" ".join(current_line_words))
        
        return lines if lines else [""]
    
    def get_line_height(self, style: Dict[str, Any]) -> float:
        """

        Calculates height of one line.

        Args:
        style: Dictionary with styles

        Returns:
        Line height in points

        """
        font_size = float(style.get("font_size", 11))
        line_spacing = float(style.get("line_spacing", 1.2))
        return font_size * line_spacing

