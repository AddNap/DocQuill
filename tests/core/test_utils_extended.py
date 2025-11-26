"""
Extended tests for utility functions.

Tests for modules that were not covered in test_utils.py:
- ColorUtils
- IDManager
- DocumentValidators
- Cache
"""

import pytest
import time
from unittest.mock import Mock, MagicMock

from docquill.utils.color_utils import ColorUtils
from docquill.utils.id_manager import IDManager
from docquill.utils.validators import DocumentValidators
from docquill.utils.cache import Cache


class TestColorUtils:
    """Test cases for ColorUtils class."""
    
    def test_init(self):
        """Test ColorUtils initialization."""
        utils = ColorUtils()
        assert utils is not None
        assert hasattr(utils, 'color_map')
        assert 'black' in utils.color_map
        assert 'white' in utils.color_map
    
    def test_hex_to_rgb_valid(self):
        """Test hex to RGB conversion with valid hex colors."""
        utils = ColorUtils()
        
        # Full hex
        assert utils.hex_to_rgb("#FF0000") == (255, 0, 0)
        assert utils.hex_to_rgb("#00FF00") == (0, 255, 0)
        assert utils.hex_to_rgb("#0000FF") == (0, 0, 255)
        assert utils.hex_to_rgb("#FFFFFF") == (255, 255, 255)
        assert utils.hex_to_rgb("#000000") == (0, 0, 0)
        
        # Short hex
        assert utils.hex_to_rgb("#F00") == (255, 0, 0)
        assert utils.hex_to_rgb("#0F0") == (0, 255, 0)
        assert utils.hex_to_rgb("#00F") == (0, 0, 255)
        
        # Without #
        assert utils.hex_to_rgb("FF0000") == (255, 0, 0)
        assert utils.hex_to_rgb("F00") == (255, 0, 0)
    
    def test_hex_to_rgb_invalid(self):
        """Test hex to RGB conversion with invalid hex colors."""
        utils = ColorUtils()
        
        assert utils.hex_to_rgb(None) is None
        assert utils.hex_to_rgb("") is None
        assert utils.hex_to_rgb(123) is None
        assert utils.hex_to_rgb("#GGGGGG") is None
        assert utils.hex_to_rgb("#12") is None
    
    def test_rgb_to_hex_valid(self):
        """Test RGB to hex conversion with valid RGB colors."""
        utils = ColorUtils()
        
        assert utils.rgb_to_hex((255, 0, 0)) == "#ff0000"
        assert utils.rgb_to_hex((0, 255, 0)) == "#00ff00"
        assert utils.rgb_to_hex((0, 0, 255)) == "#0000ff"
        assert utils.rgb_to_hex((255, 255, 255)) == "#ffffff"
        assert utils.rgb_to_hex((0, 0, 0)) == "#000000"
        
        # List instead of tuple
        assert utils.rgb_to_hex([255, 0, 0]) == "#ff0000"
    
    def test_rgb_to_hex_invalid(self):
        """Test RGB to hex conversion with invalid RGB colors."""
        utils = ColorUtils()
        
        assert utils.rgb_to_hex(None) is None
        assert utils.rgb_to_hex((255,)) is None
        assert utils.rgb_to_hex((255, 0)) is None
        assert utils.rgb_to_hex((255, 0, 0, 0)) is None
        assert utils.rgb_to_hex("invalid") is None
    
    def test_parse_theme_color(self):
        """Test parsing theme colors."""
        utils = ColorUtils()
        
        assert utils.parse_theme_color("black") == (0, 0, 0)
        assert utils.parse_theme_color("white") == (255, 255, 255)
        assert utils.parse_theme_color("red") == (255, 0, 0)
        assert utils.parse_theme_color("BLACK") == (0, 0, 0)  # Case insensitive
        assert utils.parse_theme_color("gray") == (128, 128, 128)
        assert utils.parse_theme_color("grey") == (128, 128, 128)
        
        assert utils.parse_theme_color("unknown") is None
        assert utils.parse_theme_color(None) is None
        assert utils.parse_theme_color(123) is None
    
    def test_validate_color(self):
        """Test color validation."""
        utils = ColorUtils()
        
        # Valid hex colors (must start with #)
        assert utils.validate_color("#FF0000") == True
        assert utils.validate_color("#F00") == True
        # Note: validate_color requires # prefix for hex colors
        
        # Valid named colors
        assert utils.validate_color("black") == True
        assert utils.validate_color("red") == True
        
        # Valid RGB tuples
        assert utils.validate_color((255, 0, 0)) == True
        assert utils.validate_color([255, 0, 0]) == True
        
        # Invalid colors
        assert utils.validate_color(None) == False
        assert utils.validate_color("") == False
        assert utils.validate_color("#GGGGGG") == False
        assert utils.validate_color((300, 0, 0)) == False  # Out of range
        assert utils.validate_color((255,)) == False  # Wrong length
    
    def test_normalize_color(self):
        """Test color normalization."""
        utils = ColorUtils()
        
        # Hex to RGB (must start with #)
        assert utils.normalize_color("#FF0000") == (255, 0, 0)
        # Note: normalize_color requires # prefix for hex colors
        
        # Named color to RGB
        assert utils.normalize_color("black") == (0, 0, 0)
        assert utils.normalize_color("red") == (255, 0, 0)
        
        # RGB tuple/list stays as tuple
        assert utils.normalize_color((255, 0, 0)) == (255, 0, 0)
        assert utils.normalize_color([255, 0, 0]) == (255, 0, 0)
        
        # Invalid colors
        assert utils.normalize_color(None) is None
        assert utils.normalize_color("invalid") is None
        assert utils.normalize_color((255,)) is None


class TestIDManager:
    """Test cases for IDManager class."""
    
    def test_init(self):
        """Test IDManager initialization."""
        manager = IDManager()
        assert manager is not None
        assert hasattr(manager, 'registered_ids')
        assert hasattr(manager, 'id_to_type')
        assert hasattr(manager, 'type_to_ids')
    
    def test_generate_unique_id_no_prefix(self):
        """Test generating unique ID without prefix."""
        manager = IDManager()
        
        id1 = manager.generate_unique_id()
        id2 = manager.generate_unique_id()
        
        assert id1 != id2
        assert len(id1) > 0
        assert len(id2) > 0
    
    def test_generate_unique_id_with_prefix(self):
        """Test generating unique ID with prefix."""
        manager = IDManager()
        
        id1 = manager.generate_unique_id("para")
        id2 = manager.generate_unique_id("para")
        id3 = manager.generate_unique_id("table")
        
        assert id1 == "para_1"
        assert id2 == "para_2"
        assert id3 == "table_1"
    
    def test_register_id(self):
        """Test registering IDs."""
        manager = IDManager()
        
        assert manager.register_id("test_id", "paragraph") == True
        assert manager.register_id("test_id", "paragraph") == False  # Duplicate
        assert manager.is_id_registered("test_id") == True
    
    def test_validate_id(self):
        """Test ID validation."""
        manager = IDManager()
        
        # Valid IDs
        assert manager.validate_id("test_id") == True
        assert manager.validate_id("test-id") == True
        assert manager.validate_id("test_123") == True
        assert manager.validate_id("a") == True
        
        # Invalid IDs
        assert manager.validate_id("") == False
        assert manager.validate_id(None) == False
        assert manager.validate_id("test id") == False  # Space
        assert manager.validate_id("test@id") == False  # Invalid char
        assert manager.validate_id("a" * 101) == False  # Too long
    
    def test_get_registered_ids(self):
        """Test getting registered IDs."""
        manager = IDManager()
        
        manager.register_id("id1", "paragraph")
        manager.register_id("id2", "table")
        manager.register_id("id3", "paragraph")
        
        all_ids = manager.get_registered_ids()
        assert len(all_ids) == 3
        assert "id1" in all_ids
        assert "id2" in all_ids
        assert "id3" in all_ids
        
        para_ids = manager.get_registered_ids("paragraph")
        assert len(para_ids) == 2
        assert "id1" in para_ids
        assert "id3" in para_ids
    
    def test_get_id_type(self):
        """Test getting ID type."""
        manager = IDManager()
        
        manager.register_id("id1", "paragraph")
        manager.register_id("id2", "table")
        
        assert manager.get_id_type("id1") == "paragraph"
        assert manager.get_id_type("id2") == "table"
        assert manager.get_id_type("nonexistent") is None
    
    def test_unregister_id(self):
        """Test unregistering IDs."""
        manager = IDManager()
        
        manager.register_id("id1", "paragraph")
        assert manager.is_id_registered("id1") == True
        
        assert manager.unregister_id("id1") == True
        assert manager.is_id_registered("id1") == False
        assert manager.unregister_id("id1") == False  # Already unregistered
    
    def test_clear_registered_ids(self):
        """Test clearing all registered IDs."""
        manager = IDManager()
        
        manager.register_id("id1", "paragraph")
        manager.register_id("id2", "table")
        
        manager.clear_registered_ids()
        
        assert len(manager.get_registered_ids()) == 0
        assert manager.is_id_registered("id1") == False
    
    def test_get_stats(self):
        """Test getting ID manager statistics."""
        manager = IDManager()
        
        manager.register_id("id1", "paragraph")
        manager.register_id("id2", "table")
        
        stats = manager.get_stats()
        
        assert stats['total_ids'] == 2
        assert 'paragraph' in stats['types']
        assert 'table' in stats['types']
        assert stats['types']['paragraph'] == 1
        assert stats['types']['table'] == 1
    
    def test_generate_id_for_type(self):
        """Test generating ID for specific type."""
        manager = IDManager()
        
        id1 = manager.generate_id_for_type("paragraph")
        id2 = manager.generate_id_for_type("paragraph")
        
        assert manager.is_id_registered(id1) == True
        assert manager.get_id_type(id1) == "paragraph"
        assert id1 != id2
    
    def test_reserve_id(self):
        """Test reserving ID."""
        manager = IDManager()
        
        assert manager.reserve_id("reserved_id", "paragraph") == True
        assert manager.is_id_registered("reserved_id") == True
        assert manager.reserve_id("reserved_id", "paragraph") == False  # Already reserved


class TestDocumentValidators:
    """Test cases for DocumentValidators class."""
    
    def test_init(self):
        """Test DocumentValidators initialization."""
        validator = DocumentValidators()
        assert validator is not None
        assert hasattr(validator, '_errors')
    
    def test_validate_document_structure_valid(self):
        """Test validating valid document structure."""
        validator = DocumentValidators()
        
        # Mock valid document
        mock_body = Mock()
        mock_body.children = []
        
        mock_doc = Mock()
        mock_doc.body = mock_body
        
        # Mock Models base class
        from docquill.models.base import Models
        mock_body.__class__ = type('MockBody', (Models,), {})
        
        result = validator.validate_document_structure(mock_doc)
        assert result == True
        assert len(validator.get_validation_errors()['structure']) == 0
    
    def test_validate_document_structure_invalid(self):
        """Test validating invalid document structure."""
        validator = DocumentValidators()
        
        # None document
        assert validator.validate_document_structure(None) == False
        
        # Document without body
        mock_doc = Mock()
        mock_doc.body = None
        mock_doc.document_body = None
        assert validator.validate_document_structure(mock_doc) == False
    
    def test_validate_content_integrity(self):
        """Test validating content integrity."""
        validator = DocumentValidators()
        
        # Valid content - needs to inherit from Models
        from docquill.models.base import Models
        
        mock_element = Mock()
        mock_element.__class__ = type('MockElement', (Models,), {})
        mock_element.get_text = Mock(return_value="Test text")
        
        mock_content = Mock()
        mock_content.__class__ = type('MockContent', (Models,), {})
        mock_content.children = [mock_element]
        
        result = validator.validate_content_integrity(mock_content)
        assert result == True
    
    def test_validate_content_integrity_invalid(self):
        """Test validating invalid content."""
        validator = DocumentValidators()
        
        # None element
        mock_content = Mock()
        mock_content.children = [None]
        
        result = validator.validate_content_integrity(mock_content)
        assert result == False
        
        # Empty text
        mock_content.children = [""]
        result = validator.validate_content_integrity(mock_content)
        assert result == False
    
    def test_validate_format_compliance(self):
        """Test validating format compliance."""
        validator = DocumentValidators()
        
        # Mock document with valid format
        mock_para = Mock()
        mock_para.style = {}
        mock_para.numbering = {}
        mock_para.id = "p1"
        
        mock_body = Mock()
        mock_body.get_paragraphs_recursive = Mock(return_value=[mock_para])
        
        mock_doc = Mock()
        mock_doc.body = mock_body
        
        result = validator.validate_format_compliance(mock_doc)
        assert result == True
    
    def test_validate_format_compliance_invalid(self):
        """Test validating invalid format."""
        validator = DocumentValidators()
        
        # Mock paragraph with invalid style
        mock_para = Mock()
        mock_para.style = "invalid"  # Should be dict
        mock_para.id = "p1"
        
        mock_body = Mock()
        mock_body.get_paragraphs_recursive = Mock(return_value=[mock_para])
        
        mock_doc = Mock()
        mock_doc.body = mock_body
        
        result = validator.validate_format_compliance(mock_doc)
        assert result == False
    
    def test_validate_relationships_valid(self):
        """Test validating valid relationships."""
        validator = DocumentValidators()
        
        relationships = {
            "rId1": {
                "target": "word/media/image1.jpg",
                "type": "image"
            },
            "rId2": {
                "target": "word/media/image2.jpg",
                "type": "image"
            }
        }
        
        result = validator.validate_relationships(relationships)
        assert result == True
    
    def test_validate_relationships_invalid(self):
        """Test validating invalid relationships."""
        validator = DocumentValidators()
        
        # None relationships
        assert validator.validate_relationships(None) == False
        
        # Not a dict
        assert validator.validate_relationships([]) == False
        
        # Missing target
        relationships = {
            "rId1": {
                "type": "image"
            }
        }
        assert validator.validate_relationships(relationships) == False
        
        # Missing type
        relationships = {
            "rId1": {
                "target": "word/media/image1.jpg"
            }
        }
        assert validator.validate_relationships(relationships) == False
    
    def test_get_validation_errors(self):
        """Test getting validation errors."""
        validator = DocumentValidators()
        
        # Trigger some errors
        validator.validate_document_structure(None)
        validator.validate_relationships(None)
        
        errors = validator.get_validation_errors()
        
        assert 'structure' in errors
        assert 'relationships' in errors
        assert len(errors['structure']) > 0
        assert len(errors['relationships']) > 0


class TestCache:
    """Test cases for Cache class."""
    
    def test_init(self):
        """Test Cache initialization."""
        cache = Cache()
        assert cache is not None
        assert cache.max_size == 1024
        assert cache.default_ttl == 3600
    
    def test_init_custom(self):
        """Test Cache initialization with custom parameters."""
        cache = Cache(max_size=512, ttl=1800)
        assert cache.max_size == 512
        assert cache.default_ttl == 1800
    
    def test_set_and_get(self):
        """Test setting and getting cache values."""
        cache = Cache()
        
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        
        cache.set("key2", {"nested": "value"})
        assert cache.get("key2") == {"nested": "value"}
    
    def test_get_nonexistent(self):
        """Test getting nonexistent cache key."""
        cache = Cache()
        
        assert cache.get("nonexistent") is None
    
    def test_has(self):
        """Test checking if key exists."""
        cache = Cache()
        
        assert cache.has("key1") == False
        cache.set("key1", "value1")
        assert cache.has("key1") == True
    
    def test_delete(self):
        """Test deleting cache key."""
        cache = Cache()
        
        cache.set("key1", "value1")
        assert cache.has("key1") == True
        
        cache.delete("key1")
        assert cache.has("key1") == False
        assert cache.get("key1") is None
    
    def test_clear(self):
        """Test clearing cache."""
        cache = Cache()
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        cache.clear()
        
        assert cache.has("key1") == False
        assert cache.has("key2") == False
    
    def test_ttl_expiration(self):
        """Test TTL expiration."""
        cache = Cache(ttl=1)  # 1 second TTL
        
        cache.set("key1", "value1", ttl=1)
        assert cache.get("key1") == "value1"
        
        time.sleep(1.1)  # Wait for expiration
        
        assert cache.get("key1") is None
        assert cache.has("key1") == False
    
    def test_custom_ttl(self):
        """Test custom TTL per key."""
        cache = Cache(ttl=3600)  # Default 1 hour
        
        cache.set("key1", "value1", ttl=1)  # Custom 1 second
        cache.set("key2", "value2")  # Default TTL
        
        time.sleep(1.1)
        
        assert cache.get("key1") is None  # Expired
        assert cache.get("key2") == "value2"  # Still valid
    
    def test_max_size_limit(self):
        """Test max size limit."""
        cache = Cache(max_size=3)
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        cache.set("key4", "value4")  # Should evict oldest
        
        # At least one key should be evicted
        assert len([k for k in ["key1", "key2", "key3", "key4"] if cache.has(k)]) <= 3
    
    def test_thread_safety(self):
        """Test thread safety (basic check)."""
        import threading
        
        cache = Cache()
        results = []
        
        def set_value(key, value):
            cache.set(key, value)
            results.append(cache.get(key))
        
        threads = []
        for i in range(10):
            t = threading.Thread(target=set_value, args=(f"key{i}", f"value{i}"))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # All values should be set correctly
        assert len(results) == 10
        assert all(r is not None for r in results)

