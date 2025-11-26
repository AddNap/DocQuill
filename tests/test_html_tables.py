"""
Tests for HTML table parsing and rendering.
"""

import pytest
from docx_interpreter.parser.html_parser import HTMLParser
from docx_interpreter.models.table import Table, TableRow, TableCell
from docx_interpreter.models.paragraph import Paragraph
from docx_interpreter.models.body import Body


class TestHTMLTableParsing:
    """Test parsing tables from HTML."""
    
    def test_parse_simple_table(self):
        """Test parsing simple table."""
        html = '<table><tr><td>Cell 1</td><td>Cell 2</td></tr></table>'
        parser = HTMLParser(html)
        result = parser.parse()
        
        tables = result.get('tables', [])
        assert len(tables) == 1
        
        table = tables[0]
        assert len(table.get('rows', [])) == 1
        
        row = table['rows'][0]
        assert len(row.get('cells', [])) == 2
    
    def test_parse_table_with_header(self):
        """Test parsing table with header row."""
        html = '<table><tr><th>Header 1</th><th>Header 2</th></tr><tr><td>Cell 1</td><td>Cell 2</td></tr></table>'
        parser = HTMLParser(html)
        result = parser.parse()
        
        tables = result.get('tables', [])
        assert len(tables) == 1
        
        table = tables[0]
        rows = table.get('rows', [])
        assert len(rows) == 2
        
        # Pierwszy wiersz powinien być header
        assert rows[0].get('is_header') is True
    
    def test_parse_table_with_formatting(self):
        """Test parsing table with formatted content."""
        html = '<table><tr><td><strong>Bold</strong> text</td></tr></table>'
        parser = HTMLParser(html)
        result = parser.parse()
        
        tables = result.get('tables', [])
        assert len(tables) == 1
        
        table = tables[0]
        row = table['rows'][0]
        cell = row['cells'][0]
        
        # Komórka powinna mieć paragrafy
        paragraphs = cell.get('paragraphs', [])
        assert len(paragraphs) > 0
        
        # Sprawdź formatowanie
        if paragraphs:
            para = paragraphs[0]
            runs = para.get('runs', [])
            if runs:
                bold_run = next((r for r in runs if r.get('bold')), None)
                assert bold_run is not None
    
    def test_parse_table_with_multiple_paragraphs(self):
        """Test parsing table with multiple paragraphs in cell."""
        html = '<table><tr><td><p>Para 1</p><p>Para 2</p></td></tr></table>'
        parser = HTMLParser(html)
        result = parser.parse()
        
        tables = result.get('tables', [])
        assert len(tables) == 1
        
        table = tables[0]
        row = table['rows'][0]
        cell = row['cells'][0]
        
        # Komórka powinna mieć 2 paragrafy
        paragraphs = cell.get('paragraphs', [])
        assert len(paragraphs) >= 2
    
    def test_parse_mixed_content(self):
        """Test parsing mixed paragraphs and tables."""
        html = '<p>Paragraph 1</p><table><tr><td>Cell</td></tr></table><p>Paragraph 2</p>'
        parser = HTMLParser(html)
        result = parser.parse()
        
        paragraphs = result.get('paragraphs', [])
        tables = result.get('tables', [])
        
        assert len(paragraphs) >= 2
        assert len(tables) == 1

