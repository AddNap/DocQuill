"""
Tests for Document class.

This module contains unit tests for the Document functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil

# Updated imports for new API
try:
    from docx_interpreter import Document
    from docx_interpreter.document_api import Document as DocumentAPI
except ImportError:
    # Fallback for old API if exists
    try:
        from docx_interpreter.document import Document
    except ImportError:
        Document = None
    
from docx_interpreter.parser import PackageReader, XMLParser
from docx_interpreter.renderers import HTMLRenderer, PDFRenderer


class TestDocument:
    """Test cases for Document class."""
    
    def test_init(self):
        """Test Document initialization."""
        doc = Document()
        
        assert doc is not None
        assert hasattr(doc, '_package_reader')
        assert hasattr(doc, '_xml_parser')
        assert hasattr(doc, '_layout_cache')
    
    def test_from_file_class_method(self, real_docx_path):
        """Test Document.from_file class method."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document.from_file(real_docx_path)
        
        assert doc is not None
        assert isinstance(doc, Document)
        assert hasattr(doc, 'parse')
        assert hasattr(doc, 'layout')
        assert hasattr(doc, 'render')
    
    def test_from_file_with_dpi(self, real_docx_path):
        """Test Document.from_file with custom DPI."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document.from_file(real_docx_path, dpi=300)
        
        assert doc is not None
        assert isinstance(doc, Document)
    
    def test_parse_method(self, real_docx_path):
        """Test Document.parse method."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document.from_file(real_docx_path)
        doc.parse()
        
        assert hasattr(doc, '_xml_parser')
        assert doc._xml_parser is not None
    
    def test_layout_method(self, real_docx_path):
        """Test Document.layout method."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document.from_file(real_docx_path)
        doc.parse()
        doc.layout()
        
        assert hasattr(doc, '_layout_cache')
        assert doc._layout_cache is not None
    
    def test_render_html(self, real_docx_path, temp_dir):
        """Test Document.render with HTML format."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document.from_file(real_docx_path)
        doc.parse()
        doc.layout()
        
        output_path = temp_dir / "output.html"
        doc.render("html", str(output_path))
        
        assert output_path.exists()
        assert output_path.stat().st_size > 0
        
        # Verify HTML content
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert "<!DOCTYPE html>" in content
        assert "<html" in content
    
    def test_render_pdf(self, real_docx_path, temp_dir):
        """Test Document.render with PDF format."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document.from_file(real_docx_path)
        doc.parse()
        doc.layout()
        
        output_path = temp_dir / "output.pdf"
        doc.render("pdf", str(output_path))
        
        assert output_path.exists()
        assert output_path.stat().st_size > 0
        
        # Verify PDF content
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert "%PDF-1.4" in content
    
    def test_get_text(self, real_docx_path):
        """Test Document.get_text method."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document.from_file(real_docx_path)
        doc.parse()
        
        text = doc.get_text()
        
        assert text is not None
        assert isinstance(text, str)
        # Real document should have some content
        if text:
            assert len(text) > 0
    
    def test_get_paragraphs(self, real_docx_path):
        """Test Document.get_paragraphs method."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document.from_file(real_docx_path)
        doc.parse()
        
        paragraphs = doc.get_paragraphs()
        
        assert paragraphs is not None
        assert isinstance(paragraphs, list)
    
    def test_get_tables(self, real_docx_path):
        """Test Document.get_tables method."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document.from_file(real_docx_path)
        doc.parse()
        
        tables = doc.get_tables()
        
        assert tables is not None
        assert isinstance(tables, list)
    
    def test_get_images(self, real_docx_path):
        """Test Document.get_images method."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document.from_file(real_docx_path)
        doc.parse()
        
        images = doc.get_images()
        
        assert images is not None
        assert isinstance(images, list)
    
    def test_get_layout_engine_html(self, real_docx_path):
        """Test Document.get_layout_engine with HTML format."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document.from_file(real_docx_path)
        engine = doc.get_layout_engine("html")
        
        assert engine is not None
        assert isinstance(engine, HTMLRenderer)
    
    def test_get_layout_engine_pdf(self, real_docx_path):
        """Test Document.get_layout_engine with PDF format."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document.from_file(real_docx_path)
        engine = doc.get_layout_engine("pdf")
        
        assert engine is not None
        assert isinstance(engine, PDFRenderer)
    
    def test_get_hybrid_estimator(self, real_docx_path):
        """Test Document.get_hybrid_estimator method."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document.from_file(real_docx_path)
        estimator = doc.get_hybrid_estimator()
        
        assert estimator is not None
        assert hasattr(estimator, 'layout_document')
    
    def test_get_document_hash(self, real_docx_path):
        """Test Document.get_document_hash method."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document.from_file(real_docx_path)
        hash_value = doc.get_document_hash()
        
        assert hash_value is not None
        assert isinstance(hash_value, str)
        assert len(hash_value) > 0
    
    def test_clear_layout_cache(self, real_docx_path):
        """Test Document.clear_layout_cache method."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document.from_file(real_docx_path)
        doc.parse()
        doc.layout()
        
        # Cache should exist
        assert doc._layout_cache is not None
        
        # Clear cache
        doc.clear_layout_cache()
        
        # Cache should be cleared
        assert doc._layout_cache is None
    
    def test_export_to_html(self, real_docx_path, temp_dir):
        """Test Document.export_to_html method."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document.from_file(real_docx_path)
        doc.parse()
        doc.layout()
        
        output_path = temp_dir / "export.html"
        doc.export_to_html(str(output_path))
        
        assert output_path.exists()
        assert output_path.stat().st_size > 0
    
    def test_export_to_pdf(self, real_docx_path, temp_dir):
        """Test Document.export_to_pdf method."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document.from_file(real_docx_path)
        doc.parse()
        doc.layout()
        
        output_path = temp_dir / "export.pdf"
        doc.export_to_pdf(str(output_path))
        
        assert output_path.exists()
        assert output_path.stat().st_size > 0
    
    def test_error_handling_invalid_file(self):
        """Test error handling with invalid file."""
        with pytest.raises(FileNotFoundError):
            Document.from_file("nonexistent.docx")
    
    def test_error_handling_invalid_format(self, real_docx_path):
        """Test error handling with invalid render format."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document.from_file(real_docx_path)
        doc.parse()
        doc.layout()
        
        with pytest.raises(ValueError):
            doc.render("invalid_format", "output.txt")
    
    def test_workflow_integration(self, real_docx_path, temp_dir):
        """Test complete workflow integration."""
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
        
        # Step 4: Get text content
        text = doc.get_text()
        assert text is not None
        
        # Step 5: Export to HTML
        html_output = temp_dir / "workflow.html"
        doc.export_to_html(str(html_output))
        assert html_output.exists()
        
        # Step 6: Export to PDF
        pdf_output = temp_dir / "workflow.pdf"
        doc.export_to_pdf(str(pdf_output))
        assert pdf_output.exists()
    
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
    
    def test_memory_usage(self, real_docx_path):
        """Test memory usage with real DOCX file."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        doc = Document.from_file(real_docx_path)
        doc.parse()
        doc.layout()
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 100MB)
        assert memory_increase < 100 * 1024 * 1024
    
    def test_concurrent_access(self, real_docx_path):
        """Test concurrent access to document."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        import threading
        import time
        
        doc = Document.from_file(real_docx_path)
        doc.parse()
        doc.layout()
        
        results = []
        
        def get_text():
            results.append(doc.get_text())
        
        def get_paragraphs():
            results.append(doc.get_paragraphs())
        
        def get_tables():
            results.append(doc.get_tables())
        
        # Create threads
        threads = [
            threading.Thread(target=get_text),
            threading.Thread(target=get_paragraphs),
            threading.Thread(target=get_tables)
        ]
        
        # Start threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(results) == 3
        assert all(result is not None for result in results)
