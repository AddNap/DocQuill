"""Tests for PDF compiler."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

from compiler import PdfCompiler, CompilerOptions
from compiler.compilation_context import CompilationContext
from docx_interpreter.engine import DocumentEngine
from docx_interpreter.engine.geometry import Size, Margins
from docx_interpreter.engine.base_engine import LayoutPage, LayoutBlock
from docx_interpreter.engine.geometry import Rect
from docx_interpreter.exceptions import CompilationError


class TestPdfCompiler:
    """Test suite for PdfCompiler."""

    def test_init_with_options(self, tmp_path):
        """Test PdfCompiler initialization with options."""
        output_path = tmp_path / "test.pdf"
        model = Mock()
        
        options = CompilerOptions(
            margins=(25, 25, 25, 25),
            page_size="A4",
            dpi=300,
            placeholder_values={"name": "Test"},
        )
        
        compiler = PdfCompiler(model, output_path, options)
        
        assert compiler.output_path == output_path
        assert compiler.options.margins == (25, 25, 25, 25)
        assert compiler.options.page_size == "A4"
        assert compiler.options.dpi == 300

    def test_init_with_dict_options(self, tmp_path):
        """Test PdfCompiler initialization with dict options."""
        output_path = tmp_path / "test.pdf"
        model = Mock()
        
        options = {
            "margins": (25, 25, 25, 25),
            "page_size": "A4",
            "dpi": 300,
        }
        
        compiler = PdfCompiler(model, output_path, options)
        
        assert compiler.options.margins == (25, 25, 25, 25)
        assert compiler.options.page_size == "A4"
        assert compiler.options.dpi == 300

    def test_init_with_external_engine(self, tmp_path):
        """Test PdfCompiler with external layout engine."""
        output_path = tmp_path / "test.pdf"
        model = Mock()
        engine = Mock(spec=DocumentEngine)
        
        compiler = PdfCompiler(model, output_path, layout_engine=engine)
        
        assert compiler._external_engine is engine

    def test_compile_pipeline(self, tmp_path):
        """Test full compilation pipeline."""
        output_path = tmp_path / "test.pdf"
        model = Mock()
        model._numbering = {}
        model._context = Mock()
        model._context.doc_defaults = {"paragraph": {}, "run": {}}
        model.placeholder_values = {}
        
        # Mock preprocessor
        processed_model = Mock()
        processed_model._numbering = {}
        processed_model._context = model._context
        processed_model.placeholder_values = {}
        
        # Mock layout engine
        layout_page = LayoutPage(
            number=1,
            size=Size(width=210.0, height=297.0),
            margins=Margins(top=25.4, right=25.4, bottom=25.4, left=25.4),
        )
        
        layout_block = LayoutBlock(
            frame=Rect(x=25.4, y=25.4, width=159.2, height=20.0),
            content={"text": "Test paragraph"},
            style={},
            block_type="paragraph",
        )
        layout_page.add_block(layout_block)
        
        engine = Mock(spec=DocumentEngine)
        engine.build_layout.return_value = [layout_page]
        
        with patch('compiler.pdf_compiler.Preprocessor') as mock_preprocessor:
            mock_preprocessor.return_value.process.return_value = processed_model
            
            compiler = PdfCompiler(model, output_path, layout_engine=engine)
            result = compiler.compile()
            
            assert result == output_path
            assert output_path.exists()

    def test_compile_error_handling(self, tmp_path):
        """Test error handling during compilation."""
        output_path = tmp_path / "test.pdf"
        model = Mock()
        
        engine = Mock(spec=DocumentEngine)
        engine.build_layout.side_effect = Exception("Layout error")
        
        compiler = PdfCompiler(model, output_path, layout_engine=engine)
        
        with pytest.raises(CompilationError) as exc_info:
            compiler.compile()
        
        assert "PDF compilation failed" in str(exc_info.value)

    def test_resolve_geometry_from_model(self, tmp_path):
        """Test geometry resolution from model."""
        output_path = tmp_path / "test.pdf"
        model = Mock()
        
        size = Size(width=210.0, height=297.0)
        margins = Margins(top=25.4, right=25.4, bottom=25.4, left=25.4)
        model._determine_page_geometry.return_value = (size, margins)
        
        compiler = PdfCompiler(model, output_path)
        geometry = compiler._resolve_geometry(model)
        
        assert geometry[0] == size
        assert geometry[1] == margins

    def test_resolve_geometry_from_options(self, tmp_path):
        """Test geometry resolution from options."""
        output_path = tmp_path / "test.pdf"
        model = Mock()
        
        options = CompilerOptions(
            page_size="Letter",
            margins=(20, 20, 20, 20),
        )
        
        compiler = PdfCompiler(model, output_path, options)
        size, margins = compiler._resolve_geometry(model)
        
        assert size.width > 0
        assert size.height > 0
        assert margins.top == 20.0

    def test_coerce_size(self, tmp_path):
        """Test size coercion."""
        output_path = tmp_path / "test.pdf"
        
        # Test with Size object
        size = Size(width=210.0, height=297.0)
        result = PdfCompiler._coerce_size(size)
        assert result == size
        
        # Test with tuple
        result = PdfCompiler._coerce_size((210.0, 297.0))
        assert result is not None
        assert result.width == 210.0
        assert result.height == 297.0
        
        # Test with invalid input
        result = PdfCompiler._coerce_size("invalid")
        assert result is None

    def test_coerce_margins(self, tmp_path):
        """Test margins coercion."""
        output_path = tmp_path / "test.pdf"
        
        # Test with Margins object
        margins = Margins(top=25.4, right=25.4, bottom=25.4, left=25.4)
        result = PdfCompiler._coerce_margins(margins)
        assert result == margins
        
        # Test with tuple
        result = PdfCompiler._coerce_margins((25.4, 25.4, 25.4, 25.4))
        assert result is not None
        assert result.top == 25.4
        
        # Test with invalid input
        result = PdfCompiler._coerce_margins("invalid")
        assert result is None


class TestCompilerOptions:
    """Test suite for CompilerOptions."""

    def test_default_options(self):
        """Test default options."""
        options = CompilerOptions()
        
        assert options.margins is None
        assert options.page_size is None
        assert options.dpi is None
        assert options.placeholder_values is None
        assert options.renderer is None

    def test_custom_options(self):
        """Test custom options."""
        options = CompilerOptions(
            margins=(25, 25, 25, 25),
            page_size="A4",
            dpi=300,
            placeholder_values={"name": "Test"},
            renderer="reportlab",
        )
        
        assert options.margins == (25, 25, 25, 25)
        assert options.page_size == "A4"
        assert options.dpi == 300
        assert options.placeholder_values == {"name": "Test"}
        assert options.renderer == "reportlab"

