"""
SmartArt model for DOCX documents.

Handles SmartArt functionality, diagram support, node management, layout support, and style support.
"""

from typing import List, Dict, Any, Optional
from .base import Models
import logging

logger = logging.getLogger(__name__)

class SmartArt(Models):
    """
    Represents a SmartArt diagram in the document.
    
    Handles SmartArt functionality, diagram structure, node management, and layout support.
    """
    
    def __init__(self, diagram_type: str = "process", layout: str = "basic", 
                 nodes: List[Dict[str, Any]] = None, style: Dict[str, Any] = None):
        """
        Initialize SmartArt.
        
        Args:
            diagram_type: Type of SmartArt diagram
            layout: Layout type for the diagram
            nodes: List of nodes in the diagram
            style: Style information for the diagram
        """
        super().__init__()
        self.diagram_type = diagram_type
        self.layout = layout
        self.nodes = nodes or []
        self.style = style or {}
        self.properties = {}
        self.validation_errors = []
        
        logger.debug(f"SmartArt initialized: {diagram_type}")
    
    def add_node(self, node: Dict[str, Any]) -> None:
        """
        Add node to diagram.
        
        Args:
            node: Node information dictionary
        """
        if not isinstance(node, dict):
            raise ValueError("Node must be a dictionary")
        
        self.nodes.append(node)
        logger.debug(f"Node added to SmartArt: {node.get('id', 'unknown')}")
    
    def set_layout(self, layout: str) -> None:
        """
        Set diagram layout.
        
        Args:
            layout: Layout type for the diagram
        """
        if not layout or not isinstance(layout, str):
            raise ValueError("Layout must be a non-empty string")
        
        self.layout = layout
        logger.debug(f"SmartArt layout set to: {layout}")
    
    def get_nodes(self) -> List[Dict[str, Any]]:
        """
        Get all nodes in diagram.
        
        Returns:
            List of nodes
        """
        return self.nodes.copy()
    
    def get_text(self) -> str:
        """
        Get text content from all nodes.
        
        Returns:
            Combined text content from all nodes
        """
        text_parts = []
        for node in self.nodes:
            if 'text' in node:
                text_parts.append(str(node['text']))
            elif 'content' in node:
                text_parts.append(str(node['content']))
        
        return ' '.join(text_parts)
    
    def get_diagram_type(self) -> str:
        """
        Get diagram type.
        
        Returns:
            Diagram type
        """
        return self.diagram_type
    
    def set_diagram_type(self, diagram_type: str) -> None:
        """
        Set diagram type.
        
        Args:
            diagram_type: Type of SmartArt diagram
        """
        if not diagram_type or not isinstance(diagram_type, str):
            raise ValueError("Diagram type must be a non-empty string")
        
        self.diagram_type = diagram_type
        logger.debug(f"Diagram type set to: {diagram_type}")
    
    def get_layout(self) -> str:
        """
        Get diagram layout.
        
        Returns:
            Diagram layout
        """
        return self.layout
    
    def set_style(self, style: Dict[str, Any]) -> None:
        """
        Set diagram style.
        
        Args:
            style: Style information dictionary
        """
        if not isinstance(style, dict):
            raise ValueError("Style must be a dictionary")
        
        self.style = style.copy()
        logger.debug(f"SmartArt style set: {style}")
    
    def get_style(self) -> Dict[str, Any]:
        """
        Get diagram style.
        
        Returns:
            Style information
        """
        return self.style.copy()
    
    def set_property(self, key: str, value: Any) -> None:
        """
        Set SmartArt property.
        
        Args:
            key: Property key
            value: Property value
        """
        self.properties[key] = value
        logger.debug(f"SmartArt property set: {key} = {value}")
    
    def get_property(self, key: str, default: Any = None) -> Any:
        """
        Get SmartArt property.
        
        Args:
            key: Property key
            default: Default value if property not found
            
        Returns:
            Property value or default
        """
        return self.properties.get(key, default)
    
    def validate(self) -> bool:
        """
        Validate SmartArt.
        
        Returns:
            True if SmartArt is valid, False otherwise
        """
        self.validation_errors = []
        
        # Validate diagram type
        if not self.diagram_type:
            self.validation_errors.append("Diagram type is required")
        
        # Validate layout
        if not self.layout:
            self.validation_errors.append("Layout is required")
        
        # Validate nodes
        if not isinstance(self.nodes, list):
            self.validation_errors.append("Nodes must be a list")
        
        # Validate style
        if not isinstance(self.style, dict):
            self.validation_errors.append("Style must be a dictionary")
        
        # Validate node structure
        for i, node in enumerate(self.nodes):
            if not isinstance(node, dict):
                self.validation_errors.append(f"Node {i} must be a dictionary")
            elif 'id' not in node:
                self.validation_errors.append(f"Node {i} must have an ID")
        
        is_valid = len(self.validation_errors) == 0
        logger.debug(f"SmartArt validation: {'valid' if is_valid else 'invalid'}")
        
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
        Convert SmartArt to dictionary.
        
        Returns:
            Dictionary representation of SmartArt
        """
        return {
            'type': 'smartart',
            'diagram_type': self.diagram_type,
            'layout': self.layout,
            'nodes': self.nodes.copy(),
            'style': self.style.copy(),
            'properties': self.properties.copy(),
            'validation_errors': self.validation_errors.copy()
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """
        Load SmartArt from dictionary.
        
        Args:
            data: Dictionary data
        """
        self.diagram_type = data.get('diagram_type', 'process')
        self.layout = data.get('layout', 'basic')
        self.nodes = data.get('nodes', [])
        self.style = data.get('style', {})
        self.properties = data.get('properties', {})
        self.validation_errors = data.get('validation_errors', [])
        
        logger.debug(f"SmartArt loaded from dictionary: {self.diagram_type}")
    
    def get_smartart_info(self) -> Dict[str, Any]:
        """
        Get SmartArt information.
        
        Returns:
            Dictionary with SmartArt information
        """
        return {
            'diagram_type': self.diagram_type,
            'layout': self.layout,
            'nodes_count': len(self.nodes),
            'style_properties_count': len(self.style),
            'properties_count': len(self.properties),
            'is_valid': self.validate(),
            'validation_errors_count': len(self.validation_errors)
        }
    
    def clear_nodes(self) -> None:
        """Clear all nodes from diagram."""
        self.nodes.clear()
        logger.debug("SmartArt nodes cleared")
    
    def clear_style(self) -> None:
        """Clear all diagram styling."""
        self.style.clear()
        logger.debug("SmartArt style cleared")
    
    def clear_properties(self) -> None:
        """Clear all SmartArt properties."""
        self.properties.clear()
        logger.debug("SmartArt properties cleared")
    
    def has_property(self, key: str) -> bool:
        """
        Check if SmartArt has property.
        
        Args:
            key: Property key
            
        Returns:
            True if property exists, False otherwise
        """
        return key in self.properties
    
    def remove_property(self, key: str) -> bool:
        """
        Remove SmartArt property.
        
        Args:
            key: Property key to remove
            
        Returns:
            True if property was removed, False if not found
        """
        if key in self.properties:
            del self.properties[key]
            logger.debug(f"SmartArt property removed: {key}")
            return True
        return False
    
    def is_empty(self) -> bool:
        """
        Check if SmartArt is empty.
        
        Returns:
            True if SmartArt has no nodes, False otherwise
        """
        return len(self.nodes) == 0
    
    def get_nodes_count(self) -> int:
        """
        Get number of nodes.
        
        Returns:
            Number of nodes
        """
        return len(self.nodes)
    
    def remove_node(self, index: int) -> bool:
        """
        Remove node from diagram.
        
        Args:
            index: Index of node to remove
            
        Returns:
            True if node was removed, False if index out of range
        """
        if 0 <= index < len(self.nodes):
            removed_node = self.nodes.pop(index)
            logger.debug(f"Node removed from SmartArt: {removed_node.get('id', 'unknown')}")
            return True
        return False
    
    def get_node_by_id(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        Get node by ID.
        
        Args:
            node_id: Node identifier
            
        Returns:
            Node dictionary or None if not found
        """
        for node in self.nodes:
            if node.get('id') == node_id:
                return node
        return None
    
    def update_node(self, node_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update node by ID.
        
        Args:
            node_id: Node identifier
            updates: Updates to apply to node
            
        Returns:
            True if node was updated, False if not found
        """
        for i, node in enumerate(self.nodes):
            if node.get('id') == node_id:
                self.nodes[i].update(updates)
                logger.debug(f"Node updated: {node_id}")
                return True
        return False
