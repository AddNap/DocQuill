"""
Tests for HybridLayoutEstimator class.

This module contains unit tests for the HybridLayoutEstimator functionality.
"""

import pytest
from unittest.mock import Mock, patch
import time

from docx_interpreter.Layout_engine.hybrid_layout_estimator import (
    HybridLayoutEstimator, PageGeometry, Paragraph, Page, LayoutRenderer
)
from docx_interpreter.Layout_engine.utils import FontMetrics


class TestPageGeometry:
    """Test cases for PageGeometry class."""
    
    def test_init_with_defaults(self):
        """Test PageGeometry initialization with defaults."""
        geometry = PageGeometry()
        
        assert geometry.width_mm == 210.0  # A4 width
        assert geometry.height_mm == 297.0  # A4 height
        assert geometry.margin_top_mm == 25.4
        assert geometry.margin_bottom_mm == 25.4
        assert geometry.margin_left_mm == 25.4
        assert geometry.margin_right_mm == 25.4
    
    def test_init_with_custom_values(self):
        """Test PageGeometry initialization with custom values."""
        geometry = PageGeometry(
            width_mm=300.0,
            height_mm=400.0,
            margin_top_mm=30.0,
            margin_bottom_mm=30.0,
            margin_left_mm=30.0,
            margin_right_mm=30.0
        )
        
        assert geometry.width_mm == 300.0
        assert geometry.height_mm == 400.0
        assert geometry.margin_top_mm == 30.0
        assert geometry.margin_bottom_mm == 30.0
        assert geometry.margin_left_mm == 30.0
        assert geometry.margin_right_mm == 30.0
    
    def test_available_width_mm(self):
        """Test available width calculation."""
        geometry = PageGeometry(
            width_mm=210.0,
            margin_left_mm=20.0,
            margin_right_mm=20.0
        )
        
        assert geometry.available_width_mm == 170.0
    
    def test_available_height_mm(self):
        """Test available height calculation."""
        geometry = PageGeometry(
            height_mm=297.0,
            margin_top_mm=25.0,
            margin_bottom_mm=25.0
        )
        
        assert geometry.available_height_mm == 247.0


class TestFontMetrics:
    """Test cases for FontMetrics class."""
    
    def test_init_with_defaults(self):
        """Test FontMetrics initialization with defaults."""
        metrics = FontMetrics()
        
        assert metrics.font_family == "Arial"
        assert metrics.font_size_pt == 12.0
        assert metrics.avg_char_width_mm > 0
        assert metrics.line_height_mm > 0
    
    def test_init_with_custom_values(self):
        """Test FontMetrics initialization with custom values."""
        metrics = FontMetrics(
            font_family="Times New Roman",
            font_size_pt=14.0
        )
        
        assert metrics.font_family == "Times New Roman"
        assert metrics.font_size_pt == 14.0
    
    def test_compute_avg_width_mm(self):
        """Test average character width computation."""
        metrics = FontMetrics(font_family="Arial", font_size_pt=12.0)
        avg_width = metrics.compute_avg_width_mm()
        
        assert avg_width > 0
        assert isinstance(avg_width, float)
    
    def test_compute_line_height_mm(self):
        """Test line height computation."""
        metrics = FontMetrics(font_family="Arial", font_size_pt=12.0)
        line_height = metrics.compute_line_height_mm()
        
        assert line_height > 0
        assert isinstance(line_height, float)


class TestParagraph:
    """Test cases for Paragraph class."""
    
    def test_init_with_text(self):
        """Test Paragraph initialization with text."""
        paragraph = Paragraph("Sample paragraph text")
        
        assert paragraph.text == "Sample paragraph text"
        assert paragraph.words == ["Sample", "paragraph", "text"]
        assert paragraph.word_count == 3
    
    def test_init_with_empty_text(self):
        """Test Paragraph initialization with empty text."""
        paragraph = Paragraph("")
        
        assert paragraph.text == ""
        assert paragraph.words == []
        assert paragraph.word_count == 0
    
    def test_word_count(self):
        """Test word count calculation."""
        paragraph = Paragraph("This is a test paragraph with multiple words")
        
        assert paragraph.word_count == 8
    
    def test_estimated_lines(self):
        """Test estimated lines calculation."""
        paragraph = Paragraph("This is a test paragraph")
        paragraph.estimated_lines = 2
        
        assert paragraph.estimated_lines == 2


class TestPage:
    """Test cases for Page class."""
    
    def test_init(self):
        """Test Page initialization."""
        page = Page(page_number=1)
        
        assert page.page_number == 1
        assert page.paragraphs == []
        assert page.height_mm == 0.0
    
    def test_add_paragraph(self):
        """Test adding paragraph to page."""
        page = Page(page_number=1)
        paragraph = Paragraph("Test paragraph")
        
        page.add_paragraph(paragraph)
        
        assert len(page.paragraphs) == 1
        assert page.paragraphs[0] == paragraph
    
    def test_set_height(self):
        """Test setting page height."""
        page = Page(page_number=1)
        page.set_height(250.0)
        
        assert page.height_mm == 250.0


class TestLayoutRenderer:
    """Test cases for LayoutRenderer class."""
    
    def test_init(self):
        """Test LayoutRenderer initialization."""
        renderer = LayoutRenderer()
        
        assert renderer is not None
    
    def test_render_headers(self):
        """Test rendering headers."""
        renderer = LayoutRenderer()
        headers = [Mock(), Mock()]
        
        result = renderer.render_headers(headers)
        
        assert result is not None
        assert isinstance(result, list)
        assert len(result) == len(headers)
    
    def test_render_footers(self):
        """Test rendering footers."""
        renderer = LayoutRenderer()
        footers = [Mock(), Mock()]
        
        result = renderer.render_footers(footers)
        
        assert result is not None
        assert isinstance(result, list)
        assert len(result) == len(footers)


class TestHybridLayoutEstimator:
    """Test cases for HybridLayoutEstimator class."""
    
    def test_init_with_defaults(self):
        """Test HybridLayoutEstimator initialization with defaults."""
        estimator = HybridLayoutEstimator()
        
        assert estimator is not None
        assert hasattr(estimator, 'page_geometry')
        assert hasattr(estimator, 'font_metrics')
    
    def test_init_with_custom_values(self):
        """Test HybridLayoutEstimator initialization with custom values."""
        page_geometry = PageGeometry(width_mm=300.0, height_mm=400.0)
        font_metrics = FontMetrics(font_family="Times New Roman", font_size_pt=14.0)
        
        estimator = HybridLayoutEstimator(page_geometry, font_metrics)
        
        assert estimator.page_geometry == page_geometry
        assert estimator.font_metrics == font_metrics
    
    def test_estimate_paragraph_lines(self):
        """Test paragraph lines estimation."""
        estimator = HybridLayoutEstimator()
        paragraph = Paragraph("This is a test paragraph with multiple words")
        
        lines = estimator.estimate_paragraph_lines_with_paragraph(paragraph)
        
        assert lines > 0
        assert isinstance(lines, int)
    
    def test_estimate_page_count(self):
        """Test page count estimation."""
        estimator = HybridLayoutEstimator()
        paragraphs = [
            Paragraph("First paragraph"),
            Paragraph("Second paragraph"),
            Paragraph("Third paragraph")
        ]
        
        page_count = estimator.estimate_page_count(paragraphs)
        
        assert page_count > 0
        assert isinstance(page_count, int)
    
    def test_refine_paragraph(self):
        """Test paragraph refinement."""
        estimator = HybridLayoutEstimator()
        paragraph = Paragraph("This is a test paragraph")
        
        refined_paragraph = estimator.refine_paragraph(paragraph)
        
        assert refined_paragraph is not None
        assert hasattr(refined_paragraph, 'estimated_lines')
    
    def test_adjust_estimator(self):
        """Test estimator adjustment."""
        estimator = HybridLayoutEstimator()
        paragraphs = [Paragraph("Test paragraph")]
        
        estimator.adjust_estimator(paragraphs)
        
        # Should not raise any exceptions
        assert True
    
    def test_paginate(self):
        """Test pagination."""
        estimator = HybridLayoutEstimator()
        paragraphs = [
            Paragraph("First paragraph"),
            Paragraph("Second paragraph"),
            Paragraph("Third paragraph")
        ]
        
        pages = estimator.paginate(paragraphs)
        
        assert pages is not None
        assert isinstance(pages, list)
        assert len(pages) > 0
    
    def test_fix_widows_and_orphans(self):
        """Test widow and orphan control."""
        estimator = HybridLayoutEstimator()
        pages = [Page(1), Page(2)]
        
        fixed_pages = estimator.fix_widows_and_orphans(pages)
        
        assert fixed_pages is not None
        assert isinstance(fixed_pages, list)
        assert len(fixed_pages) == len(pages)
    
    def test_layout_document(self):
        """Test document layout."""
        estimator = HybridLayoutEstimator()
        paragraphs = [
            Paragraph("First paragraph"),
            Paragraph("Second paragraph"),
            Paragraph("Third paragraph")
        ]
        
        layout_result = estimator.layout_document(paragraphs)
        
        assert layout_result is not None
        assert hasattr(layout_result, 'pages')
        assert hasattr(layout_result, 'total_pages')
        assert hasattr(layout_result, 'execution_time')
    
    def test_layout_document_performance(self):
        """Test document layout performance."""
        estimator = HybridLayoutEstimator()
        
        # Create a larger document for performance testing
        paragraphs = [Paragraph(f"Paragraph {i}") for i in range(100)]
        
        start_time = time.time()
        layout_result = estimator.layout_document(paragraphs)
        end_time = time.time()
        
        assert layout_result is not None
        assert end_time - start_time < 5.0  # Should complete within 5 seconds
    
    def test_empty_document(self):
        """Test layout with empty document."""
        estimator = HybridLayoutEstimator()
        paragraphs = []
        
        layout_result = estimator.layout_document(paragraphs)
        
        assert layout_result is not None
        assert layout_result.total_pages == 0
        assert len(layout_result.pages) == 0
    
    def test_single_paragraph(self):
        """Test layout with single paragraph."""
        estimator = HybridLayoutEstimator()
        paragraphs = [Paragraph("Single paragraph")]
        
        layout_result = estimator.layout_document(paragraphs)
        
        assert layout_result is not None
        assert layout_result.total_pages > 0
        assert len(layout_result.pages) > 0
    
    def test_very_long_paragraph(self):
        """Test layout with very long paragraph."""
        estimator = HybridLayoutEstimator()
        long_text = "This is a very long paragraph. " * 100
        paragraphs = [Paragraph(long_text)]
        
        layout_result = estimator.layout_document(paragraphs)
        
        assert layout_result is not None
        assert layout_result.total_pages > 0
        assert len(layout_result.pages) > 0
    
    def test_multiple_paragraphs(self):
        """Test layout with multiple paragraphs."""
        estimator = HybridLayoutEstimator()
        paragraphs = [
            Paragraph("First paragraph with some content"),
            Paragraph("Second paragraph with different content"),
            Paragraph("Third paragraph with even more content"),
            Paragraph("Fourth paragraph to test pagination"),
            Paragraph("Fifth paragraph for additional testing")
        ]
        
        layout_result = estimator.layout_document(paragraphs)
        
        assert layout_result is not None
        assert layout_result.total_pages > 0
        assert len(layout_result.pages) > 0
    
    def test_custom_page_geometry(self):
        """Test layout with custom page geometry."""
        page_geometry = PageGeometry(
            width_mm=150.0,  # Narrower page
            height_mm=200.0,  # Shorter page
            margin_top_mm=20.0,
            margin_bottom_mm=20.0,
            margin_left_mm=20.0,
            margin_right_mm=20.0
        )
        estimator = HybridLayoutEstimator(page_geometry)
        
        paragraphs = [Paragraph("Test paragraph")]
        layout_result = estimator.layout_document(paragraphs)
        
        assert layout_result is not None
        assert layout_result.total_pages > 0
    
    def test_custom_font_metrics(self):
        """Test layout with custom font metrics."""
        font_metrics = FontMetrics(
            font_family="Times New Roman",
            font_size_pt=16.0
        )
        estimator = HybridLayoutEstimator(font_metrics=font_metrics)
        
        paragraphs = [Paragraph("Test paragraph")]
        layout_result = estimator.layout_document(paragraphs)
        
        assert layout_result is not None
        assert layout_result.total_pages > 0
    
    def test_error_handling(self):
        """Test error handling in layout estimator."""
        estimator = HybridLayoutEstimator()
        
        # Test with None paragraphs
        with pytest.raises((TypeError, AttributeError)):
            estimator.layout_document(None)
        
        # Test with invalid paragraph
        with pytest.raises((TypeError, AttributeError)):
            estimator.layout_document([None])
    
    def test_memory_usage(self):
        """Test memory usage with large document."""
        estimator = HybridLayoutEstimator()
        
        # Create a large document
        paragraphs = [Paragraph(f"Paragraph {i} with some content") for i in range(1000)]
        
        layout_result = estimator.layout_document(paragraphs)
        
        assert layout_result is not None
        assert layout_result.total_pages > 0
        assert len(layout_result.pages) > 0
