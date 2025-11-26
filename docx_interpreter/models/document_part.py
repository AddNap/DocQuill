"""
Document part model for DOCX documents.

Handles document part functionality, abstraction, properties, validation, and inheritance.
"""

from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
from .base import Models
import logging

logger = logging.getLogger(__name__)

class DocumentPart(Models, ABC):
    """
    Abstract base for document parts (sections, headers, footers).
    
    Handles document part functionality, abstraction, properties, and validation.
    """
    
    def __init__(self, part_type: str = "", properties: Dict[str, Any] = None, 
                 content: List[Any] = None):
        """
        Initialize document part.
        
        Args:
            part_type: Type of document part
            properties: Part properties
            content: Part content
        """
        super().__init__()
        self.part_type = part_type
        self.properties = properties or {}
        self.content = content or []
        self.validation_errors = []
        
        logger.debug(f"DocumentPart initialized: {part_type}")
    
    def set_part_type(self, part_type: str) -> None:
        """
        Set part type.
        
        Args:
            part_type: Type of document part
        """
        if not part_type or not isinstance(part_type, str):
            raise ValueError("Part type must be a non-empty string")
        
        self.part_type = part_type
        logger.debug(f"Part type set to: {part_type}")
    
    def set_part_properties(self, properties: Dict[str, Any]) -> None:
        """
        Set part properties.
        
        Args:
            properties: Part properties dictionary
        """
        if not isinstance(properties, dict):
            raise ValueError("Part properties must be a dictionary")
        
        self.properties = properties.copy()
        logger.debug(f"Part properties set: {properties}")
    
    def get_part_type(self) -> str:
        """
        Get part type.
        
        Returns:
            Part type
        """
        return self.part_type
    
    def get_content(self) -> List[Any]:
        """
        Get part content.
        
        Returns:
            Part content
        """
        return self.content.copy()
    
    def add_content(self, item: Any) -> None:
        """
        Add content to part.
        
        Args:
            item: Content item to add
        """
        self.content.append(item)
        logger.debug(f"Content added to part: {type(item).__name__}")
    
    def remove_content(self, index: int) -> bool:
        """
        Remove content from part.
        
        Args:
            index: Index of content to remove
            
        Returns:
            True if content was removed, False if index out of range
        """
        if 0 <= index < len(self.content):
            removed_item = self.content.pop(index)
            logger.debug(f"Content removed from part: {type(removed_item).__name__}")
            return True
        return False
    
    def set_property(self, key: str, value: Any) -> None:
        """
        Set part property.
        
        Args:
            key: Property key
            value: Property value
        """
        self.properties[key] = value
        logger.debug(f"Part property set: {key} = {value}")
    
    def get_property(self, key: str, default: Any = None) -> Any:
        """
        Get part property.
        
        Args:
            key: Property key
            default: Default value if property not found
            
        Returns:
            Property value or default
        """
        return self.properties.get(key, default)
    
    def validate(self) -> bool:
        """
        Validate document part.
        
        Returns:
            True if part is valid, False otherwise
        """
        self.validation_errors = []
        
        # Validate part type
        if not self.part_type:
            self.validation_errors.append("Part type is required")
        
        # Validate properties
        if not isinstance(self.properties, dict):
            self.validation_errors.append("Part properties must be a dictionary")
        
        # Validate content
        if not isinstance(self.content, list):
            self.validation_errors.append("Part content must be a list")
        
        # Call abstract validation method
        self._validate_part_specific()
        
        is_valid = len(self.validation_errors) == 0
        logger.debug(f"DocumentPart validation: {'valid' if is_valid else 'invalid'}")
        
        return is_valid
    
    @abstractmethod
    def _validate_part_specific(self) -> None:
        """
        Validate part-specific requirements.
        
        This method should be implemented by subclasses to validate
        part-specific requirements.
        """
        pass
    
    def get_validation_errors(self) -> List[str]:
        """
        Get validation errors.
        
        Returns:
            List of validation errors
        """
        return self.validation_errors.copy()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert document part to dictionary.
        
        Returns:
            Dictionary representation of document part
        """
        return {
            'type': 'document_part',
            'part_type': self.part_type,
            'properties': self.properties.copy(),
            'content': [item.to_dict() if hasattr(item, 'to_dict') else str(item) for item in self.content],
            'validation_errors': self.validation_errors.copy()
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        Load document part from dictionary.
        
        Args:
            data: Dictionary data
        """
        self.part_type = data.get('part_type', '')
        self.properties = data.get('properties', {})
        self.content = data.get('content', [])
        self.validation_errors = data.get('validation_errors', [])
        
        logger.debug(f"DocumentPart loaded from dictionary: {self.part_type}")
    
    def get_part_info(self) -> Dict[str, Any]:
        """
        Get part information.
        
        Returns:
            Dictionary with part information
        """
        return {
            'part_type': self.part_type,
            'properties_count': len(self.properties),
            'content_count': len(self.content),
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors)
        }
    
    def clear_content(self) -> None:
        """Clear all part content."""
        self.content.clear()
        logger.debug("Part content cleared")
    
    def clear_properties(self) -> None:
        """Clear all part properties."""
        self.properties.clear()
        logger.debug("Part properties cleared")
    
    def has_property(self, key: str) -> bool:
        """
        Check if part has property.
        
        Args:
            key: Property key
            
        Returns:
            True if property exists, False otherwise
        """
        return key in self.properties
    
    def remove_property(self, key: str) -> bool:
        """
        Remove part property.
        
        Args:
            key: Property key to remove
            
        Returns:
            True if property was removed, False if not found
        """
        if key in self.properties:
            del self.properties[key]
            logger.debug(f"Part property removed: {key}")
            return True
        return False
    
    def is_empty(self) -> bool:
        """
        Check if part is empty.
        
        Returns:
            True if part has no content, False otherwise
        """
        return len(self.content) == 0
    
    def get_content_count(self) -> int:
        """
        Get number of content items.
        
        Returns:
            Number of content items
        """
        return len(self.content)
