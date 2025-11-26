"""
Paragraph style for DOCX documents.

Handles paragraph style functionality, paragraph formatting, alignment support, spacing support, and border support.
"""

from typing import Dict, Any, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)

class ParagraphStyle:
    """
    Represents paragraph style and formatting.
    
    Handles paragraph style functionality, paragraph formatting, alignment support, and spacing support.
    """
    
    def __init__(self, style_name: str = "", parent_style: str = ""):
        """
        Initialize paragraph style.
        
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
        
        logger.debug(f"ParagraphStyle initialized: {style_name}")
    
    def set_alignment(self, alignment: str) -> None:
        """
        Set paragraph alignment.
        
        Args:
            alignment: Alignment value (left, center, right, justify)
        """
        if not alignment or not isinstance(alignment, str):
            raise ValueError("Alignment must be a non-empty string")
        
        valid_alignments = ['left', 'center', 'right', 'justify', 'distribute']
        if alignment not in valid_alignments:
            raise ValueError(f"Invalid alignment: {alignment}. Must be one of: {valid_alignments}")
        
        self.properties['alignment'] = alignment
        logger.debug(f"Paragraph alignment set to: {alignment}")
    
    def set_spacing(self, before: float = 0, after: float = 0, line_spacing: str = "single") -> None:
        """
        Set paragraph spacing.
        
        Args:
            before: Space before paragraph in points
            after: Space after paragraph in points
            line_spacing: Line spacing type (single, 1.5, double, multiple, exactly, at_least)
        """
        if not isinstance(before, (int, float)) or before < 0:
            raise ValueError("Space before must be a non-negative number")
        
        if not isinstance(after, (int, float)) or after < 0:
            raise ValueError("Space after must be a non-negative number")
        
        valid_line_spacing = ['single', '1.5', 'double', 'multiple', 'exactly', 'at_least']
        if line_spacing not in valid_line_spacing:
            raise ValueError(f"Invalid line spacing: {line_spacing}. Must be one of: {valid_line_spacing}")
        
        self.properties['space_before'] = before
        self.properties['space_after'] = after
        self.properties['line_spacing'] = line_spacing
        
        logger.debug(f"Paragraph spacing set: before={before}, after={after}, line_spacing={line_spacing}")
    
    def set_indentation(self, left: float = 0, right: float = 0, first_line: float = 0) -> None:
        """
        Set paragraph indentation.
        
        Args:
            left: Left indentation in points
            right: Right indentation in points
            first_line: First line indentation in points
        """
        if not isinstance(left, (int, float)) or left < 0:
            raise ValueError("Left indentation must be a non-negative number")
        
        if not isinstance(right, (int, float)) or right < 0:
            raise ValueError("Right indentation must be a non-negative number")
        
        if not isinstance(first_line, (int, float)):
            raise ValueError("First line indentation must be a number")
        
        self.properties['indent_left'] = left
        self.properties['indent_right'] = right
        self.properties['indent_first_line'] = first_line
        
        logger.debug(f"Paragraph indentation set: left={left}, right={right}, first_line={first_line}")
    
    def set_borders(self, borders: Dict[str, Any]) -> None:
        """
        Set paragraph borders.
        
        Args:
            borders: Border configuration dictionary
        """
        if not isinstance(borders, dict):
            raise ValueError("Borders must be a dictionary")
        
        # Validate border properties
        valid_border_sides = ['top', 'bottom', 'left', 'right']
        for side in borders.keys():
            if side not in valid_border_sides:
                raise ValueError(f"Invalid border side: {side}. Must be one of: {valid_border_sides}")
        
        self.properties['borders'] = borders.copy()
        logger.debug(f"Paragraph borders set: {borders}")
    
    def get_alignment(self) -> str:
        """
        Get paragraph alignment.
        
        Returns:
            Paragraph alignment
        """
        return self.properties.get('alignment', 'left')
    
    def get_spacing(self) -> Dict[str, Any]:
        """
        Get paragraph spacing.
        
        Returns:
            Dictionary with spacing information
        """
        return {
            'space_before': self.properties.get('space_before', 0),
            'space_after': self.properties.get('space_after', 0),
            'line_spacing': self.properties.get('line_spacing', 'single')
        }
    
    def get_indentation(self) -> Dict[str, float]:
        """
        Get paragraph indentation.
        
        Returns:
            Dictionary with indentation information
        """
        return {
            'left': self.properties.get('indent_left', 0),
            'right': self.properties.get('indent_right', 0),
            'first_line': self.properties.get('indent_first_line', 0)
        }
    
    def get_borders(self) -> Dict[str, Any]:
        """
        Get paragraph borders.
        
        Returns:
            Dictionary with border information
        """
        return self.properties.get('borders', {})
    
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
        Validate paragraph style.
        
        Returns:
            True if style is valid, False otherwise
        """
        self.validation_errors = []
        
        # Validate alignment
        alignment = self.properties.get('alignment', 'left')
        valid_alignments = ['left', 'center', 'right', 'justify', 'distribute']
        if alignment not in valid_alignments:
            self.validation_errors.append(f"Invalid alignment: {alignment}")
        
        # Validate spacing
        space_before = self.properties.get('space_before', 0)
        space_after = self.properties.get('space_after', 0)
        if not isinstance(space_before, (int, float)) or space_before < 0:
            self.validation_errors.append("Invalid space before value")
        if not isinstance(space_after, (int, float)) or space_after < 0:
            self.validation_errors.append("Invalid space after value")
        
        # Validate line spacing
        line_spacing = self.properties.get('line_spacing', 'single')
        valid_line_spacing = ['single', '1.5', 'double', 'multiple', 'exactly', 'at_least']
        if line_spacing not in valid_line_spacing:
            self.validation_errors.append(f"Invalid line spacing: {line_spacing}")
        
        # Validate indentation
        indent_left = self.properties.get('indent_left', 0)
        indent_right = self.properties.get('indent_right', 0)
        if not isinstance(indent_left, (int, float)) or indent_left < 0:
            self.validation_errors.append("Invalid left indentation value")
        if not isinstance(indent_right, (int, float)) or indent_right < 0:
            self.validation_errors.append("Invalid right indentation value")
        
        is_valid = len(self.validation_errors) == 0
        logger.debug(f"ParagraphStyle validation: {'valid' if is_valid else 'invalid'}")
        
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
        Convert paragraph style to dictionary.
        
        Returns:
            Dictionary representation of paragraph style
        """
        return {
            'type': 'paragraph_style',
            'style_name': self.style_name,
            'parent_style': self.parent_style,
            'properties': self.properties.copy(),
            'validation_errors': self.validation_errors.copy()
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        Load paragraph style from dictionary.
        
        Args:
            data: Dictionary data
        """
        self.style_name = data.get('style_name', '')
        self.parent_style = data.get('parent_style', '')
        self.properties = data.get('properties', {})
        self.validation_errors = data.get('validation_errors', [])
        
        logger.debug(f"ParagraphStyle loaded from dictionary: {self.style_name}")
    
    def get_style_info(self) -> Dict[str, Any]:
        """
        Get paragraph style information.
        
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
        """Initialize default paragraph properties."""
        self.properties = {
            'alignment': 'left',
            'space_before': 0,
            'space_after': 0,
            'line_spacing': 'single',
            'indent_left': 0,
            'indent_right': 0,
            'indent_first_line': 0,
            'borders': {}
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
            'has_borders': bool(self.properties.get('borders')),
            'has_indentation': any(self.properties.get(f'indent_{side}', 0) != 0 for side in ['left', 'right', 'first_line']),
            'has_spacing': any(self.properties.get(f'space_{side}', 0) != 0 for side in ['before', 'after'])
        }
