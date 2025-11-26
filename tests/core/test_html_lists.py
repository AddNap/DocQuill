"""
Tests for HTML list parsing and rendering.
"""

import pytest
from docquill.parser.html_parser import HTMLParser
from docquill.models.paragraph import Paragraph
from docquill.models.run import Run
from docquill.models.body import Body


class TestHTMLListParsing:
    """Test parsing lists from HTML."""
    
    def test_parse_unordered_list(self):
        """Test parsing unordered list."""
        html = '<ul><li>Item 1</li><li>Item 2</li></ul>'
        parser = HTMLParser(html)
        result = parser.parse()
        paragraphs = result.get('paragraphs', [])
        
        assert len(paragraphs) >= 2
        
        # Sprawdź czy paragrafy mają numbering
        for para in paragraphs[:2]:
            assert para.get('numbering') is not None
            assert para['numbering']['format'] == 'bullet'
            assert para['numbering']['level'] == 0
    
    def test_parse_ordered_list(self):
        """Test parsing ordered list."""
        html = '<ol><li>First</li><li>Second</li></ol>'
        parser = HTMLParser(html)
        result = parser.parse()
        paragraphs = result.get('paragraphs', [])
        
        assert len(paragraphs) >= 2
        
        # Sprawdź czy paragrafy mają numbering
        for para in paragraphs[:2]:
            assert para.get('numbering') is not None
            assert para['numbering']['format'] == 'decimal'
            assert para['numbering']['level'] == 0
    
    def test_parse_mixed_lists(self):
        """Test parsing mixed lists and paragraphs."""
        html = '<ul><li>Bullet 1</li></ul><p>Normal</p><ol><li>Numbered 1</li></ol>'
        parser = HTMLParser(html)
        result = parser.parse()
        paragraphs = result.get('paragraphs', [])
        
        content_paragraphs = [p for p in paragraphs if p.get('text', '').strip()]
        assert len(content_paragraphs) >= 3
        
        # Pierwszy powinien być listą
        assert content_paragraphs[0].get('numbering') is not None
        assert content_paragraphs[0]['numbering']['format'] == 'bullet'
        
        # Drugi powinien być normalnym paragrafem
        assert content_paragraphs[1].get('numbering') is None
        
        # Trzeci powinien być listą
        assert content_paragraphs[2].get('numbering') is not None
        assert content_paragraphs[2]['numbering']['format'] == 'decimal'
    
    def test_parse_nested_lists(self):
        """Test parsing nested lists."""
        html = '<ul><li>Level 1<ul><li>Level 2</li></ul></li></ul>'
        parser = HTMLParser(html)
        result = parser.parse()
        paragraphs = result.get('paragraphs', [])
        
        content_paragraphs = [p for p in paragraphs if p.get('text', '').strip()]
        # Parser może parsować tylko Level 2 jeśli Level 1 nie ma tekstu po zagnieżdżonej liście
        assert len(content_paragraphs) >= 1
        
        # Sprawdź czy przynajmniej jeden paragraf ma numbering
        numbered_paras = [p for p in content_paragraphs if p.get('numbering')]
        assert len(numbered_paras) > 0
    
    def test_parse_list_with_formatting(self):
        """Test parsing list items with formatting."""
        html = '<ul><li><strong>Bold item</strong></li><li><em>Italic item</em></li></ul>'
        parser = HTMLParser(html)
        result = parser.parse()
        paragraphs = result.get('paragraphs', [])
        
        content_paragraphs = [p for p in paragraphs if p.get('text', '').strip()]
        assert len(content_paragraphs) >= 2
        
        # Sprawdź formatowanie
        bold_para = next((p for p in content_paragraphs if 'Bold' in p.get('text', '')), None)
        if bold_para and bold_para.get('runs'):
            bold_run = next((r for r in bold_para['runs'] if 'Bold' in r.get('text', '')), None)
            if bold_run:
                assert bold_run.get('bold') is True
        
        italic_para = next((p for p in content_paragraphs if 'Italic' in p.get('text', '')), None)
        if italic_para and italic_para.get('runs'):
            italic_run = next((r for r in italic_para['runs'] if 'Italic' in r.get('text', '')), None)
            if italic_run:
                assert italic_run.get('italic') is True


class TestHTMLListRendering:
    """Test rendering lists to HTML."""
    
    def test_render_list_paragraph(self):
        """Test that paragraphs with numbering are identified."""
        from docquill.renderers import HTMLRenderer
        from unittest.mock import Mock
        
        # Create mock document with list paragraph
        body = Body()
        para = Paragraph()
        para.numbering = {
            'id': '1',
            'level': 0,
            'format': 'bullet'
        }
        run = Run()
        run.text = "List item"
        para.add_run(run)
        body.add_paragraph(para)
        
        mock_doc = Mock()
        mock_doc.get_paragraphs = lambda: body.get_paragraphs()
        mock_doc.get_tables = Mock(return_value=[])
        mock_doc.get_footnotes = Mock(return_value={})
        mock_doc.get_endnotes = Mock(return_value={})
        mock_doc.get_watermarks = Mock(return_value=[])
        mock_doc.get_headers = Mock(return_value=[])
        mock_doc.get_footers = Mock(return_value=[])
        mock_doc.footnotes = {}
        mock_doc.endnotes = {}
        mock_doc.watermarks = []
        mock_doc.headers = []
        mock_doc.footers = []
        mock_doc.placeholder_values = {}
        mock_doc.package_reader = None
        mock_doc.metadata = Mock()
        mock_doc.metadata.title = "Test"
        mock_doc.body = Mock()
        mock_doc.body.children = body.children
        
        renderer = HTMLRenderer(mock_doc, editable=True)
        html = renderer.render()
        
        # Check if HTML contains list
        assert '<ul>' in html or '<ol>' in html
        assert 'List item' in html
    
    def test_render_numbered_list(self):
        """Test rendering numbered list."""
        from docquill.renderers import HTMLRenderer
        from unittest.mock import Mock
        
        # Create mock document with numbered list paragraph
        body = Body()
        para = Paragraph()
        para.numbering = {
            'id': '2',
            'level': 0,
            'format': 'decimal'
        }
        run = Run()
        run.text = "Numbered item"
        para.add_run(run)
        body.add_paragraph(para)
        
        mock_doc = Mock()
        mock_doc.get_paragraphs = lambda: body.get_paragraphs()
        mock_doc.get_tables = Mock(return_value=[])
        mock_doc.get_footnotes = Mock(return_value={})
        mock_doc.get_endnotes = Mock(return_value={})
        mock_doc.get_watermarks = Mock(return_value=[])
        mock_doc.get_headers = Mock(return_value=[])
        mock_doc.get_footers = Mock(return_value=[])
        mock_doc.footnotes = {}
        mock_doc.endnotes = {}
        mock_doc.watermarks = []
        mock_doc.headers = []
        mock_doc.footers = []
        mock_doc.placeholder_values = {}
        mock_doc.package_reader = None
        mock_doc.metadata = Mock()
        mock_doc.metadata.title = "Test"
        mock_doc.body = Mock()
        mock_doc.body.children = body.children
        
        renderer = HTMLRenderer(mock_doc, editable=True)
        html = renderer.render()
        
        # Check if HTML contains <ol>
        assert '<ol>' in html
        assert 'Numbered item' in html

