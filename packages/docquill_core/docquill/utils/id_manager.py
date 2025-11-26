"""
ID manager for DOCX documents.

Implements ID management functionality including unique ID generation,
ID validation, ID tracking, and ID management.
"""

from typing import Dict, Any, Optional, Set, List
import uuid
import logging

logger = logging.getLogger(__name__)

class IDManager:
    """
    Generates and manages unique IDs for document elements.
    
    Provides functionality for:
    - Unique ID generation with prefixes
    - ID registration and tracking
    - ID validation and uniqueness checking
    - ID cleanup and management
    """
    
    def __init__(self):
        """
        Initialize ID manager.
        
        Sets up ID generation, tracking, and validation.
        """
        self.registered_ids: Set[str] = set()
        self.id_to_type: Dict[str, str] = {}
        self.type_to_ids: Dict[str, Set[str]] = {}
        self.id_counter: Dict[str, int] = {}
        self.prefix_counter: Dict[str, int] = {}
    
    def generate_unique_id(self, prefix: str = "") -> str:
        """
        Generate unique ID.
        
        Args:
            prefix: Optional prefix for the ID
            
        Returns:
            Unique ID string
        """
        if prefix:
            # Generate prefixed ID with counter
            if prefix not in self.prefix_counter:
                self.prefix_counter[prefix] = 0
            
            self.prefix_counter[prefix] += 1
            element_id = f"{prefix}_{self.prefix_counter[prefix]}"
        else:
            # Generate UUID-based ID
            element_id = str(uuid.uuid4()).replace('-', '')[:12]
        
        # Ensure uniqueness
        while element_id in self.registered_ids:
            if prefix:
                self.prefix_counter[prefix] += 1
                element_id = f"{prefix}_{self.prefix_counter[prefix]}"
            else:
                element_id = str(uuid.uuid4()).replace('-', '')[:12]
        
        return element_id
    
    def register_id(self, element_id: str, element_type: str) -> bool:
        """
        Register element ID.
        
        Args:
            element_id: ID to register
            element_type: Type of element
            
        Returns:
            True if registration successful, False if ID already exists
        """
        if element_id in self.registered_ids:
            logger.warning(f"ID {element_id} already registered")
            return False
        
        self.registered_ids.add(element_id)
        self.id_to_type[element_id] = element_type
        
        if element_type not in self.type_to_ids:
            self.type_to_ids[element_type] = set()
        self.type_to_ids[element_type].add(element_id)
        
        logger.debug(f"Registered ID {element_id} for type {element_type}")
        return True
    
    def validate_id(self, element_id: str) -> bool:
        """
        Validate element ID.
        
        Args:
            element_id: ID to validate
            
        Returns:
            True if ID is valid, False otherwise
        """
        if not element_id:
            return False
        
        # Check format (alphanumeric, underscore, hyphen)
        if not all(c.isalnum() or c in '_-' for c in element_id):
            return False
        
        # Check length (reasonable bounds)
        if len(element_id) < 1 or len(element_id) > 100:
            return False
        
        return True
    
    def get_registered_ids(self, element_type: Optional[str] = None) -> List[str]:
        """
        Get all registered IDs.
        
        Args:
            element_type: Optional filter by element type
            
        Returns:
            List of registered IDs
        """
        if element_type:
            return list(self.type_to_ids.get(element_type, set()))
        else:
            return list(self.registered_ids)
    
    def is_id_registered(self, element_id: str) -> bool:
        """
        Check if ID is registered.
        
        Args:
            element_id: ID to check
            
        Returns:
            True if ID is registered, False otherwise
        """
        return element_id in self.registered_ids
    
    def get_id_type(self, element_id: str) -> Optional[str]:
        """
        Get type of registered ID.
        
        Args:
            element_id: ID to check
            
        Returns:
            Element type if ID is registered, None otherwise
        """
        return self.id_to_type.get(element_id)
    
    def clear_registered_ids(self):
        """
        Clear all registered IDs.
        
        Resets all ID tracking and counters.
        """
        self.registered_ids.clear()
        self.id_to_type.clear()
        self.type_to_ids.clear()
        self.id_counter.clear()
        self.prefix_counter.clear()
        logger.info("Cleared all registered IDs")
    
    def unregister_id(self, element_id: str) -> bool:
        """
        Unregister element ID.
        
        Args:
            element_id: ID to unregister
            
        Returns:
            True if unregistration successful, False if ID not found
        """
        if element_id not in self.registered_ids:
            return False
        
        element_type = self.id_to_type.get(element_id)
        
        self.registered_ids.discard(element_id)
        self.id_to_type.pop(element_id, None)
        
        if element_type and element_type in self.type_to_ids:
            self.type_to_ids[element_type].discard(element_id)
            if not self.type_to_ids[element_type]:
                del self.type_to_ids[element_type]
        
        logger.debug(f"Unregistered ID {element_id}")
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get ID manager statistics.
        
        Returns:
            Dictionary with statistics
        """
        return {
            'total_ids': len(self.registered_ids),
            'types': {t: len(ids) for t, ids in self.type_to_ids.items()},
            'prefixes': dict(self.prefix_counter),
            'registered_ids': list(self.registered_ids)
        }
    
    def generate_id_for_type(self, element_type: str, prefix: Optional[str] = None) -> str:
        """
        Generate ID for specific element type.
        
        Args:
            element_type: Type of element
            prefix: Optional prefix (defaults to element_type)
            
        Returns:
            Generated unique ID
        """
        if prefix is None:
            prefix = element_type.lower()
        
        element_id = self.generate_unique_id(prefix)
        self.register_id(element_id, element_type)
        
        return element_id
    
    def reserve_id(self, element_id: str, element_type: str) -> bool:
        """
        Reserve ID without registering it yet.
        
        Args:
            element_id: ID to reserve
            element_type: Type of element
            
        Returns:
            True if reservation successful, False if ID already exists
        """
        if element_id in self.registered_ids:
            return False
        
        self.registered_ids.add(element_id)
        self.id_to_type[element_id] = element_type
        
        if element_type not in self.type_to_ids:
            self.type_to_ids[element_type] = set()
        self.type_to_ids[element_type].add(element_id)
        
        logger.debug(f"Reserved ID {element_id} for type {element_type}")
        return True
