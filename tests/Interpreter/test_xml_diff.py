"""
Tests for XML diff functionality.

This module contains unit tests for advanced XML diffing and comparison.
"""

import pytest
from unittest.mock import Mock, patch
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
import zipfile
import re
from typing import Dict, List, Any, Tuple
from difflib import unified_diff, SequenceMatcher
import json
import time
import psutil
import os

from docx_interpreter.document import Document
from docx_interpreter.parser import PackageReader, XMLParser
from docx_interpreter.export.xml_exporter import XMLExporter
from tests.Interpreter.test_xml_comparison import XMLComparator


class XMLDiffAnalyzer:
    """Advanced XML diff analyzer."""
    
    def __init__(self):
        self.comparator = XMLComparator()
        self.ignore_whitespace = True
        self.ignore_namespaces = True
        self.ignore_attributes = ['xmlns', 'xmlns:w', 'xmlns:r', 'xmlns:wp', 'xmlns:a']
        self.ignore_elements = ['w:document', 'w:body']
    
    def analyze_differences(self, xml1: str, xml2: str) -> Dict[str, Any]:
        """Analyze differences between two XML documents."""
        try:
            # Normalize both XMLs
            normalized1 = self.comparator.normalize_xml(xml1)
            normalized2 = self.comparator.normalize_xml(xml2)
            
            # Basic comparison
            basic_result = self.comparator.compare_xml(xml1, xml2)
            
            # Advanced analysis
            advanced_result = self._analyze_advanced_differences(normalized1, normalized2)
            
            # Combine results
            result = {
                **basic_result,
                'advanced_analysis': advanced_result,
                'summary': self._generate_summary(basic_result, advanced_result)
            }
            
            return result
            
        except Exception as e:
            return {
                'identical': False,
                'error': str(e),
                'similarity': 0.0,
                'length_diff': 0,
                'differences': [],
                'advanced_analysis': {},
                'summary': f"Error analyzing differences: {e}"
            }
    
    def _analyze_advanced_differences(self, xml1: str, xml2: str) -> Dict[str, Any]:
        """Perform advanced difference analysis."""
        try:
            # Parse both XMLs
            root1 = ET.fromstring(xml1)
            root2 = ET.fromstring(xml2)
            
            # Element-level analysis
            elements1 = self._extract_element_info(root1)
            elements2 = self._extract_element_info(root2)
            
            # Text content analysis
            text1 = self.comparator.extract_text_content(xml1)
            text2 = self.comparator.extract_text_content(xml2)
            
            # Structure analysis
            structure1 = self._analyze_structure(root1)
            structure2 = self._analyze_structure(root2)
            
            return {
                'element_analysis': self._compare_elements(elements1, elements2),
                'text_analysis': self._compare_text(text1, text2),
                'structure_analysis': self._compare_structures(structure1, structure2),
                'attribute_analysis': self._compare_attributes(elements1, elements2),
                'namespace_analysis': self._compare_namespaces(xml1, xml2)
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _extract_element_info(self, root: ET.Element) -> List[Dict[str, Any]]:
        """Extract detailed information about elements."""
        elements = []
        
        def extract_recursive(element, path=""):
            current_path = f"{path}/{element.tag}" if path else element.tag
            
            element_info = {
                'tag': element.tag,
                'path': current_path,
                'text': element.text or '',
                'tail': element.tail or '',
                'attributes': element.attrib.copy(),
                'children_count': len(element),
                'depth': current_path.count('/')
            }
            
            elements.append(element_info)
            
            for child in element:
                extract_recursive(child, current_path)
        
        extract_recursive(root)
        return elements
    
    def _analyze_structure(self, root: ET.Element) -> Dict[str, Any]:
        """Analyze XML structure."""
        structure = {
            'total_elements': 0,
            'max_depth': 0,
            'element_counts': {},
            'attribute_counts': {},
            'text_elements': 0,
            'empty_elements': 0
        }
        
        def analyze_recursive(element, depth=0):
            structure['total_elements'] += 1
            structure['max_depth'] = max(structure['max_depth'], depth)
            
            tag = element.tag
            structure['element_counts'][tag] = structure['element_counts'].get(tag, 0) + 1
            
            if element.attrib:
                structure['attribute_counts'][tag] = structure['attribute_counts'].get(tag, 0) + len(element.attrib)
            
            if element.text and element.text.strip():
                structure['text_elements'] += 1
            
            if not element.text and not element.tail and len(element) == 0:
                structure['empty_elements'] += 1
            
            for child in element:
                analyze_recursive(child, depth + 1)
        
        analyze_recursive(root)
        return structure
    
    def _compare_elements(self, elements1: List[Dict], elements2: List[Dict]) -> Dict[str, Any]:
        """Compare element information."""
        tags1 = [e['tag'] for e in elements1]
        tags2 = [e['tag'] for e in elements2]
        
        common_tags = set(tags1) & set(tags2)
        unique_to_1 = set(tags1) - set(tags2)
        unique_to_2 = set(tags2) - set(tags1)
        
        return {
            'total_elements_1': len(elements1),
            'total_elements_2': len(elements2),
            'common_tags': len(common_tags),
            'unique_to_1': len(unique_to_1),
            'unique_to_2': len(unique_to_2),
            'tag_similarity': len(common_tags) / max(len(set(tags1)), len(set(tags2)), 1)
        }
    
    def _compare_text(self, text1: str, text2: str) -> Dict[str, Any]:
        """Compare text content."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        common_words = words1 & words2
        unique_to_1 = words1 - words2
        unique_to_2 = words2 - words1
        
        return {
            'text_length_1': len(text1),
            'text_length_2': len(text2),
            'word_count_1': len(words1),
            'word_count_2': len(words2),
            'common_words': len(common_words),
            'unique_to_1': len(unique_to_1),
            'unique_to_2': len(unique_to_2),
            'text_similarity': len(common_words) / max(len(words1), len(words2), 1)
        }
    
    def _compare_structures(self, structure1: Dict, structure2: Dict) -> Dict[str, Any]:
        """Compare XML structures."""
        return {
            'total_elements_diff': structure1['total_elements'] - structure2['total_elements'],
            'max_depth_diff': structure1['max_depth'] - structure2['max_depth'],
            'text_elements_diff': structure1['text_elements'] - structure2['text_elements'],
            'empty_elements_diff': structure1['empty_elements'] - structure2['empty_elements'],
            'structure_similarity': self._calculate_structure_similarity(structure1, structure2)
        }
    
    def _calculate_structure_similarity(self, structure1: Dict, structure2: Dict) -> float:
        """Calculate structure similarity."""
        total_diff = abs(structure1['total_elements'] - structure2['total_elements'])
        depth_diff = abs(structure1['max_depth'] - structure2['max_depth'])
        text_diff = abs(structure1['text_elements'] - structure2['text_elements'])
        
        max_values = max(structure1['total_elements'], structure2['total_elements'], 1)
        max_depth = max(structure1['max_depth'], structure2['max_depth'], 1)
        max_text = max(structure1['text_elements'], structure2['text_elements'], 1)
        
        similarity = 1.0 - (total_diff / max_values + depth_diff / max_depth + text_diff / max_text) / 3
        return max(0.0, similarity)
    
    def _compare_attributes(self, elements1: List[Dict], elements2: List[Dict]) -> Dict[str, Any]:
        """Compare element attributes."""
        attrs1 = {}
        attrs2 = {}
        
        for elem in elements1:
            for attr_name, attr_value in elem['attributes'].items():
                if attr_name not in attrs1:
                    attrs1[attr_name] = []
                attrs1[attr_name].append(attr_value)
        
        for elem in elements2:
            for attr_name, attr_value in elem['attributes'].items():
                if attr_name not in attrs2:
                    attrs2[attr_name] = []
                attrs2[attr_name].append(attr_value)
        
        common_attrs = set(attrs1.keys()) & set(attrs2.keys())
        unique_to_1 = set(attrs1.keys()) - set(attrs2.keys())
        unique_to_2 = set(attrs2.keys()) - set(attrs1.keys())
        
        return {
            'common_attributes': len(common_attrs),
            'unique_to_1': len(unique_to_1),
            'unique_to_2': len(unique_to_2),
            'attribute_similarity': len(common_attrs) / max(len(attrs1), len(attrs2), 1)
        }
    
    def _compare_namespaces(self, xml1: str, xml2: str) -> Dict[str, Any]:
        """Compare XML namespaces."""
        ns1 = self._extract_namespaces(xml1)
        ns2 = self._extract_namespaces(xml2)
        
        common_ns = ns1 & ns2
        unique_to_1 = ns1 - ns2
        unique_to_2 = ns2 - ns1
        
        return {
            'namespaces_1': len(ns1),
            'namespaces_2': len(ns2),
            'common_namespaces': len(common_ns),
            'unique_to_1': len(unique_to_1),
            'unique_to_2': len(unique_to_2),
            'namespace_similarity': len(common_ns) / max(len(ns1), len(ns2), 1)
        }
    
    def _extract_namespaces(self, xml: str) -> set:
        """Extract namespaces from XML."""
        namespaces = set()
        
        # Find xmlns declarations
        xmlns_pattern = r'xmlns(?::\w+)?\s*=\s*["\']([^"\']+)["\']'
        matches = re.findall(xmlns_pattern, xml)
        namespaces.update(matches)
        
        return namespaces
    
    def _generate_summary(self, basic_result: Dict, advanced_result: Dict) -> str:
        """Generate a summary of the analysis."""
        if 'error' in basic_result:
            return f"Analysis failed: {basic_result['error']}"
        
        summary_parts = []
        
        # Basic summary
        if basic_result['identical']:
            summary_parts.append("XML documents are identical")
        else:
            summary_parts.append(f"XML documents are {basic_result['similarity']:.1%} similar")
            summary_parts.append(f"Length difference: {basic_result['length_diff']} characters")
        
        # Advanced summary
        if 'element_analysis' in advanced_result:
            elem_analysis = advanced_result['element_analysis']
            summary_parts.append(f"Elements: {elem_analysis['common_tags']} common, {elem_analysis['unique_to_1']} unique to first, {elem_analysis['unique_to_2']} unique to second")
        
        if 'text_analysis' in advanced_result:
            text_analysis = advanced_result['text_analysis']
            summary_parts.append(f"Text similarity: {text_analysis['text_similarity']:.1%}")
        
        if 'structure_analysis' in advanced_result:
            struct_analysis = advanced_result['structure_analysis']
            summary_parts.append(f"Structure similarity: {struct_analysis['structure_similarity']:.1%}")
        
        return "; ".join(summary_parts)
    
    def generate_diff_report(self, xml1: str, xml2: str) -> str:
        """Generate a detailed diff report."""
        analysis = self.analyze_differences(xml1, xml2)
        
        report = []
        report.append("XML Diff Analysis Report")
        report.append("=" * 50)
        report.append("")
        
        # Basic information
        report.append("Basic Comparison:")
        report.append(f"  Identical: {analysis['identical']}")
        report.append(f"  Similarity: {analysis['similarity']:.2%}")
        report.append(f"  Length difference: {analysis['length_diff']}")
        report.append("")
        
        # Advanced analysis
        if 'advanced_analysis' in analysis:
            advanced = analysis['advanced_analysis']
            
            if 'element_analysis' in advanced:
                elem = advanced['element_analysis']
                report.append("Element Analysis:")
                report.append(f"  Total elements (1): {elem['total_elements_1']}")
                report.append(f"  Total elements (2): {elem['total_elements_2']}")
                report.append(f"  Common tags: {elem['common_tags']}")
                report.append(f"  Unique to first: {elem['unique_to_1']}")
                report.append(f"  Unique to second: {elem['unique_to_2']}")
                report.append(f"  Tag similarity: {elem['tag_similarity']:.2%}")
                report.append("")
            
            if 'text_analysis' in advanced:
                text = advanced['text_analysis']
                report.append("Text Analysis:")
                report.append(f"  Text length (1): {text['text_length_1']}")
                report.append(f"  Text length (2): {text['text_length_2']}")
                report.append(f"  Word count (1): {text['word_count_1']}")
                report.append(f"  Word count (2): {text['word_count_2']}")
                report.append(f"  Common words: {text['common_words']}")
                report.append(f"  Text similarity: {text['text_similarity']:.2%}")
                report.append("")
            
            if 'structure_analysis' in advanced:
                struct = advanced['structure_analysis']
                report.append("Structure Analysis:")
                report.append(f"  Total elements difference: {struct['total_elements_diff']}")
                report.append(f"  Max depth difference: {struct['max_depth_diff']}")
                report.append(f"  Text elements difference: {struct['text_elements_diff']}")
                report.append(f"  Structure similarity: {struct['structure_similarity']:.2%}")
                report.append("")
        
        # Summary
        if 'summary' in analysis:
            report.append("Summary:")
            report.append(f"  {analysis['summary']}")
        
        return "\n".join(report)


class TestXMLDiff:
    """Test cases for XML diff functionality."""
    
    def test_xml_diff_analyzer_init(self):
        """Test XMLDiffAnalyzer initialization."""
        analyzer = XMLDiffAnalyzer()
        
        assert analyzer.comparator is not None
        assert analyzer.ignore_whitespace == True
        assert analyzer.ignore_namespaces == True
        assert analyzer.ignore_attributes is not None
        assert analyzer.ignore_elements is not None
    
    def test_analyze_differences_identical(self):
        """Test analyzing identical XML documents."""
        analyzer = XMLDiffAnalyzer()
        
        xml1 = "<root><child>Text</child></root>"
        xml2 = "<root><child>Text</child></root>"
        
        result = analyzer.analyze_differences(xml1, xml2)
        
        assert result['identical'] == True
        assert result['similarity'] == 1.0
        assert result['length_diff'] == 0
        assert 'advanced_analysis' in result
        assert 'summary' in result
    
    def test_analyze_differences_different(self):
        """Test analyzing different XML documents."""
        analyzer = XMLDiffAnalyzer()
        
        xml1 = "<root><child>Text1</child></root>"
        xml2 = "<root><child>Text2 longer</child></root>"
        
        result = analyzer.analyze_differences(xml1, xml2)
        
        assert result['identical'] == False
        assert result['similarity'] < 1.0
        assert result['length_diff'] > 0
        assert 'advanced_analysis' in result
        assert 'summary' in result
    
    def test_analyze_differences_with_namespaces(self):
        """Test analyzing XML documents with namespaces."""
        analyzer = XMLDiffAnalyzer()
        
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
        
        result = analyzer.analyze_differences(xml1, xml2)
        
        # Should be identical after normalization
        assert result['identical'] == True
        assert result['similarity'] == 1.0
    
    def test_analyze_differences_with_attributes(self):
        """Test analyzing XML documents with attributes."""
        analyzer = XMLDiffAnalyzer()
        
        xml1 = '<root><child attr="value1">Text</child></root>'
        xml2 = '<root><child attr="value2">Text</child></root>'
        
        result = analyzer.analyze_differences(xml1, xml2)
        
        assert result['identical'] == False
        assert result['similarity'] < 1.0
        assert 'advanced_analysis' in result
    
    def test_analyze_differences_with_structure(self):
        """Test analyzing XML documents with different structures."""
        analyzer = XMLDiffAnalyzer()
        
        xml1 = '<root><child1>Text</child1></root>'
        xml2 = '<root><child2>Text</child2></root>'
        
        result = analyzer.analyze_differences(xml1, xml2)
        
        assert result['identical'] == False
        assert result['similarity'] < 1.0
        assert 'advanced_analysis' in result
    
    def test_analyze_differences_with_text(self):
        """Test analyzing XML documents with different text content."""
        analyzer = XMLDiffAnalyzer()
        
        xml1 = '<root><child>Text 1</child></root>'
        xml2 = '<root><child>Text 2</child></root>'
        
        result = analyzer.analyze_differences(xml1, xml2)
        
        assert result['identical'] == False
        assert result['similarity'] < 1.0
        assert 'advanced_analysis' in result
    
    def test_analyze_differences_with_whitespace(self):
        """Test analyzing XML documents with whitespace differences."""
        analyzer = XMLDiffAnalyzer()
        
        xml1 = '<root><child>Text</child></root>'
        xml2 = '<root>\n  <child>\n    Text\n  </child>\n</root>'
        
        result = analyzer.analyze_differences(xml1, xml2)
        
        # Should be identical after whitespace normalization
        assert result['identical'] == True
        assert result['similarity'] == 1.0
    
    def test_analyze_differences_with_comments(self):
        """Test analyzing XML documents with comments."""
        analyzer = XMLDiffAnalyzer()
        
        xml1 = '<root><!-- comment --><child>Text</child></root>'
        xml2 = '<root><child>Text</child></root>'
        
        result = analyzer.analyze_differences(xml1, xml2)
        
        # Should be identical (comments are ignored)
        assert result['identical'] == True
        assert result['similarity'] == 1.0
    
    def test_analyze_differences_with_processing_instructions(self):
        """Test analyzing XML documents with processing instructions."""
        analyzer = XMLDiffAnalyzer()
        
        xml1 = '<?xml version="1.0"?><root><child>Text</child></root>'
        xml2 = '<root><child>Text</child></root>'
        
        result = analyzer.analyze_differences(xml1, xml2)
        
        # Should be identical (processing instructions are ignored)
        assert result['identical'] == True
        assert result['similarity'] == 1.0
    
    def test_analyze_differences_with_cdata(self):
        """Test analyzing XML documents with CDATA sections."""
        analyzer = XMLDiffAnalyzer()
        
        xml1 = '<root><child><![CDATA[Text content]]></child></root>'
        xml2 = '<root><child>Text content</child></root>'
        
        result = analyzer.analyze_differences(xml1, xml2)
        
        # Should be identical (CDATA content is normalized)
        assert result['identical'] == True
        assert result['similarity'] == 1.0
    
    def test_analyze_differences_with_entities(self):
        """Test analyzing XML documents with entities."""
        analyzer = XMLDiffAnalyzer()
        
        xml1 = '<root><child>&lt;Text&gt;</child></root>'
        xml2 = '<root><child>&lt;Text&gt;</child></root>'
        
        result = analyzer.analyze_differences(xml1, xml2)
        
        # Should be identical (same entities)
        assert result['identical'] == True
        assert result['similarity'] == 1.0
    
    def test_analyze_differences_with_mixed_content(self):
        """Test analyzing XML documents with mixed content."""
        analyzer = XMLDiffAnalyzer()
        
        xml1 = '<root>Text <child>child text</child> more text</root>'
        xml2 = '<root>Text <child>child text</child> more text</root>'
        
        result = analyzer.analyze_differences(xml1, xml2)
        
        assert result['identical'] == True
        assert result['similarity'] == 1.0
    
    def test_analyze_differences_with_unicode(self):
        """Test analyzing XML documents with Unicode content."""
        analyzer = XMLDiffAnalyzer()
        
        xml1 = '<root><child>Text with émojis 🎉</child></root>'
        xml2 = '<root><child>Text with émojis 🎉</child></root>'
        
        result = analyzer.analyze_differences(xml1, xml2)
        
        assert result['identical'] == True
        assert result['similarity'] == 1.0
    
    def test_analyze_differences_with_large_documents(self):
        """Test analyzing large XML documents."""
        analyzer = XMLDiffAnalyzer()
        
        # Create large XML documents
        xml1 = '<root>' + ''.join(f'<child{i}>Text {i}</child{i}>' for i in range(1000)) + '</root>'
        xml2 = '<root>' + ''.join(f'<child{i}>Text {i}</child{i}>' for i in range(1000)) + '</root>'
        
        result = analyzer.analyze_differences(xml1, xml2)
        
        assert result['identical'] == True
        assert result['similarity'] == 1.0
        assert result['length_diff'] == 0
    
    def test_analyze_differences_with_performance(self):
        """Test analyzing differences performance."""
        analyzer = XMLDiffAnalyzer()
        
        import time
        
        # Create medium-sized XML documents
        xml1 = '<root>' + ''.join(f'<child{i}>Text {i}</child{i}>' for i in range(100)) + '</root>'
        xml2 = '<root>' + ''.join(f'<child{i}>Text {i}</child{i}>' for i in range(100)) + '</root>'
        
        start_time = time.time()
        result = analyzer.analyze_differences(xml1, xml2)
        end_time = time.time()
        
        assert result['identical'] == True
        assert end_time - start_time < 2.0  # Should complete within 2 seconds
    
    def test_analyze_differences_with_memory_usage(self):
        """Test analyzing differences memory usage."""
        analyzer = XMLDiffAnalyzer()
        
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Create large XML documents
        xml1 = '<root>' + ''.join(f'<child{i}>Text {i}</child{i}>' for i in range(1000)) + '</root>'
        xml2 = '<root>' + ''.join(f'<child{i}>Text {i}</child{i}>' for i in range(1000)) + '</root>'
        
        result = analyzer.analyze_differences(xml1, xml2)
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        assert result['identical'] == True
        assert memory_increase < 100 * 1024 * 1024  # Should use less than 100MB
    
    def test_analyze_differences_with_error_handling(self):
        """Test analyzing differences error handling."""
        analyzer = XMLDiffAnalyzer()
        
        # Test with invalid XML
        result = analyzer.analyze_differences("invalid xml", "also invalid")
        
        assert result['identical'] == False
        assert 'error' in result
        assert result['similarity'] == 0.0
    
    def test_analyze_differences_with_partial_matches(self):
        """Test analyzing differences with partial matches."""
        analyzer = XMLDiffAnalyzer()
        
        xml1 = '<root><child1>Text</child1><child2>Text</child2></root>'
        xml2 = '<root><child1>Text</child1><child3>Text</child3></root>'
        
        result = analyzer.analyze_differences(xml1, xml2)
        
        assert result['identical'] == False
        assert result['similarity'] > 0.0  # Should have some similarity
        assert result['similarity'] < 1.0  # But not identical
    
    def test_generate_diff_report(self):
        """Test generating diff report."""
        analyzer = XMLDiffAnalyzer()
        
        xml1 = '<root><child>Text1</child></root>'
        xml2 = '<root><child>Text2</child></root>'
        
        report = analyzer.generate_diff_report(xml1, xml2)
        
        assert isinstance(report, str)
        assert "XML Diff Analysis Report" in report
        assert "Basic Comparison:" in report
        assert "Element Analysis:" in report
        assert "Text Analysis:" in report
        assert "Structure Analysis:" in report
        assert "Summary:" in report
    
    def test_generate_diff_report_identical(self):
        """Test generating diff report for identical documents."""
        analyzer = XMLDiffAnalyzer()
        
        xml1 = '<root><child>Text</child></root>'
        xml2 = '<root><child>Text</child></root>'
        
        report = analyzer.generate_diff_report(xml1, xml2)
        
        assert "XML documents are identical" in report
        assert "100.00%" in report or "100.0%" in report
    
    def test_generate_diff_report_different(self):
        """Test generating diff report for different documents."""
        analyzer = XMLDiffAnalyzer()
        
        xml1 = '<root><child>Text1</child></root>'
        xml2 = '<root><child>Text2</child></root>'
        
        report = analyzer.generate_diff_report(xml1, xml2)
        
        assert "XML documents are" in report
        assert "similar" in report
        assert "Element Analysis:" in report
        assert "Text Analysis:" in report
    
    def test_generate_diff_report_with_error(self):
        """Test generating diff report with error."""
        analyzer = XMLDiffAnalyzer()
        
        report = analyzer.generate_diff_report("invalid xml", "also invalid")
        
        assert "Error analyzing differences:" in report or "Analysis failed:" in report
        assert "error" in report.lower()
    
    def test_generate_diff_report_with_large_documents(self):
        """Test generating diff report with large documents."""
        analyzer = XMLDiffAnalyzer()
        
        # Create large XML documents
        xml1 = '<root>' + ''.join(f'<child{i}>Text {i}</child{i}>' for i in range(100)) + '</root>'
        xml2 = '<root>' + ''.join(f'<child{i}>Text {i}</child{i}>' for i in range(100)) + '</root>'
        
        report = analyzer.generate_diff_report(xml1, xml2)
        
        assert isinstance(report, str)
        assert len(report) > 0
        assert "XML Diff Analysis Report" in report
    
    def test_generate_diff_report_with_performance(self):
        """Test generating diff report performance."""
        analyzer = XMLDiffAnalyzer()
        
        import time
        
        # Create medium-sized XML documents
        xml1 = '<root>' + ''.join(f'<child{i}>Text {i}</child{i}>' for i in range(50)) + '</root>'
        xml2 = '<root>' + ''.join(f'<child{i}>Text {i}</child{i}>' for i in range(50)) + '</root>'
        
        start_time = time.time()
        report = analyzer.generate_diff_report(xml1, xml2)
        end_time = time.time()
        
        assert isinstance(report, str)
        assert end_time - start_time < 1.0  # Should complete within 1 second
    
    def test_generate_diff_report_with_memory_usage(self):
        """Test generating diff report memory usage."""
        analyzer = XMLDiffAnalyzer()
        
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss
        
        # Create large XML documents
        xml1 = '<root>' + ''.join(f'<child{i}>Text {i}</child{i}>' for i in range(500)) + '</root>'
        xml2 = '<root>' + ''.join(f'<child{i}>Text {i}</child{i}>' for i in range(500)) + '</root>'
        
        report = analyzer.generate_diff_report(xml1, xml2)
        
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory
        
        assert isinstance(report, str)
        assert memory_increase < 50 * 1024 * 1024  # Should use less than 50MB
