"""
Bookmark model for DOCX documents.

Handles bookmark functionality, properties, validation, positioning, and management.
"""

from typing import Dict, Any, Optional, List
from .base import Models
import logging

logger = logging.getLogger(__name__)

class Bookmark(Models):
    """
    Represents a bookmark in the document.
    
    Handles bookmark functionality, properties, validation, and positioning.
    """
    
    def __init__(self, name: str = "", bookmark_id: str = "", position: Dict[str, Any] = None):
        """
        Initialize bookmark.
        
        Args:
            name: Bookmark name
            bookmark_id: Bookmark identifier
            position: Bookmark position information
        """
        super().__init__()
        self.name = name
        self.bookmark_id = bookmark_id
        self.position = position or {}
        self.properties = {}
        self.validation_errors = []
        
        logger.debug(f"Bookmark initialized: {name}")
    
    def set_bookmark_name(self, name: str) -> None:
        """
        Set bookmark name.
        
        Args:
            name: Bookmark name
        """
        if not name or not isinstance(name, str):
            raise ValueError("Bookmark name must be a non-empty string")
        
        self.name = name
        logger.debug(f"Bookmark name set to: {name}")
    
    def set_bookmark_id(self, bookmark_id: str) -> None:
        """
        Set bookmark ID.
        
        Args:
            bookmark_id: Bookmark identifier
        """
        if not bookmark_id or not isinstance(bookmark_id, str):
            raise ValueError("Bookmark ID must be a non-empty string")
        
        self.bookmark_id = bookmark_id
        logger.debug(f"Bookmark ID set to: {bookmark_id}")
    
    def set_position(self, position: Dict[str, Any]) -> None:
        """
        Set bookmark position.
        
        Args:
            position: Position information dictionary
        """
        if not isinstance(position, dict):
            raise ValueError("Position must be a dictionary")
        
        self.position = position.copy()
        logger.debug(f"Bookmark position set: {position}")
    
    def get_bookmark_name(self) -> str:
        """
        Get bookmark name.
        
        Returns:
            Bookmark name
        """
        return self.name
    
    def get_position(self) -> Dict[str, Any]:
        """
        Get bookmark position.
        
        Returns:
            Position information dictionary
        """
        return self.position.copy()
    
    def get_bookmark_id(self) -> str:
        """
        Get bookmark ID.
        
        Returns:
            Bookmark identifier
        """
        return self.bookmark_id
    
    def set_property(self, key: str, value: Any) -> None:
        """
        Set bookmark property.
        
        Args:
            key: Property key
            value: Property value
        """
        self.properties[key] = value
        logger.debug(f"Bookmark property set: {key} = {value}")
    
    def get_property(self, key: str, default: Any = None) -> Any:
        """
        Get bookmark property.
        
        Args:
            key: Property key
            default: Default value if property not found
            
        Returns:
            Property value or default
        """
        return self.properties.get(key, default)
    
    def validate(self) -> bool:
        """
        Validate bookmark.
        
        Returns:
            True if bookmark is valid, False otherwise
        """
        self.validation_errors = []
        
        # Validate name
        if not self.name:
            self.validation_errors.append("Bookmark name is required")
        
        # Validate ID
        if not self.bookmark_id:
            self.validation_errors.append("Bookmark ID is required")
        
        # Validate position
        if not self.position:
            self.validation_errors.append("Bookmark position is required")
        
        # Check for duplicate properties
        if len(self.properties) != len(set(self.properties.keys())):
            self.validation_errors.append("Duplicate properties found")
        
        is_valid = len(self.validation_errors) == 0
        logger.debug(f"Bookmark validation: {'valid' if is_valid else 'invalid'}")
        
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
        Convert bookmark to dictionary.
        
        Returns:
            Dictionary representation of bookmark
        """
        return {
            'type': 'bookmark',
            'name': self.name,
            'bookmark_id': self.bookmark_id,
            'position': self.position.copy(),
            'properties': self.properties.copy(),
            'validation_errors': self.validation_errors.copy()
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        Load bookmark from dictionary.
        
        Args:
            data: Dictionary data
        """
        self.name = data.get('name', '')
        self.bookmark_id = data.get('bookmark_id', '')
        self.position = data.get('position', {})
        self.properties = data.get('properties', {})
        self.validation_errors = data.get('validation_errors', [])
        
        logger.debug(f"Bookmark loaded from dictionary: {self.name}")
    
    def get_bookmark_info(self) -> Dict[str, Any]:
        """
        Get bookmark information.
        
        Returns:
            Dictionary with bookmark information
        """
        return {
            'name': self.name,
            'bookmark_id': self.bookmark_id,
            'position': self.position,
            'properties_count': len(self.properties),
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors)
        }
    
    def clear_properties(self) -> None:
        """Clear all bookmark properties."""
        self.properties.clear()
        logger.debug("Bookmark properties cleared")
    
    def has_property(self, key: str) -> bool:
        """
        Check if bookmark has property.
        
        Args:
            key: Property key
            
        Returns:
            True if property exists, False otherwise
        """
        return key in self.properties
    
    def remove_property(self, key: str) -> bool:
        """
        Remove bookmark property.
        
        Args:
            key: Property key to remove
            
        Returns:
            True if property was removed, False if not found
        """
        if key in self.properties:
            del self.properties[key]
            logger.debug(f"Bookmark property removed: {key}")
            return True
        return False
