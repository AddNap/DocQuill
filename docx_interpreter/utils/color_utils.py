"""Color utilities for DOCX documents."""

from typing import Dict, Any, Optional, Tuple

class ColorUtils:
    """Utility functions for color conversion and validation."""
    
    def __init__(self):
        """Initialize color utilities."""
        self.color_map = {
            'black': (0, 0, 0),
            'white': (255, 255, 255),
            'red': (255, 0, 0),
            'green': (0, 255, 0),
            'blue': (0, 0, 255),
            'yellow': (255, 255, 0),
            'cyan': (0, 255, 255),
            'magenta': (255, 0, 255),
            'gray': (128, 128, 128),
            'grey': (128, 128, 128)
        }
    
    def hex_to_rgb(self, hex_color):
        """Convert hex color to RGB."""
        if not hex_color or not isinstance(hex_color, str):
            return None
        
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 3:
            hex_color = ''.join([c*2 for c in hex_color])
        
        try:
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        except ValueError:
            return None
    
    def rgb_to_hex(self, rgb_color):
        """Convert RGB color to hex."""
        if not rgb_color or not isinstance(rgb_color, (tuple, list)) or len(rgb_color) != 3:
            return None
        
        try:
            r, g, b = [int(c) for c in rgb_color]
            return f"#{r:02x}{g:02x}{b:02x}"
        except (ValueError, TypeError):
            return None
    
    def parse_theme_color(self, theme_color):
        """Parse theme color reference."""
        if not theme_color or not isinstance(theme_color, str):
            return None
        
        theme_color = theme_color.lower()
        return self.color_map.get(theme_color)
    
    def validate_color(self, color_value):
        """Validate color value."""
        if not color_value:
            return False
        
        if isinstance(color_value, str):
            # Check if it's a hex color
            if color_value.startswith('#'):
                return self.hex_to_rgb(color_value) is not None
            # Check if it's a named color
            return color_value.lower() in self.color_map
        
        if isinstance(color_value, (tuple, list)) and len(color_value) == 3:
            try:
                r, g, b = [int(c) for c in color_value]
                return 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255
            except (ValueError, TypeError):
                return False
        
        return False
    
    def normalize_color(self, color_value):
        """Normalize color value."""
        if not color_value:
            return None
        
        if isinstance(color_value, str):
            if color_value.startswith('#'):
                return self.hex_to_rgb(color_value)
            else:
                return self.parse_theme_color(color_value)
        
        if isinstance(color_value, (tuple, list)) and len(color_value) == 3:
            return tuple(color_value)
        
        return None
