"""
Metadata reference model for DOCX documents.

Handles metadata reference functionality, properties, validation, resolution, and inheritance.
"""

from typing import Dict, Any, Optional, List, List
from .base import Models
import logging

logger = logging.getLogger(__name__)

class MetadataReference(Models):
    """
    Represents a metadata reference in the document.
    
    Handles metadata reference functionality, properties, validation, and resolution.
    """
    
    def __init__(self, metadata_type: str = "", value: Any = None, 
                 source: str = "", properties: Dict[str, Any] = None):
        """
        Initialize metadata reference.
        
        Args:
            metadata_type: Type of metadata reference
            value: Metadata value
            source: Metadata source
            properties: Metadata properties
        """
        super().__init__()
        self.metadata_type = metadata_type
        self.value = value
        self.source = source
        self.properties = properties or {}
        self.resolved_metadata = {}
        self.validation_errors = []
        
        logger.debug(f"MetadataReference initialized: {metadata_type}")
    
    def set_metadata_type(self, metadata_type: str) -> None:
        """
        Set metadata type.
        
        Args:
            metadata_type: Type of metadata reference
        """
        if not metadata_type or not isinstance(metadata_type, str):
            raise ValueError("Metadata type must be a non-empty string")
        
        self.metadata_type = metadata_type
        logger.debug(f"Metadata type set to: {metadata_type}")
    
    def set_metadata_value(self, value: Any) -> None:
        """
        Set metadata value.
        
        Args:
            value: Metadata value
        """
        self.value = value
        logger.debug(f"Metadata value set: {value}")
    
    def set_metadata_source(self, source: str) -> None:
        """
        Set metadata source.
        
        Args:
            source: Metadata source
        """
        if not isinstance(source, str):
            raise ValueError("Metadata source must be a string")
        
        self.source = source
        logger.debug(f"Metadata source set to: {source}")
    
    def get_metadata_type(self) -> str:
        """
        Get metadata type.
        
        Returns:
            Metadata type
        """
        return self.metadata_type
    
    def get_metadata_value(self) -> Any:
        """
        Get metadata value.
        
        Returns:
            Metadata value
        """
        return self.value
    
    def get_metadata_source(self) -> str:
        """
        Get metadata source.
        
        Returns:
            Metadata source
        """
        return self.source
    
    def resolve_metadata(self, metadata_registry: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Resolve metadata reference.
        
        Args:
            metadata_registry: Registry of available metadata
            
        Returns:
            Resolved metadata
        """
        if not metadata_registry:
            metadata_registry = {}
        
        resolved_metadata = {
            'type': self.metadata_type,
            'value': self.value,
            'source': self.source,
            'properties': self.properties.copy()
        }
        
        # Add registry data if available
        if self.metadata_type in metadata_registry:
            registry_data = metadata_registry[self.metadata_type]
            if isinstance(registry_data, dict):
                resolved_metadata.update(registry_data)
        
        # Store resolved metadata
        self.resolved_metadata = resolved_metadata.copy()
        
        logger.debug(f"Metadata resolved: {self.metadata_type}")
        return resolved_metadata
    
    def get_resolved_metadata(self) -> Dict[str, Any]:
        """
        Get resolved metadata.
        
        Returns:
            Resolved metadata
        """
        return self.resolved_metadata.copy()
    
    def set_property(self, key: str, value: Any) -> None:
        """
        Set metadata property.
        
        Args:
            key: Property key
            value: Property value
        """
        self.properties[key] = value
        logger.debug(f"Metadata property set: {key} = {value}")
    
    def get_property(self, key: str, default: Any = None) -> Any:
        """
        Get metadata property.
        
        Args:
            key: Property key
            default: Default value if property not found
            
        Returns:
            Property value or default
        """
        return self.properties.get(key, default)
    
    def validate(self) -> bool:
        """
        Validate metadata reference.
        
        Returns:
            True if metadata reference is valid, False otherwise
        """
        self.validation_errors = []
        
        # Validate metadata type
        if not self.metadata_type:
            self.validation_errors.append("Metadata type is required")
        
        # Validate value
        if self.value is None:
            self.validation_errors.append("Metadata value is required")
        
        # Validate source
        if not self.source:
            self.validation_errors.append("Metadata source is required")
        
        # Validate properties
        if not isinstance(self.properties, dict):
            self.validation_errors.append("Metadata properties must be a dictionary")
        
        is_valid = len(self.validation_errors) == 0
        logger.debug(f"MetadataReference validation: {'valid' if is_valid else 'invalid'}")
        
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
        Convert metadata reference to dictionary.
        
        Returns:
            Dictionary representation of metadata reference
        """
        return {
            'type': 'metadata_reference',
            'metadata_type': self.metadata_type,
            'value': self.value,
            'source': self.source,
            'properties': self.properties.copy(),
            'resolved_metadata': self.resolved_metadata.copy(),
            'validation_errors': self.validation_errors.copy()
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        Load metadata reference from dictionary.
        
        Args:
            data: Dictionary data
        """
        self.metadata_type = data.get('metadata_type', '')
        self.value = data.get('value')
        self.source = data.get('source', '')
        self.properties = data.get('properties', {})
        self.resolved_metadata = data.get('resolved_metadata', {})
        self.validation_errors = data.get('validation_errors', [])
        
        logger.debug(f"MetadataReference loaded from dictionary: {self.metadata_type}")
    
    def get_metadata_info(self) -> Dict[str, Any]:
        """
        Get metadata reference information.
        
        Returns:
            Dictionary with metadata reference information
        """
        return {
            'metadata_type': self.metadata_type,
            'value_type': type(self.value).__name__,
            'source': self.source,
            'properties_count': len(self.properties),
            'resolved_properties_count': len(self.resolved_metadata),
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors)
        }
    
    def clear_properties(self) -> None:
        """Clear all metadata properties."""
        self.properties.clear()
        logger.debug("Metadata properties cleared")
    
    def clear_resolved_metadata(self) -> None:
        """Clear resolved metadata."""
        self.resolved_metadata.clear()
        logger.debug("Resolved metadata cleared")
    
    def has_property(self, key: str) -> bool:
        """
        Check if metadata has property.
        
        Args:
            key: Property key
            
        Returns:
            True if property exists, False otherwise
        """
        return key in self.properties
    
    def remove_property(self, key: str) -> bool:
        """
        Remove metadata property.
        
        Args:
            key: Property key to remove
            
        Returns:
            True if property was removed, False if not found
        """
        if key in self.properties:
            del self.properties[key]
            logger.debug(f"Metadata property removed: {key}")
            return True
        return False
    
    def is_resolved(self) -> bool:
        """
        Check if metadata is resolved.
        
        Returns:
            True if metadata is resolved, False otherwise
        """
        return len(self.resolved_metadata) > 0
    
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
        return len(self.resolved_metadata)
    
    def merge_with_registry(self, registry_data: Dict[str, Any]) -> None:
        """
        Merge with registry data.
        
        Args:
            registry_data: Registry data to merge with
        """
        if not isinstance(registry_data, dict):
            raise ValueError("Registry data must be a dictionary")
        
        # Merge registry data with current properties
        merged_metadata = registry_data.copy()
        merged_metadata.update(self.properties)
        
        self.resolved_metadata = merged_metadata
        logger.debug(f"Metadata merged with registry: {self.metadata_type}")
    
    def override_property(self, key: str, value: Any) -> None:
        """
        Override a property in resolved metadata.
        
        Args:
            key: Property key
            value: Property value
        """
        self.resolved_metadata[key] = value
        logger.debug(f"Resolved metadata property overridden: {key} = {value}")
    
    def get_resolved_property(self, key: str, default: Any = None) -> Any:
        """
        Get resolved metadata property.
        
        Args:
            key: Property key
            default: Default value if property not found
            
        Returns:
            Resolved property value or default
        """
        return self.resolved_metadata.get(key, default)
    
    def update_value(self, new_value: Any) -> None:
        """
        Update metadata value.
        
        Args:
            new_value: New metadata value
        """
        self.value = new_value
        logger.debug(f"Metadata value updated: {new_value}")
    
    def update_source(self, new_source: str) -> None:
        """
        Update metadata source.
        
        Args:
            new_source: New metadata source
        """
        if not isinstance(new_source, str):
            raise ValueError("Metadata source must be a string")
        
        self.source = new_source
        logger.debug(f"Metadata source updated: {new_source}")
