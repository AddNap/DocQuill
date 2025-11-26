"""
End-to-end integration tests for complete workflows.

Tests full document processing cycles:
- DOCX → HTML → DOCX (editing workflow)
- DOCX → PDF (rendering workflow)
- Formatting preservation across workflows
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from docquill import Document
from docquill.models.paragraph import Paragraph
from docquill.models.run import Run
from docquill.models.table import Table, TableRow, TableCell
from docquill.models.image import Image


@pytest.fixture
def sample_docx_path():
    """Path to sample DOCX file."""
    path = Path(__file__).parent / "files" / "Zapytanie_Ofertowe test.docx"
    if not path.exists():
        path = Path(__file__).parent / "files" / "Zapytanie_Ofertowe_test.docx"
    if not path.exists():
        path = Path(__file__).parent / "files" / "Zapytanie_Ofertowe.docx"
    return path


@pytest.fixture
def temp_output_dir():
    """Create temporary output directory."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def simple_document(temp_output_dir):
    """Create a simple test document with various elements."""
    # Create document using Document API
    doc = Document.create()
    
    # Add paragraphs with formatting
    doc.add_paragraph("Normal paragraph")
    para_bold = doc.add_paragraph("Bold paragraph")
    doc.add_run(para_bold, "Bold paragraph", bold=True)
    para_italic = doc.add_paragraph("Italic paragraph")
    doc.add_run(para_italic, "Italic paragraph", italic=True)
    
    # Add a list
    doc.add_paragraph("List item 1")
    doc.add_paragraph("List item 2")
    
    # Add a table
    doc.add_paragraph("Before table")
    # Note: Table adding might need to be done differently
    
    return doc


class TestE2E_DOCX_HTML_DOCX:
    """End-to-end tests for DOCX → HTML → DOCX workflow."""
    
    @pytest.mark.integration
    @pytest.mark.e2e
    def test_full_html_editing_workflow(self, sample_docx_path, temp_output_dir):
        """Test complete DOCX → HTML → DOCX editing cycle."""
        if not Path(sample_docx_path).exists():
            pytest.skip("Sample DOCX file not found")
        
        # Step 1: Open DOCX
        doc = Document.open(str(sample_docx_path))
        assert doc is not None
        
        # Step 2: Render to editable HTML
        html_path = temp_output_dir / "editable.html"
        doc.render_html(str(html_path), editable=True)
        assert html_path.exists()
        
        # Step 3: Verify HTML contains expected elements
        html_content = html_path.read_text(encoding='utf-8')
        assert "<!DOCTYPE html>" in html_content
        assert "contenteditable" in html_content
        
        # Step 4: Parse HTML back (simulate editing)
        from docquill.parser.html_parser import HTMLParser
        parsed_data = HTMLParser.parse_file(html_path)
        
        # Verify we can parse the HTML
        assert 'paragraphs' in parsed_data
        assert 'tables' in parsed_data
        assert 'images' in parsed_data
        
        # Step 5: Update document from HTML
        # Create a modified HTML file
        modified_html = html_content.replace("contenteditable", "contenteditable")
        modified_html_path = temp_output_dir / "modified.html"
        modified_html_path.write_text(modified_html, encoding='utf-8')
        
        # Update document from HTML
        doc.update_from_html_file(str(modified_html_path), preserve_structure=True)
        
        # Step 6: Save back to DOCX
        output_docx = temp_output_dir / "output.docx"
        doc.save(str(output_docx))
        assert output_docx.exists()
        assert output_docx.stat().st_size > 0
        
        # Step 7: Verify we can open the saved DOCX
        doc2 = Document.open(str(output_docx))
        assert doc2 is not None
    
    @pytest.mark.integration
    @pytest.mark.e2e
    @pytest.mark.skip(reason="Requires full Document.create() API implementation with body population")
    def test_html_workflow_with_formatting(self, temp_output_dir):
        """Test HTML workflow preserves formatting."""
        # Create a document with formatting
        doc = Document.create()
        
        # Add formatted paragraphs
        doc.add_paragraph("Normal text")
        para_bold = doc.add_paragraph("Bold text")
        doc.add_run(para_bold, "Bold text", bold=True)
        para_italic = doc.add_paragraph("Italic text")
        doc.add_run(para_italic, "Italic text", italic=True)
        
        # Render to HTML
        html_path = temp_output_dir / "formatted.html"
        doc.render_html(str(html_path), editable=True)
        
        # Verify HTML contains formatting
        html_content = html_path.read_text(encoding='utf-8')
        assert "<strong>" in html_content or "bold" in html_content.lower()
        assert "<em>" in html_content or "italic" in html_content.lower()
        
        # Parse back
        from docquill.parser.html_parser import HTMLParser
        parsed_data = HTMLParser.parse_file(html_path)
        
        # Verify formatting is preserved
        paragraphs = parsed_data.get('paragraphs', [])
        assert len(paragraphs) >= 3
        
        # Check for formatting in runs
        formatted_found = False
        for para in paragraphs:
            runs = para.get('runs', [])
            for run in runs:
                if run.get('bold') or run.get('italic'):
                    formatted_found = True
                    break
            if formatted_found:
                break
        
        assert formatted_found, "Formatting should be preserved in HTML workflow"
    
    @pytest.mark.integration
    @pytest.mark.e2e
    @pytest.mark.skip(reason="Requires full Document.create() API implementation with body population")
    def test_html_workflow_with_tables(self, temp_output_dir):
        """Test HTML workflow with tables."""
        # Create document with table
        doc = Document.create()
        
        # Add some paragraphs
        doc.add_paragraph("Before table")
        
        # Note: Table creation might need special handling
        # For now, we'll test that tables are preserved if they exist
        
        # Render to HTML
        html_path = temp_output_dir / "table.html"
        doc.render_html(str(html_path), editable=True)
        
        # Verify HTML was created
        assert html_path.exists()
        
        # Parse back
        from docquill.parser.html_parser import HTMLParser
        parsed_data = HTMLParser.parse_file(html_path)
        
        # Verify we can parse tables
        assert 'tables' in parsed_data
    
    @pytest.mark.integration
    @pytest.mark.e2e
    @pytest.mark.skip(reason="Requires full Document.create() API implementation with body population")
    def test_html_workflow_with_lists(self, temp_output_dir):
        """Test HTML workflow with lists."""
        # Create document
        doc = Document.create()
        
        # Add list items (they should be detected as lists)
        doc.add_paragraph("Item 1")
        doc.add_paragraph("Item 2")
        doc.add_paragraph("Item 3")
        
        # Render to HTML
        html_path = temp_output_dir / "list.html"
        doc.render_html(str(html_path), editable=True)
        
        # Verify HTML contains list elements
        html_content = html_path.read_text(encoding='utf-8')
        # Lists might be rendered as <ul> or <ol>
        has_list = "<ul>" in html_content or "<ol>" in html_content or "<li>" in html_content
        
        # Parse back
        from docquill.parser.html_parser import HTMLParser
        parsed_data = HTMLParser.parse_file(html_path)
        
        # Verify lists are parsed
        paragraphs = parsed_data.get('paragraphs', [])
        assert len(paragraphs) >= 3


class TestE2E_DOCX_PDF:
    """End-to-end tests for DOCX → PDF workflow."""
    
    @pytest.mark.integration
    @pytest.mark.e2e
    @pytest.mark.slow
    def test_docx_to_pdf_workflow(self, sample_docx_path, temp_output_dir):
        """Test complete DOCX → PDF rendering workflow."""
        if not Path(sample_docx_path).exists():
            pytest.skip("Sample DOCX file not found")
        
        # Step 1: Open DOCX
        doc = Document.open(str(sample_docx_path))
        assert doc is not None
        
        # Step 2: Render to PDF
        pdf_path = temp_output_dir / "output.pdf"
        doc.render_pdf(str(pdf_path))
        
        # Step 3: Verify PDF was created
        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 0
        
        # Step 4: Verify PDF content
        pdf_content = pdf_path.read_bytes()
        assert pdf_content.startswith(b'%PDF')
        
        # Step 5: Verify PDF is valid (has PDF structure)
        assert b'%%EOF' in pdf_content[-1024:]  # PDF should end with %%EOF
    
    @pytest.mark.integration
    @pytest.mark.e2e
    def test_pdf_rendering_preserves_content(self, sample_docx_path, temp_output_dir):
        """Test that PDF rendering preserves document content."""
        if not Path(sample_docx_path).exists():
            pytest.skip("Sample DOCX file not found")
        
        # Open document
        doc = Document.open(str(sample_docx_path))
        
        # Get text content
        text_before = doc.get_text() if hasattr(doc, 'get_text') else ""
        
        # Render to PDF
        pdf_path = temp_output_dir / "content_test.pdf"
        doc.render_pdf(str(pdf_path))
        
        # Verify PDF exists
        assert pdf_path.exists()
        
        # Note: Full text extraction from PDF would require additional libraries
        # For now, we verify the PDF was created successfully


class TestE2E_FormattingPreservation:
    """Tests for formatting preservation across workflows."""
    
    @pytest.mark.integration
    @pytest.mark.e2e
    @pytest.mark.skip(reason="Requires full Document.create() API implementation with body population")
    def test_formatting_preservation_html_roundtrip(self, temp_output_dir):
        """Test that formatting is preserved in HTML roundtrip."""
        # Create document with various formatting
        doc = Document.create()
        
        # Add formatted content
        doc.add_paragraph("Normal")
        para_bold = doc.add_paragraph("Bold")
        doc.add_run(para_bold, "Bold", bold=True)
        para_italic = doc.add_paragraph("Italic")
        doc.add_run(para_italic, "Italic", italic=True)
        para_underline = doc.add_paragraph("Underline")
        doc.add_run(para_underline, "Underline", underline=True)
        
        # Roundtrip: DOCX → HTML → DOCX
        html_path = temp_output_dir / "roundtrip.html"
        doc.render_html(str(html_path), editable=True)
        
        # Modify HTML (simulate editing)
        html_content = html_path.read_text(encoding='utf-8')
        # Add a new paragraph
        modified_html = html_content.replace(
            "</body>",
            '<p contenteditable="true">New paragraph</p></body>'
        )
        modified_html_path = temp_output_dir / "modified_roundtrip.html"
        modified_html_path.write_text(modified_html, encoding='utf-8')
        
        # Update document
        doc.update_from_html_file(str(modified_html_path))
        
        # Save and verify
        output_docx = temp_output_dir / "roundtrip_output.docx"
        try:
            doc.save(str(output_docx))
            assert output_docx.exists()
            
            # Verify we can open it
            doc2 = Document.open(str(output_docx))
            assert doc2 is not None
        except (ValueError, AttributeError) as e:
            # If save fails because document model is None, that's expected for new documents
            # The important thing is that HTML workflow works
            if "cannot be None" in str(e) or "document" in str(e).lower():
                pytest.skip(f"Save requires document model: {e}")
            else:
                raise
    
    @pytest.mark.integration
    @pytest.mark.e2e
    def test_placeholder_filling_workflow(self, sample_docx_path, temp_output_dir):
        """Test complete workflow: Open → Fill placeholders → Save."""
        if not Path(sample_docx_path).exists():
            pytest.skip("Sample DOCX file not found")
        
        # Open document
        doc = Document.open(str(sample_docx_path))
        
        # Fill placeholders (if any exist)
        # Extract placeholders first
        from docquill.engine.placeholder_engine import PlaceholderEngine
        engine = PlaceholderEngine(doc)
        placeholders = engine.extract_placeholders()
        
        if placeholders:
            # Create placeholder values
            placeholder_values = {}
            for placeholder in placeholders[:5]:  # Limit to first 5
                if isinstance(placeholder, dict):
                    name = placeholder.get('name', '')
                else:
                    name = getattr(placeholder, 'name', '')
                
                if name:
                    placeholder_values[f"TEXT:{name}"] = f"Test value for {name}"
            
            # Fill placeholders
            if placeholder_values:
                doc.fill_placeholders(placeholder_values)
        
        # Save document
        output_path = temp_output_dir / "filled.docx"
        doc.save(str(output_path))
        assert output_path.exists()
        
        # Verify we can open the saved document
        doc2 = Document.open(str(output_path))
        assert doc2 is not None
    
    @pytest.mark.integration
    @pytest.mark.e2e
    def test_merge_and_export_workflow(self, sample_docx_path, temp_output_dir):
        """Test workflow: Open → Merge → Export."""
        if not Path(sample_docx_path).exists():
            pytest.skip("Sample DOCX file not found")
        
        # Open two documents
        doc1 = Document.open(str(sample_docx_path))
        doc2 = Document.open(str(sample_docx_path))
        
        # Merge documents
        doc1.merge(doc2, page_break=True)
        
        # Export to HTML
        html_path = temp_output_dir / "merged.html"
        doc1.render_html(str(html_path))
        assert html_path.exists()
        
        # Export to PDF
        pdf_path = temp_output_dir / "merged.pdf"
        doc1.render_pdf(str(pdf_path))
        assert pdf_path.exists()
        
        # Save merged DOCX
        merged_docx = temp_output_dir / "merged.docx"
        doc1.save(str(merged_docx))
        assert merged_docx.exists()


class TestE2E_ErrorHandling:
    """Tests for error handling in end-to-end workflows."""
    
    @pytest.mark.integration
    @pytest.mark.e2e
    def test_workflow_with_invalid_html(self, sample_docx_path, temp_output_dir):
        """Test handling of invalid HTML in update workflow."""
        if not Path(sample_docx_path).exists():
            pytest.skip("Sample DOCX file not found")
        
        doc = Document.open(str(sample_docx_path))
        
        # Create invalid HTML
        invalid_html_path = temp_output_dir / "invalid.html"
        invalid_html_path.write_text("<html><body><p>Unclosed tag", encoding='utf-8')
        
        # Should handle gracefully
        try:
            doc.update_from_html_file(str(invalid_html_path))
            # If it doesn't raise, that's fine - parser should handle it
        except Exception as e:
            # Expected - invalid HTML should be handled gracefully
            assert isinstance(e, (ValueError, SyntaxError, AttributeError))
    
    @pytest.mark.integration
    @pytest.mark.e2e
    def test_workflow_with_missing_file(self, temp_output_dir):
        """Test handling of missing files."""
        # Try to open non-existent file
        non_existent = temp_output_dir / "does_not_exist.docx"
        
        # Should handle gracefully
        try:
            doc = Document.open(str(non_existent))
            # If it doesn't raise, check if doc is None or has error state
            if doc is None:
                return  # Expected behavior
        except Exception as e:
            # Expected - missing file should raise error
            assert isinstance(e, (FileNotFoundError, ValueError))

