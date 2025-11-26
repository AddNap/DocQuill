"""
Run style for DOCX documents.

Handles run style functionality, character formatting, font support, color support, and formatting support.
"""

from typing import Dict, Any, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)

class RunStyle:
    """
    Represents run style and character formatting.
    
    Handles run style functionality, character formatting, font support, and color support.
    """
    
    def __init__(self, style_name: str = "", parent_style: str = ""):
        """
        Initialize run style.
        
        Args:
            style_name: Style name
            parent_style: Parent style name
        """
        self.style_name = style_name
        self.parent_style = parent_style
        self.properties = {}
        self.validation_errors = []
        
        # Initialize default properties
        self._initialize_default_properties()
        
        logger.debug(f"RunStyle initialized: {style_name}")
    
    def set_font(self, font_name: str, font_size: float) -> None:
        """
        Set font properties.
        
        Args:
            font_name: Font family name
            font_size: Font size in points
        """
        if not font_name or not isinstance(font_name, str):
            raise ValueError("Font name must be a non-empty string")
        
        if not isinstance(font_size, (int, float)) or font_size <= 0:
            raise ValueError("Font size must be a positive number")
        
        self.properties['font_family'] = font_name
        self.properties['font_size'] = font_size
        
        logger.debug(f"Font properties set: {font_name}, {font_size}pt")
    
    def set_color(self, color: str) -> None:
        """
        Set text color.
        
        Args:
            color: Color value (hex, rgb, or color name)
        """
        if not color or not isinstance(color, str):
            raise ValueError("Color must be a non-empty string")
        
        self.properties['color'] = color
        logger.debug(f"Text color set to: {color}")
    
    def set_bold(self, bold: bool) -> None:
        """
        Set bold formatting.
        
        Args:
            bold: Bold formatting flag
        """
        if not isinstance(bold, bool):
            raise ValueError("Bold must be a boolean value")
        
        self.properties['bold'] = bold
        logger.debug(f"Bold formatting set to: {bold}")
    
    def set_italic(self, italic: bool) -> None:
        """
        Set italic formatting.
        
        Args:
            italic: Italic formatting flag
        """
        if not isinstance(italic, bool):
            raise ValueError("Italic must be a boolean value")
        
        self.properties['italic'] = italic
        logger.debug(f"Italic formatting set to: {italic}")
    
    def set_underline(self, underline: str) -> None:
        """
        Set underline formatting.
        
        Args:
            underline: Underline type (none, single, double, thick, dotted, dashed)
        """
        if not isinstance(underline, str):
            raise ValueError("Underline must be a string")
        
        valid_underlines = ['none', 'single', 'double', 'thick', 'dotted', 'dashed', 'wave']
        if underline not in valid_underlines:
            raise ValueError(f"Invalid underline type: {underline}. Must be one of: {valid_underlines}")
        
        self.properties['underline'] = underline
        logger.debug(f"Underline formatting set to: {underline}")
    
    def set_strikethrough(self, strikethrough: bool) -> None:
        """
        Set strikethrough formatting.
        
        Args:
            strikethrough: Strikethrough formatting flag
        """
        if not isinstance(strikethrough, bool):
            raise ValueError("Strikethrough must be a boolean value")
        
        self.properties['strikethrough'] = strikethrough
        logger.debug(f"Strikethrough formatting set to: {strikethrough}")
    
    def set_superscript(self, superscript: bool) -> None:
        """
        Set superscript formatting.
        
        Args:
            superscript: Superscript formatting flag
        """
        if not isinstance(superscript, bool):
            raise ValueError("Superscript must be a boolean value")
        
        self.properties['superscript'] = superscript
        logger.debug(f"Superscript formatting set to: {superscript}")
    
    def set_subscript(self, subscript: bool) -> None:
        """
        Set subscript formatting.
        
        Args:
            subscript: Subscript formatting flag
        """
        if not isinstance(subscript, bool):
            raise ValueError("Subscript must be a boolean value")
        
        self.properties['subscript'] = subscript
        logger.debug(f"Subscript formatting set to: {subscript}")
    
    def get_font(self) -> Dict[str, Any]:
        """
        Get font properties.
        
        Returns:
            Dictionary with font properties
        """
        return {
            'font_family': self.properties.get('font_family', 'Calibri'),
            'font_size': self.properties.get('font_size', 11)
        }
    
    def get_color(self) -> str:
        """
        Get text color.
        
        Returns:
            Text color value
        """
        return self.properties.get('color', 'auto')
    
    def get_bold(self) -> bool:
        """
        Get bold formatting.
        
        Returns:
            Bold formatting flag
        """
        return self.properties.get('bold', False)
    
    def get_italic(self) -> bool:
        """
        Get italic formatting.
        
        Returns:
            Italic formatting flag
        """
        return self.properties.get('italic', False)
    
    def get_underline(self) -> str:
        """
        Get underline formatting.
        
        Returns:
            Underline type
        """
        return self.properties.get('underline', 'none')
    
    def get_strikethrough(self) -> bool:
        """
        Get strikethrough formatting.
        
        Returns:
            Strikethrough formatting flag
        """
        return self.properties.get('strikethrough', False)
    
    def get_superscript(self) -> bool:
        """
        Get superscript formatting.
        
        Returns:
            Superscript formatting flag
        """
        return self.properties.get('superscript', False)
    
    def get_subscript(self) -> bool:
        """
        Get subscript formatting.
        
        Returns:
            Subscript formatting flag
        """
        return self.properties.get('subscript', False)
    
    def set_property(self, property_name: str, property_value: Any) -> None:
        """
        Set style property.
        
        Args:
            property_name: Property name
            property_value: Property value
        """
        if not property_name or not isinstance(property_name, str):
            raise ValueError("Property name must be a non-empty string")
        
        self.properties[property_name] = property_value
        logger.debug(f"Style property set: {property_name} = {property_value}")
    
    def get_property(self, property_name: str, default: Any = None) -> Any:
        """
        Get style property.
        
        Args:
            property_name: Property name
            default: Default value if property not found
            
        Returns:
            Property value or default
        """
        return self.properties.get(property_name, default)
    
    def has_property(self, property_name: str) -> bool:
        """
        Check if style has property.
        
        Args:
            property_name: Property name
            
        Returns:
            True if property exists, False otherwise
        """
        return property_name in self.properties
    
    def remove_property(self, property_name: str) -> bool:
        """
        Remove style property.
        
        Args:
            property_name: Property name to remove
            
        Returns:
            True if property was removed, False if not found
        """
        if property_name in self.properties:
            del self.properties[property_name]
            logger.debug(f"Style property removed: {property_name}")
            return True
        return False
    
    def validate(self) -> bool:
        """
        Validate run style.
        
        Returns:
            True if style is valid, False otherwise
        """
        self.validation_errors = []
        
        # Validate font family
        font_family = self.properties.get('font_family', 'Calibri')
        if not font_family or not isinstance(font_family, str):
            self.validation_errors.append("Invalid font family")
        
        # Validate font size
        font_size = self.properties.get('font_size', 11)
        if not isinstance(font_size, (int, float)) or font_size <= 0:
            self.validation_errors.append("Invalid font size")
        
        # Validate color
        color = self.properties.get('color', 'auto')
        if not color or not isinstance(color, str):
            self.validation_errors.append("Invalid color value")
        
        # Validate boolean properties
        boolean_props = ['bold', 'italic', 'strikethrough', 'superscript', 'subscript']
        for prop in boolean_props:
            if prop in self.properties and not isinstance(self.properties[prop], bool):
                self.validation_errors.append(f"Invalid {prop} value")
        
        # Validate underline
        underline = self.properties.get('underline', 'none')
        valid_underlines = ['none', 'single', 'double', 'thick', 'dotted', 'dashed', 'wave']
        if underline not in valid_underlines:
            self.validation_errors.append(f"Invalid underline type: {underline}")
        
        is_valid = len(self.validation_errors) == 0
        logger.debug(f"RunStyle validation: {'valid' if is_valid else 'invalid'}")
        
        return is_valid
    
    def get_validation_errors(self) -> List[str]:
        """
        Get validation errors.
        
        Returns:
            List of validation errors
        """
        return self.validation_errors.copy()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert run style to dictionary.
        
        Returns:
            Dictionary representation of run style
        """
        return {
            'type': 'run_style',
            'style_name': self.style_name,
            'parent_style': self.parent_style,
            'properties': self.properties.copy(),
            'validation_errors': self.validation_errors.copy()
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        Load run style from dictionary.
        
        Args:
            data: Dictionary data
        """
        self.style_name = data.get('style_name', '')
        self.parent_style = data.get('parent_style', '')
        self.properties = data.get('properties', {})
        self.validation_errors = data.get('validation_errors', [])
        
        logger.debug(f"RunStyle loaded from dictionary: {self.style_name}")
    
    def get_style_info(self) -> Dict[str, Any]:
        """
        Get run style information.
        
        Returns:
            Dictionary with style information
        """
        return {
            'style_name': self.style_name,
            'parent_style': self.parent_style,
            'properties_count': len(self.properties),
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors)
        }
    
    def clear_properties(self) -> None:
        """Clear all style properties."""
        self.properties.clear()
        logger.debug("All style properties cleared")
    
    def get_properties_count(self) -> int:
        """
        Get number of properties.
        
        Returns:
            Number of properties
        """
        return len(self.properties)
    
    def update_property(self, property_name: str, property_value: Any) -> None:
        """
        Update style property.
        
        Args:
            property_name: Property name
            property_value: Property value
        """
        if not property_name or not isinstance(property_name, str):
            raise ValueError("Property name must be a non-empty string")
        
        self.properties[property_name] = property_value
        logger.debug(f"Style property updated: {property_name} = {property_value}")
    
    def get_property_names(self) -> List[str]:
        """
        Get list of property names.
        
        Returns:
            List of property names
        """
        return list(self.properties.keys())
    
    def _initialize_default_properties(self) -> None:
        """Initialize default run properties."""
        self.properties = {
            'font_family': 'Calibri',
            'font_size': 11,
            'color': 'auto',
            'bold': False,
            'italic': False,
            'underline': 'none',
            'strikethrough': False,
            'superscript': False,
            'subscript': False
        }
    
    def get_style_summary(self) -> Dict[str, Any]:
        """
        Get style summary.
        
        Returns:
            Dictionary with style summary
        """
        return {
            'style_name': self.style_name,
            'parent_style': self.parent_style,
            'properties_count': len(self.properties),
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors),
            'has_formatting': any(self.properties.get(prop, False) for prop in ['bold', 'italic', 'underline', 'strikethrough']),
            'has_positioning': any(self.properties.get(prop, False) for prop in ['superscript', 'subscript']),
            'font_info': self.get_font()
        }
