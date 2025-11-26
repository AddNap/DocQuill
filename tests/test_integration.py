"""
Integration tests for docx_interpreter.

This module contains integration tests that use real DOCX files.
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from docx_interpreter.document import Document
from docx_interpreter.parser import PackageReader, XMLParser
from docx_interpreter.renderers import HTMLRenderer, PDFRenderer, DOCXRenderer


class TestIntegration:
    """Integration tests using real DOCX files."""
    
    @pytest.mark.integration
    def test_document_from_real_file(self, real_docx_path):
        """Test Document.from_file with real DOCX file."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Test Document.from_file
        doc = Document.from_file(real_docx_path)
        assert doc is not None
        assert hasattr(doc, 'parse')
        assert hasattr(doc, 'layout')
        assert hasattr(doc, 'render')
    
    @pytest.mark.integration
    def test_package_reader_with_real_file(self, real_docx_path):
        """Test PackageReader with real DOCX file."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        with PackageReader(real_docx_path) as reader:
            # Test basic functionality
            assert str(reader.docx_path) == str(real_docx_path)
            assert reader.zip_file is not None
            
            # Test getting XML content
            document_xml = reader.get_xml_content("word/document.xml")
            assert document_xml is not None
            assert isinstance(document_xml, str)
            assert len(document_xml) > 0
            
            # Test getting content types
            content_types = reader.get_content_types()
            assert isinstance(content_types, dict)
            assert len(content_types) > 0
            
            # Test getting relationships
            relationships = reader.get_relationships("word/document.xml")
            assert isinstance(relationships, dict)
            
            # Test getting metadata
            metadata = reader.get_metadata()
            assert isinstance(metadata, dict)
            assert 'core_properties' in metadata
            assert 'app_properties' in metadata
            assert 'custom_properties' in metadata
    
    @pytest.mark.integration
    def test_xml_parser_with_real_file(self, real_docx_path):
        """Test XMLParser with real DOCX file."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        with PackageReader(real_docx_path) as reader:
            parser = XMLParser(reader)
            
            # Test parsing metadata
            metadata = parser.parse_metadata()
            assert isinstance(metadata, dict)
            assert 'core_properties' in metadata
            assert 'app_properties' in metadata
            assert 'custom_properties' in metadata
            
            # Test parsing body
            body = parser.parse_body()
            assert body is not None
            
            # Test parsing sections
            sections = parser.parse_sections()
            assert sections is not None
    
    @pytest.mark.integration
    def test_html_renderer_with_real_file(self, real_docx_path, temp_dir):
        """Test HTMLRenderer with real DOCX file."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Create document from real file
        doc = Document.from_file(real_docx_path)
        
        # Test HTML renderer
        html_renderer = HTMLRenderer(doc)
        html_content = html_renderer.render()
        
        assert html_content is not None
        assert isinstance(html_content, str)
        assert len(html_content) > 0
        assert "<!DOCTYPE html>" in html_content
        assert "<html" in html_content
        assert "</html>" in html_content
        
        # Test saving to file
        output_path = temp_dir / "output.html"
        success = html_renderer.save_to_file(html_content, str(output_path))
        assert success
        assert output_path.exists()
        assert output_path.stat().st_size > 0
    
    @pytest.mark.integration
    def test_pdf_renderer_with_real_file(self, real_docx_path, temp_dir):
        """Test PDFRenderer with real DOCX file."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Create document from real file
        doc = Document.from_file(real_docx_path)
        
        # Test PDF renderer
        pdf_renderer = PDFRenderer(doc)
        pdf_content = pdf_renderer.render()
        
        assert pdf_content is not None
        assert isinstance(pdf_content, bytes)
        assert len(pdf_content) > 0
        assert b"%PDF-1.4" in pdf_content
        
        # Test saving to file
        output_path = temp_dir / "output.pdf"
        success = pdf_renderer.save_to_file(pdf_content, str(output_path))
        assert success
        assert output_path.exists()
        assert output_path.stat().st_size > 0
    
    @pytest.mark.integration
    def test_docx_renderer_with_real_file(self, real_docx_path, temp_dir):
        """Test DOCXRenderer with real DOCX file."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Create document from real file
        doc = Document.from_file(real_docx_path)
        
        # Test DOCX renderer
        docx_renderer = DOCXRenderer(doc)
        docx_content = docx_renderer.render()
        
        assert docx_content is not None
        assert isinstance(docx_content, str)
        assert len(docx_content) > 0
        assert "DOCX Document Structure" in docx_content
        
        # Test saving to file
        output_path = temp_dir / "output.docx"
        success = docx_renderer.save_to_file(docx_content, str(output_path))
        assert success
        assert output_path.exists()
        assert output_path.stat().st_size > 0
    
    @pytest.mark.integration
    def test_full_workflow_with_real_file(self, real_docx_path, temp_dir):
        """Test complete workflow with real DOCX file."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Step 1: Load document
        doc = Document.from_file(real_docx_path)
        assert doc is not None
        
        # Step 2: Parse document
        doc.parse()
        assert hasattr(doc, '_xml_parser')
        
        # Step 3: Layout document
        doc.layout()
        assert hasattr(doc, '_layout_cache')
        
        # Step 4: Render to HTML
        html_output = temp_dir / "output.html"
        doc.render("html", str(html_output))
        assert html_output.exists()
        assert html_output.stat().st_size > 0
        
        # Step 5: Render to PDF
        pdf_output = temp_dir / "output.pdf"
        doc.render("pdf", str(pdf_output))
        assert pdf_output.exists()
        assert pdf_output.stat().st_size > 0
    
    @pytest.mark.integration
    def test_document_properties_with_real_file(self, real_docx_path):
        """Test document properties extraction with real file."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        with PackageReader(real_docx_path) as reader:
            metadata = reader.get_metadata()
            
            # Test core properties
            core_props = metadata.get('core_properties', {})
            assert isinstance(core_props, dict)
            
            # Test app properties
            app_props = metadata.get('app_properties', {})
            assert isinstance(app_props, dict)
            
            # Test custom properties
            custom_props = metadata.get('custom_properties', {})
            assert isinstance(custom_props, dict)
    
    @pytest.mark.integration
    def test_document_content_extraction(self, real_docx_path):
        """Test content extraction from real DOCX file."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        with PackageReader(real_docx_path) as reader:
            parser = XMLParser(reader)
            
            # Parse document body
            body = parser.parse_body()
            assert body is not None
            
            # Test that we can extract text content
            if hasattr(body, 'get_text'):
                text_content = body.get_text()
                assert isinstance(text_content, str)
                # Real document should have some content
                if text_content:
                    assert len(text_content) > 0
    
    @pytest.mark.integration
    def test_media_files_extraction(self, real_docx_path):
        """Test media files extraction from real DOCX file."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        with PackageReader(real_docx_path) as reader:
            # Get media files
            media_files = reader.get_media_files()
            assert isinstance(media_files, list)
            
            # If there are media files, test accessing them
            if media_files:
                for media_file in media_files:
                    assert isinstance(media_file, str)
                    assert media_file.startswith("word/media/")
                    
                    # Test getting binary content
                    binary_content = reader.get_binary_content(media_file)
                    assert isinstance(binary_content, bytes)
                    assert len(binary_content) > 0
    
    @pytest.mark.integration
    def test_relationships_parsing(self, real_docx_path):
        """Test relationships parsing from real DOCX file."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        with PackageReader(real_docx_path) as reader:
            # Test main relationships
            main_rels = reader.get_relationships("word/document.xml")
            assert isinstance(main_rels, dict)
            
            # Test that relationships have expected structure
            for rel_id, rel_data in main_rels.items():
                assert isinstance(rel_id, str)
                assert isinstance(rel_data, dict)
                assert 'Type' in rel_data
                assert 'Target' in rel_data
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_performance_with_real_file(self, real_docx_path):
        """Test performance with real DOCX file."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        import time
        
        # Test loading performance
        start_time = time.time()
        doc = Document.from_file(real_docx_path)
        load_time = time.time() - start_time
        
        assert load_time < 5.0  # Should load within 5 seconds
        
        # Test parsing performance
        start_time = time.time()
        doc.parse()
        parse_time = time.time() - start_time
        
        assert parse_time < 10.0  # Should parse within 10 seconds
        
        # Test layout performance
        start_time = time.time()
        doc.layout()
        layout_time = time.time() - start_time
        
        assert layout_time < 15.0  # Should layout within 15 seconds
