"""
Shape model for DOCX documents.

Handles shape functionality, properties, positioning, styling, and content.
"""

from typing import Dict, Any, Optional, List, List
from .base import Models
import logging

logger = logging.getLogger(__name__)

class Shape(Models):
    """
    Represents a shape in the document.
    
    Handles shape functionality, properties, positioning, and styling.
    """
    
    def __init__(self, shape_type: str = "rectangle", position: Dict[str, Any] = None, 
                 size: Dict[str, Any] = None, style: Dict[str, Any] = None, 
                 content: List[Any] = None):
        """
        Initialize shape.
        
        Args:
            shape_type: Type of shape (rectangle, circle, line, etc.)
            position: Shape position information
            size: Shape size information
            style: Shape styling information
            content: Shape content
        """
        super().__init__()
        self.shape_type = shape_type
        self.position = position or {}
        self.size = size or {}
        self.style = style or {}
        self.content = content or []
        self.properties = {}
        self.validation_errors = []
        
        logger.debug(f"Shape initialized: {shape_type}")
    
    def set_shape_type(self, shape_type: str) -> None:
        """
        Set shape type.
        
        Args:
            shape_type: Type of shape
        """
        if not shape_type or not isinstance(shape_type, str):
            raise ValueError("Shape type must be a non-empty string")
        
        self.shape_type = shape_type
        logger.debug(f"Shape type set to: {shape_type}")
    
    def set_position(self, position: Dict[str, Any]) -> None:
        """
        Set shape position.
        
        Args:
            position: Position information dictionary
        """
        if not isinstance(position, dict):
            raise ValueError("Position must be a dictionary")
        
        self.position = position.copy()
        logger.debug(f"Shape position set: {position}")
    
    def set_size(self, size: Dict[str, Any]) -> None:
        """
        Set shape size.
        
        Args:
            size: Size information dictionary
        """
        if not isinstance(size, dict):
            raise ValueError("Size must be a dictionary")
        
        self.size = size.copy()
        logger.debug(f"Shape size set: {size}")
    
    def set_style(self, style: Dict[str, Any]) -> None:
        """
        Set shape style.
        
        Args:
            style: Style information dictionary
        """
        if not isinstance(style, dict):
            raise ValueError("Style must be a dictionary")
        
        self.style = style.copy()
        logger.debug(f"Shape style set: {style}")
    
    def add_content(self, content: Any) -> None:
        """
        Add content to shape.
        
        Args:
            content: Content to add to shape
        """
        self.content.append(content)
        logger.debug(f"Content added to shape: {type(content).__name__}")
    
    def get_shape_type(self) -> str:
        """
        Get shape type.
        
        Returns:
            Shape type
        """
        return self.shape_type
    
    def get_position(self) -> Dict[str, Any]:
        """
        Get shape position.
        
        Returns:
            Position information
        """
        return self.position.copy()
    
    def get_size(self) -> Dict[str, Any]:
        """
        Get shape size.
        
        Returns:
            Size information
        """
        return self.size.copy()
    
    def get_style(self) -> Dict[str, Any]:
        """
        Get shape style.
        
        Returns:
            Style information
        """
        return self.style.copy()
    
    def get_content(self) -> List[Any]:
        """
        Get shape content.
        
        Returns:
            Shape content
        """
        return self.content.copy()
    
    def set_property(self, key: str, value: Any) -> None:
        """
        Set shape property.
        
        Args:
            key: Property key
            value: Property value
        """
        self.properties[key] = value
        logger.debug(f"Shape property set: {key} = {value}")
    
    def get_property(self, key: str, default: Any = None) -> Any:
        """
        Get shape property.
        
        Args:
            key: Property key
            default: Default value if property not found
            
        Returns:
            Property value or default
        """
        return self.properties.get(key, default)
    
    def validate(self) -> bool:
        """
        Validate shape.
        
        Returns:
            True if shape is valid, False otherwise
        """
        self.validation_errors = []
        
        # Validate shape type
        if not self.shape_type:
            self.validation_errors.append("Shape type is required")
        
        # Validate position
        if not isinstance(self.position, dict):
            self.validation_errors.append("Shape position must be a dictionary")
        
        # Validate size
        if not isinstance(self.size, dict):
            self.validation_errors.append("Shape size must be a dictionary")
        
        # Validate style
        if not isinstance(self.style, dict):
            self.validation_errors.append("Shape style must be a dictionary")
        
        # Validate content
        if not isinstance(self.content, list):
            self.validation_errors.append("Shape content must be a list")
        
        is_valid = len(self.validation_errors) == 0
        logger.debug(f"Shape validation: {'valid' if is_valid else 'invalid'}")
        
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
        Convert shape to dictionary.
        
        Returns:
            Dictionary representation of shape
        """
        return {
            'type': 'shape',
            'shape_type': self.shape_type,
            'position': self.position.copy(),
            'size': self.size.copy(),
            'style': self.style.copy(),
            'content': [item.to_dict() if hasattr(item, 'to_dict') else str(item) for item in self.content],
            'properties': self.properties.copy(),
            'validation_errors': self.validation_errors.copy()
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        Load shape from dictionary.
        
        Args:
            data: Dictionary data
        """
        self.shape_type = data.get('shape_type', 'rectangle')
        self.position = data.get('position', {})
        self.size = data.get('size', {})
        self.style = data.get('style', {})
        self.content = data.get('content', [])
        self.properties = data.get('properties', {})
        self.validation_errors = data.get('validation_errors', [])
        
        logger.debug(f"Shape loaded from dictionary: {self.shape_type}")
    
    def get_shape_info(self) -> Dict[str, Any]:
        """
        Get shape information.
        
        Returns:
            Dictionary with shape information
        """
        return {
            'shape_type': self.shape_type,
            'position_properties_count': len(self.position),
            'size_properties_count': len(self.size),
            'style_properties_count': len(self.style),
            'content_count': len(self.content),
            'properties_count': len(self.properties),
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors)
        }
    
    def clear_content(self) -> None:
        """Clear all shape content."""
        self.content.clear()
        logger.debug("Shape content cleared")
    
    def clear_style(self) -> None:
        """Clear all shape styling."""
        self.style.clear()
        logger.debug("Shape style cleared")
    
    def clear_properties(self) -> None:
        """Clear all shape properties."""
        self.properties.clear()
        logger.debug("Shape properties cleared")
    
    def has_property(self, key: str) -> bool:
        """
        Check if shape has property.
        
        Args:
            key: Property key
            
        Returns:
            True if property exists, False otherwise
        """
        return key in self.properties
    
    def remove_property(self, key: str) -> bool:
        """
        Remove shape property.
        
        Args:
            key: Property key to remove
            
        Returns:
            True if property was removed, False if not found
        """
        if key in self.properties:
            del self.properties[key]
            logger.debug(f"Shape property removed: {key}")
            return True
        return False
    
    def is_empty(self) -> bool:
        """
        Check if shape is empty.
        
        Returns:
            True if shape has no content, False otherwise
        """
        return len(self.content) == 0
    
    def get_content_count(self) -> int:
        """
        Get number of content items.
        
        Returns:
            Number of content items
        """
        return len(self.content)
    
    def remove_content(self, index: int) -> bool:
        """
        Remove content from shape.
        
        Args:
            index: Index of content to remove
            
        Returns:
            True if content was removed, False if index out of range
        """
        if 0 <= index < len(self.content):
            removed_item = self.content.pop(index)
            logger.debug(f"Content removed from shape: {type(removed_item).__name__}")
            return True
        return False
