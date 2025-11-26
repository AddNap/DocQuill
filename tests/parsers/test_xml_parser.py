"""
Tests for XMLParser class.

This module contains unit tests for the XMLParser functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import xml.etree.ElementTree as ET

from docx_interpreter.parser.xml_parser import XMLParser


class TestXMLParser:
    """Test cases for XMLParser class."""
    
    def test_init_with_package_reader(self):
        """Test XMLParser initialization with package reader."""
        mock_reader = Mock()
        parser = XMLParser(mock_reader)
        
        assert parser.package_reader == mock_reader
        assert parser.ns is not None
        assert parser.parser_registry is not None
    
    def test_parse_metadata(self):
        """Test parsing document metadata."""
        mock_reader = Mock()
        mock_reader.get_xml_content.side_effect = [
            "<core>core content</core>",
            "<app>app content</app>",
            "<custom>custom content</custom>"
        ]
        
        parser = XMLParser(mock_reader)
        metadata = parser.parse_metadata()
        
        assert isinstance(metadata, dict)
        assert 'core_properties' in metadata
        assert 'app_properties' in metadata
        assert 'custom_properties' in metadata
    
    def test_parse_body(self):
        """Test parsing document body."""
        mock_reader = Mock()
        mock_reader.get_xml_content.return_value = """
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
        
        parser = XMLParser(mock_reader)
        body = parser.parse_body()
        
        assert body is not None
        mock_reader.get_xml_content.assert_called_with("word/document.xml")
    
    def test_parse_element_paragraph(self):
        """Test parsing paragraph element."""
        mock_reader = Mock()
        parser = XMLParser(mock_reader)
        
        # Create a mock paragraph element
        paragraph_xml = """
        <w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:r>
                <w:t>Sample paragraph</w:t>
            </w:r>
        </w:p>
        """
        element = ET.fromstring(paragraph_xml)
        
        result = parser.parse_element(element, None)
        assert result is not None
    
    def test_parse_element_table(self):
        """Test parsing table element."""
        mock_reader = Mock()
        parser = XMLParser(mock_reader)
        
        # Create a mock table element
        table_xml = """
        <w:tbl xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:tr>
                <w:tc>
                    <w:p>
                        <w:r>
                            <w:t>Cell content</w:t>
                        </w:r>
                    </w:p>
                </w:tc>
            </w:tr>
        </w:tbl>
        """
        element = ET.fromstring(table_xml)
        
        result = parser.parse_element(element, None)
        assert result is not None
    
    def test_parse_container(self):
        """Test parsing container element."""
        mock_reader = Mock()
        parser = XMLParser(mock_reader)
        
        # Create a mock container element
        container_xml = """
        <w:tc xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:p>
                <w:r>
                    <w:t>Container content</w:t>
                </w:r>
            </w:p>
        </w:tc>
        """
        element = ET.fromstring(container_xml)
        
        result = parser.parse_container(element, None)
        assert result is not None
    
    def test_parse_run(self):
        """Test parsing run element."""
        mock_reader = Mock()
        parser = XMLParser(mock_reader)
        
        # Create a mock run element
        run_xml = """
        <w:r xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:rPr>
                <w:b/>
            </w:rPr>
            <w:t>Bold text</w:t>
        </w:r>
        """
        element = ET.fromstring(run_xml)
        
        result = parser.parse_run(element, None)
        assert result is not None
        assert 'text' in result
        assert 'style' in result
    
    def test_parse_run_with_space_attribute(self):
        """Test parsing run element with xml:space attribute."""
        mock_reader = Mock()
        parser = XMLParser(mock_reader)
        
        # Create a mock run element with xml:space
        run_xml = """
        <w:r xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
             xmlns:xml="http://www.w3.org/XML/1998/namespace"
             xml:space="preserve">
            <w:t>  Preserved spaces  </w:t>
        </w:r>
        """
        element = ET.fromstring(run_xml)
        
        result = parser.parse_run(element, None)
        assert result is not None
        assert result.get('space') == 'preserve'
    
    def test_parse_sections(self):
        """Test parsing document sections."""
        mock_reader = Mock()
        mock_reader.get_xml_content.return_value = """
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body>
                <w:sectPr>
                    <w:pgSz w:w="12240" w:h="15840"/>
                    <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>
                </w:sectPr>
            </w:body>
        </w:document>
        """
        
        parser = XMLParser(mock_reader)
        sections = parser.parse_sections()
        
        assert sections is not None
        mock_reader.get_xml_content.assert_called_with("word/document.xml")
    
    def test_parse_core_properties(self):
        """Test parsing core properties."""
        mock_reader = Mock()
        parser = XMLParser(mock_reader)
        
        core_xml = """
        <cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties">
            <dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">Test Document</dc:title>
            <dc:creator xmlns:dc="http://purl.org/dc/elements/1.1/">Test Author</dc:creator>
            <dcterms:created xmlns:dcterms="http://purl.org/dc/terms/">2024-01-01T00:00:00Z</dcterms:created>
        </cp:coreProperties>
        """
        element = ET.fromstring(core_xml)
        
        result = parser._parse_core_properties(core_xml)
        assert result is not None
        assert 'title' in result
        assert 'creator' in result
        assert 'created' in result
    
    def test_parse_app_properties(self):
        """Test parsing application properties."""
        mock_reader = Mock()
        parser = XMLParser(mock_reader)
        
        app_xml = """
        <Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
            <Application>Microsoft Word</Application>
            <AppVersion>16.0</AppVersion>
            <Company>Test Company</Company>
        </Properties>
        """
        
        result = parser._parse_app_properties(app_xml)
        assert result is not None
        assert 'Application' in result
        assert 'AppVersion' in result
        assert 'Company' in result
    
    def test_parse_custom_properties(self):
        """Test parsing custom properties."""
        mock_reader = Mock()
        parser = XMLParser(mock_reader)
        
        custom_xml = """
        <Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties">
            <property fmtid="{D5CDD505-2E9C-101B-9397-08002B2CF9AE}" pid="2" name="CustomProperty">
                <vt:lpwstr xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">Custom Value</vt:lpwstr>
            </property>
        </Properties>
        """
        
        result = parser._parse_custom_properties(custom_xml)
        assert result is not None
        assert 'CustomProperty' in result
    
    def test_parse_paragraph_properties(self):
        """Test parsing paragraph properties."""
        mock_reader = Mock()
        parser = XMLParser(mock_reader)
        
        p_pr_xml = """
        <w:pPr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:jc w:val="center"/>
            <w:spacing w:before="240" w:after="240"/>
        </w:pPr>
        """
        element = ET.fromstring(p_pr_xml)
        
        result = parser._parse_paragraph_properties(element)
        assert result is not None
        assert 'alignment' in result
        assert 'spacing' in result
    
    def test_parse_run_properties(self):
        """Test parsing run properties."""
        mock_reader = Mock()
        parser = XMLParser(mock_reader)
        
        r_pr_xml = """
        <w:rPr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:b/>
            <w:i/>
            <w:sz w:val="24"/>
            <w:color w:val="FF0000"/>
        </w:rPr>
        """
        element = ET.fromstring(r_pr_xml)
        
        result = parser._parse_run_properties(element)
        assert result is not None
        assert 'bold' in result
        assert 'italic' in result
        assert 'size' in result
        assert 'color' in result
    
    def test_parse_table_properties(self):
        """Test parsing table properties."""
        mock_reader = Mock()
        parser = XMLParser(mock_reader)
        
        tbl_pr_xml = """
        <w:tblPr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:tblStyle w:val="TableGrid"/>
            <w:tblW w:w="5000" w:type="dxa"/>
            <w:tblBorders>
                <w:top w:val="single" w:sz="4"/>
                <w:bottom w:val="single" w:sz="4"/>
            </w:tblBorders>
        </w:tblPr>
        """
        element = ET.fromstring(tbl_pr_xml)
        
        result = parser._parse_table_properties(element)
        assert result is not None
        assert 'style' in result
        assert 'width' in result
        assert 'borders' in result
    
    def test_parse_section_properties(self):
        """Test parsing section properties."""
        mock_reader = Mock()
        parser = XMLParser(mock_reader)
        
        sect_pr_xml = """
        <w:sectPr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:pgSz w:w="12240" w:h="15840"/>
            <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>
            <w:cols w:space="708"/>
        </w:sectPr>
        """
        element = ET.fromstring(sect_pr_xml)
        
        result = parser._parse_section_properties(element)
        assert result is not None
        assert 'page_size' in result
        assert 'margins' in result
        assert 'columns' in result
    
    def test_error_handling(self):
        """Test error handling in XMLParser."""
        mock_reader = Mock()
        mock_reader.get_xml_content.side_effect = Exception("XML parsing error")
        
        parser = XMLParser(mock_reader)
        
        with pytest.raises(Exception):
            parser.parse_body()
    
    def test_namespace_handling(self):
        """Test namespace handling in XMLParser."""
        mock_reader = Mock()
        parser = XMLParser(mock_reader)
        
        # Test that namespaces are properly defined
        assert 'w' in parser.ns
        assert parser.ns['w'] == "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    
    def test_parser_registry(self):
        """Test parser registry functionality."""
        mock_reader = Mock()
        parser = XMLParser(mock_reader)
        
        # Test that parser registry is properly initialized
        assert parser.parser_registry is not None
        assert isinstance(parser.parser_registry, dict)
        
        # Test that common parsers are registered
        assert 'Paragraph' in parser.parser_registry
        assert 'Table' in parser.parser_registry
        assert 'Run' in parser.parser_registry
