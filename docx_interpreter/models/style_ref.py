"""
Style reference model for DOCX documents.

Handles style reference functionality, properties, validation, resolution, and inheritance.
"""

from typing import Dict, Any, Optional, List, List
from .base import Models
import logging

logger = logging.getLogger(__name__)

class StyleReference(Models):
    """
    Represents a style reference in the document.
    
    Handles style reference functionality, properties, validation, and resolution.
    """
    
    def __init__(self, style_id: str = "", style_type: str = "paragraph", 
                 properties: Dict[str, Any] = None, parent_style: str = ""):
        """
        Initialize style reference.
        
        Args:
            style_id: Style identifier
            style_type: Type of style (paragraph, character, table, etc.)
            properties: Style properties
            parent_style: Parent style identifier
        """
        super().__init__()
        self.style_id = style_id
        self.style_type = style_type
        self.properties = properties or {}
        self.parent_style = parent_style
        self.resolved_style = {}
        self.validation_errors = []
        
        logger.debug(f"StyleReference initialized: {style_id}")
    
    def set_style_id(self, style_id: str) -> None:
        """
        Set style ID.
        
        Args:
            style_id: Style identifier
        """
        if not style_id or not isinstance(style_id, str):
            raise ValueError("Style ID must be a non-empty string")
        
        self.style_id = style_id
        logger.debug(f"Style ID set to: {style_id}")
    
    def set_style_type(self, style_type: str) -> None:
        """
        Set style type.
        
        Args:
            style_type: Type of style
        """
        if not style_type or not isinstance(style_type, str):
            raise ValueError("Style type must be a non-empty string")
        
        self.style_type = style_type
        logger.debug(f"Style type set to: {style_type}")
    
    def set_style_properties(self, properties: Dict[str, Any]) -> None:
        """
        Set style properties.
        
        Args:
            properties: Style properties dictionary
        """
        if not isinstance(properties, dict):
            raise ValueError("Style properties must be a dictionary")
        
        self.properties = properties.copy()
        logger.debug(f"Style properties set: {properties}")
    
    def get_style_id(self) -> str:
        """
        Get style ID.
        
        Returns:
            Style identifier
        """
        return self.style_id
    
    def get_style_type(self) -> str:
        """
        Get style type.
        
        Returns:
            Style type
        """
        return self.style_type
    
    def get_style_properties(self) -> Dict[str, Any]:
        """
        Get style properties.
        
        Returns:
            Style properties
        """
        return self.properties.copy()
    
    def set_parent_style(self, parent_style: str) -> None:
        """
        Set parent style.
        
        Args:
            parent_style: Parent style identifier
        """
        if not isinstance(parent_style, str):
            raise ValueError("Parent style must be a string")
        
        self.parent_style = parent_style
        logger.debug(f"Parent style set to: {parent_style}")
    
    def get_parent_style(self) -> str:
        """
        Get parent style.
        
        Returns:
            Parent style identifier
        """
        return self.parent_style
    
    def resolve_style(self, style_registry: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Resolve style reference.
        
        Args:
            style_registry: Registry of available styles
            
        Returns:
            Resolved style properties
        """
        if not style_registry:
            style_registry = {}
        
        resolved_style = {}
        
        # Start with parent style if available
        if self.parent_style and self.parent_style in style_registry:
            parent_style_data = style_registry[self.parent_style]
            if isinstance(parent_style_data, dict):
                resolved_style.update(parent_style_data)
        
        # Apply current style properties (override parent)
        resolved_style.update(self.properties)
        
        # Store resolved style
        self.resolved_style = resolved_style.copy()
        
        logger.debug(f"Style resolved: {self.style_id}")
        return resolved_style
    
    def get_resolved_style(self) -> Dict[str, Any]:
        """
        Get resolved style.
        
        Returns:
            Resolved style properties
        """
        return self.resolved_style.copy()
    
    def set_property(self, key: str, value: Any) -> None:
        """
        Set style property.
        
        Args:
            key: Property key
            value: Property value
        """
        self.properties[key] = value
        logger.debug(f"Style property set: {key} = {value}")
    
    def get_property(self, key: str, default: Any = None) -> Any:
        """
        Get style property.
        
        Args:
            key: Property key
            default: Default value if property not found
            
        Returns:
            Property value or default
        """
        return self.properties.get(key, default)
    
    def validate(self) -> bool:
        """
        Validate style reference.
        
        Returns:
            True if style reference is valid, False otherwise
        """
        self.validation_errors = []
        
        # Validate style ID
        if not self.style_id:
            self.validation_errors.append("Style ID is required")
        
        # Validate style type
        if not self.style_type:
            self.validation_errors.append("Style type is required")
        
        # Validate properties
        if not isinstance(self.properties, dict):
            self.validation_errors.append("Style properties must be a dictionary")
        
        # Validate parent style
        if self.parent_style and not isinstance(self.parent_style, str):
            self.validation_errors.append("Parent style must be a string")
        
        is_valid = len(self.validation_errors) == 0
        logger.debug(f"StyleReference validation: {'valid' if is_valid else 'invalid'}")
        
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
        Convert style reference to dictionary.
        
        Returns:
            Dictionary representation of style reference
        """
        return {
            'type': 'style_reference',
            'style_id': self.style_id,
            'style_type': self.style_type,
            'properties': self.properties.copy(),
            'parent_style': self.parent_style,
            'resolved_style': self.resolved_style.copy(),
            'validation_errors': self.validation_errors.copy()
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        Load style reference from dictionary.
        
        Args:
            data: Dictionary data
        """
        self.style_id = data.get('style_id', '')
        self.style_type = data.get('style_type', 'paragraph')
        self.properties = data.get('properties', {})
        self.parent_style = data.get('parent_style', '')
        self.resolved_style = data.get('resolved_style', {})
        self.validation_errors = data.get('validation_errors', [])
        
        logger.debug(f"StyleReference loaded from dictionary: {self.style_id}")
    
    def get_style_info(self) -> Dict[str, Any]:
        """
        Get style reference information.
        
        Returns:
            Dictionary with style reference information
        """
        return {
            'style_id': self.style_id,
            'style_type': self.style_type,
            'properties_count': len(self.properties),
            'parent_style': self.parent_style,
            'resolved_properties_count': len(self.resolved_style),
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors)
        }
    
    def clear_properties(self) -> None:
        """Clear all style properties."""
        self.properties.clear()
        logger.debug("Style properties cleared")
    
    def clear_resolved_style(self) -> None:
        """Clear resolved style."""
        self.resolved_style.clear()
        logger.debug("Resolved style cleared")
    
    def has_property(self, key: str) -> bool:
        """
        Check if style has property.
        
        Args:
            key: Property key
            
        Returns:
            True if property exists, False otherwise
        """
        return key in self.properties
    
    def remove_property(self, key: str) -> bool:
        """
        Remove style property.
        
        Args:
            key: Property key to remove
            
        Returns:
            True if property was removed, False if not found
        """
        if key in self.properties:
            del self.properties[key]
            logger.debug(f"Style property removed: {key}")
            return True
        return False
    
    def is_resolved(self) -> bool:
        """
        Check if style is resolved.
        
        Returns:
            True if style is resolved, False otherwise
        """
        return len(self.resolved_style) > 0
    
    def get_properties_count(self) -> int:
        """
        Get number of properties.
        
        Returns:
            Number of properties
        """
        return len(self.properties)
    
    def get_resolved_properties_count(self) -> int:
        """
        Get number of resolved properties.
        
        Returns:
            Number of resolved properties
        """
        return len(self.resolved_style)
    
    def merge_with_parent(self, parent_style_data: Dict[str, Any]) -> None:
        """
        Merge with parent style data.
        
        Args:
            parent_style_data: Parent style data to merge with
        """
        if not isinstance(parent_style_data, dict):
            raise ValueError("Parent style data must be a dictionary")
        
        # Merge parent style with current properties
        merged_style = parent_style_data.copy()
        merged_style.update(self.properties)
        
        self.resolved_style = merged_style
        logger.debug(f"Style merged with parent: {self.style_id}")
    
    def override_property(self, key: str, value: Any) -> None:
        """
        Override a property in resolved style.
        
        Args:
            key: Property key
            value: Property value
        """
        self.resolved_style[key] = value
        logger.debug(f"Resolved style property overridden: {key} = {value}")
    
    def get_resolved_property(self, key: str, default: Any = None) -> Any:
        """
        Get resolved style property.
        
        Args:
            key: Property key
            default: Default value if property not found
            
        Returns:
            Resolved property value or default
        """
        return self.resolved_style.get(key, default)
