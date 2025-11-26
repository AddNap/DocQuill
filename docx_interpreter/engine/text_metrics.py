"""
TextMetricsEngine — obliczanie rzeczywistej szerokości i wysokości tekstu.

Używa ReportLab do metryk fontów i oblicza:
- szerokość tekstu
- wysokość tekstu (z uwzględnieniem line spacing)
- liczbę linii
- strukturę linii
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
    """Reprezentuje pojedynczy glif w tekście."""
    glyph_id: int
    cluster: int
    x: float
    y: float
    x_advance: float
    y_advance: float


@dataclass(slots=True)
class TextLayout:
    """Struktura wynikowa dla układu tekstu."""
    width: float
    height: float
    line_count: int = 1
    lines: List[str] = field(default_factory=list)
    glyphs: List[Glyph] = field(default_factory=list)
    font_size: float = 11.0
    direction: str = "ltr"  # ltr or rtl


class TextMetricsEngine:
    """
    Silnik do obliczania metryk tekstu.
    
    Używa ReportLab do pomiarów szerokości i oblicza wysokość
    na podstawie line spacing i liczby linii.
    """
    
    def __init__(self):
        """Inicjalizacja silnika metryk."""
        self._font_cache: Dict[str, bool] = {}
        register_default_fonts()
        self._ensure_default_fonts()
    
    def _ensure_default_fonts(self) -> None:
        """Upewnia się, że domyślne fonty są zarejestrowane."""
        if not REPORTLAB_AVAILABLE:
            return
        
        # Domyślne fonty ReportLab są zawsze dostępne
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
        Pobiera nazwę fontu z stylu.
        
        Args:
            style: Słownik ze stylami
            
        Returns:
            Nazwa fontu do użycia w ReportLab
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
        Mierzy szerokość i wysokość tekstu.
        
        Args:
            text: Tekst do zmierzenia
            style: Słownik ze stylami (font_name, font_size, line_spacing, etc.)
            
        Returns:
            Dict z metrykami: {"width": float, "height": float, "line_count": int}
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
                # Zmierz szerokość całego tekstu
                width = pdfmetrics.stringWidth(text, font_name, font_size)
                
                # Oblicz wysokość (jedna linia)
                height = font_size * line_spacing
                
                return {
                    "width": width,
                    "height": height,
                    "line_count": 1
                }
            except Exception:
                # Fallback jeśli font nie jest dostępny
                pass
        
        # Fallback: proste szacowanie
        char_width = font_size * 0.6 # Przybliżona szerokość znaku
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
        Układa tekst w linie i oblicza metryki.
        
        Args:
            text: Tekst do układania
            style: Słownik ze stylami
            max_width: Maksymalna szerokość (opcjonalnie, do łamania linii)
            
        Returns:
            TextLayout z metrykami i liniami
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
        
        # Jeśli nie ma max_width, po prostu zmierz tekst
        if max_width is None:
            metrics = self.measure_text(text, style)
            return TextLayout(
                width=metrics["width"],
                height=metrics["height"],
                line_count=1,
                lines=[text],
                font_size=font_size
            )
        
        # Łamanie linii
        lines = self._break_text_into_lines(text, font_name, font_size, max_width)
        
        # Oblicz szerokość najszerszej linii
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
        
        # Oblicz całkowitą wysokość
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
        Łamie tekst na linie zgodnie z max_width.
        
        Args:
            text: Tekst do złamania
            font_name: Nazwa fontu
            font_size: Rozmiar fontu
            max_width: Maksymalna szerokość linii
            
        Returns:
            Lista linii tekstu
        """
        if not text.strip():
            return [""]
        
        # Podziel na słowa
        words = text.split()
        if not words:
            return [""]
        
        lines: List[str] = []
        current_line = ""
        
        if REPORTLAB_AVAILABLE:
            try:
                for word in words:
                    # Spróbuj dodać słowo do bieżącej linii
                    candidate = f"{current_line} {word}".strip() if current_line else word
                    candidate_width = pdfmetrics.stringWidth(candidate, font_name, font_size)
                    
                    if candidate_width <= max_width:
                        # Słowo mieści się
                        current_line = candidate
                    else:
                        # Słowo nie mieści się - dodaj bieżącą linię i zacznij nową
                        if current_line:
                            lines.append(current_line)
                            current_line = word
                        else:
                            # Słowo jest zbyt długie - dodaj je mimo wszystko
                            lines.append(word)
                            current_line = ""
                
                # Dodaj ostatnią linię
                if current_line:
                    lines.append(current_line)
                
                return lines if lines else [""]
            except Exception:
                # Fallback na prostszy algorytm
                pass
        
        # Fallback: proste łamanie linii
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
                    # Słowo jest zbyt długie
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
        Oblicza wysokość jednej linii.
        
        Args:
            style: Słownik ze stylami
            
        Returns:
            Wysokość linii w punktach
        """
        font_size = float(style.get("font_size", 11))
        line_spacing = float(style.get("line_spacing", 1.2))
        return font_size * line_spacing

