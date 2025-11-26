"""
Tests for PackageReader class.

This module contains unit tests for the PackageReader functionality.
"""

import pytest
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import xml.etree.ElementTree as ET

from docx_interpreter.parser.package_reader import PackageReader


class TestPackageReader:
    """Test cases for PackageReader class."""
    
    def test_init_with_valid_docx(self, temp_dir, sample_zip_content):
        """Test PackageReader initialization with valid DOCX file."""
        # Create a mock DOCX file
        docx_path = temp_dir / "test.docx"
        with zipfile.ZipFile(docx_path, 'w') as zf:
            for filename, content in sample_zip_content.items():
                zf.writestr(filename, content)
        
        with PackageReader(str(docx_path)) as reader:
            assert reader.docx_path == docx_path
            assert reader.zip_file is not None
            assert reader.content_types is not None
            assert reader.relationships is not None
    
    def test_init_with_nonexistent_file(self):
        """Test PackageReader initialization with nonexistent file."""
        with pytest.raises(FileNotFoundError):
            PackageReader("nonexistent.docx")
    
    def test_init_with_invalid_zip(self, temp_dir):
        """Test PackageReader initialization with invalid ZIP file."""
        invalid_file = temp_dir / "invalid.docx"
        invalid_file.write_text("This is not a ZIP file")
        
        with pytest.raises(zipfile.BadZipFile):
            PackageReader(str(invalid_file))
    
    def test_get_xml_content(self, temp_dir, sample_zip_content):
        """Test getting XML content from package."""
        docx_path = temp_dir / "test.docx"
        with zipfile.ZipFile(docx_path, 'w') as zf:
            for filename, content in sample_zip_content.items():
                zf.writestr(filename, content)
        
        with PackageReader(str(docx_path)) as reader:
            xml_content = reader.get_xml_content("word/document.xml")
            assert xml_content is not None
            assert isinstance(xml_content, str)
    
    def test_get_xml_content_nonexistent(self, temp_dir, sample_zip_content):
        """Test getting XML content for nonexistent part."""
        docx_path = temp_dir / "test.docx"
        with zipfile.ZipFile(docx_path, 'w') as zf:
            for filename, content in sample_zip_content.items():
                zf.writestr(filename, content)
        
        with PackageReader(str(docx_path)) as reader:
            with pytest.raises(KeyError):
                reader.get_xml_content("nonexistent.xml")
    
    def test_get_binary_content(self, temp_dir, sample_zip_content):
        """Test getting binary content from package."""
        docx_path = temp_dir / "test.docx"
        with zipfile.ZipFile(docx_path, 'w') as zf:
            for filename, content in sample_zip_content.items():
                zf.writestr(filename, content)
        
        with PackageReader(str(docx_path)) as reader:
            binary_content = reader.get_binary_content("word/document.xml")
            assert binary_content is not None
            assert isinstance(binary_content, bytes)
    
    def test_get_media_files(self, temp_dir, sample_zip_content):
        """Test getting media files from package."""
        # Add a media file to the sample content
        sample_zip_content['word/media/image1.jpg'] = b'fake image data'
        
        docx_path = temp_dir / "test.docx"
        with zipfile.ZipFile(docx_path, 'w') as zf:
            for filename, content in sample_zip_content.items():
                zf.writestr(filename, content)
        
        with PackageReader(str(docx_path)) as reader:
            media_files = reader.get_media_files()
            assert isinstance(media_files, list)
            assert "word/media/image1.jpg" in media_files
    
    def test_get_content_types(self, temp_dir, sample_zip_content):
        """Test getting content types from package."""
        docx_path = temp_dir / "test.docx"
        with zipfile.ZipFile(docx_path, 'w') as zf:
            for filename, content in sample_zip_content.items():
                zf.writestr(filename, content)
        
        with PackageReader(str(docx_path)) as reader:
            content_types = reader.get_content_types()
            assert isinstance(content_types, dict)
            assert len(content_types) > 0
    
    def test_get_relationships(self, temp_dir, sample_zip_content):
        """Test getting relationships from package."""
        docx_path = temp_dir / "test.docx"
        with zipfile.ZipFile(docx_path, 'w') as zf:
            for filename, content in sample_zip_content.items():
                zf.writestr(filename, content)
        
        with PackageReader(str(docx_path)) as reader:
            relationships = reader.get_relationships("word/document.xml")
            assert isinstance(relationships, dict)
    
    def test_get_metadata(self, temp_dir, sample_zip_content):
        """Test getting metadata from package."""
        docx_path = temp_dir / "test.docx"
        with zipfile.ZipFile(docx_path, 'w') as zf:
            for filename, content in sample_zip_content.items():
                zf.writestr(filename, content)
        
        with PackageReader(str(docx_path)) as reader:
            metadata = reader.get_metadata()
            assert isinstance(metadata, dict)
            assert 'core_properties' in metadata
            assert 'app_properties' in metadata
            assert 'custom_properties' in metadata
    
    def test_context_manager(self, temp_dir, sample_zip_content):
        """Test PackageReader as context manager."""
        docx_path = temp_dir / "test.docx"
        with zipfile.ZipFile(docx_path, 'w') as zf:
            for filename, content in sample_zip_content.items():
                zf.writestr(filename, content)
        
        with PackageReader(str(docx_path)) as reader:
            assert reader.zip_file is not None
        
        # After context exit, zip_file should be None (closed)
        assert reader.zip_file is None
    
    def test_close_method(self, temp_dir, sample_zip_content):
        """Test close method."""
        docx_path = temp_dir / "test.docx"
        with zipfile.ZipFile(docx_path, 'w') as zf:
            for filename, content in sample_zip_content.items():
                zf.writestr(filename, content)
        
        reader = PackageReader(str(docx_path))
        assert reader.zip_file is not None
        reader.close()
        assert reader.zip_file.closed
    
    def test_parse_content_types(self, temp_dir, sample_zip_content):
        """Test parsing content types."""
        docx_path = temp_dir / "test.docx"
        with zipfile.ZipFile(docx_path, 'w') as zf:
            for filename, content in sample_zip_content.items():
                zf.writestr(filename, content)
        
        with PackageReader(str(docx_path)) as reader:
            content_types = reader.get_content_types()
            assert isinstance(content_types, dict)
            # Check for common content types
            assert any('document' in key for key in content_types.keys())
    
    def test_parse_relationships(self, temp_dir, sample_zip_content):
        """Test parsing relationships."""
        docx_path = temp_dir / "test.docx"
        with zipfile.ZipFile(docx_path, 'w') as zf:
            for filename, content in sample_zip_content.items():
                zf.writestr(filename, content)
        
        with PackageReader(str(docx_path)) as reader:
            relationships = reader.get_relationships("word/document.xml")
            assert isinstance(relationships, dict)
    
    def test_extract_to_parameter(self, temp_dir, sample_zip_content):
        """Test PackageReader with custom extract_to parameter."""
        docx_path = temp_dir / "test.docx"
        extract_to = temp_dir / "extracted"
        
        with zipfile.ZipFile(docx_path, 'w') as zf:
            for filename, content in sample_zip_content.items():
                zf.writestr(filename, content)
        
        with PackageReader(str(docx_path), str(extract_to)) as reader:
            assert reader.extract_to == str(extract_to)
            assert extract_to.exists()
    
    def test_get_xml_if_exists(self, temp_dir, sample_zip_content):
        """Test get_xml_if_exists method."""
        docx_path = temp_dir / "test.docx"
        with zipfile.ZipFile(docx_path, 'w') as zf:
            for filename, content in sample_zip_content.items():
                zf.writestr(filename, content)
        
        with PackageReader(str(docx_path)) as reader:
            # Test with existing file
            xml_content = reader.get_xml_if_exists("word/document.xml")
            assert xml_content is not None
            
            # Test with nonexistent file
            xml_content = reader.get_xml_if_exists("nonexistent.xml")
            assert xml_content is None
    
    def test_error_handling(self):
        """Test error handling in PackageReader."""
        # Test with invalid file path
        with pytest.raises(FileNotFoundError):
            PackageReader("nonexistent.docx")
        
        # Test with invalid file type
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Not a DOCX file")
            f.flush()
            
            with pytest.raises(zipfile.BadZipFile):
                PackageReader(f.name)
            
            Path(f.name).unlink()
