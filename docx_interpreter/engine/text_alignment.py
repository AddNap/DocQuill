"""

TextAlignmentEngine - calculating X position for text relative to column width.

Supports:
- left: left alignment (default)
- center: centering
- right: right alignment
- justify: justification (requires additional logic)

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

        Calculates X position for text based on alignment.

        Args:
        rect: Rect of text area
        text_width: Text width in points
        alignment: Alignment ("left", "center", "right", "justify")

        Returns:
        X position for text

        """
        alignment = alignment.lower() if alignment else "left"
        
        if alignment == "center":
            # Centering
            x = rect.x + (rect.width - text_width) / 2
            return max(rect.x, x)  # Don't go beyond left edge
        
        elif alignment == "right":
            # Right alignment
            x = rect.x + rect.width - text_width
            return max(rect.x, x)  # Don't go beyond left edge
        
        elif alignment == "justify":
            # Justification - text fills entire width
            # Return left edge, justification requires additional logic in renderer
            return rect.x
        
        else:  # "left" or default
            # Left alignment
            return rect.x
    
    @staticmethod
    def get_alignment_from_style(style: Dict[str, Any]) -> str:
        """

        Gets alignment from style.

        Args:
        style: Dictionary with styles

        Returns:
        Alignment string ("left", "center", "right", "justify")

        """
        alignment = style.get("alignment") or style.get("text_align") or style.get("align", "left")
        
        # Normalizuj
        alignment = str(alignment).lower()
        
        # Map different variants
        if alignment in ("left", "start", "l"):
            return "left"
        elif alignment in ("center", "middle", "c"):
            return "center"
        elif alignment in ("right", "end", "r"):
            return "right"
        elif alignment in ("justify", "justified", "j"):
            return "justify"
        else:
            return "left"  # Default
    
    @staticmethod
    def calculate_text_position(
        rect: Rect,
        text_width: float,
        style: Dict[str, Any]
    ) -> float:
        """

        Calculates X position for text based on rect, text width and style.

        Args:
        rect: Rect of text area
        text_width: Text width in points
        style: Dictionary with styles (contains alignment)

        Returns:
        X position for text

        """
        alignment = TextAlignmentEngine.get_alignment_from_style(style)
        return TextAlignmentEngine.calculate_x(rect, text_width, alignment)

