"""Utility functions for PDF generation."""

from typing import Tuple


def hex_to_rgb(hex_color: str, default: Tuple[float, float, float] = (0.0, 0.0, 0.0)) -> Tuple[float, float, float]:
    """Convert HEX color (#RRGGBB) to RGB tuple (0-1 scale).
    
    Args:
        hex_color: Color in HEX format (e.g., "#FF0000" or "FF0000")
        default: Default color to return if conversion fails
        
    Returns:
        Tuple of (r, g, b) values in 0-1 scale
    """
    # Handle special values
    if not hex_color or hex_color.lower() in ("auto", "none", "transparent"):
        return default
    
    # Remove # if present
    hex_color = hex_color.lstrip("#")
    
    # Validate hex color
    if len(hex_color) != 6:
        return default
    
    try:
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return (r, g, b)
    except (ValueError, IndexError):
        return default


def escape_pdf_string(text: str) -> str:
    """Escape special characters in PDF strings.
    
    Args:
        text: Input string (will be converted to str if not already)
        
    Returns:
        Escaped string for PDF
    """
    # Handle None and non-string inputs
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    
    # PDF string escape: \n, \r, \t, \\, \(, \)
    replacements = {
        "\\": "\\\\",
        "(": "\\(",
        ")": "\\)",
        "\n": "\\n",
        "\r": "\\r",
        "\t": "\\t",
    }
    
    result = text
    for char, escaped in replacements.items():
        result = result.replace(char, escaped)
    
    return result


def format_pdf_number(value: float) -> str:
    """Format number for PDF (limit decimal places).
    
    Args:
        value: Numeric value
        
    Returns:
        Formatted string
    """
    # PDF typically uses 2-3 decimal places
    return f"{value:.3f}".rstrip("0").rstrip(".")


def format_pdf_matrix(a: float, b: float, c: float, d: float, e: float, f: float) -> str:
    """Format transformation matrix for PDF.
    
    Args:
        a, b, c, d, e, f: Matrix values
        
    Returns:
        Formatted matrix string
    """
    return f"{format_pdf_number(a)} {format_pdf_number(b)} {format_pdf_number(c)} {format_pdf_number(d)} {format_pdf_number(e)} {format_pdf_number(f)}"

