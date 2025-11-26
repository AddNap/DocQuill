"""Tests for DocumentEngine layout engine."""

import pytest
from unittest.mock import Mock, MagicMock
from typing import List

from docx_interpreter.engine import DocumentEngine
from docx_interpreter.engine.geometry import Size, Margins
from docx_interpreter.engine.base_engine import LayoutPage, LayoutBlock
from docx_interpreter.engine.placeholder_resolver import PlaceholderResolver
from docx_interpreter.exceptions import LayoutError


class TestDocumentEngine:
    """Test suite for DocumentEngine."""

    def test_init_basic(self):
        """Test basic DocumentEngine initialization."""
        page_size = Size(width=210.0, height=297.0)
        margins = Margins(top=25.4, right=25.4, bottom=25.4, left=25.4)
        
        engine = DocumentEngine(page_size=page_size, margins=margins)
        
        assert engine.page_size == page_size
        assert engine.margins == margins
        assert engine._content_width > 0

    def test_init_with_components(self):
        """Test DocumentEngine initialization with custom components."""
        page_size = Size(width=210.0, height=297.0)
        margins = Margins()
        
        placeholder_resolver = PlaceholderResolver()
        numbering_data = {"1": {"levels": {}}}
        doc_defaults = {"paragraph": {}, "run": {}}
        
        engine = DocumentEngine(
            page_size=page_size,
            margins=margins,
            placeholder_resolver=placeholder_resolver,
            numbering_data=numbering_data,
            doc_defaults=doc_defaults,
        )
        
        assert engine.placeholder_resolver is placeholder_resolver
        assert engine.numbering_formatter is not None
        assert engine.doc_defaults == doc_defaults

    def test_build_layout_empty_document(self):
        """Test building layout for empty document."""
        page_size = Size(width=210.0, height=297.0)
        engine = DocumentEngine(page_size=page_size)
        
        document = Mock()
        document.placeholder_values = {}
        document.get_paragraphs.return_value = []
        document.get_tables.return_value = []
        document.get_images.return_value = []
        
        pages = engine.build_layout(document)
        
        assert isinstance(pages, list)
        assert len(pages) >= 1  # At least one page, even if empty
        assert pages[0].number == 1

    def test_build_layout_with_paragraph(self):
        """Test building layout with paragraph."""
        page_size = Size(width=210.0, height=297.0)
        engine = DocumentEngine(page_size=page_size)
        
        document = Mock()
        document.placeholder_values = {}
        
        # Mock paragraph
        paragraph = Mock()
        paragraph.get_text.return_value = "Test paragraph"
        paragraph.runs = []
        paragraph.style = {}
        
        document.get_paragraphs.return_value = [paragraph]
        document.get_tables.return_value = []
        document.get_images.return_value = []
        
        pages = engine.build_layout(document)
        
        assert len(pages) > 0
        assert len(pages[0].blocks) > 0
        assert pages[0].blocks[0].block_type == "paragraph"

    def test_build_layout_with_table(self):
        """Test building layout with table."""
        page_size = Size(width=210.0, height=297.0)
        engine = DocumentEngine(page_size=page_size)
        
        document = Mock()
        document.placeholder_values = {}
        
        # Mock table
        table = Mock()
        table.rows = [Mock(), Mock()]
        table.style = {}
        
        document.get_paragraphs.return_value = []
        document.get_tables.return_value = [table]
        document.get_images.return_value = []
        
        pages = engine.build_layout(document)
        
        assert len(pages) > 0
        # Check if table block is created
        has_table = any(block.block_type == "table" for page in pages for block in page.blocks)
        assert has_table

    def test_header_collection(self):
        """Test header element collection."""
        page_size = Size(width=210.0, height=297.0)
        engine = DocumentEngine(page_size=page_size)
        
        document = Mock()
        header = Mock()
        header.content = [Mock()]
        document.get_header.return_value = header
        
        elements = engine._collect_header_elements(document)
        
        assert len(elements) > 0

    def test_footer_collection(self):
        """Test footer element collection."""
        page_size = Size(width=210.0, height=297.0)
        engine = DocumentEngine(page_size=page_size)
        
        document = Mock()
        footer = Mock()
        footer.content = [Mock()]
        document.get_footer.return_value = footer
        
        elements = engine._collect_footer_elements(document)
        
        assert len(elements) > 0

    def test_placeholder_resolution(self):
        """Test placeholder resolution during layout."""
        page_size = Size(width=210.0, height=297.0)
        engine = DocumentEngine(page_size=page_size)
        
        document = Mock()
        document.placeholder_values = {"name": "Test"}
        
        paragraph = Mock()
        paragraph.get_text.return_value = "Hello {{name}}"
        paragraph.runs = []
        paragraph.style = {}
        
        document.get_paragraphs.return_value = [paragraph]
        document.get_tables.return_value = []
        document.get_images.return_value = []
        
        pages = engine.build_layout(document)
        
        # Verify placeholder resolver was called
        assert engine.placeholder_resolver.values == {"name": "Test"}

    def test_page_size_property(self):
        """Test page_size property."""
        page_size = Size(width=210.0, height=297.0)
        engine = DocumentEngine(page_size=page_size)
        
        assert engine.page_size == page_size

    def test_margins_property(self):
        """Test margins property."""
        margins = Margins(top=25.4, right=25.4, bottom=25.4, left=25.4)
        engine = DocumentEngine(page_size=Size(width=210.0, height=297.0), margins=margins)
        
        assert engine.margins == margins

    def test_content_width_calculation(self):
        """Test content width calculation."""
        page_size = Size(width=210.0, height=297.0)
        margins = Margins(top=25.4, right=25.4, bottom=25.4, left=25.4)
        
        engine = DocumentEngine(page_size=page_size, margins=margins)
        
        expected_width = 210.0 - 25.4 - 25.4
        assert engine._content_width == expected_width


class TestLayoutIntegration:
    """Integration tests for layout engine."""

    def test_full_document_layout(self):
        """Test layout for a full document with multiple elements."""
        page_size = Size(width=210.0, height=297.0)
        engine = DocumentEngine(page_size=page_size)
        
        document = Mock()
        document.placeholder_values = {}
        
        # Multiple paragraphs
        paragraphs = [Mock() for _ in range(3)]
        for p in paragraphs:
            p.get_text.return_value = "Test paragraph"
            p.runs = []
            p.style = {}
        
        # One table
        table = Mock()
        table.rows = [Mock(), Mock()]
        table.style = {}
        
        document.get_paragraphs.return_value = paragraphs
        document.get_tables.return_value = [table]
        document.get_images.return_value = []
        
        pages = engine.build_layout(document)
        
        # Verify layout was created
        assert len(pages) > 0
        
        # Count blocks
        total_blocks = sum(len(page.blocks) for page in pages)
        assert total_blocks >= 4  # 3 paragraphs + 1 table

