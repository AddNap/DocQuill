"""
Field model for DOCX documents.

Implements field functionality including field types, field code parsing,
field result parsing, and field calculation.
"""

from typing import Dict, Any, Optional, Union
from datetime import datetime
import logging
from .base import Models

logger = logging.getLogger(__name__)

class Field(Models):
    """
    Represents a field in the document.
    Terminal element - cannot contain other models.
    
    Supports various field types including:
    - PAGE: Page numbers
    - DATE: Current date
    - REF: Cross-references
    - TOC: Table of contents
    - NUMPAGES: Total page count
    """
    
    def __init__(self):
        """
        Initialize field.
        
        Sets up field type, instruction, and result properties.
        """
        super().__init__()
        self.instr: str = ""  # Field instruction (e.g., "PAGE", "DATE", "REF bookmark")
        self.value: str = ""  # Field result value
        self.field_type: str = "unknown"  # Field type
        self.format_info: Dict[str, Any] = {}  # Format information
        self.switches: list = []  # Field switches
        self.bookmark_name: Optional[str] = None  # For REF fields
        self.options: Dict[str, Any] = {}  # Field options (for TOC, etc.)
        self.current_page: int = 1  # Current page number
        self.total_pages: int = 1  # Total page count
        self.current_date: Optional[datetime] = None  # Current date
        self.reference_text: str = ""  # Reference text for REF fields
        self.toc_entries: list = []  # TOC entries
    
    def set_instr(self, instr: str):
        """
        Set field instruction.
        
        Args:
            instr: Field instruction string
        """
        self.instr = instr
        self.field_type = self._detect_field_type(instr)
        self._parse_instruction(instr)
    
    def set_value(self, value: str):
        """
        Set field value.
        
        Args:
            value: Field result value
        """
        self.value = value
    
    def get_instr(self) -> str:
        """
        Get field instruction.
        
        Returns:
            Field instruction string
        """
        return self.instr
    
    def get_value(self) -> str:
        """
        Get field value.
        
        Returns:
            Field result value
        """
        return self.value
    
    def get_text(self) -> str:
        """
        Get field text (result or code).
        
        Returns:
            Field result value or instruction if no result
        """
        return self.value if self.value else self.instr
    
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
    
    def _parse_instruction(self, instruction: str):
        """
        Parse field instruction and extract relevant information.
        
        Args:
            instruction: Field instruction string
        """
        if self.field_type == 'PAGE':
            self._parse_page_instruction(instruction)
        elif self.field_type == 'DATE':
            self._parse_date_instruction(instruction)
        elif self.field_type == 'REF':
            self._parse_ref_instruction(instruction)
        elif self.field_type == 'TOC':
            self._parse_toc_instruction(instruction)
        elif self.field_type == 'NUMPAGES':
            self._parse_numpages_instruction(instruction)
    
    def _parse_page_instruction(self, instruction: str):
        """Parse PAGE field instruction."""
        # Extract format from instruction
        # PAGE [\* format] [\# format]
        if '\\*' in instruction:
            parts = instruction.split('\\*')
            if len(parts) > 1:
                self.format_info['number_format'] = parts[1].strip()
        
        if '\\#' in instruction:
            parts = instruction.split('\\#')
            if len(parts) > 1:
                self.format_info['display_format'] = parts[1].strip()
    
    def _parse_date_instruction(self, instruction: str):
        """Parse DATE field instruction."""
        # Extract format from instruction
        # DATE [\@ "format"]
        if '\\@' in instruction:
            parts = instruction.split('\\@')
            if len(parts) > 1:
                format_str = parts[1].strip().strip('"')
                self.format_info['date_format'] = format_str
        
        self.current_date = datetime.now()
    
    def _parse_ref_instruction(self, instruction: str):
        """Parse REF field instruction."""
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
        
        self.bookmark_name = bookmark_name
        self.switches = self._extract_switches(instruction)
    
    def _parse_toc_instruction(self, instruction: str):
        """Parse TOC field instruction."""
        # Extract options from instruction
        if '\\o' in instruction:
            parts = instruction.split('\\o')
            if len(parts) > 1:
                levels_str = parts[1].strip().strip('"')
                self.options['outline_levels'] = levels_str
        
        if '\\h' in instruction:
            self.options['hyperlinks'] = True
        
        if '\\z' in instruction:
            self.options['hide_page_numbers'] = True
    
    def _parse_numpages_instruction(self, instruction: str):
        """Parse NUMPAGES field instruction."""
        # Extract format from instruction
        # NUMPAGES [\* format] [\# format]
        if '\\*' in instruction:
            parts = instruction.split('\\*')
            if len(parts) > 1:
                self.format_info['number_format'] = parts[1].strip()
        
        if '\\#' in instruction:
            parts = instruction.split('\\#')
            if len(parts) > 1:
                self.format_info['display_format'] = parts[1].strip()
    
    def _extract_switches(self, instruction: str) -> list:
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
    
    def calculate_value(self, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Calculate field value based on current context.
        
        Args:
            context: Optional context with page numbers, dates, etc.
            
        Returns:
            Calculated field value
        """
        if context:
            self.current_page = context.get('current_page', 1)
            self.total_pages = context.get('total_pages', 1)
            self.current_date = context.get('current_date', datetime.now())
        
        if self.field_type == 'PAGE':
            return str(self.current_page)
        elif self.field_type == 'DATE':
            if self.current_date:
                format_str = self.format_info.get('date_format', '%d.%m.%Y')
                return self.current_date.strftime(format_str)
            return datetime.now().strftime('%d.%m.%Y')
        elif self.field_type == 'NUMPAGES':
            return str(self.total_pages)
        elif self.field_type == 'REF':
            return self.reference_text or f"[REF: {self.bookmark_name}]"
        elif self.field_type == 'TOC':
            return "[TOC]"
        else:
            return self.value or self.instr
    
    def update_context(self, context: Dict[str, Any]):
        """
        Update field with new context information.
        
        Args:
            context: Context information (page numbers, dates, etc.)
        """
        if 'current_page' in context:
            self.current_page = context['current_page']
        if 'total_pages' in context:
            self.total_pages = context['total_pages']
        if 'current_date' in context:
            self.current_date = context['current_date']
        if 'reference_text' in context and self.field_type == 'REF':
            self.reference_text = context['reference_text']
        if 'toc_entries' in context and self.field_type == 'TOC':
            self.toc_entries = context['toc_entries']
    
    def is_page_field(self) -> bool:
        """Check if this is a PAGE field."""
        return self.field_type == 'PAGE'
    
    def is_date_field(self) -> bool:
        """Check if this is a DATE field."""
        return self.field_type == 'DATE'
    
    def is_ref_field(self) -> bool:
        """Check if this is a REF field."""
        return self.field_type == 'REF'
    
    def is_toc_field(self) -> bool:
        """Check if this is a TOC field."""
        return self.field_type == 'TOC'
    
    def is_numpages_field(self) -> bool:
        """Check if this is a NUMPAGES field."""
        return self.field_type == 'NUMPAGES'
