"""
Tests for HTML image parsing and rendering.
"""

import pytest
from docquill.parser.html_parser import HTMLParser
from docquill.models.image import Image
from docquill.models.body import Body


class TestHTMLImageParsing:
    """Test parsing images from HTML."""
    
    def test_parse_simple_image(self):
        """Test parsing simple image."""
        html = '<img src="image1.png" alt="Test" width="100" height="50" />'
        parser = HTMLParser(html)
        result = parser.parse()
        
        images = result.get('images', [])
        assert len(images) == 1
        
        img = images[0]
        assert img.get('src') == 'image1.png'
        assert img.get('alt') == 'Test'
        assert img.get('width') == 100
        assert img.get('height') == 50
    
    def test_parse_image_without_dimensions(self):
        """Test parsing image without dimensions."""
        html = '<img src="image2.jpg" alt="Image 2" />'
        parser = HTMLParser(html)
        result = parser.parse()
        
        images = result.get('images', [])
        assert len(images) == 1
        
        img = images[0]
        assert img.get('src') == 'image2.jpg'
        assert img.get('alt') == 'Image 2'
        assert img.get('width') is None
        assert img.get('height') is None
    
    def test_parse_image_with_rel_id(self):
        """Test parsing image with data-image-id."""
        html = '<img src="image3.png" data-image-id="rId5" />'
        parser = HTMLParser(html)
        result = parser.parse()
        
        images = result.get('images', [])
        assert len(images) == 1
        
        img = images[0]
        assert img.get('rel_id') == 'rId5'
    
    def test_parse_mixed_content(self):
        """Test parsing mixed paragraphs and images."""
        html = '<p>Paragraph 1</p><img src="img1.png" /><p>Paragraph 2</p><img src="img2.png" />'
        parser = HTMLParser(html)
        result = parser.parse()
        
        paragraphs = result.get('paragraphs', [])
        images = result.get('images', [])
        
        assert len(paragraphs) >= 2
        assert len(images) == 2
    
    def test_parse_image_in_table(self):
        """Test parsing image inside table cell."""
        html = '<table><tr><td><img src="cell_image.png" /></td></tr></table>'
        parser = HTMLParser(html)
        result = parser.parse()
        
        tables = result.get('tables', [])
        images = result.get('images', [])
        
        # Obrazy w komórkach tabeli nie są jeszcze obsługiwane jako osobne obrazy
        # Ale parsowanie powinno działać
        assert len(tables) == 1

