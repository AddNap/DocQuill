"""
TextAlignmentEngine — obliczanie pozycji X dla tekstu względem szerokości kolumny.

Obsługuje:
- left: wyrównanie do lewej (domyślne)
- center: wyśrodkowanie
- right: wyrównanie do prawej
- justify: justowanie (wymaga dodatkowej logiki)
"""

from typing import Dict, Any
from .geometry import Rect


class TextAlignmentEngine:
    """
    Silnik do obliczania pozycji X dla tekstu na podstawie alignment.
    """
    
    @staticmethod
    def calculate_x(
        rect: Rect,
        text_width: float,
        alignment: str = "left"
    ) -> float:
        """
        Oblicza pozycję X dla tekstu na podstawie alignment.
        
        Args:
            rect: Rect obszaru tekstu
            text_width: Szerokość tekstu w punktach
            alignment: Wyrównanie ("left", "center", "right", "justify")
            
        Returns:
            Pozycja X dla tekstu
        """
        alignment = alignment.lower() if alignment else "left"
        
        if alignment == "center":
            # Wyśrodkowanie
            x = rect.x + (rect.width - text_width) / 2
            return max(rect.x, x)  # Nie wychodź poza lewą krawędź
        
        elif alignment == "right":
            # Wyrównanie do prawej
            x = rect.x + rect.width - text_width
            return max(rect.x, x)  # Nie wychodź poza lewą krawędź
        
        elif alignment == "justify":
            # Justowanie - tekst wypełnia całą szerokość
            # Zwróć lewą krawędź, justowanie wymaga dodatkowej logiki w rendererze
            return rect.x
        
        else:  # "left" lub domyślne
            # Wyrównanie do lewej
            return rect.x
    
    @staticmethod
    def get_alignment_from_style(style: Dict[str, Any]) -> str:
        """
        Pobiera alignment z stylu.
        
        Args:
            style: Słownik ze stylami
            
        Returns:
            Alignment string ("left", "center", "right", "justify")
        """
        alignment = style.get("alignment") or style.get("text_align") or style.get("align", "left")
        
        # Normalizuj
        alignment = str(alignment).lower()
        
        # Mapuj różne warianty
        if alignment in ("left", "start", "l"):
            return "left"
        elif alignment in ("center", "middle", "c"):
            return "center"
        elif alignment in ("right", "end", "r"):
            return "right"
        elif alignment in ("justify", "justified", "j"):
            return "justify"
        else:
            return "left"  # Domyślne
    
    @staticmethod
    def calculate_text_position(
        rect: Rect,
        text_width: float,
        style: Dict[str, Any]
    ) -> float:
        """
        Oblicza pozycję X dla tekstu na podstawie rect, szerokości tekstu i stylu.
        
        Args:
            rect: Rect obszaru tekstu
            text_width: Szerokość tekstu w punktach
            style: Słownik ze stylami (zawiera alignment)
            
        Returns:
            Pozycja X dla tekstu
        """
        alignment = TextAlignmentEngine.get_alignment_from_style(style)
        return TextAlignmentEngine.calculate_x(rect, text_width, alignment)

