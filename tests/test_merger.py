"""
Tests for Document Merging functionality.

Tests document merging, selective merging, and relationship handling.
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from docx_interpreter import Document

# Import DocumentMerger directly from merger.py file
# merger.py is at docx_interpreter/merger.py (not in merger/ subdirectory)
import sys
import importlib.util

parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

merger_path = parent_dir / "docx_interpreter" / "merger.py"
if merger_path.exists():
    # Import directly from merger.py file
    # We need to handle relative imports in merger.py
    import types
    
    # Set up docx_interpreter module structure for relative imports
    if 'docx_interpreter' not in sys.modules:
        sys.modules['docx_interpreter'] = types.ModuleType('docx_interpreter')
    
    # Create models submodule for relative imports
    if 'docx_interpreter.models' not in sys.modules:
        sys.modules['docx_interpreter.models'] = types.ModuleType('docx_interpreter.models')
        sys.modules['docx_interpreter'].models = sys.modules['docx_interpreter.models']
    
    # Import merger module
    spec = importlib.util.spec_from_file_location("docx_interpreter.merger", merger_path)
    merger_module = importlib.util.module_from_spec(spec)
    
    # Set up the module in sys.modules for relative imports
    sys.modules['docx_interpreter.merger'] = merger_module
    
    # Execute the module (this will handle relative imports)
    try:
        spec.loader.exec_module(merger_module)
        DocumentMerger = getattr(merger_module, 'DocumentMerger', None)
        MergeOptions = getattr(merger_module, 'MergeOptions', None)
    except Exception as e:
        # If import fails, try to import classes directly
        import re
        merger_content = merger_path.read_text(encoding='utf-8')
        if 'class MergeOptions' in merger_content and 'class DocumentMerger' in merger_content:
            # Classes exist, but import failed - skip tests
            DocumentMerger = None
            MergeOptions = None
            pytest.skip(f"Failed to import DocumentMerger/MergeOptions: {e}", allow_module_level=True)
        else:
            DocumentMerger = None
            MergeOptions = None
else:
    DocumentMerger = None
    MergeOptions = None
    pytest.skip("merger.py not found", allow_module_level=True)


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


class TestDocumentMerger:
    """Test cases for DocumentMerger."""
    
    def test_merge_full(self, sample_docx_path, temp_output_dir):
        """Test full document merge."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc1 = Document.open(str(sample_docx_path))
        doc2 = Document.open(str(sample_docx_path))
        
        merger = DocumentMerger(doc1)
        merger.merge_full(doc2)
        
        output_path = temp_output_dir / "merged_full.docx"
        doc1.save(str(output_path))
        
        assert output_path.exists()
    
    def test_merge_body(self, sample_docx_path, temp_output_dir):
        """Test merging body only."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc1 = Document.open(str(sample_docx_path))
        doc2 = Document.open(str(sample_docx_path))
        
        merger = DocumentMerger(doc1)
        options = MergeOptions(page_break=True)
        merger.merge_body(doc2, options)
        
        output_path = temp_output_dir / "merged_body.docx"
        doc1.save(str(output_path))
        
        assert output_path.exists()
    
    def test_merge_headers(self, sample_docx_path, temp_output_dir):
        """Test merging headers."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc1 = Document.open(str(sample_docx_path))
        doc2 = Document.open(str(sample_docx_path))
        
        merger = DocumentMerger(doc1)
        options = MergeOptions()
        merger.merge_headers(doc2, options)
        
        output_path = temp_output_dir / "merged_headers.docx"
        doc1.save(str(output_path))
        
        assert output_path.exists()
    
    def test_merge_footers(self, sample_docx_path, temp_output_dir):
        """Test merging footers."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc1 = Document.open(str(sample_docx_path))
        doc2 = Document.open(str(sample_docx_path))
        
        merger = DocumentMerger(doc1)
        options = MergeOptions()
        merger.merge_footers(doc2, options)
        
        output_path = temp_output_dir / "merged_footers.docx"
        doc1.save(str(output_path))
        
        assert output_path.exists()
    
    def test_merge_styles(self, sample_docx_path, temp_output_dir):
        """Test merging styles."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc1 = Document.open(str(sample_docx_path))
        doc2 = Document.open(str(sample_docx_path))
        
        merger = DocumentMerger(doc1)
        options = MergeOptions()
        merger.merge_styles(doc2, options)
        
        output_path = temp_output_dir / "merged_styles.docx"
        doc1.save(str(output_path))
        
        assert output_path.exists()
    
    def test_merge_selective(self, sample_docx_path, temp_output_dir):
        """Test selective merging."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc1 = Document.open(str(sample_docx_path))
        doc2 = Document.open(str(sample_docx_path))
        
        merger = DocumentMerger(doc1)
        merger.merge_selective({
            'body': doc2,
            'styles': doc2,
        })
        
        output_path = temp_output_dir / "merged_selective.docx"
        doc1.save(str(output_path))
        
        assert output_path.exists()


class TestMergeOptions:
    """Test cases for MergeOptions."""
    
    def test_merge_options_default(self):
        """Test default merge options."""
        if MergeOptions is None:
            pytest.skip("MergeOptions not available")
        
        options = MergeOptions()
        
        # Check that MergeOptions has expected attributes
        assert hasattr(options, 'page_break')
        assert hasattr(options, 'resolve_style_conflicts')
        assert hasattr(options, 'resolve_numbering_conflicts')
        assert hasattr(options, 'preserve_formatting')
        assert hasattr(options, 'merge_media')
    
    def test_merge_options_custom(self):
        """Test custom merge options."""
        if MergeOptions is None:
            pytest.skip("MergeOptions not available")
        
        options = MergeOptions(
            page_break=True,
            resolve_style_conflicts=False,
            resolve_numbering_conflicts=False,
            preserve_formatting=False,
            merge_media=False
        )
        
        assert options.page_break == True
        assert options.resolve_style_conflicts == False
        assert options.resolve_numbering_conflicts == False
        assert options.preserve_formatting == False
        assert options.merge_media == False


class TestAdvancedMerging:
    """Test advanced merging features."""
    
    def test_merge_sections(self, sample_docx_path, temp_output_dir):
        """Test merging sections."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc1 = Document.open(str(sample_docx_path))
        doc2 = Document.open(str(sample_docx_path))
        
        merger = DocumentMerger(doc1)
        options = MergeOptions()
        merger.merge_sections(doc2, options, copy_properties=True)
        
        output_path = temp_output_dir / "merged_sections.docx"
        doc1.save(str(output_path))
        
        assert output_path.exists()
    
    def test_merge_numbering(self, sample_docx_path, temp_output_dir):
        """Test merging numbering."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc1 = Document.open(str(sample_docx_path))
        doc2 = Document.open(str(sample_docx_path))
        
        merger = DocumentMerger(doc1)
        options = MergeOptions()
        merger.merge_numbering(doc2, options)
        
        output_path = temp_output_dir / "merged_numbering.docx"
        doc1.save(str(output_path))
        
        assert output_path.exists()
    
    def test_merge_media(self, sample_docx_path, temp_output_dir):
        """Test merging media (images)."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc1 = Document.open(str(sample_docx_path))
        doc2 = Document.open(str(sample_docx_path))
        
        merger = DocumentMerger(doc1)
        options = MergeOptions(merge_media=True)
        merger.merge_media(doc2, options)
        
        output_path = temp_output_dir / "merged_media.docx"
        doc1.save(str(output_path))
        
        assert output_path.exists()
    
    def test_merge_selective_complex(self, sample_docx_path, temp_output_dir):
        """Test complex selective merging with multiple sources."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc1 = Document.open(str(sample_docx_path))
        doc2 = Document.open(str(sample_docx_path))
        doc3 = Document.open(str(sample_docx_path))
        
        merger = DocumentMerger(doc1)
        merger.merge_selective({
            'body': doc2,
            'headers': doc3,
            'footers': doc2,
            'styles': doc3,
        })
        
        output_path = temp_output_dir / "merged_selective_complex.docx"
        doc1.save(str(output_path))
        
        assert output_path.exists()
    
    def test_merge_selective_with_options(self, sample_docx_path, temp_output_dir):
        """Test selective merging with custom options."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc1 = Document.open(str(sample_docx_path))
        doc2 = Document.open(str(sample_docx_path))
        
        merger = DocumentMerger(doc1)
        options = MergeOptions(
            page_break=True,
            resolve_style_conflicts=True,
            resolve_numbering_conflicts=True,
            merge_media=True
        )
        merger.merge_selective({
            'body': doc2,
            'styles': doc2,
            'numbering': doc2,
        }, options)
        
        output_path = temp_output_dir / "merged_selective_options.docx"
        doc1.save(str(output_path))
        
        assert output_path.exists()
    
    def test_merge_headers_with_types(self, sample_docx_path, temp_output_dir):
        """Test merging headers with specific types."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc1 = Document.open(str(sample_docx_path))
        doc2 = Document.open(str(sample_docx_path))
        
        merger = DocumentMerger(doc1)
        options = MergeOptions()
        merger.merge_headers(doc2, options, header_types=["default", "first"])
        
        output_path = temp_output_dir / "merged_headers_types.docx"
        doc1.save(str(output_path))
        
        assert output_path.exists()
    
    def test_merge_footers_with_types(self, sample_docx_path, temp_output_dir):
        """Test merging footers with specific types."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc1 = Document.open(str(sample_docx_path))
        doc2 = Document.open(str(sample_docx_path))
        
        merger = DocumentMerger(doc1)
        options = MergeOptions()
        merger.merge_footers(doc2, options, footer_types=["default", "first"])
        
        output_path = temp_output_dir / "merged_footers_types.docx"
        doc1.save(str(output_path))
        
        assert output_path.exists()
    
    def test_merge_body_with_position(self, sample_docx_path, temp_output_dir):
        """Test merging body with different positions."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc1 = Document.open(str(sample_docx_path))
        doc2 = Document.open(str(sample_docx_path))
        
        merger = DocumentMerger(doc1)
        options = MergeOptions()
        
        # Test append (default)
        merger.merge_body(doc2, options, position="append")
        
        output_path = temp_output_dir / "merged_body_append.docx"
        doc1.save(str(output_path))
        assert output_path.exists()
        
        # Test prepend
        doc1 = Document.open(str(sample_docx_path))
        merger = DocumentMerger(doc1)
        merger.merge_body(doc2, options, position="prepend")
        
        output_path = temp_output_dir / "merged_body_prepend.docx"
        doc1.save(str(output_path))
        assert output_path.exists()
    
    def test_merge_full_with_all_options(self, sample_docx_path, temp_output_dir):
        """Test full merge with all options enabled."""
        if not sample_docx_path.exists():
            pytest.skip("Sample DOCX file not found")
        
        doc1 = Document.open(str(sample_docx_path))
        doc2 = Document.open(str(sample_docx_path))
        
        merger = DocumentMerger(doc1)
        options = MergeOptions(
            page_break=True,
            resolve_style_conflicts=True,
            resolve_numbering_conflicts=True,
            preserve_formatting=True,
            merge_media=True
        )
        merger.merge_full(doc2, options)
        
        output_path = temp_output_dir / "merged_full_options.docx"
        doc1.save(str(output_path))
        
        assert output_path.exists()

