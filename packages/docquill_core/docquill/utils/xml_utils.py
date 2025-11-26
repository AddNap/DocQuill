"""
XML utilities for DOCX documents.

Handles XML utilities functionality, XML parsing helpers, XML validation, XML manipulation, and namespace handling.
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class XMLUtils:
    """
    Utility functions for XML processing.
    
    Handles XML utilities functionality, XML parsing helpers, XML validation, XML manipulation, and namespace handling.
    """
    
    def __init__(self):
        """
        Initialize XML utilities.
        """
        self.namespaces = {
            'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
            'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
            'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
            'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture',
            'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
            'rels': 'http://schemas.openxmlformats.org/package/2006/relationships',
            'ct': 'http://schemas.openxmlformats.org/package/2006/content-types',
            'cp': 'http://schemas.openxmlformats.org/package/2006/metadata/core-properties',
            'dc': 'http://purl.org/dc/elements/1.1/',
            'dcterms': 'http://purl.org/dc/terms/',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
        }
        
        logger.debug("XML utilities initialized")
    
    def parse_xml(self, xml_string: str) -> Optional[ET.Element]:
        """
        Parse XML string.
        
        Args:
            xml_string: XML content to parse
            
        Returns:
            Root element or None if parsing fails
        """
        if not isinstance(xml_string, str):
            raise ValueError("XML string must be a string")
        
        try:
            root = ET.fromstring(xml_string)
            logger.debug(f"XML parsed successfully: {root.tag}")
            return root
        except ET.ParseError as e:
            logger.error(f"XML parsing failed: {e}")
            return None
    
    def validate_xml(self, xml_element: ET.Element) -> bool:
        """
        Validate XML element.
        
        Args:
            xml_element: XML element to validate
            
        Returns:
            True if XML is valid, False otherwise
        """
        if not isinstance(xml_element, ET.Element):
            return False
        
        try:
            # Basic validation - check if element is well-formed
            ET.tostring(xml_element, encoding='unicode')
            return True
        except ET.ParseError:
            return False
    
    def get_namespace(self, element: ET.Element) -> Optional[str]:
        """
        Get namespace from element.
        
        Args:
            element: XML element
            
        Returns:
            Namespace URI or None
        """
        if not isinstance(element, ET.Element):
            return None
        
        tag = element.tag
        if tag.startswith('{'):
            return tag[1:tag.find('}')]
        
        return None
    
    def find_element(self, parent: ET.Element, tag_name: str, namespace: str = None) -> Optional[ET.Element]:
        """
        Find element by tag name.
        
        Args:
            parent: Parent element
            tag_name: Tag name to find
            namespace: Namespace prefix
            
        Returns:
            Found element or None
        """
        if not isinstance(parent, ET.Element):
            raise ValueError("Parent must be an XML element")
        
        if not tag_name or not isinstance(tag_name, str):
            raise ValueError("Tag name must be a non-empty string")
        
        # Build full tag name with namespace
        if namespace and namespace in self.namespaces:
            full_tag = f"{{{self.namespaces[namespace]}}}{tag_name}"
        else:
            full_tag = tag_name
        
        # Find element
        found = parent.find(full_tag)
        if found is not None:
            logger.debug(f"Element found: {tag_name} in {parent.tag}")
            return found
        
        return None
    
    def get_attribute(self, element: ET.Element, attr_name: str, default: Any = None) -> Any:
        """
        Get attribute value.
        
        Args:
            element: XML element
            attr_name: Attribute name
            default: Default value if attribute not found
            
        Returns:
            Attribute value or default
        """
        if not isinstance(element, ET.Element):
            raise ValueError("Element must be an XML element")
        
        if not attr_name or not isinstance(attr_name, str):
            raise ValueError("Attribute name must be a non-empty string")
        
        return element.get(attr_name, default)
    
    def get_text_content(self, element: ET.Element) -> str:
        """
        Get text content from element.
        
        Args:
            element: XML element
            
        Returns:
            Text content
        """
        if not isinstance(element, ET.Element):
            raise ValueError("Element must be an XML element")
        
        text = element.text or ""
        if element.tail:
            text += element.tail
        
        return text.strip()
    
    def get_all_text(self, element: ET.Element) -> str:
        """
        Get all text content including child elements.
        
        Args:
            element: XML element
            
        Returns:
            All text content
        """
        if not isinstance(element, ET.Element):
            raise ValueError("Element must be an XML element")
        
        text_parts = []
        
        # Add element text
        if element.text:
            text_parts.append(element.text)
        
        # Add child element text
        for child in element:
            child_text = self.get_all_text(child)
            if child_text:
                text_parts.append(child_text)
        
        # Add tail text
        if element.tail:
            text_parts.append(element.tail)
        
        return "".join(text_parts).strip()
    
    def find_elements(self, parent: ET.Element, tag_name: str, namespace: str = None) -> List[ET.Element]:
        """
        Find all elements by tag name.
        
        Args:
            parent: Parent element
            tag_name: Tag name to find
            namespace: Namespace prefix
            
        Returns:
            List of found elements
        """
        if not isinstance(parent, ET.Element):
            raise ValueError("Parent must be an XML element")
        
        if not tag_name or not isinstance(tag_name, str):
            raise ValueError("Tag name must be a non-empty string")
        
        # Build full tag name with namespace
        if namespace and namespace in self.namespaces:
            full_tag = f"{{{self.namespaces[namespace]}}}{tag_name}"
        else:
            full_tag = tag_name
        
        # Find all elements
        found = parent.findall(full_tag)
        logger.debug(f"Found {len(found)} elements: {tag_name} in {parent.tag}")
        return found
    
    def has_attribute(self, element: ET.Element, attr_name: str) -> bool:
        """
        Check if element has attribute.
        
        Args:
            element: XML element
            attr_name: Attribute name
            
        Returns:
            True if attribute exists, False otherwise
        """
        if not isinstance(element, ET.Element):
            return False
        
        if not attr_name or not isinstance(attr_name, str):
            return False
        
        return attr_name in element.attrib
    
    def get_attributes(self, element: ET.Element) -> Dict[str, str]:
        """
        Get all attributes of element.
        
        Args:
            element: XML element
            
        Returns:
            Dictionary of attributes
        """
        if not isinstance(element, ET.Element):
            raise ValueError("Element must be an XML element")
        
        return element.attrib.copy()
    
    def get_local_name(self, element: ET.Element) -> str:
        """
        Get local name of element (without namespace).
        
        Args:
            element: XML element
            
        Returns:
            Local name
        """
        if not isinstance(element, ET.Element):
            raise ValueError("Element must be an XML element")
        
        tag = element.tag
        if tag.startswith('{'):
            return tag[tag.find('}') + 1:]
        
        return tag
    
    def is_element(self, element: ET.Element, tag_name: str, namespace: str = None) -> bool:
        """
        Check if element matches tag and namespace.
        
        Args:
            element: XML element
            tag_name: Tag name to check
            namespace: Namespace prefix
            
        Returns:
            True if element matches, False otherwise
        """
        if not isinstance(element, ET.Element):
            return False
        
        if not tag_name or not isinstance(tag_name, str):
            return False
        
        # Check local name
        local_name = self.get_local_name(element)
        if local_name != tag_name:
            return False
        
        # Check namespace if specified
        if namespace and namespace in self.namespaces:
            element_namespace = self.get_namespace(element)
            if element_namespace != self.namespaces[namespace]:
                return False
        
        return True
    
    def get_children(self, element: ET.Element) -> List[ET.Element]:
        """
        Get all child elements.
        
        Args:
            element: XML element
            
        Returns:
            List of child elements
        """
        if not isinstance(element, ET.Element):
            raise ValueError("Element must be an XML element")
        
        return list(element)
    
    def get_child_count(self, element: ET.Element) -> int:
        """
        Get number of child elements.
        
        Args:
            element: XML element
            
        Returns:
            Number of child elements
        """
        if not isinstance(element, ET.Element):
            raise ValueError("Element must be an XML element")
        
        return len(element)
    
    def has_children(self, element: ET.Element) -> bool:
        """
        Check if element has children.
        
        Args:
            element: XML element
            
        Returns:
            True if element has children, False otherwise
        """
        if not isinstance(element, ET.Element):
            return False
        
        return len(element) > 0
    
    def is_empty(self, element: ET.Element) -> bool:
        """
        Check if element is empty (no text and no children).
        
        Args:
            element: XML element
            
        Returns:
            True if element is empty, False otherwise
        """
        if not isinstance(element, ET.Element):
            return False
        
        has_text = bool(element.text and element.text.strip())
        has_children = len(element) > 0
        
        return not has_text and not has_children
    
    def get_element_info(self, element: ET.Element) -> Dict[str, Any]:
        """
        Get element information.
        
        Args:
            element: XML element
            
        Returns:
            Dictionary with element information
        """
        if not isinstance(element, ET.Element):
            raise ValueError("Element must be an XML element")
        
        return {
            'tag': element.tag,
            'local_name': self.get_local_name(element),
            'namespace': self.get_namespace(element),
            'attributes': self.get_attributes(element),
            'text': element.text,
            'tail': element.tail,
            'children_count': self.get_child_count(element),
            'has_children': self.has_children(element),
            'is_empty': self.is_empty(element)
        }
    
    def validate_xml_string(self, xml_content: str) -> bool:
        """
        Validate XML content string.
        
        Args:
            xml_content: XML content to validate
            
        Returns:
            True if XML is valid, False otherwise
        """
        if not isinstance(xml_content, str):
            return False
        
        try:
            ET.fromstring(xml_content)
            return True
        except ET.ParseError:
            return False
    
    def get_namespace_prefix(self, namespace_uri: str) -> Optional[str]:
        """
        Get namespace prefix for URI.
        
        Args:
            namespace_uri: Namespace URI
            
        Returns:
            Namespace prefix or None
        """
        for prefix, uri in self.namespaces.items():
            if uri == namespace_uri:
                return prefix
        
        return None
    
    def get_namespace_uri(self, prefix: str) -> Optional[str]:
        """
        Get namespace URI for prefix.
        
        Args:
            prefix: Namespace prefix
            
        Returns:
            Namespace URI or None
        """
        return self.namespaces.get(prefix)
    
    def get_all_namespaces(self) -> Dict[str, str]:
        """
        Get all namespaces.
        
        Returns:
            Dictionary of namespace prefixes to URIs
        """
        return self.namespaces.copy()
    
    def get_child_text(self, parent: ET.Element, tag_name: str, namespace: str = None, default: str = None) -> str:
        """
        Get text content from a child element.
        
        Args:
            parent: Parent element
            tag_name: Child tag name
            namespace: Namespace URI (optional)
            default: Default value if child not found
            
        Returns:
            Text content or default value
        """
        child = self.find_element(parent, tag_name, namespace)
        if child is not None:
            return self.get_text_content(child)
        return default
    
    def serialize_xml(self, element: ET.Element, encoding: str = 'utf-8') -> str:
        """
        Serialize XML element to string.
        
        Args:
            element: XML element to serialize
            encoding: XML encoding
            
        Returns:
            XML string
        """
        try:
            return ET.tostring(element, encoding=encoding, method='xml').decode(encoding)
        except Exception as e:
            logger.error(f"Failed to serialize XML: {e}")
            return ""
    
    # Static methods for convenience
    @staticmethod
    def get_child_text(parent: ET.Element, tag_name: str, namespace: str = None, default: str = None) -> str:
        """Static method to get child text."""
        if namespace:
            # Use namespace in tag name
            full_tag = f"{{{namespace}}}{tag_name}"
            child = parent.find(full_tag)
        else:
            child = parent.find(tag_name)
        
        if child is not None:
            return child.text or ""
        return default
    
    @staticmethod
    def get_attribute(element: ET.Element, attr_name: str, default: Any = None) -> Any:
        """Static method to get attribute."""
        return element.get(attr_name, default)
    
    @staticmethod
    def validate_xml(xml_content) -> bool:
        """Static method to validate XML."""
        try:
            # If it's a string, try to parse it
            if isinstance(xml_content, str):
                ET.fromstring(xml_content)
                return True
            # If it's an element, try to serialize it
            elif hasattr(xml_content, 'tag'):
                ET.tostring(xml_content)
                return True
            return False
        except Exception:
            return False
    
    @staticmethod
    def parse_xml(xml_string: str) -> Optional[ET.Element]:
        """Static method to parse XML."""
        if not isinstance(xml_string, str):
            return None
        return ET.fromstring(xml_string)
    
    @staticmethod
    def serialize_xml(element: ET.Element, encoding: str = 'utf-8') -> str:
        """Static method to serialize XML."""
        try:
            return ET.tostring(element, encoding=encoding, method='xml').decode(encoding)
        except Exception:
            return ""
