"""
Pytest configuration for DocQuill
"""

import pytest
import logging
import sys
import os


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
        yield temp_dir


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
    """Create mock document for testing."""
    from unittest.mock import Mock
    doc = Mock()
    doc.metadata = Mock()
    doc.metadata.title = "Test Document"
    doc.get_paragraphs = Mock(return_value=[])
    doc.get_text = Mock(return_value="")
    doc.placeholder_values = {}
    return doc


# Configure pytest to ignore logging errors
def pytest_configure(config):
    """Configure pytest."""
    # Ignore logging errors during tests
    logging.raiseExceptions = False


# Add custom markers
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
