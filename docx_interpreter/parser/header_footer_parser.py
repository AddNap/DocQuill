"""
Header/Footer parser for DOCX documents.

Handles header.xml parsing, footer.xml parsing, content parsing, and validation.
"""

import xml.etree.ElementTree as ET
from lxml import etree as lxml_etree
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class HeaderFooterParser:
    """
    Parser for headers and footers.
    
    Handles header/footer parsing, content parsing, and relationship discovery.
    """
    
    def __init__(self, package_reader):
        """
        Initialize header/footer parser.
        
        Args:
            package_reader: PackageReader instance for accessing header/footer files
        """
        self.package_reader = package_reader
        self.headers = {}
        self.footers = {}
        self.header_footer_info = {}
        self._current_part_path: Optional[str] = None
        self._current_relationship_file: Optional[str] = None
        
        # Parse headers and footers
        self._parse_headers_footers()
        
        logger.debug("Header/footer parser initialized")
    
    def parse_header(self, header_path: str) -> Dict[str, Any]:
        """
        Parse header from header.xml.
        
        Args:
            header_path: Path to header XML file
            
        Returns:
            Dictionary of parsed header content
        """
        try:
            xml_content = self.package_reader.get_xml_content(header_path)
            if xml_content:
                previous_part = self._current_part_path
                previous_rel = self._current_relationship_file
                self._current_part_path = header_path
                self._current_relationship_file = self._get_relationship_file_for_part(header_path)
                try:
                    return self._parse_header_xml(xml_content)
                finally:
                    self._current_part_path = previous_part
                    self._current_relationship_file = previous_rel
            else:
                logger.warning(f"No content found for header: {header_path}")
                return {'type': 'header', 'content': [], 'error': 'No content found'}
        except Exception as e:
            logger.error(f"Failed to parse header {header_path}: {e}")
            return {'type': 'header', 'content': [], 'error': str(e)}
    
    def parse_footer(self, footer_path: str) -> Dict[str, Any]:
        """
        Parse footer from footer.xml.
        
        Args:
            footer_path: Path to footer XML file
            
        Returns:
            Dictionary of parsed footer content
        """
        try:
            xml_content = self.package_reader.get_xml_content(footer_path)
            if xml_content:
                previous_part = self._current_part_path
                previous_rel = self._current_relationship_file
                self._current_part_path = footer_path
                self._current_relationship_file = self._get_relationship_file_for_part(footer_path)
                try:
                    return self._parse_footer_xml(xml_content)
                finally:
                    self._current_part_path = previous_part
                    self._current_relationship_file = previous_rel
            else:
                logger.warning(f"No content found for footer: {footer_path}")
                return {'type': 'footer', 'content': [], 'error': 'No content found'}
        except Exception as e:
            logger.error(f"Failed to parse footer {footer_path}: {e}")
            return {'type': 'footer', 'content': [], 'error': str(e)}
    
    def parse_header_footer_content(self, content_element: ET.Element) -> Dict[str, Any]:
        """
        Parse header/footer content.
        
        Args:
            content_element: Content XML element
            
        Returns:
            Dictionary of parsed content
        """
        content = {
            'type': 'content',
            'elements': [],
            'styles': {},
            'properties': {}
        }
        
        # Parse content elements
        for child in content_element:
            if child.tag.endswith('}p'):  # Paragraph
                paragraph = self._parse_paragraph(child)
                content['elements'].append(paragraph)
            elif child.tag.endswith('}tbl'):  # Table
                table = self._parse_table(child)
                content['elements'].append(table)
            elif child.tag.endswith('}drawing'):  # Drawing
                drawing = self._parse_drawing(child)
                content['elements'].append(drawing)
        
        return content
    
    def get_header_footer_relationships(self) -> Dict[str, Any]:
        """
        Get header/footer relationships.
        
        Returns:
            Dictionary of header/footer relationships
        """
        relationships = {
            'headers': {},
            'footers': {},
            'total_headers': len(self.headers),
            'total_footers': len(self.footers)
        }
        
        # Get header relationships
        for header_id, header_content in self.headers.items():
            relationships['headers'][header_id] = {
                'content_type': header_content.get('type', 'header'),
                'content_count': len(header_content.get('content', [])),
                'has_styles': bool(header_content.get('styles', {}))
            }
        
        # Get footer relationships
        for footer_id, footer_content in self.footers.items():
            relationships['footers'][footer_id] = {
                'content_type': footer_content.get('type', 'footer'),
                'content_count': len(footer_content.get('content', [])),
                'has_styles': bool(footer_content.get('styles', {}))
            }
        
        return relationships
    
    def get_headers(self) -> Dict[str, Any]:
        """
        Get all headers.
        
        Returns:
            Dictionary of headers
        """
        return self.headers.copy()
    
    def get_footers(self) -> Dict[str, Any]:
        """
        Get all footers.
        
        Returns:
            Dictionary of footers
        """
        return self.footers.copy()
    
    def get_header(self, header_id: str) -> Optional[Dict[str, Any]]:
        """
        Get specific header.
        
        Args:
            header_id: Header identifier
            
        Returns:
            Header content or None if not found
        """
        return self.headers.get(header_id)
    
    def get_footer(self, footer_id: str) -> Optional[Dict[str, Any]]:
        """
        Get specific footer.
        
        Args:
            footer_id: Footer identifier
            
        Returns:
            Footer content or None if not found
        """
        return self.footers.get(footer_id)
    
    def get_header_footer_info(self) -> Dict[str, Any]:
        """
        Get header/footer information.
        
        Returns:
            Dictionary with header/footer metadata
        """
        return self.header_footer_info.copy()
    
    def _parse_headers_footers(self) -> None:
        """Parse headers and footers from the package."""
        try:
            # Find header/footer files
            header_footer_files = self._discover_header_footer_files()
            
            for file_path, file_type in header_footer_files:
                try:
                    xml_content = self.package_reader.get_xml_content(file_path)
                    if xml_content:
                        previous_part = self._current_part_path
                        previous_rel = self._current_relationship_file
                        self._current_part_path = file_path
                        self._current_relationship_file = self._get_relationship_file_for_part(file_path)
                        if file_type == 'header':
                            header_id = self._extract_header_id(file_path)
                            header_content = self._parse_header_xml(xml_content)
                            self.headers[header_id] = header_content
                        elif file_type == 'footer':
                            footer_id = self._extract_footer_id(file_path)
                            footer_content = self._parse_footer_xml(xml_content)
                            self.footers[footer_id] = footer_content
                        self._current_part_path = previous_part
                        self._current_relationship_file = previous_rel
                            
                except Exception as e:
                    logger.warning(f"Failed to parse {file_path}: {e}")
            
            # Update info
            self.header_footer_info = {
                'total_headers': len(self.headers),
                'total_footers': len(self.footers),
                'header_ids': list(self.headers.keys()),
                'footer_ids': list(self.footers.keys())
            }
            
            logger.info(f"Parsed {len(self.headers)} headers and {len(self.footers)} footers")
            
        except Exception as e:
            logger.error(f"Failed to parse headers/footers: {e}")
    
    def _discover_header_footer_files(self) -> List[Tuple[str, str]]:
        """Discover header and footer files in the package."""
        files = []
        
        # Common header/footer patterns
        patterns = [
            ('word/header1.xml', 'header'),
            ('word/header2.xml', 'header'),
            ('word/header3.xml', 'header'),
            ('word/footer1.xml', 'footer'),
            ('word/footer2.xml', 'footer'),
            ('word/footer3.xml', 'footer')
        ]
        
        for pattern, file_type in patterns:
            try:
                # Check if file exists by trying to get content
                content = self.package_reader.get_xml_content(pattern)
                if content:
                    files.append((pattern, file_type))
            except Exception:
                # File doesn't exist, continue
                continue
        
        return files
    
    def _extract_header_id(self, file_path: str) -> str:
        """Extract header ID from file path."""
        filename = Path(file_path).stem
        return filename.replace('header', 'header_')
    
    def _extract_footer_id(self, file_path: str) -> str:
        """Extract footer ID from file path."""
        filename = Path(file_path).stem
        return filename.replace('footer', 'footer_')

    def _get_relationship_file_for_part(self, file_path: str) -> Optional[str]:
        """Build the relationship file path for a given header/footer part."""
        try:
            part_path = Path(file_path)
            rel_dir = part_path.parent / "_rels"
            rel_file = rel_dir / f"{part_path.name}.rels"
            return rel_file.as_posix()
        except Exception:
            return None
    
    def _parse_header_xml(self, xml_content: str) -> Dict[str, Any]:
        """Parse header XML content."""
        try:
            root = ET.fromstring(xml_content)
            return self.parse_header_footer_content(root)
        except ET.ParseError as e:
            logger.error(f"Failed to parse header XML: {e}")
            return {'type': 'header', 'content': [], 'error': str(e)}
    
    def _parse_footer_xml(self, xml_content: str) -> Dict[str, Any]:
        """Parse footer XML content."""
        try:
            root = ET.fromstring(xml_content)
            return self.parse_header_footer_content(root)
        except ET.ParseError as e:
            logger.error(f"Failed to parse footer XML: {e}")
            return {'type': 'footer', 'content': [], 'error': str(e)}
    
    def _parse_paragraph(self, paragraph_element: ET.Element) -> Dict[str, Any]:
        """Parse paragraph element."""
        paragraph = {
            'type': 'paragraph',
            'runs': [],
            'styles': {},
            'fields': [],  # Fields at paragraph level (fldSimple directly in paragraph)
            'vml_shapes': []  # VML shapes (watermarks)
        }
        
        # Parse field codes directly in paragraph (fldSimple at paragraph level)
        para_field_elements = paragraph_element.findall('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}fldSimple')
        for field_elem in para_field_elements:
            field_instr = field_elem.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}instr', '')
            if not field_instr:
                field_instr = field_elem.get('instr', '')
            field_result = ""
            field_text_elem = field_elem.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
            if field_text_elem is not None and field_text_elem.text:
                field_result = field_text_elem.text
            paragraph['fields'].append({
                'type': 'field',
                'instr': field_instr,
                'result': field_result
            })
        
        # Parse w:pict elements (VML shapes, often watermarks)
        ns_v = {'v': 'urn:schemas-microsoft-com:vml'}
        pict_elements = paragraph_element.findall('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pict')
        for pict_elem in pict_elements:
            vml_shape = self._parse_vml_pict(pict_elem)
            if vml_shape:
                paragraph['vml_shapes'].append(vml_shape)
        
        # Parse runs
        for run in paragraph_element.findall('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r'):
            # Skip runs inside textboxes to avoid duplication
            if self._is_run_inside_textbox(run):
                continue
            run_content = self._parse_run(run)
            paragraph['runs'].append(run_content)
        
        # Parse paragraph properties
        p_pr = paragraph_element.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pPr')
        if p_pr is not None:
            paragraph['styles'] = self._parse_paragraph_properties(p_pr)
        
        return paragraph
    
    def _is_run_inside_textbox(self, run_element: ET.Element) -> bool:
        """
        Check if run is inside a textbox to avoid duplication.
        
        Args:
            run_element: Run XML element
            
        Returns:
            True if run is inside textbox, False otherwise
        """
        # Check if run is inside txbxContent by checking parent tags
        parent = run_element
        while parent is not None:
            tag = parent.tag
            if any(x in tag for x in ('txbxContent', 'wps:txbx', 'v:textbox')):
                return True
            # Try to get parent - use getparent if available (lxml), otherwise None
            parent = getattr(parent, 'getparent', lambda: None)() or None
        return False
    
    def _parse_run(self, run_element: ET.Element) -> Dict[str, Any]:
        """Parse run element."""
        run = {
            'type': 'run',
            'text': '',
            'styles': {},
            'drawings': []
        }
        
        # Parse drawing elements first
        has_textbox = False
        drawing_elements = run_element.findall('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing')
        for drawing_elem in drawing_elements:
            drawing = self._parse_drawing(drawing_elem)
            run['drawings'].append(drawing)
            # Check if this drawing has textbox content
            for content in drawing.get('content', []):
                if content.get('type') == 'drawing_anchor' and content.get('textbox_content'):
                    has_textbox = True
                    break
        
        # Check for AlternateContent in run (not in drawing)
        alt_content = run_element.find('.//{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent')
        if alt_content is not None:
            # Use Choice if available, otherwise Fallback
            choice = alt_content.find('.//{http://schemas.openxmlformats.org/markup-compatibility/2006}Choice')
            if choice is not None:
                textbox_node = choice.find('.//{http://schemas.microsoft.com/office/word/2010/wordprocessingShape}txbx')
            else:
                fallback = alt_content.find('.//{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback')
                if fallback is not None:
                    textbox_node = fallback.find('.//{urn:schemas-microsoft-com:vml}textbox')
                else:
                    textbox_node = None
            
            if textbox_node is not None:
                textbox_content = self._parse_textbox_content(textbox_node)
                if textbox_content:
                    # Add textbox content to run
                    run['textbox'] = textbox_content
                    has_textbox = True
        
        # Parse field codes (fldSimple) - fields in headers/footers
        field_elements = run_element.findall('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}fldSimple')
        if field_elements:
            if 'fields' not in run:
                run['fields'] = []
            for field_elem in field_elements:
                field_instr = field_elem.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}instr', '')
                if not field_instr:
                    field_instr = field_elem.get('instr', '')
                # Get field result text
                field_result = ""
                field_text_elem = field_elem.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
                if field_text_elem is not None and field_text_elem.text:
                    field_result = field_text_elem.text
                run['fields'].append({
                    'type': 'field',
                    'instr': field_instr,
                    'result': field_result
                })
        
        # Parse text - but skip if run has textbox to avoid duplication
        if not has_textbox:
            text_elements = run_element.findall('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t')
            for text_elem in text_elements:
                run['text'] += text_elem.text or ''
        
        # Parse run properties
        r_pr = run_element.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr')
        if r_pr is not None:
            run['styles'] = self._parse_run_properties(r_pr)
        
        return run
    
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
            'cells': [],
            'styles': {}
        }
        
        # Parse row properties
        tr_pr = row_element.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}trPr')
        if tr_pr is not None:
            row['styles'] = self._parse_table_row_properties(tr_pr)
        
        # Parse cells
        for cell in row_element.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc'):
            cell_content = self._parse_table_cell(cell)
            row['cells'].append(cell_content)
        
        return row
    
    def _parse_table_cell(self, cell_element: ET.Element) -> Dict[str, Any]:
        """Parse table cell element."""
        cell = {
            'type': 'table_cell',
            'content': [],
            'styles': {}
        }
        
        # Parse cell properties
        tc_pr = cell_element.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tcPr')
        if tc_pr is not None:
            cell['styles'] = self._parse_table_cell_properties(tc_pr)
        
        # Parse cell content
        for child in cell_element:
            if child.tag.endswith('}p'):  # Paragraph
                paragraph = self._parse_paragraph(child)
                cell['content'].append(paragraph)
            elif child.tag.endswith('}tbl'):  # Nested table
                table = self._parse_table(child)
                cell['content'].append(table)
            elif child.tag.endswith('}sdt'):  # Structured Document Tag inside cell
                # Extract content from sdtContent
                sdt_content = child.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sdtContent')
                if sdt_content is not None:
                    for sc_child in sdt_content:
                        if sc_child.tag.endswith('}p'):
                            paragraph = self._parse_paragraph(sc_child)
                            cell['content'].append(paragraph)
                        elif sc_child.tag.endswith('}drawing'):
                            drawing = self._parse_drawing(sc_child)
                            cell['content'].append(drawing)
                        elif sc_child.tag.endswith('}tbl'):
                            table = self._parse_table(sc_child)
                            cell['content'].append(table)
        
        return cell
    
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
                anchor_info = {
                    'type': 'drawing_anchor',
                    'anchor_type': 'anchor' if child.tag.endswith('}anchor') else 'inline',
                    'properties': dict(child.attrib)
                }

                try:
                    anchor_info['raw_xml'] = ET.tostring(child, encoding='unicode')
                except Exception:
                    anchor_info['raw_xml'] = None

                # Extract extent and positioning info for anchor computations
                if child.tag.endswith('}anchor'):
                    # Extract z-order (behindDoc attribute)
                    behind_doc = child.get('{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}behindDoc')
                    if behind_doc == '1' or behind_doc == 'true':
                        anchor_info['z_order'] = 'behind'  # Render behind text
                    else:
                        anchor_info['z_order'] = 'front'  # Render in front of text (default)
                    
                    pos_h = child.find('{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}positionH')
                    pos_v = child.find('{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}positionV')
                    position: Dict[str, Any] = {}
                    if pos_h is not None:
                        rel = pos_h.get('relativeFrom') or pos_h.get('{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}relativeFrom')
                        if rel:
                            position['x_rel'] = rel
                        offset = pos_h.find('{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}posOffset')
                        if offset is not None and offset.text:
                            try:
                                position['x'] = int(offset.text)
                            except ValueError:
                                position['x'] = 0
                    if pos_v is not None:
                        rel = pos_v.get('relativeFrom') or pos_v.get('{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}relativeFrom')
                        if rel:
                            position['y_rel'] = rel
                        offset = pos_v.find('{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}posOffset')
                        if offset is not None and offset.text:
                            try:
                                position['y'] = int(offset.text)
                            except ValueError:
                                position['y'] = 0
                    if position:
                        anchor_info['position'] = position
                else:
                    # Inline images are always in front of text
                    anchor_info['z_order'] = 'front'
                
                # Try to find relationship ID for image
                blip = child.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}blip')
                if blip is not None:
                    r_embed = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                    if r_embed:
                        anchor_info['relationship_id'] = r_embed
                        anchor_info['relationship_source'] = getattr(self, '_current_relationship_file', None)
                        anchor_info['part_path'] = getattr(self, '_current_part_path', None)
                        
                        # Get image path from relationship if there is rel_id
                        try:
                            relationship_source = anchor_info['relationship_source']
                            if not relationship_source:
                                # Try to build relationship_source from part_path
                                part_path = anchor_info.get('part_path')
                                if part_path:
                                    # Build path to relationship file
                                    from pathlib import Path
                                    part_path_obj = Path(part_path)
                                    rel_dir = part_path_obj.parent / "_rels"
                                    rel_file = rel_dir / f"{part_path_obj.name}.rels"
                                    relationship_source = str(rel_file)
                            
                            if relationship_source:
                                # Get relationships for this source
                                # relationship_source is path to .rels file, e.g. "word/_rels/footer1...
                                # package_reader przechowuje relationships z kluczami jak "word/_rels/footer1.xml.rels"
                                # So we can use relationship_source directly as key
                                relationships = self.package_reader.get_relationships(relationship_source)
                                if relationships and r_embed in relationships:
                                    rel_data = relationships[r_embed]
                                    rel_target = rel_data.get("target", "")
                                    if rel_target:
                                        # Get full path to image
                                        # rel_target is relative path in DOCX, e.g. "media/image2.jpeg"
                                        # We need to build full path in extracted directory
                                        # Images are in word/media/, so we need to add "word/" before rel_target
                                        from pathlib import Path
                                        extract_to = self.package_reader.extract_to
                                        # rel_target may already have "word/" or not
                                        if rel_target.startswith("word/"):
                                            image_path = Path(extract_to) / rel_target
                                        else:
                                            image_path = Path(extract_to) / "word" / rel_target
                                        if image_path.exists():
                                            anchor_info['path'] = str(image_path)
                                            anchor_info['image_path'] = str(image_path)
                                            logger.debug(f"Pobrano ścieżkę obrazu z relationship: {image_path}")
                                        else:
                                            logger.debug(f"Obraz nie istnieje: {image_path}")
                        except Exception as e:
                            logger.debug(f"Nie udało się pobrać ścieżki obrazu z rel_id {r_embed}: {e}")
                
                # Check for textbox content - handle AlternateContent properly
                textbox_node = None
                
                # First check for AlternateContent
                alt_content = child.find('.//{http://schemas.openxmlformats.org/markup-compatibility/2006}AlternateContent')
                if alt_content is not None:
                    # Use Choice if available, otherwise Fallback
                    choice = alt_content.find('.//{http://schemas.openxmlformats.org/markup-compatibility/2006}Choice')
                    if choice is not None:
                        textbox_node = choice.find('.//{http://schemas.microsoft.com/office/word/2010/wordprocessingShape}txbx')
                    else:
                        fallback = alt_content.find('.//{http://schemas.openxmlformats.org/markup-compatibility/2006}Fallback')
                        if fallback is not None:
                            textbox_node = fallback.find('.//{urn:schemas-microsoft-com:vml}textbox')
                else:
                    # No AlternateContent, try both formats directly
                    textbox_node = child.find('.//{http://schemas.microsoft.com/office/word/2010/wordprocessingShape}txbx') or child.find('.//{urn:schemas-microsoft-com:vml}textbox')
                
                if textbox_node is not None:
                    textbox_content = self._parse_textbox_content(textbox_node)
                    if textbox_content:
                        anchor_info['textbox_content'] = textbox_content
                
                # Get dimensions
                extent = child.find('.//{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}extent')
                if extent is not None:
                    anchor_info['width'] = extent.get('cx', '0')
                    anchor_info['height'] = extent.get('cy', '0')
                
                drawing['content'].append(anchor_info)
        
        return drawing
    
    def _parse_textbox_content(self, textbox_node: ET.Element) -> List[Dict[str, Any]]:
        """Parse textbox content and return list of paragraph dictionaries."""
        try:
            paragraphs = []
            
            # Find txbxContent element
            txbx_content = textbox_node.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}txbxContent')
            if txbx_content is None:
                return paragraphs
            
            # Parse paragraphs in txbxContent
            for p_elem in txbx_content.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
                paragraph = self._parse_paragraph(p_elem)
                if paragraph:
                    paragraphs.append(paragraph)
            
            return paragraphs
        except Exception as e:
            logger.error(f"Failed to parse textbox content: {e}")
            return []
    
    def _parse_paragraph_properties(self, p_pr_element: ET.Element) -> Dict[str, Any]:
        """Parse paragraph properties with detailed information."""
        properties = {}
        
        try:
            for child in p_pr_element:
                tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag

                if tag_name == 'jc':
                    # Paragraph alignment
                    properties['alignment'] = child.get('val', 'left')
                elif tag_name == 'spacing':
                    # Paragraph spacing
                    spacing = {}
                    for attr in ['before', 'after', 'line', 'lineRule']:
                        val = child.get(attr)
                        if val:
                            spacing[attr] = val
                    if spacing:
                        properties['spacing'] = spacing
                elif tag_name == 'ind':
                    # Paragraph indentation
                    indent = {}
                    for attr in ['left', 'right', 'firstLine', 'hanging']:
                        val = child.get(attr)
                        if val:
                            indent[attr] = val
                    if indent:
                        properties['indent'] = indent
                elif tag_name == 'pBdr':
                    # Paragraph borders
                    borders = {}
                    for border in child:
                        border_name = border.tag.split('}')[-1]
                        borders[border_name] = {
                            'val': border.get('val', ''),
                            'sz': border.get('sz', ''),
                            'space': border.get('space', ''),
                            'color': border.get('color', ''),
                            'themeColor': border.get('themeColor', ''),
                            'themeTint': border.get('themeTint', ''),
                            'themeShade': border.get('themeShade', '')
                        }
                    if borders:
                        properties['borders'] = borders
                elif tag_name == 'shd':
                    # Paragraph shading/background
                    properties['shading'] = {
                        'val': child.get('val', ''),
                        'color': child.get('color', ''),
                        'fill': child.get('fill', ''),
                        'themeColor': child.get('themeColor', ''),
                        'themeTint': child.get('themeTint', ''),
                        'themeShade': child.get('themeShade', '')
                    }
                elif tag_name == 'effect':
                    # Paragraph effects (shadow, outline, etc.)
                    properties['effect'] = {
                        'val': child.get('val', ''),
                        'color': child.get('color', ''),
                        'themeColor': child.get('themeColor', ''),
                        'themeTint': child.get('themeTint', ''),
                        'themeShade': child.get('themeShade', '')
                    }
                elif tag_name == 'outline':
                    # Paragraph outline
                    properties['outline'] = {
                        'val': child.get('val', ''),
                        'color': child.get('color', ''),
                        'themeColor': child.get('themeColor', ''),
                        'themeTint': child.get('themeTint', ''),
                        'themeShade': child.get('themeShade', '')
                    }
                elif tag_name == 'shadow':
                    # Paragraph shadow
                    properties['shadow'] = {
                        'val': child.get('val', ''),
                        'color': child.get('color', ''),
                        'themeColor': child.get('themeColor', ''),
                        'themeTint': child.get('themeTint', ''),
                        'themeShade': child.get('themeShade', '')
                    }
                elif tag_name == 'highlight':
                    # Paragraph highlight
                    properties['highlight'] = {
                        'val': child.get('val', ''),
                        'color': child.get('color', ''),
                        'themeColor': child.get('themeColor', ''),
                        'themeTint': child.get('themeTint', ''),
                        'themeShade': child.get('themeShade', '')
                    }
                else:
                    # Default: just mark as present
                    properties[tag_name] = True
        except Exception as e:
            logger.error(f"Failed to parse paragraph properties: {e}")
        
        return properties
    
    def _parse_run_properties(self, r_pr_element: ET.Element) -> Dict[str, Any]:
        """Parse run properties with detailed information."""
        properties = {}
        
        try:
            for child in r_pr_element:
                tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag

                if tag_name == 'rFonts':
                    # Run fonts
                    fonts = {}
                    for attr in ['ascii', 'hAnsi', 'cs', 'eastAsia']:
                        val = child.get(attr)
                        if val:
                            fonts[attr] = val
                    if fonts:
                        properties['fonts'] = fonts
                elif tag_name == 'sz':
                    # Font size
                    properties['size'] = child.get('val', '')
                elif tag_name == 'szCs':
                    # Font size for complex scripts
                    properties['sizeCs'] = child.get('val', '')
                elif tag_name == 'b':
                    # Bold - check val attribute (may be "true", "false", "1", "0", or missing...)
                    val_attr = child.get('val', '')
                    if val_attr in ('false', '0', 'off'):
                        properties['bold'] = False
                    else:
                        # Default True if there is <w:b/> without val or val="true"/"1"
                        properties['bold'] = True
                elif tag_name == 'i':
                    # Italic
                    properties['italic'] = True
                elif tag_name == 'u':
                    # Underline
                    properties['underline'] = {
                        'val': child.get('val', ''),
                        'color': child.get('color', ''),
                        'themeColor': child.get('themeColor', ''),
                        'themeTint': child.get('themeTint', ''),
                        'themeShade': child.get('themeShade', '')
                    }
                elif tag_name == 'strike':
                    # Strikethrough
                    properties['strikethrough'] = True
                elif tag_name == 'dstrike':
                    # Double strikethrough
                    properties['double_strikethrough'] = True
                elif tag_name == 'vertAlign':
                    # Vertical alignment (superscript, subscript)
                    properties['vertical_align'] = child.get('val', '')
                elif tag_name == 'color':
                    # Text color
                    properties['color'] = {
                        'val': child.get('val', ''),
                        'themeColor': child.get('themeColor', ''),
                        'themeTint': child.get('themeTint', ''),
                        'themeShade': child.get('themeShade', '')
                    }
                elif tag_name == 'highlight':
                    # Text highlight
                    properties['highlight'] = {
                        'val': child.get('val', ''),
                        'color': child.get('color', ''),
                        'themeColor': child.get('themeColor', ''),
                        'themeTint': child.get('themeTint', ''),
                        'themeShade': child.get('themeShade', '')
                    }
                elif tag_name == 'shd':
                    # Run shading/background
                    properties['shading'] = {
                        'val': child.get('val', ''),
                        'color': child.get('color', ''),
                        'fill': child.get('fill', ''),
                        'themeColor': child.get('themeColor', ''),
                        'themeTint': child.get('themeTint', ''),
                        'themeShade': child.get('themeShade', '')
                    }
                elif tag_name == 'effect':
                    # Run effects (shadow, outline, etc.)
                    properties['effect'] = {
                        'val': child.get('val', ''),
                        'color': child.get('color', ''),
                        'themeColor': child.get('themeColor', ''),
                        'themeTint': child.get('themeTint', ''),
                        'themeShade': child.get('themeShade', '')
                    }
                elif tag_name == 'outline':
                    # Run outline
                    properties['outline'] = {
                        'val': child.get('val', ''),
                        'color': child.get('color', ''),
                        'themeColor': child.get('themeColor', ''),
                        'themeTint': child.get('themeTint', ''),
                        'themeShade': child.get('themeShade', '')
                    }
                elif tag_name == 'shadow':
                    # Run shadow
                    properties['shadow'] = {
                        'val': child.get('val', ''),
                        'color': child.get('color', ''),
                        'themeColor': child.get('themeColor', ''),
                        'themeTint': child.get('themeTint', ''),
                        'themeShade': child.get('themeShade', '')
                    }
                elif tag_name == 'emboss':
                    # Embossed text
                    properties['emboss'] = True
                elif tag_name == 'imprint':
                    # Imprinted text
                    properties['imprint'] = True
                elif tag_name == 'noProof':
                    # No proofing
                    properties['no_proof'] = True
                elif tag_name == 'webHidden':
                    # Hidden in web view
                    properties['web_hidden'] = True
                else:
                    # Default: just mark as present
                    properties[tag_name] = True
        except Exception as e:
            logger.error(f"Failed to parse run properties: {e}")
        
        return properties
    
    def _parse_table_properties(self, tbl_pr_element: ET.Element) -> Dict[str, Any]:
        """Parse table properties with detailed information."""
        properties = {}
        
        try:
            for child in tbl_pr_element:
                tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag

                if tag_name == 'tblStyle':
                    # Table style
                    properties['style'] = child.get('val', '')
                elif tag_name == 'tblW':
                    # Table width
                    properties['width'] = {
                        'type': child.get('type', ''),
                        'w': child.get('w', '')
                    }
                elif tag_name == 'jc':
                    # Table alignment
                    properties['alignment'] = child.get('val', '')
                elif tag_name == 'tblInd':
                    # Table indentation
                    properties['indent'] = {
                        'type': child.get('type', ''),
                        'w': child.get('w', '')
                    }
                elif tag_name == 'tblLayout':
                    # Table layout (auto/fixed)
                    properties['layout'] = child.get('type', '')
                elif tag_name == 'tblCellMar':
                    # Cell margins
                    cell_margins = {}
                    for margin in child:
                        margin_name = margin.tag.split('}')[-1]
                        cell_margins[margin_name] = {
                            'type': margin.get('type', ''),
                            'w': margin.get('w', '')
                        }
                    if cell_margins:
                        properties['cell_margins'] = cell_margins
                elif tag_name == 'tblLook':
                    # Table look properties
                    properties['look'] = {
                        'val': child.get('val', ''),
                        'firstRow': child.get('firstRow', ''),
                        'lastRow': child.get('lastRow', ''),
                        'firstColumn': child.get('firstColumn', ''),
                        'lastColumn': child.get('lastColumn', ''),
                        'noHBand': child.get('noHBand', ''),
                        'noVBand': child.get('noVBand', '')
                    }
                elif tag_name == 'tblBorders':
                    # Table borders
                    borders = {}
                    for border in child:
                        border_name = border.tag.split('}')[-1]
                        borders[border_name] = {
                            'val': border.get('val', ''),
                            'sz': border.get('sz', ''),
                            'space': border.get('space', ''),
                            'color': border.get('color', '')
                        }
                    if borders:
                        properties['borders'] = borders
                elif tag_name == 'tblCellSpacing':
                    # Cell spacing
                    properties['cell_spacing'] = {
                        'type': child.get('type', ''),
                        'w': child.get('w', '')
                    }
                elif tag_name == 'tblShd':
                    # Table shading
                    properties['shading'] = {
                        'val': child.get('val', ''),
                        'color': child.get('color', ''),
                        'fill': child.get('fill', '')
                    }
                elif tag_name == 'cantSplit':
                    # Can't split rows across pages
                    properties['cant_split'] = True
                elif tag_name == 'tblHeader':
                    # Repeat header rows
                    properties['header_repeat'] = True
                else:
                    # Default: just mark as present
                    properties[tag_name] = True
        except Exception as e:
            logger.error(f"Failed to parse table properties: {e}")
        
        return properties
    
    def _parse_table_row_properties(self, tr_pr_element: ET.Element) -> Dict[str, Any]:
        """Parse table row properties."""
        properties = {}
        
        try:
            for child in tr_pr_element:
                tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                
                if tag_name == 'trHeight':
                    # Row height
                    properties['height'] = {
                        'val': child.get('val', ''),
                        'hRule': child.get('hRule', '')
                    }
                elif tag_name == 'cantSplit':
                    # Can't split row across pages
                    properties['cant_split'] = True
                elif tag_name == 'tblHeader':
                    # Header row
                    properties['header'] = True
                elif tag_name == 'repeat':
                    # Repeat header row
                    properties['repeat'] = True
                elif tag_name == 'trShd':
                    # Row shading
                    properties['shading'] = {
                        'val': child.get('val', ''),
                        'color': child.get('color', ''),
                        'fill': child.get('fill', '')
                    }
                else:
                    # Default: just mark as present
                    properties[tag_name] = True
        except Exception as e:
            logger.error(f"Failed to parse table row properties: {e}")
        
        return properties
    
    def _parse_table_cell_properties(self, tc_pr_element: ET.Element) -> Dict[str, Any]:
        """Parse table cell properties."""
        properties = {}
        
        try:
            for child in tc_pr_element:
                tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                
                if tag_name == 'tcW':
                    # Cell width
                    properties['width'] = {
                        'type': child.get('type', ''),
                        'w': child.get('w', '')
                    }
                elif tag_name == 'gridSpan':
                    # Column span
                    properties['grid_span'] = child.get('val', '1')
                elif tag_name == 'vMerge':
                    # Vertical merge
                    properties['vertical_merge'] = child.get('val', 'restart')
                elif tag_name == 'tcBorders':
                    # Cell borders
                    borders = {}
                    for border in child:
                        border_name = border.tag.split('}')[-1]
                        borders[border_name] = {
                            'val': border.get('val', ''),
                            'sz': border.get('sz', ''),
                            'space': border.get('space', ''),
                            'color': border.get('color', '')
                        }
                    if borders:
                        properties['borders'] = borders
                elif tag_name == 'tcShd':
                    # Cell shading
                    properties['shading'] = {
                        'val': child.get('val', ''),
                        'color': child.get('color', ''),
                        'fill': child.get('fill', '')
                    }
                elif tag_name == 'vAlign':
                    # Vertical alignment
                    properties['vertical_align'] = child.get('val', '')
                elif tag_name == 'jc':
                    # Horizontal alignment (justification)
                    jc_val = child.get('val', '')
                    if jc_val:
                        properties['text_align'] = jc_val
                        properties['alignment'] = jc_val
                        properties['jc'] = jc_val
                elif tag_name == 'textDirection':
                    # Text direction
                    properties['text_direction'] = child.get('val', '')
                elif tag_name == 'tcMar':
                    # Cell margins (padding) - w:tcMar contains w:top, w:left, w:bottom, w:right
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
                    # Default: just mark as present
                    properties[tag_name] = True
        except Exception as e:
            logger.error(f"Failed to parse table cell properties: {e}")
        
        return properties
    
    def _parse_vml_pict(self, pict_node: ET.Element) -> Optional[Dict[str, Any]]:
        """
        Parse VML pict element (legacy format, often used for watermarks).
        
        Args:
            pict_node: w:pict XML element
            
        Returns:
            Dictionary with VML shape data or None
        """
        try:
            ns_v = {'v': 'urn:schemas-microsoft-com:vml'}
            # Find v:shape element
            vml_shape = pict_node.find(".//v:shape", ns_v)
            if vml_shape is None:
                return None
            
            vml_data = {
                "type": "vml_shape",
                "shape_type": "vml",
                "properties": {},
                "text_content": "",
                "position": {},
                "size": {},
                "is_watermark": False,
            }
            
            # Get VML properties
            shape_id = vml_shape.get("id", "")
            style = vml_shape.get("style", "")
            rotation = vml_shape.get("rotation", "")
            fillcolor = vml_shape.get("fillcolor", "")
            
            # Check if this is a watermark (PowerPlusWaterMarkObject or similar)
            if "PowerPlusWaterMarkObject" in shape_id or "WaterMark" in shape_id:
                vml_data["is_watermark"] = True
            
            # Parse style for positioning and size
            if style:
                vml_data["properties"]["style"] = style
                # Extract position and size from style (e.g., "position:absolute; margin-left:0; margin-top:0; width:468pt; height:117pt")
                style_parts = style.split(";")
                for part in style_parts:
                    part = part.strip()
                    if ":" in part:
                        key, value = part.split(":", 1)
                        key = key.strip().lower()
                        value = value.strip()
                        if key == "width":
                            # Convert pt to points (already in points)
                            try:
                                vml_data["size"]["width"] = float(value.replace("pt", "").strip())
                            except (ValueError, TypeError):
                                pass
                        elif key == "height":
                            try:
                                vml_data["size"]["height"] = float(value.replace("pt", "").strip())
                            except (ValueError, TypeError):
                                pass
                        elif key == "position" and value == "absolute":
                            vml_data["position"]["absolute"] = True
                            vml_data["is_watermark"] = True  # Absolute positioning often indicates watermark
            
            # Parse VML text content (v:textpath)
            textpath = vml_shape.find(".//v:textpath", ns_v)
            if textpath is not None:
                text_string = textpath.get("string", "")
                if text_string:
                    vml_data["text_content"] = text_string
                elif textpath.text:
                    vml_data["text_content"] = textpath.text
            
            # Parse font properties from textpath
            if textpath is not None:
                textpath_style = textpath.get("style", "")
                if textpath_style:
                    vml_data["properties"]["textpath_style"] = textpath_style
                    # Extract font-family and font-size
                    style_parts = textpath_style.split(";")
                    for part in style_parts:
                        part = part.strip()
                        if ":" in part:
                            key, value = part.split(":", 1)
                            key = key.strip().lower()
                            value = value.strip()
                            if key == "font-family":
                                vml_data["properties"]["font_name"] = value.strip("'\"")
                            elif key == "font-size":
                                try:
                                    # Convert to points (e.g., "1in" = 72pt)
                                    if value.endswith("in"):
                                        vml_data["properties"]["font_size"] = float(value.replace("in", "").strip()) * 72.0
                                    elif value.endswith("pt"):
                                        vml_data["properties"]["font_size"] = float(value.replace("pt", "").strip())
                                    else:
                                        vml_data["properties"]["font_size"] = float(value)
                                except (ValueError, TypeError):
                                    pass
            
            # Store rotation and fillcolor
            if rotation:
                try:
                    vml_data["properties"]["rotation"] = float(rotation)
                except (ValueError, TypeError):
                    pass
            if fillcolor:
                vml_data["properties"]["fillcolor"] = fillcolor
            
            # Store raw XML
            try:
                vml_data["raw_xml"] = ET.tostring(pict_node, encoding='unicode', method='xml')
            except Exception:
                vml_data["raw_xml"] = None
            
            return vml_data
            
        except Exception as e:
            logger.error(f"Failed to parse VML pict: {e}", exc_info=True)
            return None
    
    def clear_headers_footers(self) -> None:
        """Clear all headers and footers."""
        self.headers.clear()
        self.footers.clear()
        self.header_footer_info.clear()
        logger.debug("Headers and footers cleared")
