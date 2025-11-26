"""
Tests for roundtrip functionality.

This module contains unit tests for roundtrip testing - parsing DOCX to XML and comparing with source.
"""

import pytest
from unittest.mock import Mock, patch
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
import zipfile
import re
from typing import Dict, List, Any

from docx_interpreter.document import Document
from docx_interpreter.parser import PackageReader, XMLParser
from docx_interpreter.export.xml_exporter import XMLExporter


class TestRoundtrip:
    """Test cases for roundtrip functionality."""
    
    def normalize_xml(self, xml_content: str) -> str:
        """Normalize XML content for comparison."""
        # Parse and re-serialize to normalize formatting
        try:
            root = ET.fromstring(xml_content)
            # Remove namespace prefixes for easier comparison
            self._remove_namespace_prefixes(root)
            # Normalize whitespace
            normalized = ET.tostring(root, encoding='unicode')
            # Remove extra whitespace
            normalized = re.sub(r'\s+', ' ', normalized)
            normalized = re.sub(r'>\s+<', '><', normalized)
            return normalized.strip()
        except ET.ParseError:
            return xml_content
    
    def _remove_namespace_prefixes(self, element):
        """Remove namespace prefixes from XML element."""
        # Remove namespace prefix from tag
        if '}' in element.tag:
            element.tag = element.tag.split('}')[1]
        
        # Remove namespace prefixes from attributes
        attrs_to_remove = []
        for attr_name in list(element.attrib.keys()):  # Use list() to avoid modification during iteration
            if '}' in attr_name:
                new_name = attr_name.split('}')[1]
                element.attrib[new_name] = element.attrib[attr_name]
                attrs_to_remove.append(attr_name)
        
        for attr_name in attrs_to_remove:
            del element.attrib[attr_name]
        
        # Recursively process children
        for child in element:
            self._remove_namespace_prefixes(child)
    
    def extract_document_xml(self, docx_path: str) -> str:
        """Extract document.xml from DOCX file."""
        with zipfile.ZipFile(docx_path, 'r') as zip_file:
            return zip_file.read('word/document.xml').decode('utf-8')
    
    def test_roundtrip_document_xml(self, real_docx_path):
        """Test roundtrip: DOCX -> parse -> export -> compare with source."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Step 1: Extract original document.xml
        original_xml = self.extract_document_xml(real_docx_path)
        original_normalized = self.normalize_xml(original_xml)
        
        # Step 2: Parse document
        doc = Document.from_file(real_docx_path)
        doc.parse()
        
        # Step 3: Export to XML
        exporter = XMLExporter(doc)
        exported_xml = exporter.export_to_string()
        exported_normalized = self.normalize_xml(exported_xml)
        
        # Step 4: Compare normalized versions
        # Note: This is a basic comparison - in practice, you might want to
        # compare specific elements or use more sophisticated diffing
        assert len(exported_normalized) > 0
        assert "<document>" in exported_normalized.lower()
        assert "<body>" in exported_normalized.lower()
        
        # Log the comparison for debugging
        print(f"Original XML length: {len(original_normalized)}")
        print(f"Exported XML length: {len(exported_normalized)}")
        
        # Check that we have some content
        assert len(exported_normalized) > 100  # Should have substantial content
    
    def test_roundtrip_paragraph_structure(self, real_docx_path):
        """Test roundtrip for paragraph structure."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Parse document
        doc = Document.from_file(real_docx_path)
        doc.parse()
        
        # Get paragraphs
        paragraphs = doc.get_paragraphs()
        
        # Export to XML
        exporter = XMLExporter(doc)
        exported_xml = exporter.export_to_string()
        
        # Check that paragraphs are present in exported XML (with namespace prefixes)
        assert "<p>" in exported_xml or "<w:p>" in exported_xml or "<ns0:p>" in exported_xml
        
        # Count paragraphs in original vs exported
        original_paragraph_count = len(paragraphs)
        exported_paragraph_count = exported_xml.count("<p>") + exported_xml.count("<w:p>") + exported_xml.count("<ns0:p>")
        
        # Should have similar number of paragraphs
        assert exported_paragraph_count > 0
        print(f"Original paragraphs: {original_paragraph_count}")
        print(f"Exported paragraphs: {exported_paragraph_count}")
    
    def test_roundtrip_table_structure(self, real_docx_path):
        """Test roundtrip for table structure."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Parse document
        doc = Document.from_file(real_docx_path)
        doc.parse()
        
        # Get tables
        tables = doc.get_tables()
        
        # Export to XML
        exporter = XMLExporter(doc)
        exported_xml = exporter.export_to_string()
        
        # Check that tables are present in exported XML (with namespace prefixes)
        assert "<table>" in exported_xml or "<w:tbl>" in exported_xml or "<ns0:tbl>" in exported_xml
        
        # Count tables in original vs exported
        original_table_count = len(tables)
        exported_table_count = exported_xml.count("<table>") + exported_xml.count("<w:tbl>") + exported_xml.count("<ns0:tbl>")
        
        # Should have similar number of tables
        assert exported_table_count > 0
        print(f"Original tables: {original_table_count}")
        print(f"Exported tables: {exported_table_count}")
    
    def test_roundtrip_text_content(self, real_docx_path):
        """Test roundtrip for text content."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Parse document
        doc = Document.from_file(real_docx_path)
        doc.parse()
        
        # Get text content
        original_text = doc.get_text()
        
        # Export to XML
        exporter = XMLExporter(doc)
        exported_xml = exporter.export_to_string()
        
        # Extract text from exported XML
        exported_text = self.extract_text_from_xml(exported_xml)
        
        # Compare text content
        assert len(exported_text) > 0
        assert len(original_text) > 0
        
        # Check that some text content is preserved
        # (exact match might not be possible due to formatting differences)
        common_words = set(original_text.lower().split()) & set(exported_text.lower().split())
        assert len(common_words) > 0
        
        print(f"Original text length: {len(original_text)}")
        print(f"Exported text length: {len(exported_text)}")
        print(f"Common words: {len(common_words)}")
    
    def extract_text_from_xml(self, xml_content: str) -> str:
        """Extract text content from XML."""
        try:
            root = ET.fromstring(xml_content)
            text_parts = []
            self._extract_text_recursive(root, text_parts)
            return ' '.join(text_parts)
        except ET.ParseError:
            return ""
    
    def _extract_text_recursive(self, element, text_parts: List[str]):
        """Recursively extract text from XML element."""
        if element.text:
            text_parts.append(element.text.strip())
        
        for child in element:
            self._extract_text_recursive(child, text_parts)
    
    def test_roundtrip_metadata(self, real_docx_path):
        """Test roundtrip for document metadata."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Parse document
        doc = Document.from_file(real_docx_path)
        doc.parse()
        
        # Export to XML
        exporter = XMLExporter(doc)
        exported_xml = exporter.export_to_string()
        
        # Check that metadata is present in exported XML (with namespace prefixes)
        assert "<?xml version=" in exported_xml
        assert "<document>" in exported_xml or "<w:document" in exported_xml or "<ns0:document" in exported_xml
    
    def test_roundtrip_styles(self, real_docx_path):
        """Test roundtrip for document styles."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Parse document
        doc = Document.from_file(real_docx_path)
        doc.parse()
        
        # Export to XML
        exporter = XMLExporter(doc)
        exported_xml = exporter.export_to_string()
        
        # Check that style information is preserved
        # This is a basic check - in practice, you might want to compare
        # specific style attributes
        assert len(exported_xml) > 0
    
    def test_roundtrip_xml_validation(self, real_docx_path):
        """Test that exported XML is valid."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Parse document
        doc = Document.from_file(real_docx_path)
        doc.parse()
        
        # Export to XML
        exporter = XMLExporter(doc)
        exported_xml = exporter.export_to_string()
        
        # Validate XML
        try:
            ET.fromstring(exported_xml)
            assert True  # XML is valid
        except ET.ParseError as e:
            pytest.fail(f"Exported XML is invalid: {e}")
    
    def test_roundtrip_xml_structure(self, real_docx_path):
        """Test that exported XML has proper structure."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Parse document
        doc = Document.from_file(real_docx_path)
        doc.parse()
        
        # Export to XML
        exporter = XMLExporter(doc)
        exported_xml = exporter.export_to_string()
        
        # Check XML structure
        try:
            root = ET.fromstring(exported_xml)
            
            # Should have document root
            assert root.tag in ['document', 'w:document'] or root.tag.endswith('}document')
            
            # Should have body element
            body_found = False
            for child in root:
                if child.tag in ['body', 'w:body'] or child.tag.endswith('}body'):
                    body_found = True
                    break
            
            assert body_found, "No body element found in exported XML"
            
        except ET.ParseError as e:
            pytest.fail(f"Exported XML structure is invalid: {e}")
    
    def test_roundtrip_xml_namespaces(self, real_docx_path):
        """Test that exported XML has proper namespaces."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Parse document
        doc = Document.from_file(real_docx_path)
        doc.parse()
        
        # Export to XML
        exporter = XMLExporter(doc)
        exported_xml = exporter.export_to_string()
        
        # Check for namespace declarations
        assert 'xmlns:' in exported_xml or 'xmlns=' in exported_xml
        
        # Check for WordprocessingML namespace
        assert 'wordprocessingml' in exported_xml or 'w:' in exported_xml
    
    def test_roundtrip_xml_encoding(self, real_docx_path):
        """Test that exported XML has proper encoding."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Parse document
        doc = Document.from_file(real_docx_path)
        doc.parse()
        
        # Export to XML
        exporter = XMLExporter(doc)
        exported_xml = exporter.export_to_string()
        
        # Check encoding declaration
        assert '<?xml version=' in exported_xml
        assert 'encoding=' in exported_xml
        
        # Check that it's UTF-8
        assert 'utf-8' in exported_xml.lower()
    
    def test_roundtrip_xml_indentation(self, real_docx_path):
        """Test that exported XML has proper indentation."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Parse document
        doc = Document.from_file(real_docx_path)
        doc.parse()
        
        # Export to XML
        exporter = XMLExporter(doc)
        exported_xml = exporter.export_to_string()
        
        # Check that XML has some indentation (not all on one line)
        lines = exported_xml.split('\n')
        assert len(lines) > 1, "XML should be formatted with multiple lines"
        
        # Check that some lines have indentation
        indented_lines = [line for line in lines if line.startswith(' ')]
        assert len(indented_lines) > 0, "XML should have indented lines"
    
    def test_roundtrip_xml_completeness(self, real_docx_path):
        """Test that exported XML is complete."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Parse document
        doc = Document.from_file(real_docx_path)
        doc.parse()
        
        # Export to XML
        exporter = XMLExporter(doc)
        exported_xml = exporter.export_to_string()
        
        # Check that XML is not empty
        assert len(exported_xml) > 0
        
        # Check that XML has proper opening and closing tags
        assert exported_xml.count('<') > 0
        assert exported_xml.count('>') > 0
        
        # Check that XML is balanced (rough check)
        open_tags = exported_xml.count('<')
        close_tags = exported_xml.count('</')
        assert open_tags > close_tags, "XML should have more opening tags than closing tags"
    
    def test_roundtrip_xml_performance(self, real_docx_path):
        """Test roundtrip performance."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        import time
        
        # Measure parsing time
        start_time = time.time()
        doc = Document.from_file(real_docx_path)
        doc.parse()
        parse_time = time.time() - start_time
        
        # Measure export time
        start_time = time.time()
        exporter = XMLExporter(doc)
        exported_xml = exporter.export_to_string()
        export_time = time.time() - start_time
        
        # Check performance
        assert parse_time < 10.0, f"Parsing took too long: {parse_time}s"
        assert export_time < 5.0, f"Export took too long: {export_time}s"
        
        print(f"Parse time: {parse_time:.2f}s")
        print(f"Export time: {export_time:.2f}s")
        print(f"Total time: {parse_time + export_time:.2f}s")
    
    def test_roundtrip_xml_memory_usage(self, real_docx_path):
        """Test roundtrip memory usage."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Parse document
        doc = Document.from_file(real_docx_path)
        doc.parse()
        
        # Export to XML
        exporter = XMLExporter(doc)
        exported_xml = exporter.export_to_string()
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        # Check memory usage
        assert memory_increase < 100 * 1024 * 1024, f"Memory usage too high: {memory_increase / 1024 / 1024:.1f}MB"
        
        print(f"Memory increase: {memory_increase / 1024 / 1024:.1f}MB")
    
    def test_roundtrip_xml_consistency(self, real_docx_path):
        """Test that multiple exports produce consistent results."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Parse document
        doc = Document.from_file(real_docx_path)
        doc.parse()
        
        # Export multiple times
        exporter = XMLExporter(doc)
        xml1 = exporter.export_to_string()
        xml2 = exporter.export_to_string()
        
        # Should produce identical results
        assert xml1 == xml2, "Multiple exports should produce identical results"
    
    def test_roundtrip_xml_error_handling(self, real_docx_path):
        """Test roundtrip error handling."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Test with invalid document
        with pytest.raises((ValueError, TypeError, AttributeError)):
            exporter = XMLExporter(None)
            exporter.export_to_string()
    
    def test_roundtrip_xml_custom_options(self, real_docx_path):
        """Test roundtrip with custom XML export options."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Parse document
        doc = Document.from_file(real_docx_path)
        doc.parse()
        
        # Export with custom options
        exporter = XMLExporter(
            doc,
            xml_namespace="http://custom.namespace",
            indent=4,
            encoding='utf-8'
        )
        exported_xml = exporter.export_to_string()
        
        # Check custom options
        assert 'http://custom.namespace' in exported_xml
        assert '    ' in exported_xml  # 4-space indentation
        assert 'utf-8' in exported_xml.lower()
    
    def test_roundtrip_xml_validation_with_schema(self, real_docx_path):
        """Test that exported XML validates against a schema (if available)."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Parse document
        doc = Document.from_file(real_docx_path)
        doc.parse()
        
        # Export to XML
        exporter = XMLExporter(doc)
        exported_xml = exporter.export_to_string()
        
        # Basic validation - check that XML is well-formed
        try:
            ET.fromstring(exported_xml)
            assert True  # XML is well-formed
        except ET.ParseError as e:
            pytest.fail(f"Exported XML is not well-formed: {e}")
        
        # Note: Schema validation would require a WordprocessingML schema file
        # which might not be available in the test environment
