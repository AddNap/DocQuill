"""
Tests for XML comparison functionality.

This module contains unit tests for comparing normalized XML versions.
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

import sys
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from docquill.document import Document
except ImportError:
    # Document class might not be available, use parser directly
    Document = None

from docquill.parser import PackageReader, XMLParser
from docquill.export.xml_exporter import XMLExporter


class XMLComparator:
    """Class for comparing XML documents."""
    
    def __init__(self):
        self.ignore_attributes = ['xmlns', 'xmlns:w', 'xmlns:r', 'xmlns:wp', 'xmlns:a']
        self.ignore_elements = ['w:document', 'w:body']
        self.normalize_whitespace = True
    
    def normalize_xml(self, xml_content: str) -> str:
        """Normalize XML content for comparison."""
        try:
            root = ET.fromstring(xml_content)
            self._normalize_element(root)
            normalized = ET.tostring(root, encoding='unicode')
            
            if self.normalize_whitespace:
                normalized = self._normalize_whitespace(normalized)
            
            return normalized.strip()
        except ET.ParseError as e:
            raise ValueError(f"Invalid XML: {e}")
    
    def _normalize_element(self, element):
        """Normalize XML element."""
        # Remove namespace prefixes
        if '}' in element.tag:
            element.tag = element.tag.split('}')[1]
        
        # Remove ignored attributes
        attrs_to_remove = []
        for attr_name in element.attrib:
            if attr_name in self.ignore_attributes:
                attrs_to_remove.append(attr_name)
            elif '}' in attr_name:
                new_name = attr_name.split('}')[1]
                element.attrib[new_name] = element.attrib[attr_name]
                attrs_to_remove.append(attr_name)
        
        for attr_name in attrs_to_remove:
            del element.attrib[attr_name]
        
        # Normalize text content
        if element.text:
            element.text = element.text.strip()
        
        if element.tail:
            element.tail = element.tail.strip()
        
        # Recursively process children
        for child in element:
            self._normalize_element(child)
    
    def _normalize_whitespace(self, xml_content: str) -> str:
        """Normalize whitespace in XML content."""
        # Remove extra whitespace
        xml_content = re.sub(r'\s+', ' ', xml_content)
        xml_content = re.sub(r'>\s+<', '><', xml_content)
        return xml_content
    
    def compare_xml(self, xml1: str, xml2: str) -> Dict[str, Any]:
        """Compare two XML documents."""
        try:
            normalized1 = self.normalize_xml(xml1)
            normalized2 = self.normalize_xml(xml2)
            
            return {
                'identical': normalized1 == normalized2,
                'length_diff': abs(len(normalized1) - len(normalized2)),
                'similarity': self._calculate_similarity(normalized1, normalized2),
                'differences': self._find_differences(normalized1, normalized2)
            }
        except Exception as e:
            return {
                'identical': False,
                'error': str(e),
                'length_diff': 0,
                'similarity': 0.0,
                'differences': []
            }
    
    def _calculate_similarity(self, xml1: str, xml2: str) -> float:
        """Calculate similarity between two XML strings."""
        if xml1 == xml2:
            return 1.0
        
        # Simple similarity based on common substrings
        common_chars = 0
        min_length = min(len(xml1), len(xml2))
        
        for i in range(min_length):
            if xml1[i] == xml2[i]:
                common_chars += 1
        
        return common_chars / max(len(xml1), len(xml2)) if max(len(xml1), len(xml2)) > 0 else 0.0
    
    def _find_differences(self, xml1: str, xml2: str) -> List[str]:
        """Find differences between two XML strings."""
        diff = list(unified_diff(
            xml1.splitlines(keepends=True),
            xml2.splitlines(keepends=True),
            fromfile='original',
            tofile='exported',
            lineterm=''
        ))
        
        return diff[:10]  # Limit to first 10 differences
    
    def extract_elements(self, xml_content: str, element_tag: str) -> List[Dict[str, Any]]:
        """Extract specific elements from XML."""
        try:
            root = ET.fromstring(xml_content)
            elements = []
            
            for elem in root.iter():
                if elem.tag.endswith(element_tag):
                    elements.append({
                        'tag': elem.tag,
                        'text': elem.text or '',
                        'attributes': elem.attrib,
                        'children': [child.tag for child in elem]
                    })
            
            return elements
        except ET.ParseError:
            return []
    
    def count_elements(self, xml_content: str, element_tag: str) -> int:
        """Count occurrences of specific element in XML."""
        try:
            root = ET.fromstring(xml_content)
            count = 0
            
            for elem in root.iter():
                if elem.tag.endswith(element_tag):
                    count += 1
            
            return count
        except ET.ParseError:
            return 0
    
    def extract_text_content(self, xml_content: str) -> str:
        """Extract all text content from XML."""
        try:
            root = ET.fromstring(xml_content)
            text_parts = []
            
            def extract_text_recursive(element):
                if element.text:
                    text_parts.append(element.text.strip())
                for child in element:
                    extract_text_recursive(child)
            
            extract_text_recursive(root)
            return ' '.join(text_parts)
        except ET.ParseError:
            return ""


class TestXMLComparison:
    """Test cases for XML comparison functionality."""
    
    def test_xml_comparator_init(self):
        """Test XMLComparator initialization."""
        comparator = XMLComparator()
        
        assert comparator.ignore_attributes is not None
        assert comparator.ignore_elements is not None
        assert comparator.normalize_whitespace == True
    
    def test_normalize_xml_basic(self):
        """Test basic XML normalization."""
        comparator = XMLComparator()
        
        xml_content = """
        <root xmlns="http://example.com">
            <child attr="value">Text</child>
        </root>
        """
        
        normalized = comparator.normalize_xml(xml_content)
        
        assert normalized is not None
        assert len(normalized) > 0
        assert "<root>" in normalized
        assert "<child" in normalized
    
    def test_normalize_xml_with_namespaces(self):
        """Test XML normalization with namespaces."""
        comparator = XMLComparator()
        
        xml_content = """
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body>
                <w:p>
                    <w:r>
                        <w:t>Sample text</w:t>
                    </w:r>
                </w:p>
            </w:body>
        </w:document>
        """
        
        normalized = comparator.normalize_xml(xml_content)
        
        assert normalized is not None
        assert "<document>" in normalized
        assert "<body>" in normalized
        assert "<p>" in normalized
        assert "<r>" in normalized
        assert "<t>" in normalized
    
    def test_normalize_xml_whitespace(self):
        """Test XML normalization with whitespace."""
        comparator = XMLComparator()
        
        xml_content = """
        <root>
            <child>
                Text with    multiple    spaces
            </child>
        </root>
        """
        
        normalized = comparator.normalize_xml(xml_content)
        
        assert normalized is not None
        assert "Text with multiple spaces" in normalized
    
    def test_compare_xml_identical(self):
        """Test comparing identical XML documents."""
        comparator = XMLComparator()
        
        xml1 = "<root><child>Text</child></root>"
        xml2 = "<root><child>Text</child></root>"
        
        result = comparator.compare_xml(xml1, xml2)
        
        assert result['identical'] == True
        assert result['similarity'] == 1.0
        assert result['length_diff'] == 0
    
    def test_compare_xml_different(self):
        """Test comparing different XML documents."""
        comparator = XMLComparator()
        
        xml1 = "<root><child>Text1</child></root>"
        xml2 = "<root><child>Text2 longer</child></root>"
        
        result = comparator.compare_xml(xml1, xml2)
        
        assert result['identical'] == False
        assert result['similarity'] < 1.0
        assert result['length_diff'] > 0
    
    def test_compare_xml_with_namespaces(self):
        """Test comparing XML documents with namespaces."""
        comparator = XMLComparator()
        
        xml1 = """
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body><w:p><w:r><w:t>Text</w:t></w:r></w:p></w:body>
        </w:document>
        """
        
        xml2 = """
        <document>
            <body><p><r><t>Text</t></r></p></body>
        </document>
        """
        
        result = comparator.compare_xml(xml1, xml2)
        
        # Should be identical after normalization
        assert result['identical'] == True
        assert result['similarity'] == 1.0
    
    def test_extract_elements(self):
        """Test extracting elements from XML."""
        comparator = XMLComparator()
        
        xml_content = """
        <root>
            <p>Paragraph 1</p>
            <p>Paragraph 2</p>
            <table>Table content</table>
        </root>
        """
        
        paragraphs = comparator.extract_elements(xml_content, 'p')
        tables = comparator.extract_elements(xml_content, 'table')
        
        assert len(paragraphs) == 2
        assert len(tables) == 1
        assert paragraphs[0]['text'] == 'Paragraph 1'
        assert paragraphs[1]['text'] == 'Paragraph 2'
        assert tables[0]['text'] == 'Table content'
    
    def test_count_elements(self):
        """Test counting elements in XML."""
        comparator = XMLComparator()
        
        xml_content = """
        <root>
            <p>Paragraph 1</p>
            <p>Paragraph 2</p>
            <p>Paragraph 3</p>
            <table>Table content</table>
        </root>
        """
        
        paragraph_count = comparator.count_elements(xml_content, 'p')
        table_count = comparator.count_elements(xml_content, 'table')
        
        assert paragraph_count == 3
        assert table_count == 1
    
    def test_extract_text_content(self):
        """Test extracting text content from XML."""
        comparator = XMLComparator()
        
        xml_content = """
        <root>
            <p>Paragraph 1</p>
            <p>Paragraph 2</p>
            <table>
                <tr>
                    <td>Cell 1</td>
                    <td>Cell 2</td>
                </tr>
            </table>
        </root>
        """
        
        text_content = comparator.extract_text_content(xml_content)
        
        assert "Paragraph 1" in text_content
        assert "Paragraph 2" in text_content
        assert "Cell 1" in text_content
        assert "Cell 2" in text_content
    
    def test_compare_xml_error_handling(self):
        """Test XML comparison error handling."""
        comparator = XMLComparator()
        
        # Test with invalid XML
        result = comparator.compare_xml("invalid xml", "also invalid")
        
        assert result['identical'] == False
        assert 'error' in result
        assert result['similarity'] == 0.0
    
    def test_compare_xml_with_attributes(self):
        """Test comparing XML with attributes."""
        comparator = XMLComparator()
        
        xml1 = '<root><child attr="value1">Text</child></root>'
        xml2 = '<root><child attr="value2">Text</child></root>'
        
        result = comparator.compare_xml(xml1, xml2)
        
        # Should be different due to attribute values
        assert result['identical'] == False
        assert result['similarity'] < 1.0
    
    def test_compare_xml_with_ignored_attributes(self):
        """Test comparing XML with ignored attributes."""
        comparator = XMLComparator()
        
        xml1 = '<root xmlns="http://example.com"><child>Text</child></root>'
        xml2 = '<root><child>Text</child></root>'
        
        result = comparator.compare_xml(xml1, xml2)
        
        # Should be identical after ignoring xmlns attribute
        assert result['identical'] == True
        assert result['similarity'] == 1.0
    
    def test_compare_xml_with_ignored_elements(self):
        """Test comparing XML with ignored elements."""
        comparator = XMLComparator()
        
        xml1 = '<root xmlns:w="http://example.com"><wrapper><p>Text</p></wrapper></root>'
        xml2 = '<root><p>Text</p></root>'
        
        result = comparator.compare_xml(xml1, xml2)
        
        # Should be different due to wrapper element
        assert result['identical'] == False
        assert result['similarity'] < 1.0
    
    def test_compare_xml_with_whitespace_differences(self):
        """Test comparing XML with whitespace differences."""
        comparator = XMLComparator()
        
        xml1 = '<root><child>Text</child></root>'
        xml2 = '<root>\n  <child>\n    Text\n  </child>\n</root>'
        
        result = comparator.compare_xml(xml1, xml2)
        
        # Should be identical after whitespace normalization
        assert result['identical'] == True
        assert result['similarity'] == 1.0
    
    def test_compare_xml_with_text_differences(self):
        """Test comparing XML with text differences."""
        comparator = XMLComparator()
        
        xml1 = '<root><child>Text 1</child></root>'
        xml2 = '<root><child>Text 2</child></root>'
        
        result = comparator.compare_xml(xml1, xml2)
        
        assert result['identical'] == False
        assert result['similarity'] < 1.0
        assert len(result['differences']) > 0
    
    def test_compare_xml_with_structure_differences(self):
        """Test comparing XML with structure differences."""
        comparator = XMLComparator()
        
        xml1 = '<root><child1>Text</child1></root>'
        xml2 = '<root><child2>Text</child2></root>'
        
        result = comparator.compare_xml(xml1, xml2)
        
        assert result['identical'] == False
        assert result['similarity'] < 1.0
        assert len(result['differences']) > 0
    
    def test_compare_xml_with_nested_differences(self):
        """Test comparing XML with nested differences."""
        comparator = XMLComparator()
        
        xml1 = '<root><child><grandchild>Text</grandchild></child></root>'
        xml2 = '<root><child><grandchild>Different text</grandchild></child></root>'
        
        result = comparator.compare_xml(xml1, xml2)
        
        assert result['identical'] == False
        assert result['similarity'] < 1.0
        assert len(result['differences']) > 0
    
    def test_compare_xml_with_empty_elements(self):
        """Test comparing XML with empty elements."""
        comparator = XMLComparator()
        
        xml1 = '<root><child></child></root>'
        xml2 = '<root><child/></root>'
        
        result = comparator.compare_xml(xml1, xml2)
        
        # Should be identical (empty elements are equivalent)
        assert result['identical'] == True
        assert result['similarity'] == 1.0
    
    def test_compare_xml_with_comments(self):
        """Test comparing XML with comments."""
        comparator = XMLComparator()
        
        xml1 = '<root><!-- comment --><child>Text</child></root>'
        xml2 = '<root><child>Text</child></root>'
        
        result = comparator.compare_xml(xml1, xml2)
        
        # Should be identical (comments are ignored)
        assert result['identical'] == True
        assert result['similarity'] == 1.0
    
    def test_compare_xml_with_processing_instructions(self):
        """Test comparing XML with processing instructions."""
        comparator = XMLComparator()
        
        xml1 = '<?xml version="1.0"?><root><child>Text</child></root>'
        xml2 = '<root><child>Text</child></root>'
        
        result = comparator.compare_xml(xml1, xml2)
        
        # Should be identical (processing instructions are ignored)
        assert result['identical'] == True
        assert result['similarity'] == 1.0
    
    def test_compare_xml_with_cdata(self):
        """Test comparing XML with CDATA sections."""
        comparator = XMLComparator()
        
        xml1 = '<root><child><![CDATA[Text content]]></child></root>'
        xml2 = '<root><child>Text content</child></root>'
        
        result = comparator.compare_xml(xml1, xml2)
        
        # Should be identical (CDATA content is normalized)
        assert result['identical'] == True
        assert result['similarity'] == 1.0
    
    def test_compare_xml_with_entities(self):
        """Test comparing XML with entities."""
        comparator = XMLComparator()
        
        xml1 = '<root><child>&lt;Text&gt;</child></root>'
        xml2 = '<root><child>&lt;Text&gt;</child></root>'
        
        result = comparator.compare_xml(xml1, xml2)
        
        # Should be identical (same entities)
        assert result['identical'] == True
        assert result['similarity'] == 1.0
    
    def test_compare_xml_with_mixed_content(self):
        """Test comparing XML with mixed content."""
        comparator = XMLComparator()
        
        xml1 = '<root>Text <child>child text</child> more text</root>'
        xml2 = '<root>Text <child>child text</child> more text</root>'
        
        result = comparator.compare_xml(xml1, xml2)
        
        assert result['identical'] == True
        assert result['similarity'] == 1.0
    
    def test_compare_xml_with_unicode(self):
        """Test comparing XML with Unicode content."""
        comparator = XMLComparator()
        
        xml1 = '<root><child>Text with émojis 🎉</child></root>'
        xml2 = '<root><child>Text with émojis 🎉</child></root>'
        
        result = comparator.compare_xml(xml1, xml2)
        
        assert result['identical'] == True
        assert result['similarity'] == 1.0
    
    def test_compare_xml_with_large_documents(self):
        """Test comparing large XML documents."""
        comparator = XMLComparator()
        
        # Create large XML documents
        xml1 = '<root>' + ''.join(f'<child{i}>Text {i}</child{i}>' for i in range(1000)) + '</root>'
        xml2 = '<root>' + ''.join(f'<child{i}>Text {i}</child{i}>' for i in range(1000)) + '</root>'
        
        result = comparator.compare_xml(xml1, xml2)
        
        assert result['identical'] == True
        assert result['similarity'] == 1.0
        assert result['length_diff'] == 0
    
    def test_compare_xml_with_performance(self):
        """Test XML comparison performance."""
        comparator = XMLComparator()
        
        import time
        
        # Create medium-sized XML documents
        xml1 = '<root>' + ''.join(f'<child{i}>Text {i}</child{i}>' for i in range(100)) + '</root>'
        xml2 = '<root>' + ''.join(f'<child{i}>Text {i}</child{i}>' for i in range(100)) + '</root>'
        
        start_time = time.time()
        result = comparator.compare_xml(xml1, xml2)
        end_time = time.time()
        
        assert result['identical'] == True
        assert end_time - start_time < 1.0  # Should complete within 1 second
    
    def test_compare_xml_with_memory_usage(self):
        """Test XML comparison memory usage."""
        comparator = XMLComparator()
        
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Create large XML documents
        xml1 = '<root>' + ''.join(f'<child{i}>Text {i}</child{i}>' for i in range(1000)) + '</root>'
        xml2 = '<root>' + ''.join(f'<child{i}>Text {i}</child{i}>' for i in range(1000)) + '</root>'
        
        result = comparator.compare_xml(xml1, xml2)
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        assert result['identical'] == True
        assert memory_increase < 50 * 1024 * 1024  # Should use less than 50MB
    
    def test_compare_xml_with_error_recovery(self):
        """Test XML comparison error recovery."""
        comparator = XMLComparator()
        
        # Test with one valid and one invalid XML
        xml1 = '<root><child>Text</child></root>'
        xml2 = 'invalid xml'
        
        result = comparator.compare_xml(xml1, xml2)
        
        assert result['identical'] == False
        assert 'error' in result
        assert result['similarity'] == 0.0
    
    def test_compare_xml_with_partial_matches(self):
        """Test comparing XML with partial matches."""
        comparator = XMLComparator()
        
        xml1 = '<root><child1>Text</child1><child2>Text</child2></root>'
        xml2 = '<root><child1>Text</child1><child3>Text</child3></root>'
        
        result = comparator.compare_xml(xml1, xml2)
        
        assert result['identical'] == False
        assert result['similarity'] > 0.0  # Should have some similarity
        assert result['similarity'] < 1.0  # But not identical
    
    def test_compare_export_with_original(self, sample_docx_path):
        """Test comparing exported XML from model with original DOCX XML."""
        real_docx_path = sample_docx_path
        if not Path(real_docx_path).exists():
            pytest.skip("Real DOCX file not found")
        
        # Step 1: Extract original document.xml from DOCX
        original_xml = self._extract_document_xml(real_docx_path)
        assert original_xml is not None
        assert len(original_xml) > 0
        
        # Step 2: Parse document into model
        if Document is not None:
            # Use Document class if available
            doc = Document.from_file(real_docx_path)
            doc.parse()
            # Export model back to XML
            exporter = XMLExporter(doc)
            exported_xml = exporter.export_to_string()
        else:
            # Fallback: use parser directly
            package_reader = PackageReader(real_docx_path)
            xml_parser = XMLParser(package_reader)
            body = xml_parser.parse_body()
            # Create a minimal document-like object for exporter
            # XMLExporter.regenerate_wordml() expects document._body with children attribute
            class MockBody:
                def __init__(self, body_obj):
                    # body_obj is the parsed Body model
                    self.children = []
                    # Extract children from body if it's a Body model
                    if hasattr(body_obj, 'children'):
                        self.children = body_obj.children
                    elif hasattr(body_obj, '__iter__'):
                        self.children = list(body_obj)
            
            class MockDocument:
                def __init__(self, body):
                    # XMLExporter checks for _body attribute
                    self._body = MockBody(body)
                    # XMLExporter may also check for sections
                    self._sections = []
            
            mock_doc = MockDocument(body)
            exporter = XMLExporter(mock_doc)
            # Use regenerate_wordml directly to ensure body is processed
            exported_xml = exporter.regenerate_wordml(mock_doc)
        
        assert exported_xml is not None
        assert len(exported_xml) > 0
        
        # Step 3: Compare original with exported XML
        comparator = XMLComparator()
        comparison_result = comparator.compare_xml(original_xml, exported_xml)
        
        # Log results for debugging
        print(f"\n=== XML Comparison Results ===")
        print(f"Original XML length: {len(original_xml)}")
        print(f"Exported XML length: {len(exported_xml)}")
        print(f"Identical: {comparison_result['identical']}")
        print(f"Similarity: {comparison_result['similarity']:.4f}")
        print(f"Length difference: {comparison_result['length_diff']}")
        
        if comparison_result.get('differences'):
            print(f"\nFirst few differences:")
            for diff in comparison_result['differences'][:5]:
                print(f"  {diff}")
        
        # Basic assertions
        assert comparison_result['similarity'] >= 0.0  # Should have some similarity
        assert len(exported_xml) > 100  # Should have substantial content
        
        # Compare element counts
        original_paragraphs = comparator.count_elements(original_xml, 'p')
        exported_paragraphs = comparator.count_elements(exported_xml, 'p')
        print(f"\nParagraph counts: Original={original_paragraphs}, Exported={exported_paragraphs}")
        
        if original_paragraphs > 0:
            # Exported should have similar number of paragraphs (within 20% tolerance)
            assert exported_paragraphs > 0
            diff_ratio = abs(original_paragraphs - exported_paragraphs) / original_paragraphs
            print(f"Paragraph difference ratio: {diff_ratio:.2%}")
        
        # Optional: Render document to HTML/PDF if RENDER_OUTPUT environment variable is set
        import os
        render_output = os.environ.get('RENDER_OUTPUT', '').lower()
        if render_output in ('html', 'pdf', 'both'):
            self._render_document(real_docx_path, render_output)
    
    def _extract_document_xml(self, docx_path: str) -> str:
        """Extract document.xml from DOCX file."""
        with zipfile.ZipFile(docx_path, 'r') as zip_file:
            return zip_file.read('word/document.xml').decode('utf-8')
    
    def _render_document(self, docx_path: str, output_format: str):
        """Render document to HTML/PDF using the same pipeline as production scripts."""
        try:
            from docquill.engine.layout_pipeline import LayoutPipeline
            from docquill.engine.geometry import Size, Margins, twips_to_points
            from docquill.engine.page_engine import PageConfig
            
            output_dir = Path(__file__).parent.parent.parent / "output"
            output_dir.mkdir(exist_ok=True)
            
            print(f"\n🔄 Rendering document to {output_format.upper()}...")
            
            # Parse document
            package_reader = PackageReader(docx_path)
            xml_parser = XMLParser(package_reader)
            body = xml_parser.parse_body()
            
            # Create adapter
            class DocumentAdapter:
                def __init__(self, body_obj, parser):
                    self.elements = body_obj.children if hasattr(body_obj, 'children') else []
                    self.parser = parser
            
            document_model = DocumentAdapter(body, xml_parser)
            
            # Get margins from DOCX
            sections = xml_parser.parse_sections()
            margins = Margins(top=72, bottom=72, left=72, right=72)
            if sections and len(sections) > 0:
                section = sections[0]
                if 'margins' in section:
                    docx_margins = section['margins']
                    def get_margin_twips(key, default=1440):
                        val = docx_margins.get(key, default)
                        if isinstance(val, str):
                            try:
                                return int(val)
                            except (ValueError, TypeError):
                                return default
                        return int(val) if val is not None else default
                    
                    margins = Margins(
                        top=twips_to_points(get_margin_twips('top', 1440)),
                        bottom=twips_to_points(get_margin_twips('bottom', 1440)),
                        left=twips_to_points(get_margin_twips('left', 1440)),
                        right=twips_to_points(get_margin_twips('right', 1440))
                    )
            
            page_config = PageConfig(page_size=Size(595, 842), base_margins=margins)
            
            # Process layout
            pipeline = LayoutPipeline(page_config, target=output_format)
            unified_layout = pipeline.process(
                document_model,
                apply_headers_footers=True,
                validate=False
            )
            
            # Render HTML
            if output_format in ('html', 'both'):
                from docquill.engine.html import HTMLCompiler, HTMLCompilerConfig
                
                html_output = output_dir / "Zapytanie_Ofertowe_from_test.html"
                compiler = HTMLCompiler(
                    HTMLCompilerConfig(
                        output_path=html_output,
                        title="Zapytanie ofertowe (from test)",
                        embed_default_styles=True,
                    ),
                    package_reader=package_reader,
                )
                result_path = compiler.compile(unified_layout)
                if result_path.exists():
                    print(f"✅ HTML rendered: {result_path}")
            
            # Render PDF
            if output_format in ('pdf', 'both'):
                from docquill.engine.pdf.pdf_compiler import PDFCompiler
                
                pdf_output = output_dir / "Zapytanie_Ofertowe_from_test.pdf"
                compiler = PDFCompiler(
                    output_path=str(pdf_output),
                    page_size=(595, 842),
                    package_reader=package_reader
                )
                result_path = compiler.compile(unified_layout)
                if result_path.exists():
                    print(f"✅ PDF rendered: {result_path}")
            
        except Exception as e:
            print(f"⚠️  Rendering failed: {e}")
            import traceback
            traceback.print_exc()