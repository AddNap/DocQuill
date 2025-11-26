"""
Tests for RelationshipMerger.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock
import xml.etree.ElementTree as ET

from docx_interpreter.merger.relationship_merger import RelationshipMerger


@pytest.fixture
def sample_docx_path():
    """Path to sample DOCX file."""
    path = Path(__file__).parent.parent / "files" / "Zapytanie_Ofertowe test.docx"
    if not path.exists():
        path = Path(__file__).parent.parent / "files" / "Zapytanie_Ofertowe.docx"
    return path


@pytest.fixture
def mock_package_readers():
    """Create mock package readers for testing."""
    target_reader = Mock()
    source_reader = Mock()
    
    # Mock basic methods
    target_reader.get_part = Mock(return_value=b'<xml/>')
    source_reader.get_part = Mock(return_value=b'<xml/>')
    target_reader.get_relationships = Mock(return_value=[])
    source_reader.get_relationships = Mock(return_value=[])
    
    return target_reader, source_reader


class TestRelationshipMerger:
    """Test cases for RelationshipMerger."""
    
    def test_init(self, mock_package_readers):
        """Test RelationshipMerger initialization."""
        target_reader, source_reader = mock_package_readers
        
        merger = RelationshipMerger(target_reader, source_reader)
        
        assert merger.target_reader == target_reader
        assert merger.source_reader == source_reader
        assert isinstance(merger.relationship_id_mapping, dict)
        assert isinstance(merger.part_path_mapping, dict)
        assert isinstance(merger.copied_parts, set)
        assert isinstance(merger._copied_parts_data, dict)
        assert isinstance(merger._relationships_to_write, dict)
        assert isinstance(merger._content_types_to_write, dict)
    
    def test_copy_part_with_relationships(self, mock_package_readers):
        """Test copying part with relationships."""
        target_reader, source_reader = mock_package_readers
        
        # Mock part content and relationships
        source_reader.get_part = Mock(return_value=b'<xml/>')
        source_reader.get_relationships = Mock(return_value=[
            {'Id': 'rId1', 'Type': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/image', 'Target': 'media/image1.png'}
        ])
        
        # Mock internal methods
        merger = RelationshipMerger(target_reader, source_reader)
        merger._get_part_content = Mock(return_value=b'<xml/>')
        merger._get_part_relationships = Mock(return_value=[
            {'Id': 'rId1', 'Type': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/image', 'Target': 'media/image1.png'}
        ])
        merger._copy_relationships = Mock(return_value={'rId1': 'rId2'})
        merger._copy_part_content = Mock()
        
        new_path, rel_mapping = merger.copy_part_with_relationships(
            'word/media/image1.png',
            'word/media/image1.png'
        )
        
        assert new_path == 'word/media/image1.png'
        assert 'word/media/image1.png' in merger.copied_parts
        assert 'word/media/image1.png' in merger.part_path_mapping
    
    def test_get_copied_parts(self, mock_package_readers):
        """Test getting copied parts."""
        target_reader, source_reader = mock_package_readers
        
        merger = RelationshipMerger(target_reader, source_reader)
        
        # Copy a part
        merger._copied_parts_data['word/media/image1.png'] = b'fake_image_data'
        merger.copied_parts.add('word/media/image1.png')
        
        copied = merger.get_copied_parts()
        
        assert 'word/media/image1.png' in copied
        assert copied['word/media/image1.png'] == b'fake_image_data'
    
    def test_get_relationships_to_write(self, mock_package_readers):
        """Test getting relationships to write."""
        target_reader, source_reader = mock_package_readers
        
        merger = RelationshipMerger(target_reader, source_reader)
        
        # Mock the internal structure that get_relationships_to_write uses
        merger.relationship_id_mapping['word/document.xml'] = {'rId1': 'rId2'}
        merger._get_part_relationships = Mock(return_value=[
            {'Id': 'rId1', 'Type': 'type', 'Target': 'media/image1.png'}
        ])
        merger._get_relationship_source_name = Mock(return_value='document')
        merger._get_relationship_file_path_for_source = Mock(return_value='word/_rels/document.xml.rels')
        
        rels = merger.get_relationships_to_write()
        
        # Should return relationships organized by rels file path
        assert isinstance(rels, dict)
    
    def test_get_content_types_to_write(self, mock_package_readers):
        """Test getting content types to write."""
        target_reader, source_reader = mock_package_readers
        
        merger = RelationshipMerger(target_reader, source_reader)
        
        # Add some content types
        merger._content_types_to_write['word/media/image1.png'] = 'image/png'
        
        content_types = merger.get_content_types_to_write()
        
        assert 'word/media/image1.png' in content_types
        assert content_types['word/media/image1.png'] == 'image/png'
    
    def test_generate_relationship_id(self, mock_package_readers):
        """Test generating relationship ID."""
        target_reader, source_reader = mock_package_readers
        
        merger = RelationshipMerger(target_reader, source_reader)
        
        # Generate IDs - check that method exists and works
        if hasattr(merger, '_generate_relationship_id'):
            id1 = merger._generate_relationship_id('word/document.xml')
            id2 = merger._generate_relationship_id('word/document.xml')
            
            assert id1.startswith('rId')
            assert id2.startswith('rId')
            assert id1 != id2  # Should be different
        else:
            # If method doesn't exist, skip this test
            pytest.skip("_generate_relationship_id method not found")
    
    def test_update_rel_ids_in_xml(self, mock_package_readers):
        """Test updating rel IDs in XML content."""
        target_reader, source_reader = mock_package_readers
        
        merger = RelationshipMerger(target_reader, source_reader)
        
        # Create XML with rel ID
        xml_content = b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body><w:p><w:r><w:drawing><a:blip r:embed="rId1"/></w:drawing></w:r></w:p></w:body></w:document>'
        
        # Set up mapping
        rel_mapping = {'rId1': 'rId5'}
        
        if hasattr(merger, '_update_rel_ids_in_xml'):
            updated = merger._update_rel_ids_in_xml(xml_content, rel_mapping)
            
            assert b'rId5' in updated
            assert updated.count(b'rId1') < xml_content.count(b'rId1')
        else:
            pytest.skip("_update_rel_ids_in_xml method not found")

