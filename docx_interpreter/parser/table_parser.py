"""
Table parser for DOCX documents.

Handles table parsing, row parsing, cell parsing, and validation.
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class TableParser:
    """
    Parser for tables.
    
    Handles table parsing, row parsing, cell parsing, and validation.
    """
    
    def __init__(self, package_reader):
        """
        Initialize table parser.
        
        Args:
            package_reader: PackageReader instance for accessing table files
        """
        self.package_reader = package_reader
        self.tables = {}
        self.table_info = {}
        
        # Parse tables
        self._parse_tables()
        
        logger.debug("Table parser initialized")
    
    def parse_table(self, table_element: ET.Element) -> Dict[str, Any]:
        """
        Parse table element.
        
        Args:
            table_element: Table XML element
            
        Returns:
            Dictionary of parsed table content
        """
        table = {
            'type': 'table',
            'id': table_element.get('id', ''),
            'rows': [],
            'styles': {},
            'properties': {}
        }
        
        # Parse table rows
        for row in table_element.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr'):
            row_content = self.parse_table_row(row)
            table['rows'].append(row_content)
        
        # Parse table properties
        tbl_pr = table_element.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tblPr')
        if tbl_pr is not None:
            table['styles'] = self.parse_table_properties(tbl_pr)
        
        # Parse table grid
        tbl_grid = table_element.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tblGrid')
        if tbl_grid is not None:
            table['grid'] = self._parse_table_grid(tbl_grid)
        
        return table
    
    def parse_table_row(self, row_element: ET.Element) -> Dict[str, Any]:
        """
        Parse table row.
        
        Args:
            row_element: Table row XML element
            
        Returns:
            Dictionary of parsed row content
        """
        row = {
            'type': 'table_row',
            'cells': [],
            'styles': {},
            'properties': {}
        }
        
        # Parse row cells
        for cell in row_element.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc'):
            cell_content = self.parse_table_cell(cell)
            row['cells'].append(cell_content)
        
        # Parse row properties
        tr_pr = row_element.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}trPr')
        if tr_pr is not None:
            row['styles'] = self._parse_row_properties(tr_pr)
        
        return row
    
    def parse_table_cell(self, cell_element: ET.Element) -> Dict[str, Any]:
        """
        Parse table cell.
        
        Args:
            cell_element: Table cell XML element
            
        Returns:
            Dictionary of parsed cell content
        """
        cell = {
            'type': 'table_cell',
            'content': [],
            'styles': {},
            'properties': {}
        }
        
        # Parse cell content
        for child in cell_element:
            if child.tag.endswith('}p'):  # Paragraph
                paragraph = self._parse_paragraph(child)
                cell['content'].append(paragraph)
            elif child.tag.endswith('}tbl'):  # Nested table
                nested_table = self.parse_table(child)
                cell['content'].append(nested_table)
            elif child.tag.endswith('}drawing'):  # Drawing
                drawing = self._parse_drawing(child)
                cell['content'].append(drawing)
        
        # Parse cell properties
        tc_pr = cell_element.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tcPr')
        if tc_pr is not None:
            cell['styles'] = self._parse_cell_properties(tc_pr)
        
        return cell
    
    def parse_table_properties(self, tbl_pr_element: ET.Element) -> Dict[str, Any]:
        """
        Parse table properties.
        
        Args:
            tbl_pr_element: Table properties XML element
            
        Returns:
            Dictionary of parsed table properties
        """
        properties = {}
        
        for child in tbl_pr_element:
            tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if tag_name == 'tblW':
                # Table width
                properties['tblW'] = {
                    'w': child.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}w') or child.get('w'),
                    'type': child.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type') or child.get('type')
                }
            elif tag_name == 'jc':
                # Table alignment
                properties['jc'] = child.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val') or child.get('val')
            else:
                properties[tag_name] = child.get('val', '1') == '1'
        
        return properties
    
    def get_tables(self) -> Dict[str, Any]:
        """
        Get all tables.
        
        Returns:
            Dictionary of tables
        """
        return self.tables.copy()
    
    def get_table(self, table_id: str) -> Optional[Dict[str, Any]]:
        """
        Get specific table.
        
        Args:
            table_id: Table identifier
            
        Returns:
            Table content or None if not found
        """
        return self.tables.get(table_id)
    
    def get_table_info(self) -> Dict[str, Any]:
        """
        Get table information.
        
        Returns:
            Dictionary with table metadata
        """
        return self.table_info.copy()
    
    def get_tables_by_style(self, style_name: str) -> List[Dict[str, Any]]:
        """
        Get tables by style.
        
        Args:
            style_name: Style name to filter by
            
        Returns:
            List of tables with matching style
        """
        matching_tables = []
        for table_id, table_content in self.tables.items():
            if table_content.get('styles', {}).get('style') == style_name:
                matching_tables.append(table_content)
        return matching_tables
    
    def get_table_dimensions(self, table_id: str) -> Optional[Dict[str, int]]:
        """
        Get table dimensions.
        
        Args:
            table_id: Table identifier
            
        Returns:
            Dictionary with table dimensions or None if not found
        """
        table = self.get_table(table_id)
        if table:
            rows = len(table.get('rows', []))
            max_cols = 0
            for row in table.get('rows', []):
                cols = len(row.get('cells', []))
                max_cols = max(max_cols, cols)
            return {'rows': rows, 'columns': max_cols}
        return None
    
    def _parse_tables(self) -> None:
        """Parse tables from the document."""
        try:
            # Parse tables from document.xml
            self._parse_document_tables()
            
            # Parse tables from headers/footers
            self._parse_header_footer_tables()
            
            # Update info
            self.table_info = {
                'total_tables': len(self.tables),
                'table_ids': list(self.tables.keys())
            }
            
            logger.info(f"Parsed {len(self.tables)} tables")
            
        except Exception as e:
            logger.error(f"Failed to parse tables: {e}")
    
    def _parse_document_tables(self) -> None:
        """Parse tables from document.xml."""
        try:
            document_xml = self.package_reader.get_xml_content('word/document.xml')
            if document_xml:
                self._parse_tables_from_xml(document_xml, 'document')
        except Exception as e:
            logger.warning(f"Failed to parse document tables: {e}")
    
    def _parse_header_footer_tables(self) -> None:
        """Parse tables from headers and footers."""
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
                        self._parse_tables_from_xml(xml_content, pattern)
                except Exception:
                    # File doesn't exist, continue
                    continue
                    
        except Exception as e:
            logger.warning(f"Failed to parse header/footer tables: {e}")
    
    def _parse_tables_from_xml(self, xml_content: str, source: str) -> None:
        """Parse tables from XML content."""
        try:
            root = ET.fromstring(xml_content)
            
            for table in root.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tbl'):
                table_id = f"table_{len(self.tables) + 1}"
                table_content = self.parse_table(table)
                table_content['source'] = source
                self.tables[table_id] = table_content
                    
        except ET.ParseError as e:
            logger.error(f"Failed to parse tables from {source}: {e}")
    
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
    
    def _parse_drawing(self, drawing_element: ET.Element) -> Dict[str, Any]:
        """Parse drawing element."""
        drawing = {
            'type': 'drawing',
            'content': [],
            'styles': {}
        }
        
        # Parse drawing content
        for child in drawing_element:
            if child.tag.endswith('}anchor') or child.tag.endswith('}inline'):
                drawing['content'].append({
                    'type': 'drawing_anchor',
                    'properties': dict(child.attrib)
                })
        
        return drawing
    
    def _parse_table_grid(self, tbl_grid_element: ET.Element) -> List[Dict[str, Any]]:
        """Parse table grid."""
        grid = []
        
        for grid_col in tbl_grid_element.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}gridCol'):
            grid.append({
                'width': grid_col.get('w', '0'),
                'properties': dict(grid_col.attrib)
            })
        
        return grid
    
    def _parse_row_properties(self, tr_pr_element: ET.Element) -> Dict[str, Any]:
        """Parse row properties."""
        properties = {}
        
        for child in tr_pr_element:
            tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if tag_name == 'trHeight':
                properties['trHeight'] = {
                    'val': child.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val') or child.get('val'),
                    'hRule': child.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}hRule') or child.get('hRule')
                }
            else:
                properties[tag_name] = child.get('val', '1') == '1'
        
        return properties
    
    def _parse_cell_properties(self, tc_pr_element: ET.Element) -> Dict[str, Any]:
        """Parse cell properties."""
        properties = {}
        
        for child in tc_pr_element:
            tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            if tag_name == 'tcW':
                properties['tcW'] = {
                    'w': child.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}w') or child.get('w'),
                    'type': child.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type') or child.get('type')
                }
            elif tag_name == 'gridSpan':
                properties['gridSpan'] = child.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val') or child.get('val')
            elif tag_name == 'vMerge':
                properties['vMerge'] = child.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val') or child.get('val', 'continue')
            elif tag_name == 'vAlign':
                # Vertical alignment
                v_align_val = child.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val') or child.get('val', '')
                if v_align_val:
                    properties['vertical_align'] = v_align_val
                    properties['vAlign'] = v_align_val
            elif tag_name == 'jc':
                # Horizontal alignment (justification)
                jc_val = child.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val') or child.get('val', '')
                if jc_val:
                    properties['text_align'] = jc_val
                    properties['alignment'] = jc_val
                    properties['jc'] = jc_val
            elif tag_name == 'tcMar':
                # Cell margins (padding)
                margins = {}
                for margin in child:
                    margin_name = margin.tag.split('}')[-1]
                    margin_w = margin.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}w') or margin.get('w', '')
                    margin_type = margin.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type') or margin.get('type', '')
                    margins[margin_name] = {
                        'w': margin_w,
                        'type': margin_type
                    }
                if margins:
                    properties['margins'] = margins
            else:
                properties[tag_name] = child.get('val', '1') == '1'
        
        return properties
    
    def _parse_paragraph_properties(self, p_pr_element: ET.Element) -> Dict[str, Any]:
        """Parse paragraph properties."""
        properties = {}
        
        for child in p_pr_element:
            tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            properties[tag_name] = child.get('val', '1') == '1'
        
        return properties
    
    def _parse_run_properties(self, r_pr_element: ET.Element) -> Dict[str, Any]:
        """Parse run properties."""
        properties = {}
        
        for child in r_pr_element:
            tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            properties[tag_name] = child.get('val', '1') == '1'
        
        return properties
    
    def clear_tables(self) -> None:
        """Clear all tables."""
        self.tables.clear()
        self.table_info.clear()
        logger.debug("Tables cleared")
