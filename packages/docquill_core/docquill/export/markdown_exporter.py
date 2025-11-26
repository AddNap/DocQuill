"""
Markdown exporter for DOCX documents.

Handles Markdown export with formatting, validation, and optimization.
"""

from typing import Dict, Any, Optional, List, Union
from pathlib import Path
import logging
import re

logger = logging.getLogger(__name__)

class MarkdownExporter:
    """
    Exports document to Markdown format.
    
    Handles Markdown export with formatting, validation, and optimization.
    """
    
    def __init__(self, document: Any, include_images: bool = True, 
                 table_style: str = 'pipe', heading_levels: int = 6):
        """
        Initialize Markdown exporter.
        
        Args:
            document: Document to export
            include_images: Whether to include images
            table_style: Table style ('pipe', 'grid', 'simple')
            heading_levels: Maximum heading levels to preserve
        """
        self.document = document
        self.include_images = include_images
        self.table_style = table_style
        self.heading_levels = heading_levels
        
        # Markdown formatting options
        self.formatting = {
            'bold': '**{}**',
            'italic': '*{}*',
            'underline': '<u>{}</u>',
            'strikethrough': '~~{}~~',
            'code': '`{}`',
            'code_block': '```\n{}\n```'
        }
        
        logger.debug("Markdown exporter initialized")
    
    def export(self, output_path: Union[str, Path]) -> bool:
        """
        Export document to Markdown.
        
        Args:
            output_path: Output file path
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Generate Markdown content
            markdown_content = self._generate_markdown()
            
            # Format and optimize output
            formatted_content = self.format_markdown_output(markdown_content)
            
            # Write to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(formatted_content)
            
            logger.info(f"Document exported to Markdown: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export document to Markdown: {e}")
            return False
    
    def export_paragraph(self, paragraph: Union[Dict[str, Any], Any]) -> str:
        """
        Export paragraph to Markdown.
        
        Args:
            paragraph: Paragraph data (dict or object)
            
        Returns:
            Markdown formatted paragraph
        """
        # Handle both dict and object inputs
        if hasattr(paragraph, 'get_text'):
            text = paragraph.get_text()
            style = getattr(paragraph, 'style', {})
        else:
            text = paragraph.get('text', '')
            style = paragraph.get('style', {})
        
        # Apply formatting
        formatted_text = self._apply_text_formatting(text, style)
        
        # Check if it's a heading
        if isinstance(style, dict) and style.get('heading_level'):
            level = min(style['heading_level'], 6)  # Max heading level is 6
            return f"{'#' * level} {formatted_text}\n"
        
        # Check if it's a list item
        if isinstance(style, dict) and style.get('list_type'):
            list_marker = self._get_list_marker(style['list_type'], style.get('list_level', 0))
            return f"{list_marker} {formatted_text}\n"
        
        # Regular paragraph
        if formatted_text.strip():
            return f"{formatted_text}\n"
        
        return ""
    
    def export_table(self, table: Union[Dict[str, Any], Any]) -> str:
        """
        Export table to Markdown.
        
        Args:
            table: Table data (dict or object)
            
        Returns:
            Markdown formatted table
        """
        if self.table_style == 'pipe':
            return self._export_table_pipe(table)
        elif self.table_style == 'grid':
            return self._export_table_grid(table)
        else:  # simple
            return self._export_table_simple(table)
    
    def export_heading(self, heading: Union[Dict[str, Any], Any]) -> str:
        """
        Export heading to Markdown.
        
        Args:
            heading: Heading data (dict or object)
            
        Returns:
            Markdown formatted heading
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
        
        level = min(level, 6)
        
        # Don't apply formatting to headings
        return f"{'#' * level} {text}\n"
    
    def export_image(self, image: Union[Dict[str, Any], Any]) -> str:
        """
        Export image to Markdown.
        
        Args:
            image: Image data (dict or object)
            
        Returns:
            Markdown formatted image
        """
        if not self.include_images:
            return ""
        
        # Handle both dict and object inputs
        if hasattr(image, 'get_src'):
            src = image.get_src()
            alt = image.get_alt()
        else:
            src = image.get('src', '')
            alt = image.get('alt', '')
        
        return f"![{alt}]({src})\n"
    
    def format_markdown_output(self, content: str) -> str:
        """
        Format Markdown output.
        
        Args:
            content: Raw Markdown content
            
        Returns:
            Formatted Markdown content
        """
        # Remove excessive blank lines
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        # Ensure proper spacing around headings
        content = re.sub(r'\n(#{1,6}\s)', r'\n\n\1', content)
        
        # Ensure proper spacing around lists
        content = re.sub(r'\n([\*\-\+]\s)', r'\n\n\1', content)
        content = re.sub(r'\n(\d+\.\s)', r'\n\n\1', content)
        
        # Ensure proper spacing around tables
        content = re.sub(r'\n(\|)', r'\n\n\1', content)
        
        # Clean up leading/trailing whitespace
        content = content.strip()
        
        return content
    
    def _generate_markdown(self) -> str:
        """Generate complete Markdown content."""
        markdown_parts = []
        
        # Add document title if available
        if hasattr(self.document, 'title') and self.document.title:
            markdown_parts.append(f"# {self.document.title}\n")
        
        # Export paragraphs
        if hasattr(self.document, 'get_paragraphs'):
            paragraphs = self.document.get_paragraphs()
            for para in paragraphs:
                markdown_parts.append(self.export_paragraph(para))
        
        # Export tables
        if hasattr(self.document, 'get_tables'):
            tables = self.document.get_tables()
            for table in tables:
                markdown_parts.append(self.export_table(table))
        
        # Export images
        if self.include_images and hasattr(self.document, 'get_images'):
            images = self.document.get_images()
            for image in images:
                markdown_parts.append(self._export_image(image))
        
        return '\n'.join(markdown_parts)
    
    def _apply_text_formatting(self, text: str, style) -> str:
        """Apply text formatting based on style."""
        if not text or not style:
            return text
        
        # Handle string style
        if isinstance(style, str):
            return text
        
        # Apply bold
        if style.get('bold'):
            text = self.formatting['bold'].format(text)
        
        # Apply italic
        if style.get('italic'):
            text = self.formatting['italic'].format(text)
        
        # Apply underline
        if style.get('underline'):
            text = self.formatting['underline'].format(text)
        
        # Apply strikethrough
        if style.get('strikethrough'):
            text = self.formatting['strikethrough'].format(text)
        
        # Apply code formatting
        if style.get('code'):
            text = self.formatting['code'].format(text)
        
        return text
    
    def _get_list_marker(self, list_type: str, level: int) -> str:
        """Get list marker based on type and level."""
        indent = '  ' * level
        
        if list_type == 'bullet':
            return f"{indent}-"
        elif list_type == 'number':
            return f"{indent}1."
        elif list_type == 'alpha':
            return f"{indent}a."
        elif list_type == 'roman':
            return f"{indent}i."
        else:
            return f"{indent}-"
    
    def _export_table_pipe(self, table: Union[Dict[str, Any], Any]) -> str:
        """Export table in pipe format."""
        # Handle both dict and object inputs
        if hasattr(table, 'get_rows'):
            rows = table.get_rows()
        else:
            rows = table.get('rows', [])
        
        if not rows:
            return ""

        markdown_rows = []

        # Header row
        if rows:
            if hasattr(rows[0], 'get_cells'):
                header_cells = [cell.get_text() for cell in rows[0].get_cells()]
            else:
                header_cells = [cell.get('text', '') for cell in rows[0].get('cells', [])]
            markdown_rows.append('| ' + ' | '.join(header_cells) + ' |')
            markdown_rows.append('| ' + ' | '.join(['---'] * len(header_cells)) + ' |')
        
        # Data rows
        for row in rows[1:]:
            if hasattr(row, 'get_cells'):
                cells = [cell.get_text() for cell in row.get_cells()]
            else:
                cells = [cell.get('text', '') for cell in row.get('cells', [])]
            markdown_rows.append('| ' + ' | '.join(cells) + ' |')
        
        return '\n'.join(markdown_rows) + '\n'
    
    def _export_table_grid(self, table: Union[Dict[str, Any], Any]) -> str:
        """Export table in grid format."""
        # Handle both dict and object inputs
        if hasattr(table, 'get_rows'):
            rows = table.get_rows()
        else:
            rows = table.get('rows', [])
        
        if not rows:
            return ""
        
        markdown_rows = []
        
        for i, row in enumerate(rows):
            if hasattr(row, 'get_cells'):
                cells = [cell.get_text() for cell in row.get_cells()]
            else:
                cells = [cell.get('text', '') for cell in row.get('cells', [])]
            markdown_rows.append('+ ' + ' + '.join(cells) + ' +')
            
            if i == 0:  # Add separator after header
                separator = '| ' + ' | '.join(['---'] * len(cells)) + ' |'
                markdown_rows.append(separator)
        
        return '\n'.join(markdown_rows) + '\n'
    
    def _export_table_simple(self, table: Union[Dict[str, Any], Any]) -> str:
        """Export table in simple format."""
        # Handle both dict and object inputs
        if hasattr(table, 'get_rows'):
            rows = table.get_rows()
        else:
            rows = table.get('rows', [])
        
        if not rows:
            return ""

        markdown_rows = []

        for row in rows:
            if hasattr(row, 'get_cells'):
                cells = [cell.get_text() for cell in row.get_cells()]
            else:
                cells = [cell.get('text', '') for cell in row.get('cells', [])]
            markdown_rows.append('  '.join(cells))
        
        return '\n'.join(markdown_rows) + '\n'
    
    def _export_image(self, image: Dict[str, Any]) -> str:
        """Export image to Markdown."""
        filename = image.get('filename', 'image')
        alt_text = image.get('alt_text', '')
        title = image.get('title', '')
        
        if title:
            return f"![{alt_text}]({filename} \"{title}\")\n"
        else:
            return f"![{alt_text}]({filename})\n"
    
    def export_to_string(self) -> str:
        """
        Export document to Markdown string.
        
        Returns:
            Markdown string representation
        """
        return self._generate_markdown()
    
    def validate_markdown(self, markdown_content: str) -> bool:
        """
        Validate Markdown content.
        
        Args:
            markdown_content: Markdown content to validate
            
        Returns:
            True if valid Markdown, False otherwise
        """
        try:
            # Basic validation - check for common Markdown syntax
            lines = markdown_content.split('\n')
            
            for line in lines:
                # Check for valid heading syntax
                if line.startswith('#'):
                    if not re.match(r'^#{1,6}\s', line):
                        return False
                
                # Check for valid list syntax
                if re.match(r'^\s*[\*\-\+]\s', line) or re.match(r'^\s*\d+\.\s', line):
                    continue
                
                # Check for valid table syntax
                if '|' in line and not line.strip().startswith('|'):
                    return False
            
            return True
            
        except Exception:
            return False
    
    def get_export_info(self) -> Dict[str, Any]:
        """Get export information."""
        return {
            'exporter_type': 'Markdown',
            'include_images': self.include_images,
            'table_style': self.table_style,
            'heading_levels': self.heading_levels,
            'document_type': type(self.document).__name__ if self.document else None
        }
