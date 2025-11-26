"""
Theme for DOCX documents.

Handles theme functionality, color scheme support, font scheme support, effect scheme support, and theme inheritance.
"""

from typing import Dict, Any, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)

class Theme:
    """
    Represents document theme and color schemes.
    
    Handles theme functionality, color scheme support, font scheme support, and effect scheme support.
    """
    
    def __init__(self, theme_name: str = "Default"):
        """
        Initialize theme.
        
        Args:
            theme_name: Theme name
        """
        self.theme_name = theme_name
        self.color_scheme = {}
        self.font_scheme = {}
        self.effect_scheme = {}
        self.validation_errors = []
        self.theme_stats = {
            'colors': 0,
            'fonts': 0,
            'effects': 0,
            'customizations': 0
        }
        
        # Initialize with default theme
        self._initialize_default_theme()
        
        logger.debug(f"Theme initialized: {theme_name}")
    
    def set_color_scheme(self, color_scheme: Dict[str, Any]) -> None:
        """
        Set color scheme.
        
        Args:
            color_scheme: Color scheme dictionary
        """
        if not isinstance(color_scheme, dict):
            raise ValueError("Color scheme must be a dictionary")
        
        # Validate color scheme
        if not self._validate_color_scheme(color_scheme):
            raise ValueError("Invalid color scheme")
        
        self.color_scheme = color_scheme.copy()
        self.theme_stats['colors'] = len(color_scheme)
        self.theme_stats['customizations'] += 1
        
        logger.debug(f"Color scheme set: {len(color_scheme)} colors")
    
    def set_font_scheme(self, font_scheme: Dict[str, Any]) -> None:
        """
        Set font scheme.
        
        Args:
            font_scheme: Font scheme dictionary
        """
        if not isinstance(font_scheme, dict):
            raise ValueError("Font scheme must be a dictionary")
        
        # Validate font scheme
        if not self._validate_font_scheme(font_scheme):
            raise ValueError("Invalid font scheme")
        
        self.font_scheme = font_scheme.copy()
        self.theme_stats['fonts'] = len(font_scheme)
        self.theme_stats['customizations'] += 1
        
        logger.debug(f"Font scheme set: {len(font_scheme)} fonts")
    
    def set_effect_scheme(self, effect_scheme: Dict[str, Any]) -> None:
        """
        Set effect scheme.
        
        Args:
            effect_scheme: Effect scheme dictionary
        """
        if not isinstance(effect_scheme, dict):
            raise ValueError("Effect scheme must be a dictionary")
        
        # Validate effect scheme
        if not self._validate_effect_scheme(effect_scheme):
            raise ValueError("Invalid effect scheme")
        
        self.effect_scheme = effect_scheme.copy()
        self.theme_stats['effects'] = len(effect_scheme)
        self.theme_stats['customizations'] += 1
        
        logger.debug(f"Effect scheme set: {len(effect_scheme)} effects")
    
    def get_color(self, color_name: str) -> Optional[str]:
        """
        Get color by name.
        
        Args:
            color_name: Color name
            
        Returns:
            Color value or None if not found
        """
        if not color_name or not isinstance(color_name, str):
            raise ValueError("Color name must be a non-empty string")
        
        if color_name in self.color_scheme:
            logger.debug(f"Color retrieved: {color_name}")
            return self.color_scheme[color_name]
        
        logger.debug(f"Color not found: {color_name}")
        return None
    
    def get_font(self, font_name: str) -> Optional[str]:
        """
        Get font by name.
        
        Args:
            font_name: Font name
            
        Returns:
            Font value or None if not found
        """
        if not font_name or not isinstance(font_name, str):
            raise ValueError("Font name must be a non-empty string")
        
        if font_name in self.font_scheme:
            logger.debug(f"Font retrieved: {font_name}")
            return self.font_scheme[font_name]
        
        logger.debug(f"Font not found: {font_name}")
        return None
    
    def get_effect(self, effect_name: str) -> Optional[str]:
        """
        Get effect by name.
        
        Args:
            effect_name: Effect name
            
        Returns:
            Effect value or None if not found
        """
        if not effect_name or not isinstance(effect_name, str):
            raise ValueError("Effect name must be a non-empty string")
        
        if effect_name in self.effect_scheme:
            logger.debug(f"Effect retrieved: {effect_name}")
            return self.effect_scheme[effect_name]
        
        logger.debug(f"Effect not found: {effect_name}")
        return None
    
    def add_color(self, color_name: str, color_value: str) -> None:
        """
        Add color to theme.
        
        Args:
            color_name: Color name
            color_value: Color value
        """
        if not color_name or not isinstance(color_name, str):
            raise ValueError("Color name must be a non-empty string")
        
        if not color_value or not isinstance(color_value, str):
            raise ValueError("Color value must be a non-empty string")
        
        self.color_scheme[color_name] = color_value
        self.theme_stats['colors'] += 1
        self.theme_stats['customizations'] += 1
        
        logger.debug(f"Color added: {color_name} = {color_value}")
    
    def add_font(self, font_name: str, font_value: str) -> None:
        """
        Add font to theme.
        
        Args:
            font_name: Font name
            font_value: Font value
        """
        if not font_name or not isinstance(font_name, str):
            raise ValueError("Font name must be a non-empty string")
        
        if not font_value or not isinstance(font_value, str):
            raise ValueError("Font value must be a non-empty string")
        
        self.font_scheme[font_name] = font_value
        self.theme_stats['fonts'] += 1
        self.theme_stats['customizations'] += 1
        
        logger.debug(f"Font added: {font_name} = {font_value}")
    
    def add_effect(self, effect_name: str, effect_value: str) -> None:
        """
        Add effect to theme.
        
        Args:
            effect_name: Effect name
            effect_value: Effect value
        """
        if not effect_name or not isinstance(effect_name, str):
            raise ValueError("Effect name must be a non-empty string")
        
        if not effect_value or not isinstance(effect_value, str):
            raise ValueError("Effect value must be a non-empty string")
        
        self.effect_scheme[effect_name] = effect_value
        self.theme_stats['effects'] += 1
        self.theme_stats['customizations'] += 1
        
        logger.debug(f"Effect added: {effect_name} = {effect_value}")
    
    def remove_color(self, color_name: str) -> bool:
        """
        Remove color from theme.
        
        Args:
            color_name: Color name to remove
            
        Returns:
            True if color was removed, False if not found
        """
        if color_name in self.color_scheme:
            del self.color_scheme[color_name]
            self.theme_stats['colors'] -= 1
            logger.debug(f"Color removed: {color_name}")
            return True
        return False
    
    def remove_font(self, font_name: str) -> bool:
        """
        Remove font from theme.
        
        Args:
            font_name: Font name to remove
            
        Returns:
            True if font was removed, False if not found
        """
        if font_name in self.font_scheme:
            del self.font_scheme[font_name]
            self.theme_stats['fonts'] -= 1
            logger.debug(f"Font removed: {font_name}")
            return True
        return False
    
    def remove_effect(self, effect_name: str) -> bool:
        """
        Remove effect from theme.
        
        Args:
            effect_name: Effect name to remove
            
        Returns:
            True if effect was removed, False if not found
        """
        if effect_name in self.effect_scheme:
            del self.effect_scheme[effect_name]
            self.theme_stats['effects'] -= 1
            logger.debug(f"Effect removed: {effect_name}")
            return True
        return False
    
    def get_color_scheme(self) -> Dict[str, str]:
        """
        Get color scheme.
        
        Returns:
            Color scheme dictionary
        """
        return self.color_scheme.copy()
    
    def get_font_scheme(self) -> Dict[str, str]:
        """
        Get font scheme.
        
        Returns:
            Font scheme dictionary
        """
        return self.font_scheme.copy()
    
    def get_effect_scheme(self) -> Dict[str, str]:
        """
        Get effect scheme.
        
        Returns:
            Effect scheme dictionary
        """
        return self.effect_scheme.copy()
    
    def validate(self) -> bool:
        """
        Validate theme.
        
        Returns:
            True if theme is valid, False otherwise
        """
        self.validation_errors = []
        
        # Validate color scheme
        if not self._validate_color_scheme(self.color_scheme):
            self.validation_errors.append("Invalid color scheme")
        
        # Validate font scheme
        if not self._validate_font_scheme(self.font_scheme):
            self.validation_errors.append("Invalid font scheme")
        
        # Validate effect scheme
        if not self._validate_effect_scheme(self.effect_scheme):
            self.validation_errors.append("Invalid effect scheme")
        
        is_valid = len(self.validation_errors) == 0
        logger.debug(f"Theme validation: {'valid' if is_valid else 'invalid'}")
        
        return is_valid
    
    def get_validation_errors(self) -> List[str]:
        """
        Get validation errors.
        
        Returns:
            List of validation errors
        """
        return self.validation_errors.copy()
    
    def get_theme_stats(self) -> Dict[str, int]:
        """
        Get theme statistics.
        
        Returns:
            Dictionary with theme statistics
        """
        return self.theme_stats.copy()
    
    def get_theme_info(self) -> Dict[str, Any]:
        """
        Get theme information.
        
        Returns:
            Dictionary with theme information
        """
        return {
            'theme_name': self.theme_name,
            'colors_count': len(self.color_scheme),
            'fonts_count': len(self.font_scheme),
            'effects_count': len(self.effect_scheme),
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors),
            'stats': self.theme_stats.copy()
        }
    
    def clear_theme(self) -> None:
        """Clear all theme data."""
        self.color_scheme.clear()
        self.font_scheme.clear()
        self.effect_scheme.clear()
        self.validation_errors.clear()
        self.theme_stats = {
            'colors': 0,
            'fonts': 0,
            'effects': 0,
            'customizations': 0
        }
        logger.debug("Theme cleared")
    
    def _initialize_default_theme(self) -> None:
        """Initialize default theme."""
        # Default color scheme
        self.color_scheme = {
            'accent1': '#4472C4',
            'accent2': '#E7E6E6',
            'accent3': '#A5A5A5',
            'accent4': '#FFC000',
            'accent5': '#5B9BD5',
            'accent6': '#70AD47',
            'dark1': '#000000',
            'dark2': '#44546A',
            'light1': '#FFFFFF',
            'light2': '#E7E6E6'
        }
        
        # Default font scheme
        self.font_scheme = {
            'major_font': 'Calibri',
            'minor_font': 'Calibri',
            'heading_font': 'Calibri',
            'body_font': 'Calibri'
        }
        
        # Default effect scheme
        self.effect_scheme = {
            'line_style': 'solid',
            'fill_style': 'solid',
            'shadow_style': 'none',
            'glow_style': 'none'
        }
        
        # Update stats
        self.theme_stats['colors'] = len(self.color_scheme)
        self.theme_stats['fonts'] = len(self.font_scheme)
        self.theme_stats['effects'] = len(self.effect_scheme)
    
    def _validate_color_scheme(self, color_scheme: Dict[str, Any]) -> bool:
        """
        Validate color scheme.
        
        Args:
            color_scheme: Color scheme to validate
            
        Returns:
            True if color scheme is valid, False otherwise
        """
        if not isinstance(color_scheme, dict):
            return False
        
        for color_name, color_value in color_scheme.items():
            if not isinstance(color_name, str) or not isinstance(color_value, str):
                return False
        
        return True
    
    def _validate_font_scheme(self, font_scheme: Dict[str, Any]) -> bool:
        """
        Validate font scheme.
        
        Args:
            font_scheme: Font scheme to validate
            
        Returns:
            True if font scheme is valid, False otherwise
        """
        if not isinstance(font_scheme, dict):
            return False
        
        for font_name, font_value in font_scheme.items():
            if not isinstance(font_name, str) or not isinstance(font_value, str):
                return False
        
        return True
    
    def _validate_effect_scheme(self, effect_scheme: Dict[str, Any]) -> bool:
        """
        Validate effect scheme.
        
        Args:
            effect_scheme: Effect scheme to validate
            
        Returns:
            True if effect scheme is valid, False otherwise
        """
        if not isinstance(effect_scheme, dict):
            return False
        
        for effect_name, effect_value in effect_scheme.items():
            if not isinstance(effect_name, str) or not isinstance(effect_value, str):
                return False
        
        return True
    
    def get_theme_summary(self) -> Dict[str, Any]:
        """
        Get theme summary.
        
        Returns:
            Dictionary with theme summary
        """
        return {
            'theme_name': self.theme_name,
            'total_elements': len(self.color_scheme) + len(self.font_scheme) + len(self.effect_scheme),
            'color_scheme': list(self.color_scheme.keys()),
            'font_scheme': list(self.font_scheme.keys()),
            'effect_scheme': list(self.effect_scheme.keys()),
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors),
            'stats': self.theme_stats.copy()
        }
