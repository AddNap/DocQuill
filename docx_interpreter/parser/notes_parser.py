"""
Notes parser for DOCX documents.

Handles footnotes.xml parsing, endnotes.xml parsing, note content parsing, and validation.
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class NotesParser:
    """
    Parser for footnotes and endnotes.
    
    Handles notes parsing, content parsing, and validation.
    """
    
    def __init__(self, package_reader):
        """
        Initialize notes parser.
        
        Args:
            package_reader: PackageReader instance for accessing notes files
        """
        self.package_reader = package_reader
        self.footnotes = {}
        self.endnotes = {}
        self.notes_info = {}
        
        # Parse notes
        self._parse_notes()
        
        logger.debug("Notes parser initialized")
    
    def parse_footnotes(self) -> Dict[str, Any]:
        """
        Parse footnotes from footnotes.xml.
        
        Returns:
            Dictionary of parsed footnotes
        """
        return self.footnotes.copy()
    
    def parse_endnotes(self) -> Dict[str, Any]:
        """
        Parse endnotes from endnotes.xml.
        
        Returns:
            Dictionary of parsed endnotes
        """
        return self.endnotes.copy()
    
    def parse_note(self, note_element: ET.Element) -> Dict[str, Any]:
        """
        Parse individual note.
        
        Args:
            note_element: Note XML element
            
        Returns:
            Dictionary of parsed note content
        """
        ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        note_id = note_element.get(f'{{{ns}}}id', '') or note_element.get('id', '')
        
        note = {
            'type': 'note',
            'id': note_id,
            'content': [],
            'styles': {},
            'properties': {}
        }
        
        # Parse note content
        for child in note_element:
            if child.tag.endswith('}p'):  # Paragraph
                paragraph = self._parse_paragraph(child)
                note['content'].append(paragraph)
            elif child.tag.endswith('}tbl'):  # Table
                table = self._parse_table(child)
                note['content'].append(table)
            elif child.tag.endswith('}drawing'):  # Drawing
                drawing = self._parse_drawing(child)
                note['content'].append(drawing)
        
        return note
    
    def get_note_by_id(self, note_id: str) -> Optional[Dict[str, Any]]:
        """
        Get note by ID.
        
        Args:
            note_id: Note identifier
            
        Returns:
            Note content or None if not found
        """
        # Check footnotes first
        if note_id in self.footnotes:
            return self.footnotes[note_id]
        
        # Check endnotes
        if note_id in self.endnotes:
            return self.endnotes[note_id]
        
        return None
    
    def get_footnotes(self) -> Dict[str, Any]:
        """
        Get all footnotes.
        
        Returns:
            Dictionary of footnotes
        """
        return self.footnotes.copy()
    
    def get_endnotes(self) -> Dict[str, Any]:
        """
        Get all endnotes.
        
        Returns:
            Dictionary of endnotes
        """
        return self.endnotes.copy()
    
    def get_notes_info(self) -> Dict[str, Any]:
        """
        Get notes information.
        
        Returns:
            Dictionary with notes metadata
        """
        return self.notes_info.copy()
    
    def _parse_notes(self) -> None:
        """Parse footnotes and endnotes from the package."""
        try:
            # Parse footnotes
            self._parse_footnotes()
            
            # Parse endnotes
            self._parse_endnotes()
            
            # Update info
            self.notes_info = {
                'total_footnotes': len(self.footnotes),
                'total_endnotes': len(self.endnotes),
                'footnote_ids': list(self.footnotes.keys()),
                'endnote_ids': list(self.endnotes.keys())
            }
            
            logger.info(f"Parsed {len(self.footnotes)} footnotes and {len(self.endnotes)} endnotes")
            
        except Exception as e:
            logger.error(f"Failed to parse notes: {e}")
    
    def _parse_footnotes(self) -> None:
        """Parse footnotes from footnotes.xml."""
        try:
            footnotes_xml = self.package_reader.get_xml_content('word/footnotes.xml')
            if footnotes_xml:
                self.footnotes = self._parse_footnotes_xml(footnotes_xml)
                logger.debug(f"Parsed {len(self.footnotes)} footnotes")
            else:
                logger.debug("No footnotes.xml found")
        except Exception as e:
            logger.warning(f"Failed to parse footnotes: {e}")
    
    def _parse_endnotes(self) -> None:
        """Parse endnotes from endnotes.xml."""
        try:
            endnotes_xml = self.package_reader.get_xml_content('word/endnotes.xml')
            if endnotes_xml:
                self.endnotes = self._parse_endnotes_xml(endnotes_xml)
                logger.debug(f"Parsed {len(self.endnotes)} endnotes")
            else:
                logger.debug("No endnotes.xml found")
        except Exception as e:
            logger.warning(f"Failed to parse endnotes: {e}")
    
    def _parse_footnotes_xml(self, footnotes_xml: str) -> Dict[str, Any]:
        """Parse footnotes XML content."""
        footnotes = {}
        
        try:
            root = ET.fromstring(footnotes_xml)
            ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
            
            for footnote in root.findall(f'.//{{{ns}}}footnote'):
                # Get ID with namespace
                footnote_id = footnote.get(f'{{{ns}}}id', '') or footnote.get('id', '')
                footnote_type = footnote.get(f'{{{ns}}}type', 'normal') or footnote.get('type', 'normal')
                
                # Skip separators (they're not regular footnotes)
                if footnote_type in ['separator', 'continuationSeparator']:
                    continue
                
                if footnote_id:
                    footnote_content = self.parse_note(footnote)
                    footnotes[footnote_id] = footnote_content
                    
        except ET.ParseError as e:
            logger.error(f"Failed to parse footnotes XML: {e}")
        
        return footnotes
    
    def _parse_endnotes_xml(self, endnotes_xml: str) -> Dict[str, Any]:
        """Parse endnotes XML content."""
        endnotes = {}
        
        try:
            root = ET.fromstring(endnotes_xml)
            ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
            
            for endnote in root.findall(f'.//{{{ns}}}endnote'):
                # Get ID with namespace
                endnote_id = endnote.get(f'{{{ns}}}id', '') or endnote.get('id', '')
                endnote_type = endnote.get(f'{{{ns}}}type', 'normal') or endnote.get('type', 'normal')
                
                # Skip separators (they're not regular endnotes)
                if endnote_type in ['separator', 'continuationSeparator']:
                    continue
                
                if endnote_id:
                    endnote_content = self.parse_note(endnote)
                    endnotes[endnote_id] = endnote_content
                    
        except ET.ParseError as e:
            logger.error(f"Failed to parse endnotes XML: {e}")
        
        return endnotes
    
    def _parse_paragraph(self, paragraph_element: ET.Element) -> Dict[str, Any]:
        """Parse paragraph element."""
        paragraph = {
            'type': 'paragraph',
            'runs': [],
            'text': '',  # Dodaj pełny tekst paragrafu
            'styles': {}
        }
        
        # Parse runs
        for run in paragraph_element.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}r'):
            run_content = self._parse_run(run)
            paragraph['runs'].append(run_content)
            # Dodaj tekst z run do pełnego tekstu paragrafu
            if isinstance(run_content, dict) and 'text' in run_content:
                paragraph['text'] += run_content['text']
        
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
        ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        
        for child in r_pr_element:
            tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            
            if tag_name == 'rStyle':
                # Parse run style reference (odwołanie do stylu z styles.xml)
                style_id = child.get(f'{{{ns}}}val', '') or child.get('val', '')
                if style_id:
                    properties['run_style'] = style_id
            elif tag_name == 'vertAlign':
                # Parse vertical alignment (superscript/subscript)
                val = child.get(f'{{{ns}}}val', '') or child.get('val', '')
                if val:
                    properties['vertical_align'] = val.lower()
                    if val.lower() in ('superscript', 'sup'):
                        properties['superscript'] = True
                    elif val.lower() in ('subscript', 'sub'):
                        properties['subscript'] = True
            elif tag_name == 'sz':
                # Parse font size
                val = child.get(f'{{{ns}}}val', '') or child.get('val', '')
                if val:
                    properties['font_size'] = val
            elif tag_name == 'rFonts':
                # Parse font family
                ascii_font = child.get(f'{{{ns}}}ascii', '') or child.get('ascii', '')
                if ascii_font:
                    properties['font_name'] = ascii_font
            elif tag_name == 'color':
                # Parse color
                val = child.get(f'{{{ns}}}val', '') or child.get('val', '')
                if val:
                    properties['color'] = val
            else:
                # For boolean properties, check if they exist
                properties[tag_name] = True
        
        return properties
    
    def _parse_table_properties(self, tbl_pr_element: ET.Element) -> Dict[str, Any]:
        """Parse table properties."""
        properties = {}
        
        for child in tbl_pr_element:
            tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            properties[tag_name] = child.get('val', '1') == '1'
        
        return properties
    
    def clear_notes(self) -> None:
        """Clear all notes."""
        self.footnotes.clear()
        self.endnotes.clear()
        self.notes_info.clear()
        logger.debug("Notes cleared")
