"""
Field code renderer for DOCX documents.

Handles rendering of field codes (PAGE, NUMPAGES, DATE, TIME, etc.) in headers, footers, and body.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class FieldRenderer:
    """
    Renderer for field codes.
    
    Converts field codes to their actual values based on context.
    """
    
    def __init__(self, context: Optional[Dict[str, Any]] = None):
        """
        Initialize field renderer.
        
        Args:
            context: Context dictionary with page numbers, dates, etc.
                    {
                        'current_page': 1,
                        'total_pages': 10,
                        'current_date': datetime.now(),
                        'current_time': datetime.now()
                    }
        """
        self.context = context or {}
        self.current_page = self.context.get('current_page', 1)
        self.total_pages = self.context.get('total_pages', 1)
        self.current_date = self.context.get('current_date', datetime.now())
        self.current_time = self.context.get('current_time', datetime.now())
    
    def update_context(self, context: Dict[str, Any]):
        """
        Update renderer context.
        
        Args:
            context: New context values
        """
        if 'current_page' in context:
            self.current_page = context['current_page']
        if 'total_pages' in context:
            self.total_pages = context['total_pages']
        if 'current_date' in context:
            self.current_date = context['current_date']
        if 'current_time' in context:
            self.current_time = context['current_time']
        self.context.update(context)
    
    def render_field(self, field: Any) -> str:
        """
        Render a field object to its value.
        
        Args:
            field: Field object (from models.field.Field)
            
        Returns:
            Rendered field value as string
        """
        if not field:
            return ""
        
        # If field has calculate_value method, use it
        if hasattr(field, 'calculate_value'):
            try:
                context = {
                    'current_page': self.current_page,
                    'total_pages': self.total_pages,
                    'current_date': self.current_date,
                    'current_time': self.current_time
                }
                return field.calculate_value(context)
            except Exception as e:
                logger.warning(f"Failed to calculate field value: {e}")
        
        # If field has field_type, render based on type
        if hasattr(field, 'field_type'):
            return self._render_by_type(field)
        
        # If field has instr attribute, parse and render
        if hasattr(field, 'instr'):
            return self._render_from_instruction(field.instr)
        
        # If field has value attribute, return it
        if hasattr(field, 'value') and field.value:
            return str(field.value)
        
        # Fallback: return empty string
        return ""
    
    def render_field_from_instruction(self, instruction: str) -> str:
        """
        Render field from instruction string.
        
        Args:
            instruction: Field instruction (e.g., "PAGE", "DATE \\@ \"dd.MM.yyyy\"")
            
        Returns:
            Rendered field value
        """
        return self._render_from_instruction(instruction)
    
    def _render_by_type(self, field: Any) -> str:
        """Render field based on its type."""
        field_type = getattr(field, 'field_type', 'unknown').upper()
        
        if field_type == 'PAGE':
            return str(self.current_page)
        elif field_type == 'NUMPAGES':
            return str(self.total_pages)
        elif field_type == 'DATE':
            return self._render_date(field)
        elif field_type == 'TIME':
            return self._render_time(field)
        elif field_type == 'AUTHOR':
            return self._render_author(field)
        elif field_type == 'TITLE':
            return self._render_title(field)
        elif field_type == 'REF':
            return self._render_ref(field)
        elif field_type == 'TOC':
            return "[TOC]"
        else:
            # Try to get value
            if hasattr(field, 'value') and field.value:
                return str(field.value)
            return ""
    
    def _render_from_instruction(self, instruction: str) -> str:
        """Render field from instruction string."""
        if not instruction:
            return ""
        
        instruction = instruction.strip().upper()
        
        if instruction.startswith('PAGE'):
            return str(self.current_page)
        elif instruction.startswith('NUMPAGES'):
            return str(self.total_pages)
        elif instruction.startswith('DATE'):
            return self._render_date_from_instruction(instruction)
        elif instruction.startswith('TIME'):
            return self._render_time_from_instruction(instruction)
        elif instruction.startswith('AUTHOR'):
            return "[AUTHOR]"
        elif instruction.startswith('TITLE'):
            return "[TITLE]"
        elif instruction.startswith('REF'):
            return "[REF]"
        elif instruction.startswith('TOC'):
            return "[TOC]"
        else:
            return ""
    
    def _render_date(self, field: Any) -> str:
        """Render DATE field."""
        date_format = '%d.%m.%Y'  # Default format
        
        if hasattr(field, 'format_info'):
            format_info = field.format_info or {}
            date_format = format_info.get('date_format', date_format)
        elif hasattr(field, 'instr'):
            date_format = self._extract_date_format(field.instr)
        
        if hasattr(field, 'current_date') and field.current_date:
            return field.current_date.strftime(date_format)
        
        return self.current_date.strftime(date_format)
    
    def _render_date_from_instruction(self, instruction: str) -> str:
        """Render DATE field from instruction."""
        date_format = self._extract_date_format(instruction)
        return self.current_date.strftime(date_format)
    
    def _render_time(self, field: Any) -> str:
        """Render TIME field."""
        time_format = '%H:%M'  # Default format
        
        if hasattr(field, 'format_info'):
            format_info = field.format_info or {}
            time_format = format_info.get('time_format', time_format)
        elif hasattr(field, 'instr'):
            time_format = self._extract_time_format(field.instr)
        
        if hasattr(field, 'current_time') and field.current_time:
            return field.current_time.strftime(time_format)
        
        return self.current_time.strftime(time_format)
    
    def _render_time_from_instruction(self, instruction: str) -> str:
        """Render TIME field from instruction."""
        time_format = self._extract_time_format(instruction)
        return self.current_time.strftime(time_format)
    
    def _render_author(self, field: Any) -> str:
        """Render AUTHOR field."""
        if hasattr(field, 'value') and field.value:
            return str(field.value)
        return "[AUTHOR]"
    
    def _render_title(self, field: Any) -> str:
        """Render TITLE field."""
        if hasattr(field, 'value') and field.value:
            return str(field.value)
        return "[TITLE]"
    
    def _render_ref(self, field: Any) -> str:
        """Render REF field."""
        if hasattr(field, 'reference_text') and field.reference_text:
            return str(field.reference_text)
        if hasattr(field, 'bookmark_name') and field.bookmark_name:
            return f"[REF: {field.bookmark_name}]"
        return "[REF]"
    
    def _extract_date_format(self, instruction: str) -> str:
        """Extract date format from DATE instruction."""
        # Default format
        default_format = '%d.%m.%Y'
        
        # Look for \@ "format" pattern
        if '\\@' in instruction:
            parts = instruction.split('\\@')
            if len(parts) > 1:
                format_str = parts[1].strip().strip('"').strip("'")
                # Convert Word date format to Python strftime format
                return self._convert_word_date_format(format_str)
        
        return default_format
    
    def _extract_time_format(self, instruction: str) -> str:
        """Extract time format from TIME instruction."""
        # Default format
        default_format = '%H:%M'
        
        # Look for \@ "format" pattern
        if '\\@' in instruction:
            parts = instruction.split('\\@')
            if len(parts) > 1:
                format_str = parts[1].strip().strip('"').strip("'")
                # Convert Word time format to Python strftime format
                return self._convert_word_time_format(format_str)
        
        return default_format
    
    def _convert_word_date_format(self, word_format: str) -> str:
        """
        Convert Word date format to Python strftime format.
        
        Args:
            word_format: Word format string (e.g., "dd.MM.yyyy", "MM/dd/yyyy")
            
        Returns:
            Python strftime format string
        """
        # Common Word date format mappings
        mappings = {
            'dd': '%d',
            'MM': '%m',
            'yyyy': '%Y',
            'yy': '%y',
            'MMMM': '%B',  # Full month name
            'MMM': '%b',   # Abbreviated month name
            'dddd': '%A',  # Full weekday name
            'ddd': '%a',   # Abbreviated weekday name
        }
        
        result = word_format
        # Replace in order (longer patterns first)
        for word_pattern, python_pattern in sorted(mappings.items(), key=lambda x: -len(x[0])):
            result = result.replace(word_pattern, python_pattern)
        
        return result
    
    def _convert_word_time_format(self, word_format: str) -> str:
        """
        Convert Word time format to Python strftime format.
        
        Args:
            word_format: Word format string (e.g., "HH:mm", "h:mm AM/PM")
            
        Returns:
            Python strftime format string
        """
        # Common Word time format mappings
        mappings = {
            'HH': '%H',    # 24-hour format
            'hh': '%I',    # 12-hour format
            'mm': '%M',    # Minutes
            'ss': '%S',    # Seconds
            'AM/PM': '%p', # AM/PM
            'am/pm': '%p', # am/pm
        }
        
        result = word_format
        # Replace in order (longer patterns first)
        for word_pattern, python_pattern in sorted(mappings.items(), key=lambda x: -len(x[0])):
            result = result.replace(word_pattern, python_pattern)
        
        return result
    
    def replace_fields_in_text(self, text: str, fields: Optional[List[Any]] = None) -> str:
        """
        Replace field placeholders in text with their values.
        
        Args:
            text: Text that may contain field references
            fields: Optional list of field objects to search
            
        Returns:
            Text with fields replaced
        """
        # This is a simple implementation - in real DOCX, fields are embedded in runs
        # For now, we'll handle common patterns like [PAGE], [NUMPAGES], etc.
        
        if '[PAGE]' in text:
            text = text.replace('[PAGE]', str(self.current_page))
        if '[NUMPAGES]' in text:
            text = text.replace('[NUMPAGES]', str(self.total_pages))
        if '[DATE]' in text:
            text = text.replace('[DATE]', self.current_date.strftime('%d.%m.%Y'))
        if '[TIME]' in text:
            text = text.replace('[TIME]', self.current_time.strftime('%H:%M'))
        
        return text

