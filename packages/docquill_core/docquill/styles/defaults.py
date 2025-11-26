"""
Default styles for DOCX documents.

Handles default styles functionality, default style definitions, default style management, default style validation, and default style inheritance.
"""

from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class DefaultStyles:
    """
    Manages default styles (Normal, DefaultParagraphFont).
    
    Handles default styles functionality, default style definitions, default style management, and default style validation.
    """
    
    def __init__(self):
        """
        Initialize default styles.
        
        Sets up default style definitions, default style management, and default style validation.
        """
        self.default_styles = {}
        self.style_validation_errors = []
        self.style_stats = {
            'total_styles': 0,
            'valid_styles': 0,
            'invalid_styles': 0,
            'customizations': 0
        }
        
        # Initialize with standard default styles
        self._initialize_default_styles()
        
        logger.debug("DefaultStyles initialized")
    
    def get_normal_style(self) -> Dict[str, Any]:
        """
        Get Normal style definition.
        
        Returns:
            Normal style definition
        """
        return self.default_styles.get('Normal', {}).copy()
    
    def get_default_paragraph_font(self) -> Dict[str, Any]:
        """
        Get DefaultParagraphFont style definition.
        
        Returns:
            DefaultParagraphFont style definition
        """
        return self.default_styles.get('DefaultParagraphFont', {}).copy()
    
    def get_default_style(self, style_type: str) -> Optional[Dict[str, Any]]:
        """
        Get default style for type.
        
        Args:
            style_type: Style type
            
        Returns:
            Default style definition or None if not found
        """
        if not style_type or not isinstance(style_type, str):
            raise ValueError("Style type must be a non-empty string")
        
        if style_type in self.default_styles:
            logger.debug(f"Default style retrieved: {style_type}")
            return self.default_styles[style_type].copy()
        
        logger.debug(f"Default style not found: {style_type}")
        return None
    
    def set_default_style(self, style_type: str, style_definition: Dict[str, Any]) -> bool:
        """
        Set default style for type.
        
        Args:
            style_type: Style type
            style_definition: Style definition
            
        Returns:
            True if style was set successfully, False otherwise
        """
        if not style_type or not isinstance(style_type, str):
            raise ValueError("Style type must be a non-empty string")
        
        if not isinstance(style_definition, dict):
            raise ValueError("Style definition must be a dictionary")
        
        try:
            # Validate style definition
            if not self._validate_style_definition(style_definition):
                self.style_stats['invalid_styles'] += 1
                logger.warning(f"Invalid style definition for: {style_type}")
                return False
            
            # Set default style
            self.default_styles[style_type] = style_definition.copy()
            self.style_stats['total_styles'] += 1
            self.style_stats['valid_styles'] += 1
            self.style_stats['customizations'] += 1
            
            logger.debug(f"Default style set: {style_type}")
            return True
            
        except Exception as e:
            self.style_stats['invalid_styles'] += 1
            logger.error(f"Failed to set default style {style_type}: {e}")
            return False
    
    def validate_default_styles(self) -> bool:
        """
        Validate default styles.
        
        Returns:
            True if all default styles are valid, False otherwise
        """
        self.style_validation_errors = []
        
        for style_type, style_definition in self.default_styles.items():
            if not self._validate_style_definition(style_definition):
                self.style_validation_errors.append(f"Invalid style definition for: {style_type}")
        
        is_valid = len(self.style_validation_errors) == 0
        logger.debug(f"Default styles validation: {'valid' if is_valid else 'invalid'}")
        
        return is_valid
    
    def get_validation_errors(self) -> List[str]:
        """
        Get validation errors.
        
        Returns:
            List of validation errors
        """
        return self.style_validation_errors.copy()
    
    def get_default_styles(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all default styles.
        
        Returns:
            Dictionary of all default styles
        """
        return {k: v.copy() for k, v in self.default_styles.items()}
    
    def get_style_stats(self) -> Dict[str, int]:
        """
        Get style statistics.
        
        Returns:
            Dictionary with style statistics
        """
        return self.style_stats.copy()
    
    def has_default_style(self, style_type: str) -> bool:
        """
        Check if default style exists.
        
        Args:
            style_type: Style type
            
        Returns:
            True if default style exists, False otherwise
        """
        return style_type in self.default_styles
    
    def remove_default_style(self, style_type: str) -> bool:
        """
        Remove default style.
        
        Args:
            style_type: Style type to remove
            
        Returns:
            True if style was removed, False if not found
        """
        if style_type in self.default_styles:
            del self.default_styles[style_type]
            self.style_stats['total_styles'] -= 1
            logger.debug(f"Default style removed: {style_type}")
            return True
        return False
    
    def clear_default_styles(self) -> None:
        """Clear all default styles."""
        self.default_styles.clear()
        self.style_validation_errors.clear()
        self.style_stats = {
            'total_styles': 0,
            'valid_styles': 0,
            'invalid_styles': 0,
            'customizations': 0
        }
        logger.debug("All default styles cleared")
    
    def get_style_info(self, style_type: str) -> Optional[Dict[str, Any]]:
        """
        Get style information.
        
        Args:
            style_type: Style type
            
        Returns:
            Style information or None if not found
        """
        if style_type not in self.default_styles:
            return None
        
        style_definition = self.default_styles[style_type]
        return {
            'style_type': style_type,
            'properties_count': len(style_definition),
            'is_valid': self._validate_style_definition(style_definition),
            'properties': style_definition.copy()
        }
    
    def update_style_property(self, style_type: str, property_name: str, property_value: Any) -> bool:
        """
        Update style property.
        
        Args:
            style_type: Style type
            property_name: Property name
            property_value: Property value
            
        Returns:
            True if property was updated, False otherwise
        """
        if style_type not in self.default_styles:
            return False
        
        if not property_name or not isinstance(property_name, str):
            raise ValueError("Property name must be a non-empty string")
        
        self.default_styles[style_type][property_name] = property_value
        logger.debug(f"Style property updated: {style_type}.{property_name} = {property_value}")
        return True
    
    def get_style_property(self, style_type: str, property_name: str, default: Any = None) -> Any:
        """
        Get style property.
        
        Args:
            style_type: Style type
            property_name: Property name
            default: Default value if property not found
            
        Returns:
            Property value or default
        """
        if style_type not in self.default_styles:
            return default
        
        return self.default_styles[style_type].get(property_name, default)
    
    def _initialize_default_styles(self) -> None:
        """Initialize default styles with standard definitions."""
        # Normal style
        self.default_styles['Normal'] = {
            'name': 'Normal',
            'type': 'paragraph',
            'font_family': 'Calibri',
            'font_size': 11,
            'font_size_unit': 'pt',
            'color': 'auto',
            'alignment': 'left',
            'line_spacing': 'single',
            'space_before': 0,
            'space_after': 0,
            'space_before_unit': 'pt',
            'space_after_unit': 'pt'
        }
        
        # DefaultParagraphFont style
        self.default_styles['DefaultParagraphFont'] = {
            'name': 'DefaultParagraphFont',
            'type': 'character',
            'font_family': 'Calibri',
            'font_size': 11,
            'font_size_unit': 'pt',
            'color': 'auto'
        }
        
        # Heading 1 style
        self.default_styles['Heading1'] = {
            'name': 'Heading1',
            'type': 'paragraph',
            'font_family': 'Calibri',
            'font_size': 16,
            'font_size_unit': 'pt',
            'color': 'auto',
            'alignment': 'left',
            'line_spacing': 'single',
            'space_before': 12,
            'space_after': 6,
            'space_before_unit': 'pt',
            'space_after_unit': 'pt',
            'bold': True
        }
        
        # Heading 2 style
        self.default_styles['Heading2'] = {
            'name': 'Heading2',
            'type': 'paragraph',
            'font_family': 'Calibri',
            'font_size': 13,
            'font_size_unit': 'pt',
            'color': 'auto',
            'alignment': 'left',
            'line_spacing': 'single',
            'space_before': 10,
            'space_after': 6,
            'space_before_unit': 'pt',
            'space_after_unit': 'pt',
            'bold': True
        }
        
        # Update stats
        self.style_stats['total_styles'] = len(self.default_styles)
        self.style_stats['valid_styles'] = len(self.default_styles)
        
        logger.debug(f"Default styles initialized: {len(self.default_styles)} styles")
    
    def _validate_style_definition(self, style_definition: Dict[str, Any]) -> bool:
        """
        Validate style definition.
        
        Args:
            style_definition: Style definition to validate
            
        Returns:
            True if style definition is valid, False otherwise
        """
        if not isinstance(style_definition, dict):
            return False
        
        # Check required properties
        required_props = ['name', 'type']
        for prop in required_props:
            if prop not in style_definition:
                return False
        
        # Validate style type
        valid_types = ['paragraph', 'character', 'table', 'numbering']
        if style_definition['type'] not in valid_types:
            return False
        
        # Validate font size if present
        if 'font_size' in style_definition:
            font_size = style_definition['font_size']
            if not isinstance(font_size, (int, float)) or font_size <= 0:
                return False
        
        # Validate spacing if present
        spacing_props = ['space_before', 'space_after']
        for prop in spacing_props:
            if prop in style_definition:
                spacing = style_definition[prop]
                if not isinstance(spacing, (int, float)) or spacing < 0:
                    return False
        
        return True
    
    def get_style_summary(self) -> Dict[str, Any]:
        """
        Get style summary.
        
        Returns:
            Dictionary with style summary
        """
        return {
            'total_styles': len(self.default_styles),
            'style_types': list(self.default_styles.keys()),
            'stats': self.style_stats.copy(),
            'is_valid': self.validate_default_styles(),
            'validation_errors_count': len(self.style_validation_errors)
        }
