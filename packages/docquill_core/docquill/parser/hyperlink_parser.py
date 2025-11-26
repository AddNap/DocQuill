"""
Hyperlink parser for DOCX documents.

Handles hyperlink parsing, URL parsing, anchor parsing, and validation.
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class HyperlinkParser:
    """
    Parser for hyperlinks.
    
    Handles hyperlink parsing, URL parsing, anchor parsing, and validation.
    """
    
    def __init__(self, package_reader):
        """
        Initialize hyperlink parser.
        
        Args:
            package_reader: PackageReader instance for accessing hyperlink files
        """
        self.package_reader = package_reader
        self.hyperlinks = {}
        self.hyperlink_info = {}
        
        # Parse hyperlinks
        self._parse_hyperlinks()
        
        logger.debug("Hyperlink parser initialized")
    
    def parse_hyperlink(self, hyperlink_element: ET.Element) -> Dict[str, Any]:
        """
        Parse hyperlink element.
        
        Args:
            hyperlink_element: Hyperlink XML element
            
        Returns:
            Dictionary of parsed hyperlink content
        """
        hyperlink = {
            'type': 'hyperlink',
            'id': hyperlink_element.get('id', ''),
            'target': hyperlink_element.get('target', ''),
            'target_mode': hyperlink_element.get('targetMode', 'Internal'),
            'content': [],
            'styles': {},
            'properties': {}
        }
        
        # Parse hyperlink content
        for child in hyperlink_element:
            if child.tag.endswith('}r'):  # Run
                run = self._parse_run(child)
                hyperlink['content'].append(run)
            elif child.tag.endswith('}p'):  # Paragraph
                paragraph = self._parse_paragraph(child)
                hyperlink['content'].append(paragraph)
            elif child.tag.endswith('}tbl'):  # Table
                table = self._parse_table(child)
                hyperlink['content'].append(table)
        
        return hyperlink
    
    def parse_url_hyperlink(self, hyperlink_element: ET.Element) -> Dict[str, Any]:
        """
        Parse URL hyperlink.
        
        Args:
            hyperlink_element: Hyperlink XML element
            
        Returns:
            Dictionary of parsed URL hyperlink
        """
        url_hyperlink = self.parse_hyperlink(hyperlink_element)
        url_hyperlink['hyperlink_type'] = 'url'
        
        # Validate URL
        target = url_hyperlink.get('target', '')
        if target.startswith('http://') or target.startswith('https://'):
            url_hyperlink['is_valid_url'] = True
        else:
            url_hyperlink['is_valid_url'] = False
        
        return url_hyperlink
    
    def parse_anchor_hyperlink(self, hyperlink_element: ET.Element) -> Dict[str, Any]:
        """
        Parse anchor hyperlink.
        
        Args:
            hyperlink_element: Hyperlink XML element
            
        Returns:
            Dictionary of parsed anchor hyperlink
        """
        anchor_hyperlink = self.parse_hyperlink(hyperlink_element)
        anchor_hyperlink['hyperlink_type'] = 'anchor'
        
        # Validate anchor
        target = anchor_hyperlink.get('target', '')
        if target.startswith('#'):
            anchor_hyperlink['is_valid_anchor'] = True
        else:
            anchor_hyperlink['is_valid_anchor'] = False
        
        return anchor_hyperlink
    
    def resolve_hyperlink_target(self, target: str) -> Dict[str, Any]:
        """
        Resolve hyperlink target.
        
        Args:
            target: Hyperlink target
            
        Returns:
            Dictionary with resolved target information
        """
        resolved = {
            'original_target': target,
            'resolved_target': target,
            'target_type': 'unknown',
            'is_valid': False,
            'normalized_target': target
        }
        
        if target.startswith('http://') or target.startswith('https://'):
            resolved['target_type'] = 'url'
            resolved['is_valid'] = True
        elif target.startswith('#'):
            resolved['target_type'] = 'anchor'
            resolved['is_valid'] = True
        elif target.startswith('mailto:'):
            resolved['target_type'] = 'email'
            resolved['is_valid'] = True
        elif target.startswith('file://'):
            resolved['target_type'] = 'file'
            resolved['is_valid'] = True
        else:
            resolved['target_type'] = 'internal'
            resolved['is_valid'] = True
        
        return resolved
    
    def get_hyperlinks(self) -> Dict[str, Any]:
        """
        Get all hyperlinks.
        
        Returns:
            Dictionary of hyperlinks
        """
        return self.hyperlinks.copy()
    
    def get_hyperlink(self, hyperlink_id: str) -> Optional[Dict[str, Any]]:
        """
        Get specific hyperlink.
        
        Args:
            hyperlink_id: Hyperlink identifier
            
        Returns:
            Hyperlink content or None if not found
        """
        return self.hyperlinks.get(hyperlink_id)
    
    def get_hyperlink_info(self) -> Dict[str, Any]:
        """
        Get hyperlink information.
        
        Returns:
            Dictionary with hyperlink metadata
        """
        return self.hyperlink_info.copy()
    
    def get_hyperlinks_by_target(self, target: str) -> List[Dict[str, Any]]:
        """
        Get hyperlinks by target.
        
        Args:
            target: Target URL or path
            
        Returns:
            List of hyperlinks with matching target
        """
        matching_hyperlinks = []
        for hyperlink_id, hyperlink_content in self.hyperlinks.items():
            if hyperlink_content.get('target') == target:
                matching_hyperlinks.append(hyperlink_content)
        return matching_hyperlinks
    
    def get_external_hyperlinks(self) -> List[Dict[str, Any]]:
        """
        Get external hyperlinks.
        
        Returns:
            List of external hyperlinks
        """
        external_hyperlinks = []
        for hyperlink_id, hyperlink_content in self.hyperlinks.items():
            if hyperlink_content.get('target_mode') == 'External':
                external_hyperlinks.append(hyperlink_content)
        return external_hyperlinks
    
    def get_internal_hyperlinks(self) -> List[Dict[str, Any]]:
        """
        Get internal hyperlinks.
        
        Returns:
            List of internal hyperlinks
        """
        internal_hyperlinks = []
        for hyperlink_id, hyperlink_content in self.hyperlinks.items():
            if hyperlink_content.get('target_mode') == 'Internal':
                internal_hyperlinks.append(hyperlink_content)
        return internal_hyperlinks
    
    def _parse_hyperlinks(self) -> None:
        """Parse hyperlinks from the document."""
        try:
            # Parse hyperlinks from document.xml
            self._parse_document_hyperlinks()
            
            # Parse hyperlinks from headers/footers
            self._parse_header_footer_hyperlinks()
            
            # Update info
            self.hyperlink_info = {
                'total_hyperlinks': len(self.hyperlinks),
                'external_hyperlinks': len(self.get_external_hyperlinks()),
                'internal_hyperlinks': len(self.get_internal_hyperlinks()),
                'hyperlink_ids': list(self.hyperlinks.keys())
            }
            
            logger.info(f"Parsed {len(self.hyperlinks)} hyperlinks")
            
        except Exception as e:
            logger.error(f"Failed to parse hyperlinks: {e}")
    
    def _parse_document_hyperlinks(self) -> None:
        """Parse hyperlinks from document.xml."""
        try:
            document_xml = self.package_reader.get_xml_content('word/document.xml')
            if document_xml:
                self._parse_hyperlinks_from_xml(document_xml, 'document')
        except Exception as e:
            logger.warning(f"Failed to parse document hyperlinks: {e}")
    
    def _parse_header_footer_hyperlinks(self) -> None:
        """Parse hyperlinks from headers and footers."""
        try:
            # Check for header/footer files
            header_footer_patterns = [
                'word/header1.xml',
                'word/header2.xml',
                'word/header3.xml',
                'word/footer1.xml',
                'word/footer2.xml',
                'word/footer3.xml'
            ]
            
            for pattern in header_footer_patterns:
                try:
                    xml_content = self.package_reader.get_xml_content(pattern)
                    if xml_content:
                        self._parse_hyperlinks_from_xml(xml_content, pattern)
                except Exception:
                    # File doesn't exist, continue
                    continue
                    
        except Exception as e:
            logger.warning(f"Failed to parse header/footer hyperlinks: {e}")
    
    def _parse_hyperlinks_from_xml(self, xml_content: str, source: str) -> None:
        """Parse hyperlinks from XML content."""
        try:
            root = ET.fromstring(xml_content)
            
            for hyperlink in root.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}hyperlink'):
                hyperlink_id = hyperlink.get('id', '')
                if hyperlink_id:
                    hyperlink_content = self.parse_hyperlink(hyperlink)
                    hyperlink_content['source'] = source
                    self.hyperlinks[hyperlink_id] = hyperlink_content
                    
        except ET.ParseError as e:
            logger.error(f"Failed to parse hyperlinks from {source}: {e}")
    
    def _parse_run(self, run_element: ET.Element) -> Dict[str, Any]:
        """Parse run element."""
        run = {
            'type': 'run',
            'text': '',
            'styles': {}
        }
        
        # Parse text
        text_elements = run_element.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
        for text_elem in text_elements:
            run['text'] += text_elem.text or ''
        
        # Parse run properties
        r_pr = run_element.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr')
        if r_pr is not None:
            run['styles'] = self._parse_run_properties(r_pr)
        
        return run
    
    def _parse_paragraph(self, paragraph_element: ET.Element) -> Dict[str, Any]:
        """Parse paragraph element."""
        paragraph = {
            'type': 'paragraph',
            'runs': [],
            'styles': {}
        }
        
        # Parse runs
        for run in paragraph_element.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r'):
            run_content = self._parse_run(run)
            paragraph['runs'].append(run_content)
        
        # Parse paragraph properties
        p_pr = paragraph_element.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pPr')
        if p_pr is not None:
            paragraph['styles'] = self._parse_paragraph_properties(p_pr)
        
        return paragraph
    
    def _parse_table(self, table_element: ET.Element) -> Dict[str, Any]:
        """Parse table element."""
        table = {
            'type': 'table',
            'rows': [],
            'styles': {}
        }
        
        # Parse rows
        for row in table_element.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr'):
            row_content = self._parse_table_row(row)
            table['rows'].append(row_content)
        
        # Parse table properties
        tbl_pr = table_element.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tblPr')
        if tbl_pr is not None:
            table['styles'] = self._parse_table_properties(tbl_pr)
        
        return table
    
    def _parse_table_row(self, row_element: ET.Element) -> Dict[str, Any]:
        """Parse table row element."""
        row = {
            'type': 'table_row',
            'cells': []
        }
        
        # Parse cells
        for cell in row_element.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc'):
            cell_content = self._parse_table_cell(cell)
            row['cells'].append(cell_content)
        
        return row
    
    def _parse_table_cell(self, cell_element: ET.Element) -> Dict[str, Any]:
        """Parse table cell element."""
        cell = {
            'type': 'table_cell',
            'content': []
        }
        
        # Parse cell content
        for child in cell_element:
            if child.tag.endswith('}p'):  # Paragraph
                paragraph = self._parse_paragraph(child)
                cell['content'].append(paragraph)
            elif child.tag.endswith('}tbl'):  # Nested table
                table = self._parse_table(child)
                cell['content'].append(table)
        
        return cell
    
    def _parse_run_properties(self, r_pr_element: ET.Element) -> Dict[str, Any]:
        """Parse run properties."""
        properties = {}
        
        for child in r_pr_element:
            tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            properties[tag_name] = child.get('val', '1') == '1'
        
        return properties
    
    def _parse_paragraph_properties(self, p_pr_element: ET.Element) -> Dict[str, Any]:
        """Parse paragraph properties."""
        properties = {}
        
        for child in p_pr_element:
            tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            properties[tag_name] = child.get('val', '1') == '1'
        
        return properties
    
    def _parse_table_properties(self, tbl_pr_element: ET.Element) -> Dict[str, Any]:
        """Parse table properties."""
        properties = {}
        
        for child in tbl_pr_element:
            tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            properties[tag_name] = child.get('val', '1') == '1'
        
        return properties
    
    def clear_hyperlinks(self) -> None:
        """Clear all hyperlinks."""
        self.hyperlinks.clear()
        self.hyperlink_info.clear()
        logger.debug("Hyperlinks cleared")
