"""
Style resolver for DOCX documents.

Implements style resolver functionality including style inheritance resolution,
style merging, style validation, and style caching.
"""

from typing import Dict, Any, Optional, List, Union
import logging
from copy import deepcopy

logger = logging.getLogger(__name__)

class StyleResolver:
    """
    Resolves styles and their inheritance.
    
    Provides functionality for:
    - Style inheritance resolution
    - Style merging and cascading
    - Style validation and constraint checking
    - Style caching for performance
    """
    
    def __init__(self):
        """
        Initialize style resolver.
        
        Sets up style resolution, inheritance, and validation.
        """
        self.style_cache: Dict[str, Dict[str, Any]] = {}
        self.inheritance_cache: Dict[str, Dict[str, Any]] = {}
        self.style_definitions: Dict[str, Dict[str, Any]] = {}
        self.style_hierarchy: Dict[str, List[str]] = {}
    
    def resolve_style(self, element: Any, style_type: str) -> Dict[str, Any]:
        """
        Resolve style for element.
        
        Args:
            element: Element to resolve style for
            style_type: Type of style (paragraph, run, table, etc.)
            
        Returns:
            Resolved style dictionary
        """
        try:
            # Get element's style information
            element_style = self._extract_element_style(element)
            if not element_style:
                return {}
            
            # Check cache first
            cache_key = self._generate_cache_key(element_style, style_type)
            if cache_key in self.style_cache:
                return self.style_cache[cache_key]
            
            # Resolve inheritance
            resolved_style = self.resolve_inheritance(element_style, style_type)
            
            # Cache result
            self.style_cache[cache_key] = resolved_style
            
            return resolved_style
            
        except Exception as e:
            logger.error(f"Failed to resolve style: {e}")
            return {}
    
    def resolve_inheritance(self, style: Dict[str, Any], parent_style: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Resolve style inheritance.
        
        Args:
            style: Style to resolve
            parent_style: Optional parent style
            
        Returns:
            Resolved style with inheritance applied
        """
        try:
            resolved_style = deepcopy(style)
            
            if parent_style:
                # Merge parent style into current style
                resolved_style = self.merge_styles(parent_style, resolved_style)
            
            # Resolve style references
            if 'style_id' in resolved_style:
                style_def = self.style_definitions.get(resolved_style['style_id'])
                if style_def:
                    resolved_style = self.merge_styles(style_def, resolved_style)
            
            # Validate resolved style
            self.validate_style(resolved_style)
            
            return resolved_style
            
        except Exception as e:
            logger.error(f"Failed to resolve inheritance: {e}")
            return style
    
    def merge_styles(self, base_style: Dict[str, Any], override_style: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge two styles.
        
        Args:
            base_style: Base style to merge into
            override_style: Style to override with
            
        Returns:
            Merged style dictionary
        """
        try:
            base_mapping = self._coerce_mapping(base_style)
            override_mapping = self._coerce_mapping(override_style)

            merged_style = deepcopy(base_mapping)

            # Merge properties
            for key, value in override_mapping.items():
                if value is None or value == "":
                    continue

                existing = merged_style.get(key)
                if isinstance(existing, dict) and isinstance(value, dict):
                    merged_style[key] = self.merge_styles(existing, value)
                else:
                    merged_style[key] = value

            return merged_style

        except Exception as e:
            logger.error(f"Failed to merge styles: {e}")
            return base_mapping
    
    def validate_style(self, style: Dict[str, Any]) -> bool:
        """
        Validate style properties.
        
        Args:
            style: Style to validate
            
        Returns:
            True if style is valid, False otherwise
        """
        try:
            # Validate font properties
            if 'font' in style:
                font_props = style['font']
                if 'size' in font_props:
                    size = font_props['size']
                    if isinstance(size, (int, float)) and size <= 0:
                        logger.warning(f"Invalid font size: {size}")
                        return False
            
            # Validate color properties
            if 'color' in style:
                color = style['color']
                if color and not self._is_valid_color(color):
                    logger.warning(f"Invalid color: {color}")
                    return False
            
            # Validate spacing properties
            if 'spacing' in style:
                spacing = style['spacing']
                for prop in ['before', 'after', 'line']:
                    if prop in spacing:
                        value = spacing[prop]
                        if isinstance(value, (int, float)) and value < 0:
                            logger.warning(f"Invalid spacing {prop}: {value}")
                            return False
            
            # Validate indentation properties
            if 'indent' in style:
                indent = style['indent']
                for prop in ['left', 'right', 'first_line', 'hanging']:
                    if prop in indent:
                        value = indent[prop]
                        if isinstance(value, (int, float)) and value < 0:
                            logger.warning(f"Invalid indent {prop}: {value}")
                            return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to validate style: {e}")
            return False
    
    def _extract_element_style(self, element: Any) -> Dict[str, Any]:
        """
        Extract style information from element.
        
        Args:
            element: Element to extract style from
            
        Returns:
            Style dictionary
        """
        style = {}
        
        if hasattr(element, 'style_id') and element.style_id:
            style['style_id'] = element.style_id
        
        if hasattr(element, 'properties') and element.properties:
            style.update(self._coerce_mapping(element.properties))
        
        if hasattr(element, 'formatting') and element.formatting:
            style.update(self._coerce_mapping(element.formatting))
        
        return style

    def _coerce_mapping(self, value: Any) -> Dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return dict(value)
        if hasattr(value, 'to_dict') and callable(value.to_dict):
            try:
                result = value.to_dict()
                return dict(result) if isinstance(result, dict) else {}
            except Exception:
                return {}
        if hasattr(value, '__dict__'):
            return {
                k: v
                for k, v in value.__dict__.items()
                if not k.startswith('_') and v is not None
            }
        return {}
    
    def _generate_cache_key(self, style: Dict[str, Any], style_type: str) -> str:
        """
        Generate cache key for style.
        
        Args:
            style: Style dictionary
            style_type: Type of style
            
        Returns:
            Cache key string
        """
        # Create a hashable representation of the style
        style_str = str(sorted(style.items()))
        return f"{style_type}:{hash(style_str)}"
    
    def _is_valid_color(self, color: str) -> bool:
        """
        Check if color is valid.
        
        Args:
            color: Color string to validate
            
        Returns:
            True if color is valid, False otherwise
        """
        if not color:
            return True
        
        # Check hex color format
        if color.startswith('#'):
            if len(color) == 7 and all(c in '0123456789ABCDEFabcdef' for c in color[1:]):
                return True
        
        # Check named colors (basic set)
        named_colors = {
            'black', 'white', 'red', 'green', 'blue', 'yellow', 'cyan', 'magenta',
            'gray', 'grey', 'orange', 'purple', 'brown', 'pink', 'lime', 'navy'
        }
        if color.lower() in named_colors:
            return True
        
        return False
    
    def add_style_definition(self, style_id: str, style_def: Dict[str, Any]):
        """
        Add style definition to resolver.
        
        Args:
            style_id: Style identifier
            style_def: Style definition
        """
        self.style_definitions[style_id] = style_def
        logger.debug(f"Added style definition: {style_id}")
    
    def get_style_definition(self, style_id: str) -> Optional[Dict[str, Any]]:
        """
        Get style definition by ID.
        
        Args:
            style_id: Style identifier
            
        Returns:
            Style definition or None if not found
        """
        return self.style_definitions.get(style_id)
    
    def clear_cache(self):
        """Clear style cache."""
        self.style_cache.clear()
        self.inheritance_cache.clear()
        logger.info("Cleared style cache")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        return {
            'style_cache_size': len(self.style_cache),
            'inheritance_cache_size': len(self.inheritance_cache),
            'style_definitions_size': len(self.style_definitions)
        }
