"""
Enhanced Style manager for DOCX documents.

Full implementation with style loading, management, inheritance, and caching.
"""

from typing import Dict, List, Any, Optional, Union
import logging
from .style_resolver import StyleResolver

logger = logging.getLogger(__name__)

class StyleManager:
    """
    Enhanced style manager for document styles and their inheritance.
    
    Full implementation with style loading, management, inheritance, and caching.
    """
    
    def __init__(self, package_reader):
        """
        Initialize style manager.
        
        Args:
            package_reader: PackageReader instance for accessing styles.xml
        """
        self.package_reader = package_reader
        self.styles: Dict[str, Dict[str, Any]] = {}
        self.style_cache: Dict[str, Dict[str, Any]] = {}
        self.style_resolver = StyleResolver()
        
        logger.debug("Style manager initialized")
    
    def load_styles(self) -> Dict[str, Dict[str, Any]]:
        """
        Load styles from styles.xml.
        
        Returns:
            Dictionary of loaded styles
        """
        try:
            from ..parser.style_parser import StyleParser
            
            style_parser = StyleParser(self.package_reader)
            self.styles = style_parser.parse_styles()
            
            logger.info(f"Loaded {len(self.styles)} styles")
            return self.styles
            
        except Exception as e:
            logger.error(f"Failed to load styles: {e}")
            return {}
    
    def get_style(self, style_id: str) -> Optional[Dict[str, Any]]:
        """
        Get style by ID.
        
        Args:
            style_id: Style identifier
            
        Returns:
            Style data or None if not found
        """
        return self.styles.get(style_id)
    
    def get_paragraph_style(self, style_id: str) -> Optional[Dict[str, Any]]:
        """
        Get paragraph style by ID.
        
        Args:
            style_id: Style identifier
            
        Returns:
            Paragraph style data or None if not found
        """
        style = self.get_style(style_id)
        if style and style.get('type') == 'paragraph':
            return style
        return None
    
    def get_character_style(self, style_id: str) -> Optional[Dict[str, Any]]:
        """
        Get character style by ID.
        
        Args:
            style_id: Style identifier
            
        Returns:
            Character style data or None if not found
        """
        style = self.get_style(style_id)
        if style and style.get('type') == 'character':
            return style
        return None
    
    def get_table_style(self, style_id: str) -> Optional[Dict[str, Any]]:
        """
        Get table style by ID.
        
        Args:
            style_id: Style identifier
            
        Returns:
            Table style data or None if not found
        """
        style = self.get_style(style_id)
        if style and style.get('type') == 'table':
            return style
        return None
    
    def resolve_style(self, style_id: str) -> Optional[Dict[str, Any]]:
        """
        Resolve style with inheritance chain.
        
        Args:
            style_id: Style identifier
            
        Returns:
            Resolved style with inherited properties
        """
        if style_id in self.style_cache:
            return self.style_cache[style_id]
        
        style = self.get_style(style_id)
        if not style:
            return None
        
        resolved_style = style.copy()
        
        # Resolve basedOn inheritance
        if style.get('basedOn'):
            base_style = self.resolve_style(style['basedOn'])
            if base_style:
                # Merge properties (current style overrides base style)
                resolved_style['properties'] = {
                    **base_style.get('properties', {}),
                    **style.get('properties', {})
                }
        
        self.style_cache[style_id] = resolved_style
        return resolved_style
    
    def resolve_style_chain(self, style_id: str) -> List[Dict[str, Any]]:
        """
        Resolve complete style inheritance chain.
        
        Args:
            style_id: Style identifier
            
        Returns:
            List of styles in inheritance chain
        """
        chain = []
        current_id = style_id
        
        while current_id:
            style = self.get_style(current_id)
            if not style:
                break
            
            chain.append(style)
            current_id = style.get('basedOn')
            
            # Prevent infinite loops
            if current_id in [s.get('styleId') for s in chain]:
                break
        
        return chain
    
    def get_styles_by_type(self, style_type: str) -> List[Dict[str, Any]]:
        """
        Get styles by type.
        
        Args:
            style_type: Style type (paragraph, character, table)
            
        Returns:
            List of styles of specified type
        """
        return [style for style in self.styles.values() if style.get('type') == style_type]
    
    def get_style_by_name(self, style_name: str) -> Optional[Dict[str, Any]]:
        """
        Get style by name.
        
        Args:
            style_name: Style name
            
        Returns:
            Style data or None if not found
        """
        for style in self.styles.values():
            if style.get('name') == style_name:
                return style
        return None
    
    def add_style(self, style_id: str, style_data: Dict[str, Any]):
        """
        Add style to manager.
        
        Args:
            style_id: Style identifier
            style_data: Style data
        """
        self.styles[style_id] = style_data
        logger.debug(f"Added style: {style_id}")
    
    def remove_style(self, style_id: str) -> bool:
        """
        Remove style from manager.
        
        Args:
            style_id: Style identifier
            
        Returns:
            True if removed, False if not found
        """
        if style_id in self.styles:
            del self.styles[style_id]
            # Clear from cache
            if style_id in self.style_cache:
                del self.style_cache[style_id]
            logger.debug(f"Removed style: {style_id}")
            return True
        return False
    
    def clear_cache(self):
        """Clear style cache."""
        self.style_cache.clear()
        logger.debug("Style cache cleared")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            'styles_count': len(self.styles),
            'cache_count': len(self.style_cache),
            'cache_hit_ratio': len(self.style_cache) / len(self.styles) if self.styles else 0
        }
    
    def validate_styles(self) -> List[str]:
        """
        Validate all styles for consistency.
        
        Returns:
            List of validation issues
        """
        issues = []
        
        for style_id, style in self.styles.items():
            # Check required fields
            if not style.get('name'):
                issues.append(f"Style {style_id} has no name")
            
            if not style.get('type'):
                issues.append(f"Style {style_id} has no type")
            
            # Check basedOn references
            based_on = style.get('basedOn')
            if based_on and based_on not in self.styles:
                issues.append(f"Style {style_id} references non-existent base style: {based_on}")
        
        return issues
    
    def get_style_preview(self, style_id: str) -> str:
        """
        Generate style preview in HTML.
        
        Args:
            style_id: Style identifier
            
        Returns:
            HTML preview of style
        """
        style = self.resolve_style(style_id)
        if not style:
            return f"<p>Style {style_id} not found</p>"
        
        properties = style.get('properties', {})
        style_name = style.get('name', style_id)
        style_type = style.get('type', 'unknown')
        
        preview_html = f"""
        <div class="style-preview" style="border: 1px solid #ccc; padding: 10px; margin: 5px;">
            <h4>{style_name} ({style_type})</h4>
            <div class="style-properties">
                <strong>Properties:</strong>
                <ul>
        """
        
        for prop, value in properties.items():
            preview_html += f"<li>{prop}: {value}</li>"
        
        preview_html += """
                </ul>
            </div>
        </div>
        """
        
        return preview_html
