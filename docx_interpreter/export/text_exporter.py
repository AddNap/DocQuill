"""
Text exporter for DOCX documents.

Handles plain text export with formatting, validation, and optimization.
"""

from typing import Dict, Any, Optional, List, Union
from pathlib import Path
import logging
import re

logger = logging.getLogger(__name__)

class TextExporter:
    """
    Exports document to plain text.
    
    Handles plain text export with formatting, validation, and optimization.
    """
    
    def __init__(self, document: Any, preserve_formatting: bool = True, 
                 line_width: int = 80, encoding: str = 'utf-8'):
        """
        Initialize text exporter.
        
        Args:
            document: Document to export
            preserve_formatting: Whether to preserve basic formatting
            line_width: Maximum line width for text wrapping
            encoding: Text encoding for output file
        """
        self.document = document
        self.preserve_formatting = preserve_formatting
        self.line_width = line_width
        self.encoding = encoding
        
        # Text formatting options
        self.formatting = {
            'bold': '**{}**',
            'italic': '*{}*',
            'underline': '_{}_',
            'strikethrough': '~~{}~~',
            'code': '`{}`'
        }
        
        logger.debug("Text exporter initialized")
    
    def export(self, output_path: Union[str, Path]) -> bool:
        """
        Export document to plain text.
        
        Args:
            output_path: Output file path
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Generate text content
            text_content = self.export_document_text(self.document)
            
            # Format and optimize output
            formatted_content = self.format_text_output(text_content)
            
            # Write to file
            with open(output_path, 'w', encoding=self.encoding) as f:
                f.write(formatted_content)
            
            logger.info(f"Document exported to text: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export document to text: {e}")
            return False
    
    def export_document_text(self, document: Any = None) -> str:
        """
        Export document text content.
        
        Args:
            document: Document to export
            
        Returns:
            Plain text content
        """
        if document is None:
            document = self.document
        
        text_parts = []
        
        # Add document title if available
        if document and hasattr(document, 'title') and document.title:
            title = self._format_heading(document.title, 1)
            text_parts.append(title)
            text_parts.append('')  # Empty line after title
        
        # Export paragraphs
        if hasattr(document, 'get_paragraphs'):
            paragraphs = document.get_paragraphs()
            for para in paragraphs:
                para_text = self.export_paragraph_text(para)
                if para_text.strip():
                    text_parts.append(para_text)
        
        # Export tables
        if hasattr(document, 'get_tables'):
            tables = document.get_tables()
            for table in tables:
                table_text = self.export_table_text(table)
                if table_text.strip():
                    text_parts.append(table_text)
        
        # Export images (as placeholders)
        if hasattr(document, 'get_images'):
            images = document.get_images()
            for image in images:
                image_text = self._export_image_text(image)
                if image_text.strip():
                    text_parts.append(image_text)
        
        return '\n'.join(text_parts)
    
    def export_paragraph_text(self, paragraph: Union[Dict[str, Any], Any]) -> str:
        """
        Export paragraph text.
        
        Args:
            paragraph: Paragraph data (dict or object)
            
        Returns:
            Plain text paragraph
        """
        # Handle both dict and object inputs
        if hasattr(paragraph, 'get_text'):
            text = paragraph.get_text()
            style = getattr(paragraph, 'style', {})
        else:
            text = paragraph.get('text', '')
            style = paragraph.get('style', {})
        
        # Apply text formatting if enabled
        if self.preserve_formatting:
            formatted_text = self._apply_text_formatting(text, style)
        else:
            formatted_text = text
        
        # Check if it's a heading
        if isinstance(style, dict) and style.get('heading_level'):
            level = style['heading_level']
            return self._format_heading(formatted_text, level)
        
        # Check if it's a list item
        if isinstance(style, dict) and style.get('list_type'):
            list_marker = self._get_list_marker(style['list_type'], style.get('list_level', 0))
            return f"{list_marker} {formatted_text}"
        
        # Regular paragraph
        if formatted_text.strip():
            # Wrap text if line width is specified
            if self.line_width > 0:
                wrapped_text = self._wrap_text(formatted_text, self.line_width)
                return wrapped_text
            else:
                return formatted_text
        
        return ""
    
    def export_heading_text(self, heading: Union[Dict[str, Any], Any]) -> str:
        """
        Export heading text.
        
        Args:
            heading: Heading data (dict or object)
            
        Returns:
            Plain text heading
        """
        # Handle both dict and object inputs
        if hasattr(heading, 'get_text'):
            text = heading.get_text()
            level = getattr(heading, 'level', 1)
            # Ensure level is an integer
            if not isinstance(level, int):
                level = 1
        else:
            text = heading.get('text', '')
            level = heading.get('level', 1)
        
        return self._format_heading(text, level)
    
    def export_table_text(self, table: Union[Dict[str, Any], Any]) -> str:
        """
        Export table text.
        
        Args:
            table: Table data (dict or object)
            
        Returns:
            Plain text table
        """
        # Handle both dict and object inputs
        if hasattr(table, 'get_rows'):
            rows = table.get_rows()
        else:
            rows = table.get('rows', [])
        
        if not rows:
            return ""
        
        # Calculate column widths
        col_widths = self._calculate_column_widths(rows)
        
        text_rows = []
        
        # Header row
        if rows:
            if hasattr(rows[0], 'get_cells'):
                cells = rows[0].get_cells()
                header_cells = [cell.get_text() for cell in cells]
            else:
                header_cells = [cell.get('text', '') for cell in rows[0].get('cells', [])]
            header_row = self._format_table_row(header_cells, col_widths)
            text_rows.append(header_row)
            
            # Add separator line
            separator = self._format_table_separator(col_widths)
            text_rows.append(separator)
        
        # Data rows
        for row in rows[1:]:
            if hasattr(row, 'get_cells'):
                cells = row.get_cells()
                cell_texts = [cell.get_text() for cell in cells]
            else:
                cell_texts = [cell.get('text', '') for cell in row.get('cells', [])]
            data_row = self._format_table_row(cell_texts, col_widths)
            text_rows.append(data_row)
        
        return '\n'.join(text_rows)
    
    def format_text_output(self, text_content: str) -> str:
        """
        Format text output.
        
        Args:
            text_content: Raw text content
            
        Returns:
            Formatted text content
        """
        # Remove excessive blank lines
        text_content = re.sub(r'\n{3,}', '\n\n', text_content)
        
        # Ensure proper spacing around headings
        text_content = re.sub(r'\n(#{1,6}\s)', r'\n\n\1', text_content)
        
        # Ensure proper spacing around tables
        text_content = re.sub(r'\n(\|)', r'\n\n\1', text_content)
        
        # Clean up leading/trailing whitespace
        text_content = text_content.strip()
        
        # Ensure text ends with newline
        if text_content and not text_content.endswith('\n'):
            text_content += '\n'
        
        return text_content
    
    def _format_heading(self, text: str, level: int) -> str:
        """Format heading text."""
        if level == 1:
            return f"{text}\n{'=' * len(text)}"
        elif level == 2:
            return f"{text}\n{'-' * len(text)}"
        else:
            return f"{'#' * level} {text}"
    
    def _apply_text_formatting(self, text: str, style) -> str:
        """Apply text formatting based on style."""
        if not text or not style:
            return text
        
        # Handle string style
        if isinstance(style, str):
            return text
        
        formatted_text = text
        
        # Apply bold
        if style.get('bold'):
            formatted_text = self.formatting['bold'].format(formatted_text)
        
        # Apply italic
        if style.get('italic'):
            formatted_text = self.formatting['italic'].format(formatted_text)
        
        # Apply underline
        if style.get('underline'):
            formatted_text = self.formatting['underline'].format(formatted_text)
        
        # Apply strikethrough
        if style.get('strikethrough'):
            formatted_text = self.formatting['strikethrough'].format(formatted_text)
        
        # Apply code formatting
        if style.get('code'):
            formatted_text = self.formatting['code'].format(formatted_text)
        
        return formatted_text
    
    def _get_list_marker(self, list_type: str, level: int) -> str:
        """Get list marker based on type and level."""
        indent = '  ' * level
        
        if list_type == 'bullet':
            return f"{indent}•"
        elif list_type == 'number':
            return f"{indent}1."
        elif list_type == 'alpha':
            return f"{indent}a."
        elif list_type == 'roman':
            return f"{indent}i."
        else:
            return f"{indent}•"
    
    def _wrap_text(self, text: str, width: int) -> str:
        """Wrap text to specified width."""
        if not text or width <= 0:
            return text
        
        lines = []
        words = text.split()
        current_line = []
        current_length = 0
        
        for word in words:
            word_length = len(word)
            
            if current_length + word_length + 1 <= width:
                current_line.append(word)
                current_length += word_length + 1
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                    current_length = word_length
                else:
                    # Word is longer than width, add as is
                    lines.append(word)
                    current_length = 0
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return '\n'.join(lines)
    
    def _calculate_column_widths(self, rows) -> List[int]:
        """Calculate column widths for table formatting."""
        if not rows:
            return []
        
        max_cols = 0
        for row in rows:
            if hasattr(row, 'get_cells'):
                cells = row.get_cells()
                max_cols = max(max_cols, len(cells))
            else:
                max_cols = max(max_cols, len(row.get('cells', [])))
        col_widths = [0] * max_cols
        
        for row in rows:
            if hasattr(row, 'get_cells'):
                cells = row.get_cells()
                for i, cell in enumerate(cells):
                    if i < len(col_widths):
                        if hasattr(cell, 'get_text'):
                            cell_text = cell.get_text()
                        else:
                            cell_text = str(cell)
                        col_widths[i] = max(col_widths[i], len(cell_text))
            else:
                cells = row.get('cells', [])
                for i, cell in enumerate(cells):
                    if i < len(col_widths):
                        cell_text = cell.get('text', '')
                        col_widths[i] = max(col_widths[i], len(cell_text))
        
        return col_widths
    
    def _format_table_row(self, cells: List[str], col_widths: List[int]) -> str:
        """Format table row."""
        formatted_cells = []
        
        for i, cell in enumerate(cells):
            if i < len(col_widths):
                width = col_widths[i]
                formatted_cell = cell.ljust(width)
                formatted_cells.append(formatted_cell)
        
        return ' | '.join(formatted_cells)
    
    def _format_table_separator(self, col_widths: List[int]) -> str:
        """Format table separator line."""
        separator_cells = []
        
        for width in col_widths:
            separator_cells.append('-' * width)
        
        return ' | '.join(separator_cells)
    
    def _export_image_text(self, image: Dict[str, Any]) -> str:
        """Export image as text placeholder."""
        filename = image.get('filename', 'image')
        alt_text = image.get('alt_text', '')
        
        if alt_text:
            return f"[IMAGE: {alt_text} ({filename})]"
        else:
            return f"[IMAGE: {filename}]"
    
    def export_to_string(self) -> str:
        """
        Export document to text string.
        
        Returns:
            Text string representation
        """
        return self.export_document_text(self.document)
    
    def validate_text(self, text_content: str) -> bool:
        """
        Validate text content.
        
        Args:
            text_content: Text content to validate
            
        Returns:
            True if valid text, False otherwise
        """
        try:
            # Basic validation - check for common text issues
            if text_content is None:
                return False
            
            # Check for excessive whitespace
            if re.search(r'\s{10,}', text_content):
                return False
            
            # Check for proper line endings
            if '\r\n' in text_content and '\n' in text_content:
                return False
            
            return True
            
        except Exception:
            return False
    
    def get_export_info(self) -> Dict[str, Any]:
        """Get export information."""
        return {
            'exporter_type': 'Text',
            'preserve_formatting': self.preserve_formatting,
            'line_width': self.line_width,
            'encoding': self.encoding,
            'document_type': type(self.document).__name__ if self.document else None
        }
