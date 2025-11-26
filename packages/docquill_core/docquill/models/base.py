"""
Base model class for DOCX semantic models.

Enhanced implementation with full functionality.
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, List, Type, Union
from abc import ABC, abstractmethod
import uuid
import logging

logger = logging.getLogger(__name__)

class Models(ABC):
    """Abstract base class for DOCX semantic models with tree helpers."""
    
    def __init__(self):
        """Initialize base model."""
        self.xml_node: Optional[ET.Element] = None
        self.parent: Optional['Models'] = None
        self.children: List['Models'] = []
        self.id: str = str(uuid.uuid4())
        self._attributes: Dict[str, Any] = {}
        self._path: Optional[str] = None  # Hierarchical path like "body[0].p[2].r[1]"
    
    def add_child(self, model: 'Models'):
        """Add child model to this model."""
        if model not in self.children:
            self.children.append(model)
            model.parent = self
    
    def iter_children(self, type_filter: Optional[Type['Models']] = None):
        """Iterate over children, optionally filtered by type."""
        for child in self.children:
            if type_filter is None or isinstance(child, type_filter):
                yield child
    
    
    def validate(self):
        """Validate model data."""
        return True
    
    def get_text(self):
        """Get text content from model."""
        text_parts = []
        
        # Get text from attributes if any
        if 'text' in self._attributes:
            text_parts.append(str(self._attributes['text']))
        
        # Get text from children
        for child in self.children:
            child_text = child.get_text()
            if child_text:
                text_parts.append(child_text)
        
        return ' '.join(text_parts)
    
    def to_dict(self):
        """Convert model to dictionary."""
        result = {
            'type': self.__class__.__name__,
            'id': self.id,
            'attributes': self._attributes.copy(),
            'children': [child.to_dict() for child in self.children]
        }
        return result
    
    def to_xml(self):
        """Convert model to XML."""
        tag_name = self.__class__.__name__.lower()
        element = ET.Element(tag_name)
        
        if self.id:
            element.set('id', self.id)
        
        for name, value in self._attributes.items():
            element.set(name, str(value))
        
        for child in self.children:
            element.append(child.to_xml())
        
        return element
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Models':
        """Create model from dictionary representation."""
        instance = cls()
        instance.id = data.get('id', str(uuid.uuid4()))
        instance._attributes = data.get('attributes', {}).copy()
        
        # Note: children would need to be reconstructed based on type
        # This is a basic implementation - subclasses should override
        return instance
    
    def clone(self) -> 'Models':
        """Clone model with preserved hierarchy."""
        cloned = self.__class__()
        cloned.id = str(uuid.uuid4())
        cloned._attributes = self._attributes.copy()
        
        # Clone children recursively
        for child in self.children:
            cloned_child = child.clone()
            cloned_child.parent = cloned
            cloned.children.append(cloned_child)
        
        return cloned
    
    def __repr__(self) -> str:
        """String representation of model."""
        return f"{self.__class__.__name__}(id={self.id[:8]}..., children={len(self.children)})"
    
    def get_path(self) -> str:
        """Get hierarchical path of this model."""
        if self._path:
            return self._path
        
        # Build path from parent hierarchy
        path_parts = []
        current = self
        
        while current.parent:
            # Find index in parent's children
            try:
                index = current.parent.children.index(current)
                path_parts.append(f"{current.__class__.__name__.lower()}[{index}]")
            except ValueError:
                path_parts.append(current.__class__.__name__.lower())
            current = current.parent
        
        # Add root element
        if current:
            path_parts.append(current.__class__.__name__.lower())
        
        self._path = ".".join(reversed(path_parts))
        return self._path
    
    def find_by_id(self, target_id: str) -> Optional['Models']:
        """Find child model by ID."""
        if self.id == target_id:
            return self
        
        for child in self.children:
            result = child.find_by_id(target_id)
            if result:
                return result
        
        return None
    
    def find_by_path(self, path: str) -> Optional['Models']:
        """Find child model by hierarchical path."""
        if self.get_path() == path:
            return self
        
        for child in self.children:
            result = child.find_by_path(path)
            if result:
                return result
        
        return None
    
    def flatten(self) -> List['Models']:
        """Flatten structure for text search."""
        result = [self]
        for child in self.children:
            result.extend(child.flatten())
        return result
