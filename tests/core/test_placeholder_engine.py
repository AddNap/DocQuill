"""
Tests for PlaceholderEngine.

Tests placeholder extraction, filling, and custom blocks.
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from datetime import datetime

from docquill import Document
from docquill.engine.placeholder_engine import PlaceholderEngine, PlaceholderInfo


@pytest.fixture
def sample_docx_path():
    """Path to sample DOCX file."""
    # Try with space in filename first
    path = Path(__file__).parent / "files" / "Zapytanie_Ofertowe test.docx"
    if not path.exists():
        # Fallback to underscore version
        path = Path(__file__).parent / "files" / "Zapytanie_Ofertowe_test.docx"
    if not path.exists():
        # Fallback to original
        path = Path(__file__).parent / "files" / "Zapytanie_Ofertowe.docx"
    return path


@pytest.fixture
def temp_output_dir():
    """Create temporary output directory."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


class TestPlaceholderExtraction:
    """Test placeholder extraction."""
    
    def test_extract_placeholders(self, sample_docx_path):
        """Test extracting placeholders from document."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        engine = PlaceholderEngine(doc)
        
        placeholders = engine.extract_placeholders()
        
        # extract_placeholders() returns a list of PlaceholderInfo objects
        assert isinstance(placeholders, list)
        assert len(placeholders) > 0
        # Check that we have PlaceholderInfo objects
        if placeholders:
            assert hasattr(placeholders[0], 'name') or isinstance(placeholders[0], dict)
    
    def test_classify_placeholder(self):
        """Test placeholder classification."""
        from unittest.mock import Mock
        
        # Create mock document
        doc = Mock()
        doc._document_model = Mock()
        doc._document_model.body = Mock()
        doc._document_model.body.children = []
        
        engine = PlaceholderEngine(doc)
        
        # Test different placeholder types (method returns lowercase)
        assert engine._classify_placeholder("TEXT:Name") == "text"
        assert engine._classify_placeholder("DATE:Today") == "date"
        assert engine._classify_placeholder("NUMBER:Amount") == "number"
        assert engine._classify_placeholder("QR:Code") == "qr"
        assert engine._classify_placeholder("TABLE:Data") == "table"
        assert engine._classify_placeholder("LIST:Items") == "list"
        assert engine._classify_placeholder("IMAGE:Logo") == "image"
        # Test new placeholder types
        assert engine._classify_placeholder("WATERMARK:Status") == "watermark"
        assert engine._classify_placeholder("FOOTNOTE:Ref1") == "footnote"
        assert engine._classify_placeholder("ENDNOTE:Ref1") == "endnote"
        assert engine._classify_placeholder("CROSSREF:Chapter1") == "crossref"
        assert engine._classify_placeholder("FORMULA:Sum") == "formula"


class TestPlaceholderFilling:
    """Test placeholder filling."""
    
    def test_fill_text_placeholder(self, sample_docx_path, temp_output_dir):
        """Test filling text placeholder."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        values = {
            "TEXT:Name": "John Doe",
            "TEXT:Company": "Test Company",
        }
        doc.fill_placeholders(values)
        
        output_path = temp_output_dir / "filled.docx"
        doc.save(str(output_path))
        
        assert output_path.exists()
    
    def test_fill_date_placeholder(self, sample_docx_path, temp_output_dir):
        """Test filling date placeholder."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        values = {
            "DATE:Today": datetime.now(),
        }
        doc.fill_placeholders(values)
        
        output_path = temp_output_dir / "date_filled.docx"
        doc.save(str(output_path))
        
        assert output_path.exists()
    
    def test_fill_number_placeholder(self, sample_docx_path, temp_output_dir):
        """Test filling number placeholder."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        values = {
            "NUMBER:Amount": 1234.56,
        }
        doc.fill_placeholders(values)
        
        output_path = temp_output_dir / "number_filled.docx"
        doc.save(str(output_path))
        
        assert output_path.exists()


class TestCustomBlocks:
    """Test custom blocks."""
    
    def test_insert_qr_code(self, sample_docx_path, temp_output_dir):
        """Test inserting QR code."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        values = {
            "QR:Code": "https://example.com",
        }
        doc.fill_placeholders(values)
        
        output_path = temp_output_dir / "qr_code.docx"
        doc.save(str(output_path))
        
        assert output_path.exists()
    
    def test_insert_table(self, sample_docx_path, temp_output_dir):
        """Test inserting table."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        table_data = {
            "headers": ["Name", "Age"],
            "rows": [["John", "30"], ["Jane", "25"]],
            "style": "TableGrid"
        }
        values = {
            "TABLE:Data": table_data,
        }
        doc.fill_placeholders(values)
        
        output_path = temp_output_dir / "table.docx"
        doc.save(str(output_path))
        
        assert output_path.exists()
    
    def test_insert_list(self, sample_docx_path, temp_output_dir):
        """Test inserting list."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        list_data = {
            "items": ["Item 1", "Item 2"],
            "style": "bullet"
        }
        values = {
            "LIST:Items": list_data,
        }
        doc.fill_placeholders(values)
        
        output_path = temp_output_dir / "list.docx"
        doc.save(str(output_path))
        
        assert output_path.exists()


class TestAdvancedPlaceholders:
    """Test advanced placeholder types."""
    
    def test_watermark_placeholder(self, sample_docx_path, temp_output_dir):
        """Test watermark placeholder."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        values = {
            "WATERMARK:Status": {"text": "DRAFT", "angle": 45, "opacity": 0.3}
        }
        doc.fill_placeholders(values)
        
        output_path = temp_output_dir / "watermark.docx"
        doc.save(str(output_path))
        
        assert output_path.exists()
    
    def test_footnote_placeholder(self, sample_docx_path, temp_output_dir):
        """Test footnote placeholder."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        values = {
            "FOOTNOTE:Ref1": {"text": "Źródło danych", "marker": "1"}
        }
        doc.fill_placeholders(values)
        
        output_path = temp_output_dir / "footnote.docx"
        doc.save(str(output_path))
        
        assert output_path.exists()
    
    def test_endnote_placeholder(self, sample_docx_path, temp_output_dir):
        """Test endnote placeholder."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        values = {
            "ENDNOTE:Ref1": {"text": "Dodatkowe informacje", "marker": "i"}
        }
        doc.fill_placeholders(values)
        
        output_path = temp_output_dir / "endnote.docx"
        doc.save(str(output_path))
        
        assert output_path.exists()
    
    def test_crossref_placeholder(self, sample_docx_path, temp_output_dir):
        """Test cross-reference placeholder."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        values = {
            "CROSSREF:Chapter1": {"type": "heading", "number": 1}
        }
        doc.fill_placeholders(values)
        
        output_path = temp_output_dir / "crossref.docx"
        doc.save(str(output_path))
        
        assert output_path.exists()
    
    def test_formula_placeholder(self, sample_docx_path, temp_output_dir):
        """Test formula placeholder."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        values = {
            "FORMULA:Sum": {"formula": "\\sum_{i=1}^{n} x_i", "format": "latex"}
        }
        doc.fill_placeholders(values)
        
        output_path = temp_output_dir / "formula.docx"
        doc.save(str(output_path))
        
        assert output_path.exists()
    
    def test_watermark_simple_string(self):
        """Test watermark with simple string."""
        from unittest.mock import Mock
        from docquill.engine.placeholder_engine import PlaceholderEngine
        
        doc = Mock()
        body = Mock()
        body.children = []
        body.get_paragraphs = Mock(return_value=[])
        body.paragraphs = []
        body.get_tables = Mock(return_value=[])
        body.tables = []
        
        # Mock _get_body to return our mock body
        doc.body = body
        doc._body = body
        doc.get_body = Mock(return_value=body)
        
        engine = PlaceholderEngine(doc)
        
        # Test with simple string
        result = engine.insert_watermark("WATERMARK:Status", "DRAFT")
        # Should return False if placeholder not found (empty document)
        assert isinstance(result, bool)
        assert result == False  # No placeholder in empty document
    
    def test_footnote_simple_string(self):
        """Test footnote with simple string."""
        from unittest.mock import Mock
        from docquill.engine.placeholder_engine import PlaceholderEngine
        
        doc = Mock()
        body = Mock()
        body.children = []
        body.get_paragraphs = Mock(return_value=[])
        body.paragraphs = []
        body.get_tables = Mock(return_value=[])
        body.tables = []
        
        # Mock _get_body to return our mock body
        doc.body = body
        doc._body = body
        doc.get_body = Mock(return_value=body)
        
        engine = PlaceholderEngine(doc)
        
        # Test with simple string
        result = engine.insert_footnote("FOOTNOTE:Ref1", "Test footnote")
        assert isinstance(result, bool)
        assert result == False  # No placeholder in empty document
    
    def test_crossref_formatting(self):
        """Test cross-reference formatting."""
        from unittest.mock import Mock
        from docquill.engine.placeholder_engine import PlaceholderEngine
        
        doc = Mock()
        doc._document_model = Mock()
        doc._document_model.body = Mock()
        doc._document_model.body.children = []
        
        engine = PlaceholderEngine(doc)
        
        # Test different crossref types
        assert "Rozdział" in engine._format_crossref({"type": "heading", "number": 1}, "CROSSREF:Ch1")
        assert "Rysunek" in engine._format_crossref({"type": "figure", "number": 2}, "CROSSREF:Fig1")
        assert "Tabela" in engine._format_crossref({"type": "table", "number": 3}, "CROSSREF:Tab1")
        assert "Równanie" in engine._format_crossref({"type": "equation", "number": 4}, "CROSSREF:Eq1")
    
    def test_formula_latex_conversion(self):
        """Test LaTeX to readable conversion in formulas."""
        from unittest.mock import Mock
        from docquill.engine.placeholder_engine import PlaceholderEngine
        
        doc = Mock()
        body = Mock()
        body.children = []
        body.get_paragraphs = Mock(return_value=[])
        body.paragraphs = []
        body.get_tables = Mock(return_value=[])
        body.tables = []
        
        # Mock _get_body to return our mock body
        doc.body = body
        doc._body = body
        doc.get_body = Mock(return_value=body)
        
        engine = PlaceholderEngine(doc)
        
        # Test LaTeX conversion
        result = engine.insert_formula("FORMULA:Sum", "\\sum_{i=1}^{n} x_i")
        assert isinstance(result, bool)
        assert result == False  # No placeholder in empty document

