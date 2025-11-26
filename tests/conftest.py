"""
Pytest configuration for DocQuill
"""

import pytest
import logging
import sys
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add packages to path for testing
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "packages" / "docquill_core"))


@pytest.fixture(autouse=True)
def configure_logging():
    """Configure logging for tests to avoid file handler issues."""
    # Clear all existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    # Set up console-only logging for tests
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)  # Only show warnings and errors during tests
    
    formatter = logging.Formatter(
        '%(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.WARNING)
    
    yield
    
    # Cleanup after test
    root_logger.handlers.clear()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    import tempfile
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_docx_path():
    """Path to sample DOCX file for testing."""
    # Try with space in filename first
    path = os.path.join(os.path.dirname(__file__), "files", "Zapytanie_Ofertowe test.docx")
    if not os.path.exists(path):
        # Fallback to underscore version
        path = os.path.join(os.path.dirname(__file__), "files", "Zapytanie_Ofertowe_test.docx")
    if not os.path.exists(path):
        # Fallback to original
        path = os.path.join(os.path.dirname(__file__), "files", "Zapytanie_Ofertowe.docx")
    return path


@pytest.fixture
def real_docx_path():
    """Path to real DOCX file for testing (alias for sample_docx_path)."""
    # Try with space in filename first
    path = os.path.join(os.path.dirname(__file__), "files", "Zapytanie_Ofertowe test.docx")
    if not os.path.exists(path):
        # Fallback to underscore version
        path = os.path.join(os.path.dirname(__file__), "files", "Zapytanie_Ofertowe_test.docx")
    if not os.path.exists(path):
        # Fallback to original
        path = os.path.join(os.path.dirname(__file__), "files", "Zapytanie_Ofertowe.docx")
    return path


@pytest.fixture
def mock_document():
    """Create mock document for testing exporters."""
    doc = Mock()
    
    # Metadata
    doc.metadata = Mock()
    doc.metadata.title = "Test Document"
    doc.metadata.author = "Test Author"
    doc.metadata.to_dict = Mock(return_value={
        'title': 'Test Document',
        'author': 'Test Author'
    })
    
    # Body and elements - create properly configured mock paragraph
    mock_paragraph = Mock()
    mock_paragraph.text = "Test paragraph"
    mock_paragraph.get_text = Mock(return_value="Test paragraph")
    mock_paragraph.to_dict = Mock(return_value={
        'type': 'paragraph',
        'text': 'Test paragraph'
    })
    # Configure runs as empty list (not Mock)
    mock_paragraph.runs = []
    mock_paragraph.style = None
    mock_paragraph.numbering = None
    mock_paragraph.children = []
    mock_paragraph.alignment = None
    mock_paragraph.borders = None
    mock_paragraph.background = None
    mock_paragraph.shadow = None
    mock_paragraph.spacing_before = None
    mock_paragraph.spacing_after = None
    mock_paragraph.left_indent = None
    mock_paragraph.right_indent = None
    # Make sure hasattr checks work properly
    del mock_paragraph.rows  # Remove auto-created 'rows' attribute
    del mock_paragraph.get_rows  # Remove auto-created 'get_rows' attribute
    del mock_paragraph.rel_id  # Remove auto-created 'rel_id' attribute
    
    doc.body = Mock()
    doc.body.children = [mock_paragraph]
    doc.body.paragraphs = [mock_paragraph]
    doc.body.tables = []
    doc.body.images = []
    
    # Methods - return actual lists, not Mocks
    doc.get_paragraphs = Mock(return_value=[mock_paragraph])
    doc.get_tables = Mock(return_value=[])
    doc.get_images = Mock(return_value=[])
    doc.get_text = Mock(return_value="Test paragraph")
    
    # Styles
    doc.styles = Mock()
    doc.styles.to_dict = Mock(return_value={})
    
    # Layout
    doc.layout = None
    
    # Placeholder values
    doc.placeholder_values = {}
    
    # Headers and footers
    doc.headers = []
    doc.footers = []
    doc.get_headers = Mock(return_value=[])
    doc.get_footers = Mock(return_value=[])
    
    # Footnotes and endnotes - must be dicts, not lists
    doc.footnotes = {}
    doc.endnotes = {}
    doc.get_footnotes = Mock(return_value={})
    doc.get_endnotes = Mock(return_value={})
    
    # Watermarks
    doc.watermarks = []
    doc.get_watermarks = Mock(return_value=[])
    
    # Package reader - set to None to avoid style parsing issues
    doc.package_reader = None
    
    # Pages - for layout export
    doc.pages = []
    
    # Sections - for layout export
    doc.sections = []
    
    # Elements - for content export
    doc.elements = [mock_paragraph]
    
    # Title - for text export
    doc.title = "Test Document"
    
    return doc


@pytest.fixture
def mock_paragraph():
    """Create mock paragraph for testing."""
    para = Mock()
    para.text = "Test paragraph text"
    para.get_text = Mock(return_value="Test paragraph text")
    para.runs = []
    para.style = None
    para.numbering = None
    para.properties = {}
    para.to_dict = Mock(return_value={
        'type': 'paragraph',
        'text': 'Test paragraph text'
    })
    return para


@pytest.fixture
def mock_run():
    """Create mock run for testing."""
    run = Mock()
    run.text = "Test run text"
    run.get_text = Mock(return_value="Test run text")
    run.bold = False
    run.italic = False
    run.underline = False
    run.font_size = None
    run.font_name = None
    run.font_color = None
    run.properties = {}
    return run


@pytest.fixture
def mock_table():
    """Create mock table for testing."""
    table = Mock()
    table.rows = []
    table.columns = []
    table.properties = {}
    table.to_dict = Mock(return_value={
        'type': 'table',
        'rows': []
    })
    return table


@pytest.fixture
def sample_zip_content():
    """Create sample ZIP content for testing PackageReader."""
    return {
        '[Content_Types].xml': '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
    <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
    <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>''',
        '_rels/.rels': '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
    <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
    <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>''',
        'word/document.xml': '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:body>
        <w:p>
            <w:r>
                <w:t>Test paragraph</w:t>
            </w:r>
        </w:p>
    </w:body>
</w:document>''',
        'word/_rels/document.xml.rels': '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
</Relationships>''',
        'docProps/core.xml': '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/">
    <dc:title>Test Document</dc:title>
    <dc:creator>Test Author</dc:creator>
    <cp:lastModifiedBy>Test Author</cp:lastModifiedBy>
    <dcterms:created>2025-01-01T00:00:00Z</dcterms:created>
    <dcterms:modified>2025-01-01T00:00:00Z</dcterms:modified>
</cp:coreProperties>''',
        'docProps/app.xml': '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
    <Application>Microsoft Office Word</Application>
    <Pages>1</Pages>
    <Words>2</Words>
</Properties>''',
        'docProps/custom.xml': '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties">
</Properties>''',
    }


@pytest.fixture
def mock_image():
    """Create mock image for testing."""
    image = Mock()
    image.src = "image.png"
    image.width = 100
    image.height = 100
    image.rel_id = "rId1"
    image.to_dict = Mock(return_value={
        'type': 'image',
        'src': 'image.png',
        'width': 100,
        'height': 100
    })
    return image


# Configure pytest to ignore logging errors
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end tests"
    )
    # Ignore logging errors during tests
    logging.raiseExceptions = False
