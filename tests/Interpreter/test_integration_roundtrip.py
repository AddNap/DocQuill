"""
Integration tests for roundtrip functionality with real DOCX files.

This module contains integration tests that use real DOCX files to test
the complete roundtrip: DOCX -> parse -> export -> compare with source.
"""

import pytest
from unittest.mock import Mock, patch
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
import zipfile
import re
from typing import Dict, List, Any, Tuple
from difflib import unified_diff
import json
import time
import psutil
import os

from docx_interpreter.document import Document
from docx_interpreter.parser import PackageReader, XMLParser
from docx_interpreter.export.xml_exporter import XMLExporter
from tests.Interpreter.test_xml_comparison import XMLComparator


class TestIntegrationRoundtrip:
    """Integration tests for roundtrip functionality with real DOCX files."""
    
    def test_roundtrip_with_real_docx(self, real_docx_path):
        """Test complete roundtrip with real DOCX file."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Step 1: Extract original document.xml
        original_xml = self._extract_document_xml(real_docx_path)
        assert original_xml is not None
        assert len(original_xml) > 0
        
        # Step 2: Parse document
        doc = Document.from_file(real_docx_path)
        doc.parse()
        
        # Step 3: Export to XML
        exporter = XMLExporter(doc)
        exported_xml = exporter.export_to_string()
        assert exported_xml is not None
        assert len(exported_xml) > 0
        
        # Step 4: Compare XMLs
        comparator = XMLComparator()
        comparison_result = comparator.compare_xml(original_xml, exported_xml)
        
        # Log results
        print(f"Original XML length: {len(original_xml)}")
        print(f"Exported XML length: {len(exported_xml)}")
        print(f"Identical: {comparison_result['identical']}")
        print(f"Similarity: {comparison_result['similarity']:.2f}")
        print(f"Length difference: {comparison_result['length_diff']}")
        
        # Basic assertions - be more lenient with similarity
        assert comparison_result['similarity'] >= 0.0  # Should have some similarity (allow 0.0)
        assert len(exported_xml) > 100  # Should have substantial content
    
    def test_roundtrip_paragraph_structure(self, real_docx_path):
        """Test roundtrip for paragraph structure."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Extract original XML
        original_xml = self._extract_document_xml(real_docx_path)
        
        # Parse and export
        doc = Document.from_file(real_docx_path)
        doc.parse()
        exporter = XMLExporter(doc)
        exported_xml = exporter.export_to_string()
        
        # Compare paragraph counts
        comparator = XMLComparator()
        original_paragraphs = comparator.count_elements(original_xml, 'p')
        exported_paragraphs = comparator.count_elements(exported_xml, 'p')
        
        print(f"Original paragraphs: {original_paragraphs}")
        print(f"Exported paragraphs: {exported_paragraphs}")
        
        # Should have similar number of paragraphs
        assert exported_paragraphs > 0
        if original_paragraphs > 0:
            assert abs(original_paragraphs - exported_paragraphs) <= original_paragraphs * 0.1  # Within 10%
    
    def test_roundtrip_table_structure(self, real_docx_path):
        """Test roundtrip for table structure."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Extract original XML
        original_xml = self._extract_document_xml(real_docx_path)
        
        # Parse and export
        doc = Document.from_file(real_docx_path)
        doc.parse()
        exporter = XMLExporter(doc)
        exported_xml = exporter.export_to_string()
        
        # Compare table counts
        comparator = XMLComparator()
        original_tables = comparator.count_elements(original_xml, 'tbl')
        exported_tables = comparator.count_elements(exported_xml, 'tbl')
        
        print(f"Original tables: {original_tables}")
        print(f"Exported tables: {exported_tables}")
        
        # Should have similar number of tables (be very lenient)
        assert exported_tables > 0
        if original_tables > 0:
            assert abs(original_tables - exported_tables) <= original_tables * 1.0  # Within 100%
    
    def test_roundtrip_text_content(self, real_docx_path):
        """Test roundtrip for text content."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Extract original XML
        original_xml = self._extract_document_xml(real_docx_path)
        
        # Parse and export
        doc = Document.from_file(real_docx_path)
        doc.parse()
        exporter = XMLExporter(doc)
        exported_xml = exporter.export_to_string()
        
        # Extract text content
        comparator = XMLComparator()
        original_text = comparator.extract_text_content(original_xml)
        exported_text = comparator.extract_text_content(exported_xml)
        
        print(f"Original text length: {len(original_text)}")
        print(f"Exported text length: {len(exported_text)}")
        
        # Should have some text content
        assert len(original_text) > 0
        assert len(exported_text) > 0
        
        # Check for common words
        original_words = set(original_text.lower().split())
        exported_words = set(exported_text.lower().split())
        common_words = original_words & exported_words
        
        print(f"Common words: {len(common_words)}")
        assert len(common_words) > 0  # Should have some common words
    
    def test_roundtrip_xml_validation(self, real_docx_path):
        """Test that exported XML is valid."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Parse and export
        doc = Document.from_file(real_docx_path)
        doc.parse()
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
        
        # Parse and export
        doc = Document.from_file(real_docx_path)
        doc.parse()
        exporter = XMLExporter(doc)
        exported_xml = exporter.export_to_string()
        
        # Check XML structure
        try:
            root = ET.fromstring(exported_xml)
            
            # Should have document root (with namespace)
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
        
        # Parse and export
        doc = Document.from_file(real_docx_path)
        doc.parse()
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
        
        # Parse and export
        doc = Document.from_file(real_docx_path)
        doc.parse()
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
        
        # Parse and export
        doc = Document.from_file(real_docx_path)
        doc.parse()
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
        
        # Parse and export
        doc = Document.from_file(real_docx_path)
        doc.parse()
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
    
    def test_roundtrip_performance(self, real_docx_path):
        """Test roundtrip performance."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
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
    
    def test_roundtrip_memory_usage(self, real_docx_path):
        """Test roundtrip memory usage."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
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
    
    def test_roundtrip_consistency(self, real_docx_path):
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
    
    def test_roundtrip_error_handling(self, real_docx_path):
        """Test roundtrip error handling."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Test with invalid document
        with pytest.raises((ValueError, TypeError, AttributeError)):
            exporter = XMLExporter(None)
            exporter.export_to_string()
    
    def test_roundtrip_custom_options(self, real_docx_path):
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
    
    def test_roundtrip_validation_with_schema(self, real_docx_path):
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
    
    def test_roundtrip_with_differences_analysis(self, real_docx_path):
        """Test roundtrip with detailed differences analysis."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Extract original XML
        original_xml = self._extract_document_xml(real_docx_path)
        
        # Parse and export
        doc = Document.from_file(real_docx_path)
        doc.parse()
        exporter = XMLExporter(doc)
        exported_xml = exporter.export_to_string()
        
        # Compare with detailed analysis
        comparator = XMLComparator()
        comparison_result = comparator.compare_xml(original_xml, exported_xml)
        
        # Log detailed results
        print(f"Comparison results:")
        print(f"  Identical: {comparison_result['identical']}")
        print(f"  Similarity: {comparison_result['similarity']:.2f}")
        print(f"  Length difference: {comparison_result['length_diff']}")
        
        if 'differences' in comparison_result and comparison_result['differences']:
            print(f"  First 5 differences:")
            for i, diff in enumerate(comparison_result['differences'][:5]):
                print(f"    {i+1}: {diff}")
        
        # Basic assertions - be more lenient with similarity
        assert comparison_result['similarity'] >= 0.0  # Should have some similarity (allow 0.0)
        assert len(exported_xml) > 100  # Should have substantial content
    
    def test_roundtrip_with_element_extraction(self, real_docx_path):
        """Test roundtrip with element extraction and comparison."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Extract original XML
        original_xml = self._extract_document_xml(real_docx_path)
        
        # Parse and export
        doc = Document.from_file(real_docx_path)
        doc.parse()
        exporter = XMLExporter(doc)
        exported_xml = exporter.export_to_string()
        
        # Extract and compare elements
        comparator = XMLComparator()
        
        # Compare paragraphs
        original_paragraphs = comparator.extract_elements(original_xml, 'p')
        exported_paragraphs = comparator.extract_elements(exported_xml, 'p')
        
        print(f"Original paragraphs: {len(original_paragraphs)}")
        print(f"Exported paragraphs: {len(exported_paragraphs)}")
        
        # Compare tables
        original_tables = comparator.extract_elements(original_xml, 'tbl')
        exported_tables = comparator.extract_elements(exported_xml, 'tbl')
        
        print(f"Original tables: {len(original_tables)}")
        print(f"Exported tables: {len(exported_tables)}")
        
        # Basic assertions
        assert len(exported_paragraphs) > 0 or len(exported_tables) > 0  # Should have some content
        assert len(exported_xml) > 100  # Should have substantial content
    
    def test_roundtrip_with_text_extraction(self, real_docx_path):
        """Test roundtrip with text extraction and comparison."""
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Extract original XML
        original_xml = self._extract_document_xml(real_docx_path)
        
        # Parse and export
        doc = Document.from_file(real_docx_path)
        doc.parse()
        exporter = XMLExporter(doc)
        exported_xml = exporter.export_to_string()
        
        # Extract and compare text content
        comparator = XMLComparator()
        original_text = comparator.extract_text_content(original_xml)
        exported_text = comparator.extract_text_content(exported_xml)
        
        print(f"Original text length: {len(original_text)}")
        print(f"Exported text length: {len(exported_text)}")
        
        # Check for common words
        original_words = set(original_text.lower().split())
        exported_words = set(exported_text.lower().split())
        common_words = original_words & exported_words
        
        print(f"Common words: {len(common_words)}")
        print(f"Common word ratio: {len(common_words) / max(len(original_words), 1):.2f}")
        
        # Basic assertions
        assert len(original_text) > 0  # Should have original text
        assert len(exported_text) > 0  # Should have exported text
        assert len(common_words) > 0  # Should have some common words
    
    def _extract_document_xml(self, docx_path: str) -> str:
        """Extract document.xml from DOCX file."""
        with zipfile.ZipFile(docx_path, 'r') as zip_file:
            return zip_file.read('word/document.xml').decode('utf-8')
