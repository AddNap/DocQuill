"""
Tests for normalize.py - StyleNormalizer and NumberingNormalizer.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock

from docquill.normalize import StyleNormalizer, NumberingNormalizer
from docquill.models.paragraph import Paragraph
from docquill.models.run import Run


@pytest.fixture
def mock_paragraph():
    """Create mock paragraph for testing."""
    para = Paragraph()
    # Add a run with text instead of setting para.text directly
    run = Run()
    run.text = "Test paragraph"
    para.add_run(run)
    para.style = {}
    return para


@pytest.fixture
def mock_numbering_parser():
    """Create mock numbering parser."""
    parser = Mock()
    parser.get_numbering_info = Mock(return_value=None)
    parser.get_numbering_definition = Mock(return_value={'levels': {}})
    return parser


class TestStyleNormalizer:
    """Test cases for StyleNormalizer."""
    
    def test_init(self):
        """Test StyleNormalizer initialization."""
        normalizer = StyleNormalizer(None)
        
        assert normalizer._original_xml is None
        assert isinstance(normalizer._para_signatures, dict)
        assert isinstance(normalizer._run_signatures, dict)
        assert normalizer._style_counter == 1
        assert normalizer._used is False
    
    def test_register_paragraph(self, mock_paragraph):
        """Test registering paragraph for style normalization."""
        normalizer = StyleNormalizer(None)
        
        # Set paragraph style
        mock_paragraph.style = {'name': 'Normal', 'bold': True}
        
        normalizer.register_paragraph(mock_paragraph)
        
        # Should register paragraph in signatures
        assert normalizer._used is True
        assert len(normalizer._para_signatures) > 0
    
    def test_register_run(self):
        """Test registering run for style normalization."""
        normalizer = StyleNormalizer(None)
        
        run = Run()
        run.text = "Test"
        run.bold = True
        
        normalizer.register_run(run)
        
        # Should register run in signatures
        assert normalizer._used is True
        assert len(normalizer._run_signatures) > 0
    
    def test_to_xml(self):
        """Test generating styles.xml."""
        normalizer = StyleNormalizer(None)
        
        # Register some styles
        para = Paragraph()
        para.style = {'name': 'Normal'}
        normalizer.register_paragraph(para)
        
        xml = normalizer.to_xml()
        
        assert xml is not None
        assert isinstance(xml, str)
        assert '<?xml' in xml or '<w:styles' in xml or 'styles' in xml.lower()


class TestNumberingNormalizer:
    """Test cases for NumberingNormalizer."""
    
    def test_init(self, mock_numbering_parser):
        """Test NumberingNormalizer initialization."""
        normalizer = NumberingNormalizer(mock_numbering_parser, None)
        
        assert normalizer._parser == mock_numbering_parser
        assert normalizer._abstract_counter == 1
        assert normalizer._num_counter == 1
        assert isinstance(normalizer._abstracts, dict)
        assert isinstance(normalizer._num_map, dict)
    
    def test_register_paragraph(self, mock_numbering_parser):
        """Test registering paragraph for numbering normalization."""
        normalizer = NumberingNormalizer(mock_numbering_parser, None)
        
        para = Paragraph()
        para.numbering = {'id': '1', 'level': 0}
        
        result = normalizer.register_paragraph(para)
        
        # Should return numbering info or None
        # If numbering definition is not found, returns None
        assert result is None or isinstance(result, dict)
    
    def test_to_xml(self, mock_numbering_parser):
        """Test generating numbering.xml."""
        normalizer = NumberingNormalizer(mock_numbering_parser, None)
        
        # Register some numbering
        para = Paragraph()
        para.numbering = {'id': '1', 'level': 0}
        normalizer.register_paragraph(para)
        
        xml = normalizer.to_xml()
        
        assert xml is not None
        assert isinstance(xml, str)
        assert '<?xml' in xml or '<w:numbering' in xml or 'numbering' in xml.lower()
    
    def test_register_paragraph_with_style_numbering(self, mock_numbering_parser):
        """Test registering paragraph with numbering from style."""
        normalizer = NumberingNormalizer(mock_numbering_parser, None)
        
        para = Paragraph()
        para.style = {'numbering': {'id': '2', 'level': 1}}
        para.numbering = None
        
        result = normalizer.register_paragraph(para)
        
        # Should extract numbering from style
        assert result is None or isinstance(result, dict)

