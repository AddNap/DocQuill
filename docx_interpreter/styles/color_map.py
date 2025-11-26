"""
Color map for DOCX documents.

Handles color map functionality, color mapping, theme color resolution, color validation, and color conversion.
"""

from typing import Dict, Any, Optional, Tuple, List
import re
import logging

logger = logging.getLogger(__name__)

class ColorMap:
    """
    Maps theme color names to RGB values.
    
    Handles color map functionality, color mapping, theme color resolution, and color validation.
    """
    
    def __init__(self):
        """
        Initialize color map.
        
        Sets up color mapping, theme colors, and color validation.
        """
        self.color_mappings = {}
        self.theme_colors = {}
        self.color_cache = {}
        self.color_stats = {
            'mappings': 0,
            'resolutions': 0,
            'conversions': 0,
            'validations': 0
        }
        
        # Default theme colors
        self.default_theme_colors = {
            'accent1': (255, 0, 0),      # Red
            'accent2': (0, 255, 0),      # Green
            'accent3': (0, 0, 255),     # Blue
            'accent4': (255, 255, 0),   # Yellow
            'accent5': (255, 0, 255),   # Magenta
            'accent6': (0, 255, 255),   # Cyan
            'dark1': (0, 0, 0),         # Black
            'dark2': (128, 128, 128),   # Gray
            'light1': (255, 255, 255),  # White
            'light2': (192, 192, 192)   # Light Gray
        }
        
        # Initialize with default theme colors
        self.theme_colors.update(self.default_theme_colors)
        
        logger.debug("ColorMap initialized")
    
    def add_color_mapping(self, color_name: str, rgb_value: Tuple[int, int, int]) -> None:
        """
        Add color mapping.
        
        Args:
            color_name: Color name
            rgb_value: RGB color value
        """
        if not color_name or not isinstance(color_name, str):
            raise ValueError("Color name must be a non-empty string")
        
        if not isinstance(rgb_value, tuple) or len(rgb_value) != 3:
            raise ValueError("RGB value must be a tuple of 3 integers")
        
        if not all(isinstance(x, int) and 0 <= x <= 255 for x in rgb_value):
            raise ValueError("RGB values must be integers between 0 and 255")
        
        self.color_mappings[color_name] = rgb_value
        self.color_stats['mappings'] += 1
        
        logger.debug(f"Color mapping added: {color_name} -> {rgb_value}")
    
    def get_color_rgb(self, color_name: str) -> Optional[Tuple[int, int, int]]:
        """
        Get RGB value for color name.
        
        Args:
            color_name: Color name
            
        Returns:
            RGB color value or None if not found
        """
        if not color_name or not isinstance(color_name, str):
            raise ValueError("Color name must be a non-empty string")
        
        # Check cache first
        if color_name in self.color_cache:
            self.color_stats['resolutions'] += 1
            logger.debug(f"Color cache hit: {color_name}")
            return self.color_cache[color_name]
        
        # Check color mappings
        if color_name in self.color_mappings:
            rgb_value = self.color_mappings[color_name]
            self.color_cache[color_name] = rgb_value
            self.color_stats['resolutions'] += 1
            logger.debug(f"Color found in mappings: {color_name} -> {rgb_value}")
            return rgb_value
        
        # Check theme colors
        if color_name in self.theme_colors:
            rgb_value = self.theme_colors[color_name]
            self.color_cache[color_name] = rgb_value
            self.color_stats['resolutions'] += 1
            logger.debug(f"Color found in theme: {color_name} -> {rgb_value}")
            return rgb_value
        
        logger.debug(f"Color not found: {color_name}")
        return None
    
    def resolve_theme_color(self, theme_color: str) -> Optional[Tuple[int, int, int]]:
        """
        Resolve theme color to RGB.
        
        Args:
            theme_color: Theme color name
            
        Returns:
            RGB color value or None if not found
        """
        if not theme_color or not isinstance(theme_color, str):
            raise ValueError("Theme color must be a non-empty string")
        
        # Check if it's a theme color
        if theme_color.startswith('theme'):
            # Extract theme color name
            theme_name = theme_color.replace('theme', '').lower()
            if theme_name in self.theme_colors:
                rgb_value = self.theme_colors[theme_name]
                self.color_cache[theme_color] = rgb_value
                self.color_stats['resolutions'] += 1
                logger.debug(f"Theme color resolved: {theme_color} -> {rgb_value}")
                return rgb_value
        
        # Try direct lookup
        return self.get_color_rgb(theme_color)
    
    def convert_color(self, color_value: Any, target_format: str) -> Optional[str]:
        """
        Convert color between formats.
        
        Args:
            color_value: Color value to convert
            target_format: Target format (hex, rgb, hsl)
            
        Returns:
            Converted color value or None if conversion fails
        """
        if not target_format or not isinstance(target_format, str):
            raise ValueError("Target format must be a non-empty string")
        
        try:
            # Parse input color
            rgb_value = self._parse_color(color_value)
            if not rgb_value:
                return None
            
            # Convert to target format
            if target_format.lower() == 'hex':
                return self._rgb_to_hex(rgb_value)
            elif target_format.lower() == 'rgb':
                return f"rgb({rgb_value[0]}, {rgb_value[1]}, {rgb_value[2]})"
            elif target_format.lower() == 'hsl':
                return self._rgb_to_hsl(rgb_value)
            else:
                raise ValueError(f"Unsupported target format: {target_format}")
            
            self.color_stats['conversions'] += 1
            logger.debug(f"Color converted: {color_value} -> {target_format}")
            
        except Exception as e:
            logger.error(f"Color conversion failed: {e}")
            return None
    
    def validate_color(self, color_value: Any) -> bool:
        """
        Validate color value.
        
        Args:
            color_value: Color value to validate
            
        Returns:
            True if color is valid, False otherwise
        """
        try:
            rgb_value = self._parse_color(color_value)
            if not rgb_value:
                return False
            
            # Validate RGB values
            if not all(isinstance(x, int) and 0 <= x <= 255 for x in rgb_value):
                return False
            
            self.color_stats['validations'] += 1
            logger.debug(f"Color validation passed: {color_value}")
            return True
            
        except Exception as e:
            logger.error(f"Color validation failed: {e}")
            return False
    
    def get_color_mappings(self) -> Dict[str, Tuple[int, int, int]]:
        """
        Get all color mappings.
        
        Returns:
            Dictionary of color mappings
        """
        return self.color_mappings.copy()
    
    def get_theme_colors(self) -> Dict[str, Tuple[int, int, int]]:
        """
        Get all theme colors.
        
        Returns:
            Dictionary of theme colors
        """
        return self.theme_colors.copy()
    
    def get_color_stats(self) -> Dict[str, int]:
        """
        Get color statistics.
        
        Returns:
            Dictionary with color statistics
        """
        return self.color_stats.copy()
    
    def clear_cache(self) -> None:
        """Clear color cache."""
        self.color_cache.clear()
        logger.debug("Color cache cleared")
    
    def add_theme_color(self, theme_name: str, rgb_value: Tuple[int, int, int]) -> None:
        """
        Add theme color.
        
        Args:
            theme_name: Theme color name
            rgb_value: RGB color value
        """
        if not theme_name or not isinstance(theme_name, str):
            raise ValueError("Theme name must be a non-empty string")
        
        if not isinstance(rgb_value, tuple) or len(rgb_value) != 3:
            raise ValueError("RGB value must be a tuple of 3 integers")
        
        if not all(isinstance(x, int) and 0 <= x <= 255 for x in rgb_value):
            raise ValueError("RGB values must be integers between 0 and 255")
        
        self.theme_colors[theme_name] = rgb_value
        logger.debug(f"Theme color added: {theme_name} -> {rgb_value}")
    
    def remove_color_mapping(self, color_name: str) -> bool:
        """
        Remove color mapping.
        
        Args:
            color_name: Color name to remove
            
        Returns:
            True if color was removed, False if not found
        """
        if color_name in self.color_mappings:
            del self.color_mappings[color_name]
            logger.debug(f"Color mapping removed: {color_name}")
            return True
        return False
    
    def _parse_color(self, color_value: Any) -> Optional[Tuple[int, int, int]]:
        """
        Parse color value to RGB.
        
        Args:
            color_value: Color value to parse
            
        Returns:
            RGB tuple or None if parsing fails
        """
        if isinstance(color_value, tuple) and len(color_value) == 3:
            return color_value
        
        if isinstance(color_value, str):
            # Try to parse hex color
            if color_value.startswith('#'):
                return self._hex_to_rgb(color_value)
            
            # Try to parse RGB string
            if color_value.startswith('rgb('):
                return self._parse_rgb_string(color_value)
            
            # Try to parse HSL string
            if color_value.startswith('hsl('):
                return self._parse_hsl_string(color_value)
        
        return None
    
    def _hex_to_rgb(self, hex_color: str) -> Optional[Tuple[int, int, int]]:
        """
        Convert hex color to RGB.
        
        Args:
            hex_color: Hex color string
            
        Returns:
            RGB tuple or None if conversion fails
        """
        try:
            hex_color = hex_color.lstrip('#')
            if len(hex_color) == 3:
                hex_color = ''.join([c*2 for c in hex_color])
            
            if len(hex_color) != 6:
                return None
            
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            
        except Exception:
            return None
    
    def _rgb_to_hex(self, rgb_value: Tuple[int, int, int]) -> str:
        """
        Convert RGB to hex color.
        
        Args:
            rgb_value: RGB color tuple
            
        Returns:
            Hex color string
        """
        return f"#{rgb_value[0]:02x}{rgb_value[1]:02x}{rgb_value[2]:02x}"
    
    def _rgb_to_hsl(self, rgb_value: Tuple[int, int, int]) -> str:
        """
        Convert RGB to HSL.
        
        Args:
            rgb_value: RGB color tuple
            
        Returns:
            HSL color string
        """
        r, g, b = [x/255.0 for x in rgb_value]
        
        max_val = max(r, g, b)
        min_val = min(r, g, b)
        diff = max_val - min_val
        
        # Calculate lightness
        l = (max_val + min_val) / 2
        
        if diff == 0:
            h = s = 0
        else:
            # Calculate saturation
            s = diff / (2 - max_val - min_val) if l > 0.5 else diff / (max_val + min_val)
            
            # Calculate hue
            if max_val == r:
                h = (g - b) / diff + (6 if g < b else 0)
            elif max_val == g:
                h = (b - r) / diff + 2
            else:
                h = (r - g) / diff + 4
            
            h /= 6
        
        return f"hsl({int(h*360)}, {int(s*100)}%, {int(l*100)}%)"
    
    def _parse_rgb_string(self, rgb_string: str) -> Optional[Tuple[int, int, int]]:
        """
        Parse RGB string to RGB tuple.
        
        Args:
            rgb_string: RGB color string
            
        Returns:
            RGB tuple or None if parsing fails
        """
        try:
            # Extract numbers from rgb(r, g, b)
            numbers = re.findall(r'\d+', rgb_string)
            if len(numbers) == 3:
                return tuple(int(x) for x in numbers)
        except Exception:
            pass
        
        return None
    
    def _parse_hsl_string(self, hsl_string: str) -> Optional[Tuple[int, int, int]]:
        """
        Parse HSL string to RGB tuple.
        
        Args:
            hsl_string: HSL color string
            
        Returns:
            RGB tuple or None if parsing fails
        """
        try:
            # Extract numbers from hsl(h, s%, l%)
            numbers = re.findall(r'\d+', hsl_string)
            if len(numbers) == 3:
                h, s, l = [int(x) for x in numbers]
                return self._hsl_to_rgb(h, s, l)
        except Exception:
            pass
        
        return None
    
    def _hsl_to_rgb(self, h: int, s: int, l: int) -> Tuple[int, int, int]:
        """
        Convert HSL to RGB.
        
        Args:
            h: Hue (0-360)
            s: Saturation (0-100)
            l: Lightness (0-100)
            
        Returns:
            RGB tuple
        """
        h = h / 360.0
        s = s / 100.0
        l = l / 100.0
        
        if s == 0:
            r = g = b = l
        else:
            def hue_to_rgb(p, q, t):
                if t < 0:
                    t += 1
                if t > 1:
                    t -= 1
                if t < 1/6:
                    return p + (q - p) * 6 * t
                if t < 1/2:
                    return q
                if t < 2/3:
                    return p + (q - p) * (2/3 - t) * 6
                return p
            
            q = l * (1 + s) if l < 0.5 else l + s - l * s
            p = 2 * l - q
            
            r = hue_to_rgb(p, q, h + 1/3)
            g = hue_to_rgb(p, q, h)
            b = hue_to_rgb(p, q, h - 1/3)
        
        return (int(r * 255), int(g * 255), int(b * 255))
    
    def get_color_info(self, color_name: str) -> Optional[Dict[str, Any]]:
        """
        Get color information.
        
        Args:
            color_name: Color name
            
        Returns:
            Color information or None if not found
        """
        rgb_value = self.get_color_rgb(color_name)
        if not rgb_value:
            return None
        
        return {
            'name': color_name,
            'rgb': rgb_value,
            'hex': self._rgb_to_hex(rgb_value),
            'hsl': self._rgb_to_hsl(rgb_value),
            'is_theme_color': color_name in self.theme_colors,
            'is_mapped_color': color_name in self.color_mappings
        }
