"""
Tests for Document class.

This module contains unit tests for the new Document API.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil

from docx_interpreter import Document


class TestDocument:
    """Test cases for Document class."""
    
    def test_init_empty(self):
        """Test Document initialization without file."""
        doc = Document()
        assert doc is not None
    
    def test_init_with_file(self, real_docx_path):
        """Test Document initialization with file."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document(real_docx_path)
        assert doc is not None
        assert doc._file_path == Path(real_docx_path)
    
    def test_open_class_method(self, real_docx_path):
        """Test Document.open class method."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document.open(real_docx_path)
        assert doc is not None
        assert isinstance(doc, Document)
    
    def test_create_class_method(self):
        """Test Document.create class method."""
        doc = Document.create()
        assert doc is not None
        assert isinstance(doc, Document)
    
    def test_to_model(self, real_docx_path):
        """Test Document.to_model method."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document(real_docx_path)
        model = doc.to_model()
        
        assert model is not None
        assert hasattr(model, 'elements') or hasattr(model, 'parser')
    
    def test_pipeline(self, real_docx_path):
        """Test Document.pipeline method."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document(real_docx_path)
        layout = doc.pipeline()
        
        assert layout is not None
        assert hasattr(layout, 'pages')
    
    def test_to_pdf(self, real_docx_path, temp_dir):
        """Test Document.to_pdf method."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document(real_docx_path)
        output_path = temp_dir / "output.pdf"
        
        result_path = doc.to_pdf(output_path)
        
        assert result_path.exists()
        assert result_path.stat().st_size > 0
        
        # Verify PDF content
        with open(result_path, 'rb') as f:
            content = f.read(10)
        assert content.startswith(b'%PDF')
    
    def test_to_html(self, real_docx_path, temp_dir):
        """Test Document.to_html method."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document(real_docx_path)
        output_path = temp_dir / "output.html"
        
        result_path = doc.to_html(output_path)
        
        assert result_path.exists()
        assert result_path.stat().st_size > 0
        
        # Verify HTML content
        with open(result_path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert "<!DOCTYPE html>" in content or "<html" in content
    
    def test_to_json(self, real_docx_path, temp_dir):
        """Test Document.to_json method."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document(real_docx_path)
        output_path = temp_dir / "output.json"
        
        result = doc.to_json(output_path)
        
        assert result is not None
        assert isinstance(result, dict)
        assert output_path.exists()
    
    def test_get_metadata(self, real_docx_path):
        """Test Document.get_metadata method."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document(real_docx_path)
        metadata = doc.get_metadata()
        
        assert metadata is not None
        assert isinstance(metadata, dict)
    
    def test_get_stats(self, real_docx_path):
        """Test Document.get_stats method."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document(real_docx_path)
        stats = doc.get_stats()
        
        assert stats is not None
        assert isinstance(stats, dict)
        assert 'paragraphs' in stats
        assert 'tables' in stats
    
    def test_get_sections(self, real_docx_path):
        """Test Document.get_sections method."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        doc = Document(real_docx_path)
        sections = doc.get_sections()
        
        assert sections is not None
        assert isinstance(sections, list)
    
    def test_error_handling_invalid_file(self):
        """Test error handling with invalid file."""
        with pytest.raises(FileNotFoundError):
            Document("nonexistent.docx")
    
    def test_workflow_integration(self, real_docx_path, temp_dir):
        """Test complete workflow integration."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Step 1: Load document
        doc = Document(real_docx_path)
        assert doc is not None
        
        # Step 2: Get model
        model = doc.to_model()
        assert model is not None
        
        # Step 3: Process pipeline
        layout = doc.pipeline()
        assert layout is not None
        
        # Step 4: Export to HTML
        html_output = temp_dir / "workflow.html"
        doc.to_html(html_output)
        assert html_output.exists()
        
        # Step 5: Export to PDF
        pdf_output = temp_dir / "workflow.pdf"
        doc.to_pdf(pdf_output)
        assert pdf_output.exists()
    
    def test_performance_with_real_file(self, real_docx_path):
        """Test performance with real DOCX file."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        import time
        
        # Test loading performance
        start_time = time.time()
        doc = Document(real_docx_path)
        load_time = time.time() - start_time
        
        assert load_time < 5.0  # Should load within 5 seconds
        
        # Test pipeline performance
        start_time = time.time()
        doc.pipeline()
        pipeline_time = time.time() - start_time
        
        assert pipeline_time < 30.0  # Should process within 30 seconds
