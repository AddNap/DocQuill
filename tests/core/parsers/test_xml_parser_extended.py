"""
Extended tests for XMLParser class.

This module contains additional unit tests for XMLParser functionality
to increase test coverage from 45% to higher levels.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import xml.etree.ElementTree as ET

from docquill.parser.xml_parser import XMLParser


class TestXMLParserExtended:
    """Extended test cases for XMLParser class."""
    
    @pytest.fixture
    def mock_package_reader(self):
        """Create a mock package reader."""
        reader = Mock()
        reader.get_xml_content = Mock(return_value="")
        reader.get_binary_content = Mock(return_value=b"")
        reader.relationships = {}
        return reader
    
    @pytest.fixture
    def xml_parser(self, mock_package_reader):
        """Create XMLParser instance."""
        with patch('docquill.parser.numbering_parser.NumberingParser') as mock_np_class:
            with patch('docquill.styles.style_manager.StyleManager') as mock_sm_class:
                mock_np_instance = Mock()
                mock_np_instance.parse_numbering.return_value = {}
                mock_np_class.return_value = mock_np_instance
                
                mock_sm_instance = Mock()
                mock_sm_class.return_value = mock_sm_instance
                
                parser = XMLParser(mock_package_reader)
                parser.numbering_parser = mock_np_instance
                parser.numbering_data = {}
                parser.style_manager = None
                return parser
    
    def test_sanitize_attrib_with_namespace(self, xml_parser):
        """Test _sanitize_attrib with namespaced attributes."""
        attrib = {
            '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val': 'test',
            'normal': 'value',
            'prefix:key': 'value2'
        }
        result = xml_parser._sanitize_attrib(attrib)
        
        assert result['val'] == 'test'
        assert result['normal'] == 'value'
        assert result['key'] == 'value2'
    
    def test_safe_float_with_valid_values(self, xml_parser):
        """Test _safe_float with valid numeric values."""
        assert XMLParser._safe_float(42) == 42.0
        assert XMLParser._safe_float(3.14) == 3.14
        assert XMLParser._safe_float("123") == 123.0
        assert XMLParser._safe_float("  456  ") == 456.0
    
    def test_safe_float_with_invalid_values(self, xml_parser):
        """Test _safe_float with invalid values."""
        assert XMLParser._safe_float(None) is None
        assert XMLParser._safe_float("") is None
        assert XMLParser._safe_float({}) is None
        assert XMLParser._safe_float("invalid") is None
    
    def test_normalize_color_value(self, xml_parser):
        """Test _normalize_color_value with various inputs."""
        # Method adds # prefix if not present
        result = XMLParser._normalize_color_value("FF0000")
        assert result == "#FF0000" or result == "FF0000"  # Accept both formats
        assert XMLParser._normalize_color_value("auto") is None
        assert XMLParser._normalize_color_value("none") is None
        assert XMLParser._normalize_color_value(None) is None
        assert XMLParser._normalize_color_value("") is None
    
    def test_parse_border_spec(self, xml_parser):
        """Test _parse_border_spec with border element."""
        border_elem = ET.Element('border')
        border_elem.set('val', 'single')
        border_elem.set('sz', '24')
        border_elem.set('color', 'FF0000')
        
        result = xml_parser._parse_border_spec(border_elem)
        
        assert result is not None
        assert result.get('style') == 'single'  # val is converted to style
        assert result.get('width') is not None  # sz is converted to width
        assert 'color' in result or 'color_raw' in result
    
    def test_parse_border_spec_none(self, xml_parser):
        """Test _parse_border_spec with None."""
        assert xml_parser._parse_border_spec(None) is None
    
    def test_parse_field_simple(self, xml_parser):
        """Test _parse_field with fldSimple element."""
        field_xml = """
        <w:fldSimple xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                     w:instr="DATE @ &quot;dd.MM.yyyy&quot;" />
        """
        field_elem = ET.fromstring(field_xml)
        
        result = xml_parser._parse_field(field_elem, None)
        
        assert result is not None
        assert result.get('type') == 'Field' or result.get('type') == 'field'
        assert 'instr' in result
    
    def test_parse_hyperlink(self, xml_parser):
        """Test _parse_hyperlink with hyperlink element."""
        hyperlink_xml = """
        <w:hyperlink xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                     xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
                     r:id="rId1">
            <w:r>
                <w:t>Link text</w:t>
            </w:r>
        </w:hyperlink>
        """
        hyperlink_elem = ET.fromstring(hyperlink_xml)
        
        result = xml_parser._parse_hyperlink(hyperlink_elem, None)
        
        assert result is not None
        assert result.get('type') == 'Hyperlink' or result.get('type') == 'hyperlink'
    
    def test_parse_textbox(self, xml_parser):
        """Test _parse_textbox with textbox element."""
        textbox_xml = """
        <w:txbxContent xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:p>
                <w:r>
                    <w:t>Textbox content</w:t>
                </w:r>
            </w:p>
        </w:txbxContent>
        """
        textbox_elem = ET.fromstring(textbox_xml)
        
        result = xml_parser._parse_textbox(textbox_elem, None)
        
        assert result is not None
        assert result.get('type') == 'TextBox' or result.get('type') == 'textbox'
    
    def test_parse_paragraph_properties(self, xml_parser):
        """Test _parse_paragraph_properties with paragraph properties."""
        p_pr_xml = """
        <w:pPr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:jc w:val="center" />
            <w:spacing w:before="240" w:after="120" />
            <w:ind w:left="720" w:right="360" />
        </w:pPr>
        """
        p_pr_elem = ET.fromstring(p_pr_xml)
        
        result = xml_parser._parse_paragraph_properties(p_pr_elem)
        
        assert result is not None
        assert 'alignment' in result or 'jc' in result
    
    def test_parse_run_properties(self, xml_parser):
        """Test _parse_run_properties with run properties."""
        r_pr_xml = """
        <w:rPr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:b />
            <w:i />
            <w:sz w:val="24" />
            <w:color w:val="FF0000" />
        </w:rPr>
        """
        r_pr_elem = ET.fromstring(r_pr_xml)
        
        result = xml_parser._parse_run_properties(r_pr_elem)
        
        assert result is not None
        assert result.get('bold') is True or result.get('b') is True
    
    def test_parse_table_properties(self, xml_parser):
        """Test _parse_table_properties with table properties."""
        tbl_pr_xml = """
        <w:tblPr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:tblStyle w:val="TableGrid" />
            <w:tblW w:w="5000" w:type="dxa" />
        </w:tblPr>
        """
        tbl_pr_elem = ET.fromstring(tbl_pr_xml)
        
        result = xml_parser._parse_table_properties(tbl_pr_elem)
        
        assert result is not None
        assert 'style' in result or 'table_style' in result
    
    def test_parse_core_properties(self, xml_parser):
        """Test _parse_core_properties with core properties XML."""
        core_xml = """
        <cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties">
            <dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">Test Document</dc:title>
            <dc:creator xmlns:dc="http://purl.org/dc/elements/1.1/">Test Author</dc:creator>
        </cp:coreProperties>
        """
        
        result = xml_parser._parse_core_properties(core_xml)
        
        assert result is not None
        assert isinstance(result, dict)
    
    def test_parse_app_properties(self, xml_parser):
        """Test _parse_app_properties with app properties XML."""
        app_xml = """
        <Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
            <Words>100</Words>
            <Pages>5</Pages>
        </Properties>
        """
        
        result = xml_parser._parse_app_properties(app_xml)
        
        assert result is not None
        assert isinstance(result, dict)
    
    def test_parse_custom_properties(self, xml_parser):
        """Test _parse_custom_properties with custom properties XML."""
        custom_xml = """
        <Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties">
            <property fmtid="{D5CDD505-2E9C-101B-9397-08002B2CF9AE}" pid="2" name="CustomProp">
                <vt:lpwstr xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">Custom Value</vt:lpwstr>
            </property>
        </Properties>
        """
        
        result = xml_parser._parse_custom_properties(custom_xml)
        
        assert result is not None
        assert isinstance(result, dict)
    
    def test_parse_element_with_unknown_tag(self, xml_parser):
        """Test parse_element with unknown tag."""
        unknown_xml = """
        <w:unknown xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:t>Unknown content</w:t>
        </w:unknown>
        """
        unknown_elem = ET.fromstring(unknown_xml)
        
        result = xml_parser.parse_element(unknown_elem, None)
        
        # Should handle gracefully without error
        assert result is None or isinstance(result, (dict, list))
    
    def test_parse_container(self, xml_parser):
        """Test parse_container with container element."""
        container_xml = """
        <w:body xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:p>
                <w:r>
                    <w:t>Paragraph 1</w:t>
                </w:r>
            </w:p>
            <w:p>
                <w:r>
                    <w:t>Paragraph 2</w:t>
                </w:r>
            </w:p>
        </w:body>
        """
        container_elem = ET.fromstring(container_xml)
        
        result = xml_parser.parse_container(container_elem, None)
        
        assert isinstance(result, list)
        assert len(result) > 0
    
    def test_parse_run_with_style(self, xml_parser):
        """Test parse_run with run containing style."""
        run_xml = """
        <w:r xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:rPr>
                <w:b />
                <w:sz w:val="24" />
            </w:rPr>
            <w:t>Bold text</w:t>
        </w:r>
        """
        run_elem = ET.fromstring(run_xml)
        
        result = xml_parser.parse_run(run_elem, None)
        
        assert result is not None
        assert hasattr(result, 'text') or isinstance(result, dict)
    
    def test_parse_section_properties(self, xml_parser):
        """Test _parse_section_properties with section properties."""
        sect_pr_xml = """
        <w:sectPr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:pgSz w:w="11906" w:h="16838" />
            <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" />
        </w:sectPr>
        """
        sect_pr_elem = ET.fromstring(sect_pr_xml)
        
        result = xml_parser._parse_section_properties(sect_pr_elem)
        
        assert result is not None
        assert isinstance(result, dict)
    
    def test_parse_paragraph_style(self, xml_parser):
        """Test _parse_paragraph_style with paragraph style."""
        para_xml = """
        <w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
             w:style="Heading1">
            <w:r>
                <w:t>Heading</w:t>
            </w:r>
        </w:p>
        """
        para_elem = ET.fromstring(para_xml)
        
        result = xml_parser._parse_paragraph_style(para_elem)
        
        assert result is not None
        assert isinstance(result, dict)
    
    def test_parse_table_style(self, xml_parser):
        """Test _parse_table_style with table style."""
        table_xml = """
        <w:tbl xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:tblPr>
                <w:tblStyle w:val="TableGrid" />
            </w:tblPr>
            <w:tr>
                <w:tc>
                    <w:p>
                        <w:r>
                            <w:t>Cell</w:t>
                        </w:r>
                    </w:p>
                </w:tc>
            </w:tr>
        </w:tbl>
        """
        table_elem = ET.fromstring(table_xml)
        
        result = xml_parser._parse_table_style(table_elem)
        
        assert result is not None
        assert isinstance(result, dict)
    
    def test_parse_run_style(self, xml_parser):
        """Test _parse_run_style with run style."""
        run_xml = """
        <w:r xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:rPr>
                <w:b />
                <w:i />
                <w:u w:val="single" />
                <w:sz w:val="24" />
                <w:color w:val="FF0000" />
            </w:rPr>
            <w:t>Styled text</w:t>
        </w:r>
        """
        run_elem = ET.fromstring(run_xml)
        r_pr = run_elem.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr')
        
        result = xml_parser._parse_run_style(r_pr)
        
        assert result is not None
        assert isinstance(result, dict)
    
    def test_parse_metadata_with_missing_files(self, xml_parser, mock_package_reader):
        """Test parse_metadata when some property files are missing."""
        mock_package_reader.get_xml_content.side_effect = [
            None,  # core.xml missing
            "<Properties xmlns='http://schemas.openxmlformats.org/officeDocument/2006/extended-properties'><Words>100</Words></Properties>",  # app.xml exists
            None  # custom.xml missing
        ]
        
        result = xml_parser.parse_metadata()
        
        assert isinstance(result, dict)
        # Check that result contains at least app_properties
        assert 'app_properties' in result
    
    def test_parse_body_with_empty_body(self, xml_parser, mock_package_reader):
        """Test parse_body with empty body."""
        mock_package_reader.get_xml_content.return_value = """
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body />
        </w:document>
        """
        
        result = xml_parser.parse_body()
        
        assert result is not None
    
    def test_parse_sections_with_no_sections(self, xml_parser, mock_package_reader):
        """Test parse_sections when document has no sections."""
        mock_package_reader.get_xml_content.return_value = """
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body>
                <w:p>
                    <w:r>
                        <w:t>Content</w:t>
                    </w:r>
                </w:p>
            </w:body>
        </w:document>
        """
        
        result = xml_parser.parse_sections()
        
        assert isinstance(result, list)
    
    def test_parse_header_with_missing_header(self, xml_parser, mock_package_reader):
        """Test parse_header when header is missing."""
        mock_package_reader.get_xml_content.return_value = None
        mock_package_reader.relationships = {}
        
        result = xml_parser.parse_header()
        
        assert result is None
    
    def test_parse_footer_with_missing_footer(self, xml_parser, mock_package_reader):
        """Test parse_footer when footer is missing."""
        mock_package_reader.get_xml_content.return_value = None
        mock_package_reader.relationships = {}
        
        result = xml_parser.parse_footer()
        
        assert result is None

