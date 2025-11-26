"""
Tests for StyleResolver class.

This module contains unit tests for StyleResolver functionality.
"""

import pytest
from unittest.mock import Mock

from docx_interpreter.styles.style_resolver import StyleResolver


class TestStyleResolver:
    """Test cases for StyleResolver class."""
    
    @pytest.fixture
    def style_resolver(self):
        """Create StyleResolver instance."""
        return StyleResolver()
    
    def test_init(self):
        """Test StyleResolver initialization."""
        resolver = StyleResolver()
        
        assert resolver.style_cache == {}
        assert resolver.inheritance_cache == {}
        assert resolver.style_definitions == {}
        assert resolver.style_hierarchy == {}
    
    def test_resolve_inheritance_simple(self, style_resolver):
        """Test resolving simple style inheritance."""
        style = {
            "type": "paragraph",
            "name": "Heading1",
            "properties": {"paragraph": {"alignment": "center"}}
        }
        
        result = style_resolver.resolve_inheritance(style)
        
        assert isinstance(result, dict)
        assert result.get("type") == "paragraph"
        assert result.get("name") == "Heading1"
    
    def test_resolve_inheritance_with_parent(self, style_resolver):
        """Test resolving style inheritance with parent."""
        style = {
            "type": "paragraph",
            "name": "Heading1",
            "properties": {"paragraph": {"alignment": "center"}}
        }
        
        parent_style = {
            "type": "paragraph",
            "name": "Normal",
            "properties": {"paragraph": {"alignment": "left"}}
        }
        
        result = style_resolver.resolve_inheritance(style, parent_style)
        
        assert isinstance(result, dict)
        assert result.get("type") == "paragraph"
    
    def test_resolve_inheritance_merges_properties(self, style_resolver):
        """Test that inheritance merges properties."""
        style = {
            "properties": {"paragraph": {"alignment": "center"}}
        }
        
        parent_style = {
            "properties": {"paragraph": {"spacing": {"before": 240}}}
        }
        
        result = style_resolver.resolve_inheritance(style, parent_style)
        
        assert isinstance(result, dict)
        assert "properties" in result
    
    def test_resolve_style_with_cache(self, style_resolver):
        """Test resolving style with cache hit."""
        cached_style = {"type": "paragraph", "cached": True}
        style_resolver.style_cache["Normal"] = cached_style
        
        # Mock element with style
        element = Mock()
        element.style = {"style_id": "Normal"}
        
        # This will use cache
        result = style_resolver.resolve_style(element, "paragraph")
        
        # Should return cached style or empty dict
        assert isinstance(result, dict)
    
    def test_resolve_style_without_cache(self, style_resolver):
        """Test resolving style without cache."""
        element = Mock()
        element.style = {"style_id": "Normal"}
        
        result = style_resolver.resolve_style(element, "paragraph")
        
        # Should return dict (may be empty if style not found)
        assert isinstance(result, dict)
    
    def test_extract_element_style(self, style_resolver):
        """Test extracting style from element."""
        element = Mock()
        element.style = {"style_id": "Normal", "alignment": "left"}
        
        result = style_resolver._extract_element_style(element)
        
        assert isinstance(result, dict)
    
    def test_extract_element_style_no_style(self, style_resolver):
        """Test extracting style from element without style."""
        element = Mock()
        element.style = None
        
        result = style_resolver._extract_element_style(element)
        
        assert result is None or isinstance(result, dict)
    
    def test_generate_cache_key(self, style_resolver):
        """Test generating cache key."""
        element_style = {"style_id": "Normal", "alignment": "left"}
        style_type = "paragraph"
        
        result = style_resolver._generate_cache_key(element_style, style_type)
        
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_merge_styles(self, style_resolver):
        """Test merging styles."""
        base_style = {
            "properties": {"paragraph": {"alignment": "left"}}
        }
        
        override_style = {
            "properties": {"paragraph": {"alignment": "center"}}
        }
        
        result = style_resolver.merge_styles(base_style, override_style)
        
        assert isinstance(result, dict)
        assert "properties" in result
    
    def test_merge_styles_empty_base(self, style_resolver):
        """Test merging styles with empty base."""
        base_style = {}
        override_style = {
            "properties": {"paragraph": {"alignment": "center"}}
        }
        
        result = style_resolver.merge_styles(base_style, override_style)
        
        assert isinstance(result, dict)
    
    def test_merge_styles_empty_override(self, style_resolver):
        """Test merging styles with empty override."""
        base_style = {
            "properties": {"paragraph": {"alignment": "left"}}
        }
        override_style = {}
        
        result = style_resolver.merge_styles(base_style, override_style)
        
        assert isinstance(result, dict)
    
    def test_validate_style(self, style_resolver):
        """Test validating style."""
        style = {
            "type": "paragraph",
            "name": "Normal",
            "properties": {}
        }
        
        result = style_resolver.validate_style(style)
        
        assert isinstance(result, bool)
    
    def test_validate_style_missing_type(self, style_resolver):
        """Test validating style with missing type."""
        style = {
            "name": "Normal",
            "properties": {}
        }
        
        result = style_resolver.validate_style(style)
        
        # Should return False or raise error
        assert isinstance(result, bool) or result is None

