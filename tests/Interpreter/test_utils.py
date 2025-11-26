"""
Tests for utility functions.

This module contains unit tests for utility functionality.
"""

import pytest
from unittest.mock import Mock, patch
import tempfile
import os
from pathlib import Path

from docx_interpreter.utils.units import UnitsConverter as UnitConverter
from docx_interpreter.utils.xml_utils import XMLUtils
from docx_interpreter.utils.logger import get_logger, configure_logging
from docx_interpreter.utils.exceptions import (
    DocumentError, ParsingError, PackageError, RelationshipError,
    ValidationError, LayoutError, RenderError
)


class TestUnitConverter:
    """Test cases for UnitConverter class."""
    
    def test_init_with_defaults(self):
        """Test UnitConverter initialization with defaults."""
        converter = UnitConverter()
        
        assert converter is not None
        assert hasattr(converter, 'dpi')
        assert hasattr(converter, 'conversion_factors')
    
    def test_init_with_custom_dpi(self):
        """Test UnitConverter initialization with custom DPI."""
        converter = UnitConverter(dpi=300)
        
        assert converter.dpi == 300
    
    def test_convert_mm_to_pt(self):
        """Test converting millimeters to points."""
        converter = UnitConverter()
        
        # 1 mm = 2.834645669 points
        result = converter.convert(25.4, 'mm', 'pt')  # 1 inch in mm
        expected = 72.0  # 1 inch in points
        assert abs(result - expected) < 0.1
    
    def test_convert_pt_to_mm(self):
        """Test converting points to millimeters."""
        converter = UnitConverter()
        
        # 72 points = 25.4 mm (1 inch)
        result = converter.convert(72.0, 'pt', 'mm')
        expected = 25.4
        assert abs(result - expected) < 0.1
    
    def test_convert_px_to_pt(self):
        """Test converting pixels to points."""
        converter = UnitConverter(dpi=96)
        
        # 96 pixels = 72 points at 96 DPI
        result = converter.convert(96, 'px', 'pt')
        expected = 72.0
        assert abs(result - expected) < 0.1
    
    def test_convert_pt_to_px(self):
        """Test converting points to pixels."""
        converter = UnitConverter(dpi=96)
        
        # 72 points = 96 pixels at 96 DPI
        result = converter.convert(72.0, 'pt', 'px')
        expected = 96.0
        assert abs(result - expected) < 0.1
    
    def test_convert_emu_to_mm(self):
        """Test converting EMU to millimeters."""
        converter = UnitConverter()
        
        # 914400 EMU = 1 inch = 25.4 mm
        result = converter.convert(914400, 'emu', 'mm')
        expected = 25.4
        assert abs(result - expected) < 0.1
    
    def test_convert_twip_to_mm(self):
        """Test converting TWIP to millimeters."""
        converter = UnitConverter()
        
        # 1440 TWIP = 1 inch = 25.4 mm
        result = converter.convert(1440, 'twip', 'mm')
        expected = 25.4
        assert abs(result - expected) < 0.1
    
    def test_convert_invalid_units(self):
        """Test converting with invalid units."""
        converter = UnitConverter()
        
        with pytest.raises(ValueError):
            converter.convert(100, 'invalid', 'mm')
        
        with pytest.raises(ValueError):
            converter.convert(100, 'mm', 'invalid')
    
    def test_convert_same_units(self):
        """Test converting between same units."""
        converter = UnitConverter()
        
        result = converter.convert(100, 'mm', 'mm')
        assert result == 100.0
    
    def test_mm_to_pt(self):
        """Test mm_to_pt method."""
        converter = UnitConverter()
        
        result = converter.mm_to_pt(25.4)
        expected = 72.0
        assert abs(result - expected) < 0.1
    
    def test_pt_to_mm(self):
        """Test pt_to_mm method."""
        converter = UnitConverter()
        
        result = converter.pt_to_mm(72.0)
        expected = 25.4
        assert abs(result - expected) < 0.1
    
    def test_px_to_pt(self):
        """Test px_to_pt method."""
        converter = UnitConverter(dpi=96)
        
        result = converter.px_to_pt(96)
        expected = 72.0
        assert abs(result - expected) < 0.1
    
    def test_pt_to_px(self):
        """Test pt_to_px method."""
        converter = UnitConverter(dpi=96)
        
        result = converter.pt_to_px(72.0)
        expected = 96.0
        assert abs(result - expected) < 0.1


class TestXMLUtils:
    """Test cases for XMLUtils class."""
    
    def test_get_child_text(self):
        """Test getting child text from XML element."""
        import xml.etree.ElementTree as ET
        
        xml_content = """
        <root>
            <child>Sample text</child>
        </root>
        """
        root = ET.fromstring(xml_content)
        
        text = XMLUtils.get_child_text(root, 'child')
        assert text == "Sample text"
    
    def test_get_child_text_with_namespace(self):
        """Test getting child text with namespace."""
        import xml.etree.ElementTree as ET
        
        xml_content = """
        <root xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:child>Sample text</w:child>
        </root>
        """
        root = ET.fromstring(xml_content)
        
        text = XMLUtils.get_child_text(root, 'child', 'http://schemas.openxmlformats.org/wordprocessingml/2006/main')
        assert text == "Sample text"
    
    def test_get_child_text_nonexistent(self):
        """Test getting child text from nonexistent element."""
        import xml.etree.ElementTree as ET
        
        xml_content = "<root></root>"
        root = ET.fromstring(xml_content)
        
        text = XMLUtils.get_child_text(root, 'nonexistent')
        assert text is None
    
    def test_get_child_text_with_default(self):
        """Test getting child text with default value."""
        import xml.etree.ElementTree as ET
        
        xml_content = "<root></root>"
        root = ET.fromstring(xml_content)
        
        text = XMLUtils.get_child_text(root, 'nonexistent', default="Default text")
        assert text == "Default text"
    
    def test_get_attribute(self):
        """Test getting attribute from XML element."""
        import xml.etree.ElementTree as ET
        
        xml_content = '<root attr="value">Text</root>'
        root = ET.fromstring(xml_content)
        
        attr_value = XMLUtils.get_attribute(root, 'attr')
        assert attr_value == "value"
    
    def test_get_attribute_nonexistent(self):
        """Test getting nonexistent attribute."""
        import xml.etree.ElementTree as ET
        
        xml_content = '<root>Text</root>'
        root = ET.fromstring(xml_content)
        
        attr_value = XMLUtils.get_attribute(root, 'nonexistent')
        assert attr_value is None
    
    def test_get_attribute_with_default(self):
        """Test getting attribute with default value."""
        import xml.etree.ElementTree as ET
        
        xml_content = '<root>Text</root>'
        root = ET.fromstring(xml_content)
        
        attr_value = XMLUtils.get_attribute(root, 'nonexistent', default="default")
        assert attr_value == "default"
    
    def test_validate_xml(self):
        """Test XML validation."""
        import xml.etree.ElementTree as ET
        
        # Valid XML
        valid_xml = "<root><child>Text</child></root>"
        assert XMLUtils.validate_xml(valid_xml) == True
        
        # Invalid XML
        invalid_xml = "<root><child>Text</child>"
        assert XMLUtils.validate_xml(invalid_xml) == False
    
    def test_parse_xml(self):
        """Test XML parsing."""
        import xml.etree.ElementTree as ET
        
        xml_content = "<root><child>Text</child></root>"
        root = XMLUtils.parse_xml(xml_content)
        
        assert root is not None
        assert root.tag == "root"
        assert len(root) == 1
        assert root[0].tag == "child"
        assert root[0].text == "Text"
    
    def test_parse_xml_invalid(self):
        """Test parsing invalid XML."""
        import xml.etree.ElementTree as ET
        
        invalid_xml = "<root><child>Text</child>"
        
        with pytest.raises(ET.ParseError):
            XMLUtils.parse_xml(invalid_xml)
    
    def test_serialize_xml(self):
        """Test XML serialization."""
        import xml.etree.ElementTree as ET
        
        root = ET.Element("root")
        child = ET.SubElement(root, "child")
        child.text = "Text"
        
        xml_string = XMLUtils.serialize_xml(root)
        
        assert xml_string is not None
        assert "<root>" in xml_string
        assert "<child>Text</child>" in xml_string
        assert "</root>" in xml_string


class TestLogger:
    """Test cases for logger functionality."""
    
    def test_get_logger(self):
        """Test getting logger instance."""
        logger = get_logger("test_logger")
        
        assert logger is not None
        assert logger.name == "test_logger"
    
    def test_get_logger_same_name(self):
        """Test getting logger with same name returns same instance."""
        logger1 = get_logger("test_logger")
        logger2 = get_logger("test_logger")
        
        assert logger1 is logger2
    
    def test_configure_logging(self):
        """Test configuring logging."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = os.path.join(temp_dir, "test.log")
            
            configure_logging(
                level="DEBUG",
                log_file=log_file,
                max_file_size=1024,
                backup_count=3
            )
            
            logger = get_logger("test")
            logger.info("Test message")
            
            # Check if log file was created
            assert os.path.exists(log_file)
            
            # Check log content
            with open(log_file, 'r') as f:
                content = f.read()
            assert "Test message" in content
    
    def test_logger_levels(self):
        """Test logger levels."""
        logger = get_logger("test_levels")
        
        # Test different log levels
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")
        
        # Should not raise any exceptions
        assert True
    
    def test_logger_with_context(self):
        """Test logger with context."""
        logger = get_logger("test_context")
        
        # Test logging with context
        context = {"user": "test_user", "action": "test_action"}
        logger.info("Test message", extra=context)
        
        # Should not raise any exceptions
        assert True


class TestExceptions:
    """Test cases for custom exceptions."""
    
    def test_document_error(self):
        """Test DocumentError exception."""
        error = DocumentError("Test error message")
        
        assert str(error) == "DocumentError: Test error message"
        assert error.message == "Test error message"
        assert error.cause is None
        assert error.error_code is None
        assert error.details == {}
    
    def test_document_error_with_cause(self):
        """Test DocumentError with cause."""
        cause = ValueError("Original error")
        error = DocumentError("Test error message", cause=cause)
        
        assert error.cause == cause
        assert "Original error" in str(error.cause)
    
    def test_document_error_with_details(self):
        """Test DocumentError with details."""
        details = {"file": "test.docx", "line": 10}
        error = DocumentError("Test error message", details=details)
        
        assert error.details == details
    
    def test_parsing_error(self):
        """Test ParsingError exception."""
        error = ParsingError(
            "Parsing error",
            file_path="test.docx",
            line_number=10,
            column_number=5
        )
        
        assert error.file_path == "test.docx"
        assert error.line_number == 10
        assert error.column_number == 5
        
        error_info = error.get_error_info()
        assert error_info['file_path'] == "test.docx"
        assert error_info['line_number'] == 10
        assert error_info['column_number'] == 5
    
    def test_package_error(self):
        """Test PackageError exception."""
        error = PackageError(
            "Package error",
            package_path="test.docx",
            package_size=1024,
            package_format="docx"
        )
        
        assert error.package_path == "test.docx"
        assert error.package_size == 1024
        assert error.package_format == "docx"
    
    def test_relationship_error(self):
        """Test RelationshipError exception."""
        error = RelationshipError(
            "Relationship error",
            relationship_id="rId1",
            relationship_type="image",
            target_path="word/media/image1.jpg"
        )
        
        assert error.relationship_id == "rId1"
        assert error.relationship_type == "image"
        assert error.target_path == "word/media/image1.jpg"
    
    def test_validation_error(self):
        """Test ValidationError exception."""
        error = ValidationError(
            "Validation error",
            field_name="title",
            field_value="",
            validation_rule="required"
        )
        
        assert error.field_name == "title"
        assert error.field_value == ""
        assert error.validation_rule == "required"
    
    def test_layout_error(self):
        """Test LayoutError exception."""
        error = LayoutError(
            "Layout error",
            element_type="paragraph",
            element_id="p1",
            page_number=1
        )
        
        assert error.element_type == "paragraph"
        assert error.element_id == "p1"
        assert error.page_number == 1
    
    def test_render_error(self):
        """Test RenderError exception."""
        error = RenderError(
            "Render error",
            render_type="html",
            output_path="output.html",
            render_engine="HTMLRenderer"
        )
        
        assert error.render_type == "html"
        assert error.output_path == "output.html"
        assert error.render_engine == "HTMLRenderer"
    
    def test_exception_hierarchy(self):
        """Test exception hierarchy."""
        # All custom exceptions should inherit from DocumentError
        assert issubclass(ParsingError, DocumentError)
        assert issubclass(PackageError, DocumentError)
        assert issubclass(RelationshipError, DocumentError)
        assert issubclass(ValidationError, DocumentError)
        assert issubclass(LayoutError, DocumentError)
        assert issubclass(RenderError, DocumentError)
    
    def test_exception_chaining(self):
        """Test exception chaining."""
        original_error = ValueError("Original error")
        document_error = DocumentError("Document error", cause=original_error)
        
        assert document_error.cause == original_error
        assert str(original_error) in str(document_error.cause)
    
    def test_error_info(self):
        """Test error information extraction."""
        error = DocumentError(
            "Test error",
            error_code="ERR001",
            details={"key": "value"}
        )
        
        error_info = error.get_error_info()
        
        assert error_info['message'] == "Test error"
        assert error_info['error_code'] == "ERR001"
        assert error_info['details'] == {"key": "value"}
        assert 'traceback' in error_info
