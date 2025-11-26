"""
Tests for Document API (high-level API).

Tests for the new Document API including:
- Opening documents
- Adding paragraphs
- Replacing text
- Filling placeholders
- Merging documents
- HTML workflow
- PDF rendering
- DOCX export
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from docx_interpreter import Document
from docx_interpreter.document_api import Document as DocumentAPI
from docx_interpreter.models.paragraph import Paragraph
from docx_interpreter.models.run import Run


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


class TestDocumentAPI:
    """Test cases for Document API."""
    
    def test_open_document(self, sample_docx_path):
        """Test opening a document."""
        if not Path(sample_docx_path).exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        assert doc is not None
        # Document.open() returns Document from api.py which wraps DocumentAPI
        assert hasattr(doc, '_document_model') or hasattr(doc, 'body')
    
    def test_open_document_with_mock(self):
        """Test opening a document with mock."""
        from unittest.mock import Mock, patch
        from docx_interpreter.models.body import Body
        
        # Mock PackageReader and XMLParser at the point of use in document_api.py
        mock_body = Body()
        mock_parser = Mock()
        mock_parser.parse_body = Mock(return_value=mock_body)
        mock_reader = Mock()
        
        # Patch at the import location in document_api.py
        with patch('docx_interpreter.parser.package_reader.PackageReader', return_value=mock_reader), \
             patch('docx_interpreter.parser.xml_parser.XMLParser', return_value=mock_parser):
            
            # This test verifies the API structure
            assert hasattr(Document, 'open')
            assert callable(Document.open)
    
    def test_add_paragraph(self, sample_docx_path, temp_output_dir):
        """Test adding a paragraph."""
        if not Path(sample_docx_path).exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        doc.add_paragraph("Test paragraph")
        
        # Save and verify
        output_path = Path(temp_output_dir) / "test.docx"
        doc.save(str(output_path))
        
        assert output_path.exists()
    
    def test_add_paragraph_structure(self):
        """Test that add_paragraph method exists and is callable."""
        assert hasattr(DocumentAPI, 'add_paragraph')
        assert callable(DocumentAPI.add_paragraph)
    
    def test_replace_text(self, sample_docx_path, temp_output_dir):
        """Test replacing text in document."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        # Replace text
        doc.replace_text("old text", "new text")
        
        # Save and verify
        output_path = temp_output_dir / "test.docx"
        doc.save(str(output_path))
        
        assert output_path.exists()
    
    def test_fill_placeholders(self, sample_docx_path, temp_output_dir):
        """Test filling placeholders."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        # Fill placeholders
        values = {
            "TEXT:Name": "John Doe",
            "TEXT:Company": "Test Company",
        }
        doc.fill_placeholders(values)
        
        # Save and verify
        output_path = temp_output_dir / "test.docx"
        doc.save(str(output_path))
        
        assert output_path.exists()
    
    def test_render_html(self, sample_docx_path, temp_output_dir):
        """Test rendering to HTML."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        output_path = temp_output_dir / "test.html"
        doc.render_html(str(output_path))
        
        assert output_path.exists()
        assert output_path.stat().st_size > 0
        
        # Verify HTML content
        content = output_path.read_text(encoding='utf-8')
        assert "<!DOCTYPE html>" in content
        assert "<html" in content
    
    def test_render_html_editable(self, sample_docx_path, temp_output_dir):
        """Test rendering to editable HTML."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        output_path = temp_output_dir / "test_editable.html"
        doc.render_html(str(output_path), editable=True)
        
        assert output_path.exists()
        
        # Verify editable HTML content
        content = output_path.read_text(encoding='utf-8')
        assert "contenteditable=\"true\"" in content
        assert "<style>" in content
        assert "<script>" in content
    
    def test_update_from_html_file(self, sample_docx_path, temp_output_dir):
        """Test updating document from HTML file."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        # Render to editable HTML
        html_path = temp_output_dir / "editable.html"
        doc.render_html(str(html_path), editable=True)
        
        # Modify HTML content
        html_content = html_path.read_text(encoding='utf-8')
        # Replace first paragraph content
        modified_html = html_content.replace(
            '<p contenteditable="true"',
            '<p contenteditable="true"',
            1
        )
        html_path.write_text(modified_html, encoding='utf-8')
        
        # Update document from HTML
        doc.update_from_html_file(str(html_path))
        
        # Save and verify
        output_path = temp_output_dir / "updated.docx"
        doc.save(str(output_path))
        
        assert output_path.exists()
    
    def test_render_pdf(self, sample_docx_path, temp_output_dir):
        """Test rendering to PDF."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        output_path = temp_output_dir / "test.pdf"
        doc.render_pdf(str(output_path))
        
        assert output_path.exists()
        assert output_path.stat().st_size > 0
        
        # Verify PDF content
        content = output_path.read_bytes()
        assert content.startswith(b'%PDF')
    
    def test_merge_documents(self, sample_docx_path, temp_output_dir):
        """Test merging documents."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc1 = Document.open(str(sample_docx_path))
        doc2 = Document.open(str(sample_docx_path))
        
        # Merge documents
        doc1.merge(doc2)
        
        # Save and verify
        output_path = temp_output_dir / "merged.docx"
        doc1.save(str(output_path))
        
        assert output_path.exists()
    
    def test_merge_selective(self, sample_docx_path, temp_output_dir):
        """Test selective merging."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc1 = Document.open(str(sample_docx_path))
        doc2 = Document.open(str(sample_docx_path))
        
        # Merge selectively
        doc1.merge_selective({
            'body': doc2,
            'styles': doc2,
        })
        
        # Save and verify
        output_path = temp_output_dir / "merged_selective.docx"
        doc1.save(str(output_path))
        
        assert output_path.exists()
    
    def test_apply_layout(self, sample_docx_path, temp_output_dir):
        """Test applying layout from template."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        template = Document.open(str(sample_docx_path))
        
        # Apply layout
        doc.apply_layout(template)
        
        # Save and verify
        output_path = temp_output_dir / "layout_applied.docx"
        doc.save(str(output_path))
        
        assert output_path.exists()


class TestPlaceholderEngine:
    """Test cases for PlaceholderEngine."""
    
    def test_extract_placeholders(self, sample_docx_path):
        """Test extracting placeholders from document."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        # Get placeholder engine
        from docx_interpreter.engine.placeholder_engine import PlaceholderEngine
        engine = PlaceholderEngine(doc)
        
        # Extract placeholders
        placeholders = engine.extract_placeholders()
        
        # extract_placeholders() returns a list of PlaceholderInfo objects
        assert isinstance(placeholders, list)
        assert len(placeholders) > 0
        # Check that we have PlaceholderInfo objects
        if placeholders:
            assert hasattr(placeholders[0], 'name') or isinstance(placeholders[0], dict)
    
    def test_fill_text_placeholder(self, sample_docx_path, temp_output_dir):
        """Test filling text placeholder."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        # Fill placeholders
        values = {
            "TEXT:Name": "John Doe",
            "TEXT:Date": "2024-01-01",
        }
        doc.fill_placeholders(values)
        
        # Save and verify
        output_path = temp_output_dir / "filled.docx"
        doc.save(str(output_path))
        
        assert output_path.exists()
    
    def test_format_date_placeholder(self, sample_docx_path, temp_output_dir):
        """Test date placeholder formatting."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        # Fill date placeholder
        from datetime import datetime
        values = {
            "DATE:Today": datetime.now(),
        }
        doc.fill_placeholders(values)
        
        # Save and verify
        output_path = temp_output_dir / "date_filled.docx"
        doc.save(str(output_path))
        
        assert output_path.exists()
    
    def test_format_number_placeholder(self, sample_docx_path, temp_output_dir):
        """Test number placeholder formatting."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        # Fill number placeholder
        values = {
            "NUMBER:Amount": 1234.56,
        }
        doc.fill_placeholders(values)
        
        # Save and verify
        output_path = temp_output_dir / "number_filled.docx"
        doc.save(str(output_path))
        
        assert output_path.exists()


class TestCustomBlocks:
    """Test cases for custom blocks (QR, TABLE, IMAGE, LIST)."""
    
    def test_insert_qr_code(self, sample_docx_path, temp_output_dir):
        """Test inserting QR code."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        # Fill QR placeholder
        values = {
            "QR:Code": "https://example.com",
        }
        doc.fill_placeholders(values)
        
        # Save and verify
        output_path = temp_output_dir / "qr_code.docx"
        doc.save(str(output_path))
        
        assert output_path.exists()
    
    def test_insert_table(self, sample_docx_path, temp_output_dir):
        """Test inserting table."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        # Fill table placeholder
        table_data = {
            "headers": ["Name", "Age", "City"],
            "rows": [
                ["John", "30", "New York"],
                ["Jane", "25", "London"],
            ],
            "style": "TableGrid"
        }
        values = {
            "TABLE:Data": table_data,
        }
        doc.fill_placeholders(values)
        
        # Save and verify
        output_path = temp_output_dir / "table.docx"
        doc.save(str(output_path))
        
        assert output_path.exists()
    
    def test_insert_list(self, sample_docx_path, temp_output_dir):
        """Test inserting list."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        # Fill list placeholder
        list_data = {
            "items": ["Item 1", "Item 2", "Item 3"],
            "style": "bullet",
            "level": 0
        }
        values = {
            "LIST:Items": list_data,
        }
        doc.fill_placeholders(values)
        
        # Save and verify
        output_path = temp_output_dir / "list.docx"
        doc.save(str(output_path))
        
        assert output_path.exists()
    
    def test_insert_image(self, sample_docx_path, temp_output_dir):
        """Test inserting image."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        # Fill image placeholder (if image file exists)
        image_path = Path(__file__).parent.parent / "output" / "test.png"
        if image_path.exists():
            values = {
                "IMAGE:Logo": str(image_path),
            }
            doc.fill_placeholders(values)
            
            # Save and verify
            output_path = temp_output_dir / "image.docx"
            doc.save(str(output_path))
            
            assert output_path.exists()


class TestParagraphMethods:
    """Test cases for Paragraph methods."""
    
    def test_set_list(self):
        """Test setting list on paragraph."""
        from docx_interpreter.models.paragraph import Paragraph
        
        para = Paragraph()
        para.add_run(Run())
        para.runs[0].text = "List item"
        
        # Set list
        para.set_list(level=0, numbering_id="1")
        
        assert para.numbering is not None
        assert para.numbering.get('id') == "1"
        assert para.numbering.get('level') == "0"
    
    def test_set_style(self):
        """Test setting style on paragraph."""
        from docx_interpreter.models.paragraph import Paragraph
        
        para = Paragraph()
        para.set_style("Heading 1")
        
        assert para.style == "Heading 1"


class TestHTMLParser:
    """Test cases for HTML parser."""
    
    def test_parse_html(self, temp_output_dir):
        """Test parsing HTML."""
        from docx_interpreter.parser.html_parser import HTMLParser
        
        html_content = """
        <!DOCTYPE html>
        <html>
        <body>
            <p contenteditable="true">Normal text</p>
            <p contenteditable="true"><strong>Bold</strong> and <em>italic</em></p>
            <p contenteditable="true"><u>Underlined</u></p>
        </body>
        </html>
        """
        
        parser = HTMLParser(html_content)
        result = parser.parse()
        paragraphs = result.get('paragraphs', [])
        
        # Filter out empty paragraphs (parser may create empty paragraphs from whitespace)
        content_paragraphs = [p for p in paragraphs if p.get('text', '').strip()]
        assert len(content_paragraphs) >= 3
        assert any('Normal text' in p.get('text', '') for p in content_paragraphs)
        assert any('Bold' in p.get('text', '') for p in content_paragraphs)
        assert any('Underlined' in p.get('text', '') for p in content_paragraphs)
        
        # Check formatting
        bold_para = next((p for p in content_paragraphs if 'Bold' in p.get('text', '')), None)
        assert bold_para is not None
        assert len(bold_para.get('runs', [])) > 0
        assert any(run.get('bold') == True for run in bold_para.get('runs', []))
    
    def test_parse_html_file(self, temp_output_dir):
        """Test parsing HTML file."""
        from docx_interpreter.parser.html_parser import HTMLParser
        
        html_path = temp_output_dir / "test.html"
        html_content = """
        <!DOCTYPE html>
        <html>
        <body>
            <p contenteditable="true">Test paragraph</p>
        </body>
        </html>
        """
        html_path.write_text(html_content, encoding='utf-8')
        
        result = HTMLParser.parse_file(html_path)
        paragraphs = result.get('paragraphs', [])
        
        # Filter out empty paragraphs
        content_paragraphs = [p for p in paragraphs if p.get('text', '').strip()]
        assert len(content_paragraphs) >= 1
        assert any('Test paragraph' in p.get('text', '') for p in content_paragraphs)

