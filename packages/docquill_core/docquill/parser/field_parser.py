"""
Field parser for DOCX documents.

Implements parsing of various field types including PAGE, DATE, REF, TOC, etc.
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class FieldParser:
    """
    Parser for document fields.
    
    Handles parsing of various field types including:
    - PAGE: Page numbers
    - DATE: Current date
    - REF: Cross-references
    - TOC: Table of contents
    - NUMPAGES: Total page count
    """
    
    def __init__(self, package_reader, xml_mapper):
        """
        Initialize field parser.
        
        Args:
            package_reader: Package reader instance
            xml_mapper: XML mapper instance
        """
        self.package_reader = package_reader
        self.xml_mapper = xml_mapper
        self.ns = {
            'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        }
    
    def parse_field(self, field_element) -> Dict[str, Any]:
        """
        Parse field element.
        
        Args:
            field_element: XML element containing field
            
        Returns:
            Dictionary with field information
        """
        try:
            # Find field instruction
            instr_element = field_element.find('.//w:instrText', self.ns)
            if instr_element is None:
                return {'type': 'unknown', 'instruction': '', 'result': ''}
            
            instruction = instr_element.text or ''
            field_type = self._detect_field_type(instruction)
            
            # Find field result
            result_element = field_element.find('.//w:t', self.ns)
            result = result_element.text if result_element is not None else ''
            
            # Parse based on field type
            field_data = {
                'type': field_type,
                'instruction': instruction,
                'result': result,
                'raw_instruction': instruction
            }
            
            if field_type == 'PAGE':
                field_data.update(self._parse_page_field(instruction))
            elif field_type == 'DATE':
                field_data.update(self._parse_date_field(instruction))
            elif field_type == 'REF':
                field_data.update(self._parse_ref_field(instruction))
            elif field_type == 'TOC':
                field_data.update(self._parse_toc_field(instruction))
            elif field_type == 'NUMPAGES':
                field_data.update(self._parse_numpages_field(instruction))
            
            return field_data
            
        except Exception as e:
            logger.error(f"Failed to parse field: {e}")
            return {'type': 'unknown', 'instruction': '', 'result': ''}
    
    def _detect_field_type(self, instruction: str) -> str:
        """
        Detect field type from instruction.
        
        Args:
            instruction: Field instruction string
            
        Returns:
            Field type string
        """
        instruction = instruction.strip().upper()
        
        if instruction.startswith('PAGE'):
            return 'PAGE'
        elif instruction.startswith('DATE'):
            return 'DATE'
        elif instruction.startswith('REF'):
            return 'REF'
        elif instruction.startswith('TOC'):
            return 'TOC'
        elif instruction.startswith('NUMPAGES'):
            return 'NUMPAGES'
        elif instruction.startswith('TIME'):
            return 'TIME'
        elif instruction.startswith('AUTHOR'):
            return 'AUTHOR'
        elif instruction.startswith('TITLE'):
            return 'TITLE'
        else:
            return 'unknown'
    
    def _parse_page_field(self, instruction: str) -> Dict[str, Any]:
        """
        Parse PAGE field.
        
        Args:
            instruction: PAGE field instruction
            
        Returns:
            Dictionary with PAGE field data
        """
        # Extract format from instruction
        # PAGE [\* format] [\# format]
        format_info = {}
        
        if '\\*' in instruction:
            # Extract format after \*
            parts = instruction.split('\\*')
            if len(parts) > 1:
                format_info['number_format'] = parts[1].strip()
        
        if '\\#' in instruction:
            # Extract format after \#
            parts = instruction.split('\\#')
            if len(parts) > 1:
                format_info['display_format'] = parts[1].strip()
        
        return {
            'field_type': 'PAGE',
            'format_info': format_info,
            'current_page': 1,  # Will be set during rendering
            'total_pages': 1     # Will be set during rendering
        }
    
    def _parse_date_field(self, instruction: str) -> Dict[str, Any]:
        """
        Parse DATE field.
        
        Args:
            instruction: DATE field instruction
            
        Returns:
            Dictionary with DATE field data
        """
        # Extract format from instruction
        # DATE [\@ "format"]
        format_info = {}
        
        if '\\@' in instruction:
            # Extract format after \@
            parts = instruction.split('\\@')
            if len(parts) > 1:
                format_str = parts[1].strip().strip('"')
                format_info['date_format'] = format_str
        
        return {
            'field_type': 'DATE',
            'format_info': format_info,
            'current_date': datetime.now(),
            'date_string': datetime.now().strftime(format_info.get('date_format', '%d.%m.%Y'))
        }
    
    def _parse_ref_field(self, instruction: str) -> Dict[str, Any]:
        """
        Parse REF field.
        
        Args:
            instruction: REF field instruction
            
        Returns:
            Dictionary with REF field data
        """
        # Extract bookmark name from instruction
        # REF bookmark [\h] [\f] [\n] [\t] [\p] [\r] [\w] [\* format]
        bookmark_name = instruction.replace('REF', '').strip()
        
        # Remove format switches
        switches = ['\\h', '\\f', '\\n', '\\t', '\\p', '\\r', '\\w']
        for switch in switches:
            bookmark_name = bookmark_name.replace(switch, '').strip()
        
        # Remove format
        if '\\*' in bookmark_name:
            bookmark_name = bookmark_name.split('\\*')[0].strip()
        
        return {
            'field_type': 'REF',
            'bookmark_name': bookmark_name,
            'reference_text': '',  # Will be resolved during rendering
            'switches': self._extract_switches(instruction)
        }
    
    def _parse_toc_field(self, instruction: str) -> Dict[str, Any]:
        """
        Parse TOC field.
        
        Args:
            instruction: TOC field instruction
            
        Returns:
            Dictionary with TOC field data
        """
        # Extract options from instruction
        # TOC [\o "levels"] [\h] [\z] [\t "styles"] [\u] [\l "levels"] [\n "levels"] [\p "separator"] [\b "bookmark"] [\c "caption"] [\a "caption"] [\d "separator"] [\f "identifier"] [\g "identifier"] [\h] [\k "identifier"] [\l "levels"] [\m "identifier"] [\n "levels"] [\o "levels"] [\p "separator"] [\r "levels"] [\s "identifier"] [\t "styles"] [\u] [\w] [\x] [\y] [\z]
        
        options = {}
        
        # Extract \o "levels"
        if '\\o' in instruction:
            parts = instruction.split('\\o')
            if len(parts) > 1:
                levels_str = parts[1].strip().strip('"')
                options['outline_levels'] = levels_str
        
        # Extract \h switch
        if '\\h' in instruction:
            options['hyperlinks'] = True
        
        # Extract \z switch
        if '\\z' in instruction:
            options['hide_page_numbers'] = True
        
        return {
            'field_type': 'TOC',
            'options': options,
            'toc_entries': []  # Will be populated during rendering
        }
    
    def _parse_numpages_field(self, instruction: str) -> Dict[str, Any]:
        """
        Parse NUMPAGES field.
        
        Args:
            instruction: NUMPAGES field instruction
            
        Returns:
            Dictionary with NUMPAGES field data
        """
        # Extract format from instruction
        # NUMPAGES [\* format] [\# format]
        format_info = {}
        
        if '\\*' in instruction:
            # Extract format after \*
            parts = instruction.split('\\*')
            if len(parts) > 1:
                format_info['number_format'] = parts[1].strip()
        
        if '\\#' in instruction:
            # Extract format after \#
            parts = instruction.split('\\#')
            if len(parts) > 1:
                format_info['display_format'] = parts[1].strip()
        
        return {
            'field_type': 'NUMPAGES',
            'format_info': format_info,
            'total_pages': 1  # Will be set during rendering
        }
    
    def _extract_switches(self, instruction: str) -> List[str]:
        """
        Extract switches from field instruction.
        
        Args:
            instruction: Field instruction
            
        Returns:
            List of switches
        """
        switches = []
        switch_patterns = ['\\h', '\\f', '\\n', '\\t', '\\p', '\\r', '\\w']
        
        for pattern in switch_patterns:
            if pattern in instruction:
                switches.append(pattern)
        
        return switches
    
    def parse_page_field(self, field_element) -> Dict[str, Any]:
        """
        Parse PAGE field (legacy method).
        
        Args:
            field_element: Field element
            
        Returns:
            Dictionary with PAGE field data
        """
        return self.parse_field(field_element)
    
    def parse_date_field(self, field_element) -> Dict[str, Any]:
        """
        Parse DATE field (legacy method).
        
        Args:
            field_element: Field element
            
        Returns:
            Dictionary with DATE field data
        """
        return self.parse_field(field_element)
