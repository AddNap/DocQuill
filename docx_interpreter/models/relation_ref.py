"""
Relation reference model for DOCX documents.

Handles relation reference functionality, properties, validation, resolution, and management.
"""

from typing import Dict, Any, Optional, List, List
from .base import Models
import logging

logger = logging.getLogger(__name__)

class RelationReference(Models):
    """
    Represents a relation reference between document elements.
    
    Handles relation reference functionality, properties, validation, and resolution.
    """
    
    def __init__(self, relation_type: str = "", source_element: str = "", 
                 target_element: str = "", relation_id: str = "", 
                 properties: Dict[str, Any] = None):
        """
        Initialize relation reference.
        
        Args:
            relation_type: Type of relation
            source_element: Source element identifier
            target_element: Target element identifier
            relation_id: Relation identifier
            properties: Relation properties
        """
        super().__init__()
        self.relation_type = relation_type
        self.source_element = source_element
        self.target_element = target_element
        self.relation_id = relation_id
        self.properties = properties or {}
        self.resolved_relation = {}
        self.validation_errors = []
        
        logger.debug(f"RelationReference initialized: {relation_type}")
    
    def set_relation_type(self, relation_type: str) -> None:
        """
        Set relation type.
        
        Args:
            relation_type: Type of relation
        """
        if not relation_type or not isinstance(relation_type, str):
            raise ValueError("Relation type must be a non-empty string")
        
        self.relation_type = relation_type
        logger.debug(f"Relation type set to: {relation_type}")
    
    def set_source_element(self, source: str) -> None:
        """
        Set source element.
        
        Args:
            source: Source element identifier
        """
        if not source or not isinstance(source, str):
            raise ValueError("Source element must be a non-empty string")
        
        self.source_element = source
        logger.debug(f"Source element set to: {source}")
    
    def set_target_element(self, target: str) -> None:
        """
        Set target element.
        
        Args:
            target: Target element identifier
        """
        if not target or not isinstance(target, str):
            raise ValueError("Target element must be a non-empty string")
        
        self.target_element = target
        logger.debug(f"Target element set to: {target}")
    
    def set_relation_id(self, relation_id: str) -> None:
        """
        Set relation ID.
        
        Args:
            relation_id: Relation identifier
        """
        if not relation_id or not isinstance(relation_id, str):
            raise ValueError("Relation ID must be a non-empty string")
        
        self.relation_id = relation_id
        logger.debug(f"Relation ID set to: {relation_id}")
    
    def get_relation_type(self) -> str:
        """
        Get relation type.
        
        Returns:
            Relation type
        """
        return self.relation_type
    
    def get_source_element(self) -> str:
        """
        Get source element.
        
        Returns:
            Source element identifier
        """
        return self.source_element
    
    def get_target_element(self) -> str:
        """
        Get target element.
        
        Returns:
            Target element identifier
        """
        return self.target_element
    
    def get_relation_id(self) -> str:
        """
        Get relation ID.
        
        Returns:
            Relation identifier
        """
        return self.relation_id
    
    def resolve_relation(self, element_registry: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Resolve relation reference.
        
        Args:
            element_registry: Registry of available elements
            
        Returns:
            Resolved relation
        """
        if not element_registry:
            element_registry = {}
        
        resolved_relation = {
            'type': self.relation_type,
            'source': self.source_element,
            'target': self.target_element,
            'relation_id': self.relation_id,
            'properties': self.properties.copy()
        }
        
        # Add registry data if available
        if self.source_element in element_registry:
            source_data = element_registry[self.source_element]
            if isinstance(source_data, dict):
                resolved_relation['source_data'] = source_data
        
        if self.target_element in element_registry:
            target_data = element_registry[self.target_element]
            if isinstance(target_data, dict):
                resolved_relation['target_data'] = target_data
        
        # Store resolved relation
        self.resolved_relation = resolved_relation.copy()
        
        logger.debug(f"Relation resolved: {self.relation_type}")
        return resolved_relation
    
    def get_resolved_relation(self) -> Dict[str, Any]:
        """
        Get resolved relation.
        
        Returns:
            Resolved relation
        """
        return self.resolved_relation.copy()
    
    def set_property(self, key: str, value: Any) -> None:
        """
        Set relation property.
        
        Args:
            key: Property key
            value: Property value
        """
        self.properties[key] = value
        logger.debug(f"Relation property set: {key} = {value}")
    
    def get_property(self, key: str, default: Any = None) -> Any:
        """
        Get relation property.
        
        Args:
            key: Property key
            default: Default value if property not found
            
        Returns:
            Property value or default
        """
        return self.properties.get(key, default)
    
    def validate(self) -> bool:
        """
        Validate relation reference.
        
        Returns:
            True if relation reference is valid, False otherwise
        """
        self.validation_errors = []
        
        # Validate relation type
        if not self.relation_type:
            self.validation_errors.append("Relation type is required")
        
        # Validate source element
        if not self.source_element:
            self.validation_errors.append("Source element is required")
        
        # Validate target element
        if not self.target_element:
            self.validation_errors.append("Target element is required")
        
        # Validate relation ID
        if not self.relation_id:
            self.validation_errors.append("Relation ID is required")
        
        # Validate properties
        if not isinstance(self.properties, dict):
            self.validation_errors.append("Relation properties must be a dictionary")
        
        is_valid = len(self.validation_errors) == 0
        logger.debug(f"RelationReference validation: {'valid' if is_valid else 'invalid'}")
        
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
        Convert relation reference to dictionary.
        
        Returns:
            Dictionary representation of relation reference
        """
        return {
            'type': 'relation_reference',
            'relation_type': self.relation_type,
            'source_element': self.source_element,
            'target_element': self.target_element,
            'relation_id': self.relation_id,
            'properties': self.properties.copy(),
            'resolved_relation': self.resolved_relation.copy(),
            'validation_errors': self.validation_errors.copy()
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        Load relation reference from dictionary.
        
        Args:
            data: Dictionary data
        """
        self.relation_type = data.get('relation_type', '')
        self.source_element = data.get('source_element', '')
        self.target_element = data.get('target_element', '')
        self.relation_id = data.get('relation_id', '')
        self.properties = data.get('properties', {})
        self.resolved_relation = data.get('resolved_relation', {})
        self.validation_errors = data.get('validation_errors', [])
        
        logger.debug(f"RelationReference loaded from dictionary: {self.relation_type}")
    
    def get_relation_info(self) -> Dict[str, Any]:
        """
        Get relation reference information.
        
        Returns:
            Dictionary with relation reference information
        """
        return {
            'relation_type': self.relation_type,
            'source_element': self.source_element,
            'target_element': self.target_element,
            'relation_id': self.relation_id,
            'properties_count': len(self.properties),
            'resolved_properties_count': len(self.resolved_relation),
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors)
        }
    
    def clear_properties(self) -> None:
        """Clear all relation properties."""
        self.properties.clear()
        logger.debug("Relation properties cleared")
    
    def clear_resolved_relation(self) -> None:
        """Clear resolved relation."""
        self.resolved_relation.clear()
        logger.debug("Resolved relation cleared")
    
    def has_property(self, key: str) -> bool:
        """
        Check if relation has property.
        
        Args:
            key: Property key
            
        Returns:
            True if property exists, False otherwise
        """
        return key in self.properties
    
    def remove_property(self, key: str) -> bool:
        """
        Remove relation property.
        
        Args:
            key: Property key to remove
            
        Returns:
            True if property was removed, False if not found
        """
        if key in self.properties:
            del self.properties[key]
            logger.debug(f"Relation property removed: {key}")
            return True
        return False
    
    def is_resolved(self) -> bool:
        """
        Check if relation is resolved.
        
        Returns:
            True if relation is resolved, False otherwise
        """
        return len(self.resolved_relation) > 0
    
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
        return len(self.resolved_relation)
    
    def update_source_element(self, new_source: str) -> None:
        """
        Update source element.
        
        Args:
            new_source: New source element identifier
        """
        if not new_source or not isinstance(new_source, str):
            raise ValueError("Source element must be a non-empty string")
        
        self.source_element = new_source
        logger.debug(f"Source element updated: {new_source}")
    
    def update_target_element(self, new_target: str) -> None:
        """
        Update target element.
        
        Args:
            new_target: New target element identifier
        """
        if not new_target or not isinstance(new_target, str):
            raise ValueError("Target element must be a non-empty string")
        
        self.target_element = new_target
        logger.debug(f"Target element updated: {new_target}")
    
    def get_relation_path(self) -> str:
        """
        Get relation path.
        
        Returns:
            Relation path string
        """
        return f"{self.source_element} -> {self.target_element}"
    
    def is_bidirectional(self) -> bool:
        """
        Check if relation is bidirectional.
        
        Returns:
            True if relation is bidirectional, False otherwise
        """
        return self.properties.get('bidirectional', False)
    
    def set_bidirectional(self, bidirectional: bool) -> None:
        """
        Set relation bidirectional flag.
        
        Args:
            bidirectional: Whether relation is bidirectional
        """
        self.properties['bidirectional'] = bidirectional
        logger.debug(f"Relation bidirectional set to: {bidirectional}")
    
    def get_relation_strength(self) -> float:
        """
        Get relation strength.
        
        Returns:
            Relation strength value
        """
        return self.properties.get('strength', 1.0)
    
    def set_relation_strength(self, strength: float) -> None:
        """
        Set relation strength.
        
        Args:
            strength: Relation strength value
        """
        if not isinstance(strength, (int, float)):
            raise ValueError("Relation strength must be a number")
        
        self.properties['strength'] = strength
        logger.debug(f"Relation strength set to: {strength}")
