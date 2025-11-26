"""

HTML Parser - parses HTML from contenteditable and updates DOCX document...
"""

from __future__ import annotations

import re
import logging
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from html.parser import HTMLParser
from html import unescape

logger = logging.getLogger(__name__)


class HTMLContentParser(HTMLParser):
    """HTML Parser that extracts text and formatting from contenteditable."""
    
    def __init__(self):
        super().__init__()
        self.paragraphs: List[Dict[str, Any]] = []
        self.tables: List[Dict[str, Any]] = []  # Tabele
        self.images: List[Dict[str, Any]] = []  # Obrazy
        self.current_paragraph: Optional[Dict[str, Any]] = None
        self.current_run: Optional[Dict[str, Any]] = None
        self.tag_stack: List[str] = []
        self.formatting_stack: List[Dict[str, Any]] = []  # Stack for nested formatting
        self.current_list: Optional[Dict[str, Any]] = None  # Information about current list
        self.list_level: int = 0  # List nesting level
        # Stan tabeli
        self.current_table: Optional[Dict[str, Any]] = None
        self.current_row: Optional[Dict[str, Any]] = None
        self.current_cell: Optional[Dict[str, Any]] = None
        self.in_table: bool = False
    
    def handle_starttag(self, tag: str, attrs: list) -> None:
        """Handles opening HTML tags."""
        tag_lower = tag.lower()
        self.tag_stack.append(tag_lower)
        
        # Parsuj atrybuty style
        style_dict = {}
        for attr_name, attr_value in attrs:
            if attr_name.lower() == 'style' and attr_value:
                style_dict = self._parse_style(attr_value)
            elif attr_name.lower() == 'color':
                style_dict['color'] = attr_value
            elif attr_name.lower() == 'style':
                # Style attribute may already be processed
                pass
        
        # Combine styles from attributes with formatting from tag
        formatting = {}
        
        if tag_lower == 'p':
            # Nowy paragraf
            # If we are in a table, don't add to main paragraph list
            if self.current_paragraph:
                if self.in_table and self.current_cell:
                    # Add to cell
                    self.current_cell['paragraphs'].append(self.current_paragraph)
                else:
                    # Add to main paragraph list
                    self.paragraphs.append(self.current_paragraph)
            
            self.current_paragraph = {
                'runs': [],
                'text': '',
                'numbering': None
            }
            self.current_run = None
            self.formatting_stack = []
        
        elif tag_lower in ('ul', 'ol'):
            # Start list
            self.list_level += 1
            self.current_list = {
                'tag': tag_lower,
                'level': self.list_level - 1,  # Poziom listy (0-based)
                'format': 'bullet' if tag_lower == 'ul' else 'decimal'
            }
        
        elif tag_lower == 'li':
            # List element - create new paragraph with numbering
            if self.current_paragraph:
                self.paragraphs.append(self.current_paragraph)
            
            self.current_paragraph = {
                'runs': [],
                'text': '',
                'numbering': None
            }
            
            # Set numbering if we are in a list
            if self.current_list:
                self.current_paragraph['numbering'] = {
                    'id': str(hash(self.current_list['tag'] + str(self.current_list['level']))),  # Generuj unikalny ID
                    'level': self.current_list['level'],
                    'format': self.current_list['format']
                }
            
            self.current_run = None
            self.formatting_stack = []
        
        elif tag_lower == 'table':
            # Start table
            # Close previous paragraph if open
            if self.current_paragraph:
                self.paragraphs.append(self.current_paragraph)
                self.current_paragraph = None
            
            self.in_table = True
            self.current_table = {
                'rows': [],
                'type': 'table'
            }
        
        elif tag_lower == 'tr':
            # Rozpocznij wiersz tabeli
            if self.in_table and self.current_table:
                # Close previous cell if open
                if self.current_cell:
                    if self.current_row:
                        self.current_row['cells'].append(self.current_cell)
                    self.current_cell = None
                
                self.current_row = {
                    'cells': [],
                    'is_header': False
                }
        
        elif tag_lower in ('td', 'th'):
            # Start table cell
            if self.in_table and self.current_table and self.current_row:
                # Close previous cell if open
                if self.current_cell:
                    self.current_row['cells'].append(self.current_cell)
                
                # Create new cell
                self.current_cell = {
                    'paragraphs': [],
                    'is_header': tag_lower == 'th'
                }
                
                # Set is_header for row if this is <th>
                if tag_lower == 'th':
                    self.current_row['is_header'] = True
                
                # Create new paragraph for cell
                self.current_paragraph = {
                    'runs': [],
                    'text': '',
                    'numbering': None
                }
                self.current_run = None
                self.formatting_stack = []
        
        elif tag_lower in ('strong', 'b'):
            # Bold
            formatting['bold'] = True
        
        elif tag_lower in ('em', 'i'):
            # Italic
            formatting['italic'] = True
        
        elif tag_lower == 'u':
            # Underline
            formatting['underline'] = True
        
        elif tag_lower in ('span', 'font'):
            # Span/Font may have style, color, font-size, font-family
            if 'color' in style_dict:
                formatting['color'] = style_dict['color']
            if 'font-size' in style_dict:
                formatting['font_size'] = style_dict['font-size']
            if 'font-family' in style_dict:
                formatting['font_name'] = style_dict['font-family']
        
        elif tag_lower == 'img':
            # Image - close previous paragraph if open
            if self.current_paragraph:
                if self.in_table and self.current_cell:
                    self.current_cell['paragraphs'].append(self.current_paragraph)
                else:
                    self.paragraphs.append(self.current_paragraph)
                self.current_paragraph = None
            
            # Parsuj atrybuty obrazu
            image_data = {
                'src': '',
                'alt': '',
                'width': None,
                'height': None,
                'rel_id': ''
            }
            
            for attr_name, attr_value in attrs:
                attr_lower = attr_name.lower()
                if attr_lower == 'src':
                    image_data['src'] = attr_value or ''
                elif attr_lower == 'alt':
                    image_data['alt'] = attr_value or ''
                elif attr_lower == 'width':
                    try:
                        image_data['width'] = int(attr_value)
                    except (ValueError, TypeError):
                        pass
                elif attr_lower == 'height':
                    try:
                        image_data['height'] = int(attr_value)
                    except (ValueError, TypeError):
                        pass
                elif attr_lower == 'data-image-id':
                    image_data['rel_id'] = attr_value or ''
            
            # If no rel_id, generate from src
            if not image_data['rel_id'] and image_data['src']:
                import hashlib
                image_data['rel_id'] = hashlib.md5(image_data['src'].encode()).hexdigest()[:8]
            
            self.images.append(image_data)
        
        # Dodaj formatowanie do stacku
        if formatting or style_dict:
            # Combine formatting from current stack with new formatting
            combined_formatting = {}
            
            # Start from formatting from previous level (if exists)
            if self.formatting_stack:
                combined_formatting.update(self.formatting_stack[-1])
            
            # Dodaj nowe formatowanie (nadpisuje poprzednie)
            combined_formatting.update(formatting)
            combined_formatting.update(style_dict)
            
            # Dodaj do stacku
            self.formatting_stack.append(combined_formatting)
            
            # Start new run if there is formatting
            if self.current_paragraph:
                if self.current_run and self.current_run.get('text'):
                    self.current_paragraph['runs'].append(self.current_run)
                
                # Create new run with combined formatting
                new_run = {'text': ''}
                new_run.update(combined_formatting)
                self.current_run = new_run
    
    def handle_endtag(self, tag: str) -> None:
        """Handles closing HTML tags."""
        tag_lower = tag.lower()
        
        if tag_lower in self.tag_stack:
            self.tag_stack.remove(tag_lower)
        
        if tag_lower == 'p':
            # End paragraph
            if self.current_paragraph:
                if self.current_run and self.current_run.get('text'):
                    self.current_paragraph['runs'].append(self.current_run)
                self.current_paragraph['text'] = ''.join(
                    run.get('text', '') for run in self.current_paragraph['runs']
                )
                
                # If we are in a table, add to cell
                if self.in_table and self.current_cell:
                    self.current_cell['paragraphs'].append(self.current_paragraph)
                else:
                    # Add to main paragraph list
                    self.paragraphs.append(self.current_paragraph)
                
                self.current_paragraph = None
                self.current_run = None
                self.formatting_stack = []
        
        elif tag_lower == 'li':
            # End list element
            if self.current_paragraph:
                if self.current_run and self.current_run.get('text'):
                    self.current_paragraph['runs'].append(self.current_run)
                self.current_paragraph['text'] = ''.join(
                    run.get('text', '') for run in self.current_paragraph['runs']
                )
                self.paragraphs.append(self.current_paragraph)
                self.current_paragraph = None
                self.current_run = None
                self.formatting_stack = []
        
        elif tag_lower in ('ul', 'ol'):
            # End list
            self.list_level = max(0, self.list_level - 1)
            if self.list_level == 0:
                self.current_list = None
        
        elif tag_lower == 'td' or tag_lower == 'th':
            # End table cell
            if self.current_paragraph:
                if self.current_run and self.current_run.get('text'):
                    self.current_paragraph['runs'].append(self.current_run)
                self.current_paragraph['text'] = ''.join(
                    run.get('text', '') for run in self.current_paragraph['runs']
                )
                
                # Add paragraph to cell
                if self.current_cell:
                    self.current_cell['paragraphs'].append(self.current_paragraph)
                
                self.current_paragraph = None
                self.current_run = None
                self.formatting_stack = []
            
            # Add cell to row
            if self.current_cell and self.current_row:
                self.current_row['cells'].append(self.current_cell)
                self.current_cell = None
        
        elif tag_lower == 'tr':
            # End table row
            if self.current_cell:
                self.current_row['cells'].append(self.current_cell)
                self.current_cell = None
            
            if self.current_row and self.current_table:
                self.current_table['rows'].append(self.current_row)
                self.current_row = None
        
        elif tag_lower == 'table':
            # End table
            if self.current_row:
                if self.current_cell:
                    self.current_row['cells'].append(self.current_cell)
                    self.current_cell = None
                self.current_table['rows'].append(self.current_row)
                self.current_row = None
            
            if self.current_table:
                self.tables.append(self.current_table)
                self.current_table = None
            
            self.in_table = False
        
        elif tag_lower in ('strong', 'b', 'em', 'i', 'u', 'span', 'font'):
            # End run with formatting
            if self.formatting_stack:
                self.formatting_stack.pop()
            
            if self.current_run and self.current_paragraph:
                if self.current_run.get('text'):
                    self.current_paragraph['runs'].append(self.current_run)
                
                # Restore previous formatting from stack or create new run
                if self.formatting_stack:
                    # Restore formatting from previous level
                    prev_formatting = self.formatting_stack[-1].copy()
                    prev_formatting['text'] = ''
                    self.current_run = prev_formatting
                else:
                    # No formatting - regular run
                    self.current_run = {'text': ''}
    
    def handle_data(self, data: str) -> None:
        """Handles text."""
        if not self.current_paragraph:
            # Text outside paragraph - create new paragraph
            self.current_paragraph = {
                'runs': [],
                'text': ''
            }
        
        if not self.current_run:
            # Create default run with formatting from stack
            if self.formatting_stack:
                self.current_run = self.formatting_stack[-1].copy()
                self.current_run['text'] = ''
            else:
                self.current_run = {'text': ''}
        
        # Add text to current run
        self.current_run['text'] += unescape(data)
    
    def _parse_style(self, style_str: str) -> Dict[str, Any]:
        """Parsuje atrybut style z HTML."""
        style_dict = {}
        
        if not style_str:
            return style_dict
        
        # Parsuj style="color: red; font-size: 12px; font-family: Arial;"
        for declaration in style_str.split(';'):
            declaration = declaration.strip()
            if not declaration:
                continue
            
            if ':' in declaration:
                prop, value = declaration.split(':', 1)
                prop = prop.strip().lower()
                value = value.strip()
                
                if prop == 'color':
                    # Convert color to hex format (if needed)
                    color = self._normalize_color(value)
                    if color:
                        style_dict['color'] = color
                
                elif prop == 'font-size':
                    # Parsuj rozmiar czcionki (np. "12px", "1.2em", "12pt")
                    font_size = self._parse_font_size(value)
                    if font_size:
                        style_dict['font_size'] = font_size
                
                elif prop == 'font-family':
                    # Parse font name (remove quotes if present)
                    font_name = value.strip('"\'')
                    if font_name:
                        # Take first font from list
                        font_name = font_name.split(',')[0].strip()
                        style_dict['font_name'] = font_name
        
        return style_dict
    
    def _normalize_color(self, color: str) -> Optional[str]:
        """Normalizuje kolor do formatu hex (RRGGBB)."""
        color = color.strip().lower()
        
        # If already hex
        if color.startswith('#'):
            color = color[1:]
            if len(color) == 3:
                # Rozszerz #RGB do #RRGGBB
                color = ''.join(c * 2 for c in color)
            if len(color) == 6:
                return color.upper()
        
        # HTML color names
        color_names = {
            'black': '000000',
            'white': 'FFFFFF',
            'red': 'FF0000',
            'green': '008000',
            'blue': '0000FF',
            'yellow': 'FFFF00',
            'cyan': '00FFFF',
            'magenta': 'FF00FF',
            'gray': '808080',
            'grey': '808080',
            'orange': 'FFA500',
            'purple': '800080',
            'brown': 'A52A2A',
            'pink': 'FFC0CB',
        }
        
        if color in color_names:
            return color_names[color]
        
        # RGB/RGBA format
        if color.startswith('rgb'):
            import re
            match = re.search(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', color)
            if match:
                r, g, b = match.groups()
                return f"{int(r):02X}{int(g):02X}{int(b):02X}"
        
        return None
    
    def _parse_font_size(self, size_str: str) -> Optional[str]:
        """Parsuje rozmiar czcionki do formatu Word (half-points)."""
        size_str = size_str.strip().lower()
        
        # Remove units and parse number
        import re
        match = re.match(r'([\d.]+)', size_str)
        if not match:
            return None
        
        size_value = float(match.group(1))
        
        # Convert various units to points
        if 'px' in size_str:
            # 1px ≈ 0.75pt (approximation)
            size_value = size_value * 0.75
        elif 'em' in size_str:
            # 1em ≈ 12pt (default size)
            size_value = size_value * 12
        elif 'pt' in size_str:
            # Already in points
            pass
        else:
            # Assume it's points
            pass
        
        # Convert to half-points (Word uses half-points)
        half_points = int(size_value * 2)
        
        # Return as string (Word format)
        return str(half_points)
    
    def close(self) -> None:
        """Finish parsing."""
        # Close open paragraph if any
        if self.current_paragraph:
            if self.current_run and self.current_run.get('text'):
                self.current_paragraph['runs'].append(self.current_run)
            self.current_paragraph['text'] = ''.join(
                run.get('text', '') for run in self.current_paragraph['runs']
            )
            
            # If we are in a table, add paragraph to cell
            if self.in_table and self.current_cell:
                self.current_cell['paragraphs'].append(self.current_paragraph)
            else:
                self.paragraphs.append(self.current_paragraph)
            
            self.current_paragraph = None
        
        # Close open cell if any
        if self.current_cell:
            if self.current_row:
                self.current_row['cells'].append(self.current_cell)
            self.current_cell = None
        
        # Close open row if any
        if self.current_row:
            if self.current_table:
                self.current_table['rows'].append(self.current_row)
            self.current_row = None
        
        # Close open table if any
        if self.current_table:
            self.tables.append(self.current_table)
            self.current_table = None
        
        self.in_table = False
        super().close()


class HTMLParser:
    """

    HTML Parser that converts edited HTML back to document model...
    """
    
    def __init__(self, html_content: str):
        """

        Initializes HTML parser.

        Args:
        ...
        """
        self.html_content = html_content
        self.parser = HTMLContentParser()
    
    def parse(self) -> Dict[str, Any]:
        """

        Parses HTML and returns paragraphs and tables.

        Returns:...
        """
        try:
            # Clear parser
            self.parser.paragraphs = []
            self.parser.tables = []
            self.parser.current_paragraph = None
            self.parser.current_run = None
            self.parser.tag_stack = []
            self.parser.formatting_stack = []
            self.parser.current_list = None
            self.parser.list_level = 0
            self.parser.current_table = None
            self.parser.current_row = None
            self.parser.current_cell = None
            self.parser.in_table = False
            self.parser.images = []
            
            # Parsuj HTML
            self.parser.feed(self.html_content)
            self.parser.close()
            
            return {
                'paragraphs': self.parser.paragraphs,
                'tables': self.parser.tables,
                'images': self.parser.images
            }
            
        except Exception as e:
            logger.error(f"Failed to parse HTML: {e}")
            return {'paragraphs': [], 'tables': [], 'images': []}
    
    @staticmethod
    def parse_file(html_path: Union[str, Path]) -> Dict[str, Any]:
        """

        Parses HTML file.

        Args:
        html_path...
        """
        html_path = Path(html_path)
        if not html_path.exists():
            logger.error(f"HTML file not found: {html_path}")
            return {'paragraphs': [], 'tables': [], 'images': []}
        
        html_content = html_path.read_text(encoding='utf-8')
        parser = HTMLParser(html_content)
        return parser.parse()

