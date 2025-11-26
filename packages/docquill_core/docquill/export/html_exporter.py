"""
HTML exporter for DOCX documents.

Handles HTML export with logical structure, formatting, and validation.
"""

from typing import Dict, Any, Optional, List, Union
from pathlib import Path
import logging
import re

logger = logging.getLogger(__name__)

class HTMLExporter:
    """
    Exports document to logical HTML.
    
    Handles HTML export with logical structure, formatting, and validation.
    """
    
    def __init__(self, document: Any, include_css: bool = True, 
                 include_metadata: bool = True, css_style: str = 'default'):
        """
        Initialize HTML exporter.
        
        Args:
            document: Document to export
            include_css: Whether to include CSS styles
            include_metadata: Whether to include document metadata
            css_style: CSS style ('default', 'minimal', 'print')
        """
        self.document = document
        self.include_css = include_css
        self.include_metadata = include_metadata
        self.css_style = css_style
        
        # HTML structure
        self.html_parts = []
        self.css_parts = []
        
        logger.debug("HTML exporter initialized")
    
    def export(self, output_path: Union[str, Path]) -> bool:
        """
        Export document to HTML.
        
        Args:
            output_path: Output file path
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Generate HTML content
            html_content = self._generate_html()
            
            # Write to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"Document exported to HTML: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export document to HTML: {e}")
            return False
    
    def export_document_structure(self, document: Any = None) -> str:
        """
        Export document structure to HTML.
        
        Args:
            document: Document to export
            
        Returns:
            HTML structure
        """
        if document is None:
            document = self.document
        
        html_parts = []
        
        # Document header
        html_parts.append("<div class='document'>")
        
        # Document title
        if hasattr(document, 'title') and document.title:
            html_parts.append(f'<title>{self._escape_html(document.title)}</title>')
            html_parts.append(f'<h1 class="document-title">{self._escape_html(document.title)}</h1>')
        
        # Document metadata
        if self.include_metadata:
            metadata_html = self._generate_metadata_html(document)
            if metadata_html:
                html_parts.append(metadata_html)
        
        # Document content
        content_html = self._generate_content_html(document)
        html_parts.append(content_html)
        
        html_parts.append('</div>')
        
        return '\n'.join(html_parts)
    
    def export_paragraph(self, paragraph: Union[Dict[str, Any], Any]) -> str:
        """
        Export paragraph to HTML.
        
        Args:
            paragraph: Paragraph data (dict or object)
            
        Returns:
            HTML formatted paragraph
        """
        # Handle both dict and object inputs
        if hasattr(paragraph, 'get_text'):
            text = paragraph.get_text()
            style = getattr(paragraph, 'style', {})
        else:
            text = paragraph.get('text', '')
            style = paragraph.get('style', {})
        
        # Apply text formatting
        formatted_text = self._apply_text_formatting(text, style)
        
        # Determine HTML tag
        if isinstance(style, dict) and style.get('heading_level'):
            level = min(style['heading_level'], 6)
            return f'<h{level} class="heading">{formatted_text}</h{level}>'
        elif isinstance(style, dict) and style.get('list_type'):
            list_marker = self._get_list_marker(style['list_type'])
            return f'<li class="list-item">{formatted_text}</li>'
        else:
            return f"<p class='paragraph'>{formatted_text}</p>"
    
    def export_heading(self, heading: Union[Dict[str, Any], Any]) -> str:
        """
        Export heading to HTML.
        
        Args:
            heading: Heading data (dict or object)
            
        Returns:
            HTML formatted heading
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
        formatted_text = self._escape_html(text)
        return f"<h{level} class='heading'>{formatted_text}</h{level}>"
    
    def export_table(self, table: Union[Dict[str, Any], Any]) -> str:
        """
        Export table to HTML.
        
        Args:
            table: Table data (dict or object)
            
        Returns:
            HTML formatted table
        """
        # Handle both dict and object inputs
        if hasattr(table, 'get_rows'):
            rows = table.get_rows()
        else:
            rows = table.get('rows', [])
        
        if not rows:
            return ""

        html_parts = ["<table class='table'>"]

        # Header row
        if rows:
            html_parts.append('<thead>')
            html_parts.append('<tr>')
            if hasattr(rows[0], 'get_cells'):
                cells = rows[0].get_cells()
                for cell in cells:
                    if hasattr(cell, 'get_text'):
                        cell_text = cell.get_text()
                    else:
                        cell_text = str(cell)
                    html_parts.append(f'<th>{self._escape_html(cell_text)}</th>')
            else:
                for cell in rows[0].get('cells', []):
                    cell_text = self._escape_html(cell.get('text', ''))
                    html_parts.append(f'<th class="table-header">{cell_text}</th>')
            html_parts.append('</tr>')
            html_parts.append('</thead>')
            
            # Add data row with same content as header for single row tables
            if len(rows) == 1:
                html_parts.append('<tbody>')
                html_parts.append('<tr>')
                if hasattr(rows[0], 'get_cells'):
                    cells = rows[0].get_cells()
                    for cell in cells:
                        if hasattr(cell, 'get_text'):
                            cell_text = cell.get_text()
                        else:
                            cell_text = str(cell)
                        html_parts.append(f'<td>{self._escape_html(cell_text)}</td>')
                else:
                    for cell in rows[0].get('cells', []):
                        cell_text = self._escape_html(cell.get('text', ''))
                        html_parts.append(f'<td>{cell_text}</td>')
                html_parts.append('</tr>')
                html_parts.append('</tbody>')
        
        # Data rows
        html_parts.append('<tbody>')
        for row in rows[1:]:
            html_parts.append('<tr>')
            if hasattr(row, 'get_cells'):
                cells = row.get_cells()
                for cell in cells:
                    if hasattr(cell, 'get_text'):
                        cell_text = cell.get_text()
                    else:
                        cell_text = str(cell)
                    html_parts.append(f'<td class="table-cell">{self._escape_html(cell_text)}</td>')
            else:
                for cell in row.get('cells', []):
                    cell_text = self._escape_html(cell.get('text', ''))
                    html_parts.append(f'<td class="table-cell">{cell_text}</td>')
            html_parts.append('</tr>')
        html_parts.append('</tbody>')
        
        html_parts.append('</table>')
        
        return '\n'.join(html_parts)
    
    def generate_css_styles(self, document: Any = None) -> str:
        """
        Generate CSS styles for HTML.
        
        Args:
            document: Document to generate styles for
            
        Returns:
            CSS styles
        """
        if document is None:
            document = self.document
        
        if self.css_style == 'minimal':
            return self._generate_minimal_css()
        elif self.css_style == 'print':
            return self._generate_print_css()
        else:  # default
            return self._generate_default_css()
    
    def _generate_html(self) -> str:
        """Generate complete HTML document."""
        html_parts = []
        
        # HTML document start
        html_parts.append('<!DOCTYPE html>')
        html_parts.append('<html lang="en">')
        html_parts.append('<head>')
        html_parts.append('<meta charset="UTF-8">')
        html_parts.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
        
        # Document title
        if hasattr(self.document, 'title') and self.document.title:
            html_parts.append(f'<title>{self._escape_html(self.document.title)}</title>')
        else:
            html_parts.append('<title>Document</title>')
        
        # CSS styles
        if self.include_css:
            css_styles = self.generate_css_styles(self.document)
            html_parts.append(f'<style>\n{css_styles}\n</style>')
        
        html_parts.append('</head>')
        html_parts.append('<body>')
        
        # Document content
        document_html = self.export_document_structure(self.document)
        html_parts.append(document_html)
        
        html_parts.append('</body>')
        html_parts.append('</html>')
        
        return '\n'.join(html_parts)
    
    def _generate_metadata_html(self, document: Any) -> str:
        """Generate metadata HTML."""
        metadata_parts = []
        
        if hasattr(document, 'author') and document.author:
            metadata_parts.append(f'<div class="metadata-item"><strong>Author:</strong> {self._escape_html(document.author)}</div>')
        
        if hasattr(document, 'created') and document.created:
            metadata_parts.append(f'<div class="metadata-item"><strong>Created:</strong> {self._escape_html(str(document.created))}</div>')
        
        if hasattr(document, 'modified') and document.modified:
            metadata_parts.append(f'<div class="metadata-item"><strong>Modified:</strong> {self._escape_html(str(document.modified))}</div>')
        
        if metadata_parts:
            return f'<div class="document-metadata">\n' + '\n'.join(metadata_parts) + '\n</div>'
        
        return ""
    
    def _generate_content_html(self, document: Any) -> str:
        """Generate content HTML."""
        content_parts = []
        content_parts.append("<div class='content'>")
        
        # Export paragraphs
        if hasattr(document, 'get_paragraphs'):
            paragraphs = document.get_paragraphs()
            for para in paragraphs:
                content_parts.append(self.export_paragraph(para))
        
        # Export tables
        if hasattr(document, 'get_tables'):
            tables = document.get_tables()
            for table in tables:
                content_parts.append(self.export_table(table))
        
        # Export images
        if hasattr(document, 'get_images'):
            images = document.get_images()
            for image in images:
                content_parts.append(self._export_image(image))
        
        content_parts.append("</div>")
        return '\n'.join(content_parts)
    
    def _apply_text_formatting(self, text: str, style) -> str:
        """Apply text formatting based on style."""
        if text is None:
            text = ""
        escaped_text = self._escape_html(text).replace("\n", "<br/>")
        if not style:
            return escaped_text
        
        # Handle string style
        if isinstance(style, str):
            return escaped_text
        
        formatted_text = escaped_text
        
        # Apply bold
        if style.get('bold'):
            formatted_text = f'<strong>{formatted_text}</strong>'
        
        # Apply italic
        if style.get('italic'):
            formatted_text = f'<em>{formatted_text}</em>'
        
        # Apply underline
        if style.get('underline'):
            formatted_text = f'<u>{formatted_text}</u>'
        
        # Apply strikethrough
        if style.get('strikethrough'):
            formatted_text = f'<s>{formatted_text}</s>'
        
        # Apply code formatting
        if style.get('code'):
            formatted_text = f'<code>{formatted_text}</code>'
        
        return formatted_text
    
    def _get_list_marker(self, list_type: str) -> str:
        """Get list marker based on type."""
        if list_type == 'bullet':
            return '•'
        elif list_type == 'number':
            return '1.'
        elif list_type == 'alpha':
            return 'a.'
        elif list_type == 'roman':
            return 'i.'
        else:
            return '•'
    
    def _export_image(self, image: Dict[str, Any]) -> str:
        """Export image to HTML."""
        filename = image.get('filename', 'image')
        alt_text = image.get('alt_text', '')
        title = image.get('title', '')
        width = image.get('width', '')
        height = image.get('height', '')
        
        img_attrs = [f'alt="{self._escape_html(alt_text)}"']
        
        if title:
            img_attrs.append(f'title="{self._escape_html(title)}"')
        
        if width:
            img_attrs.append(f'width="{width}"')
        
        if height:
            img_attrs.append(f'height="{height}"')
        
        return f'<img src="{filename}" {" ".join(img_attrs)} class="image">'
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        if not text:
            return ""
        
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&#x27;')
        
        return text
    
    def _generate_default_css(self) -> str:
        """Generate default CSS styles."""
        return """
body {
    font-family: Arial, sans-serif;
    line-height: 1.6;
    margin: 0;
    padding: 20px;
    background-color: #ffffff;
    color: #333333;
}

.document {
    max-width: 800px;
    margin: 0 auto;
    background-color: #ffffff;
    padding: 20px;
    box-shadow: 0 0 10px rgba(0,0,0,0.1);
}

.document-title {
    color: #2c3e50;
    border-bottom: 2px solid #3498db;
    padding-bottom: 10px;
    margin-bottom: 20px;
}

.document-metadata {
    background-color: #f8f9fa;
    padding: 15px;
    border-left: 4px solid #3498db;
    margin-bottom: 20px;
}

.metadata-item {
    margin-bottom: 5px;
}

.paragraph {
    margin-bottom: 15px;
    text-align: justify;
}

.heading {
    color: #2c3e50;
    margin-top: 30px;
    margin-bottom: 15px;
}

.heading:first-child {
    margin-top: 0;
}

.table {
    width: 100%;
    border-collapse: collapse;
    margin: 20px 0;
}

.table-header {
    background-color: #3498db;
    color: white;
    padding: 12px;
    text-align: left;
    font-weight: bold;
}

.table-cell {
    padding: 12px;
    border-bottom: 1px solid #ddd;
}

.table tr:nth-child(even) {
    background-color: #f2f2f2;
}

.list-item {
    margin-bottom: 5px;
}

.image {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 20px auto;
}
"""
    
    def _generate_minimal_css(self) -> str:
        """Generate minimal CSS styles."""
        return """
body {
    font-family: Arial, sans-serif;
    line-height: 1.6;
    margin: 20px;
}

.document-title {
    font-size: 24px;
    font-weight: bold;
    margin-bottom: 20px;
}

.paragraph {
    margin-bottom: 10px;
}

.heading {
    font-weight: bold;
    margin-top: 20px;
    margin-bottom: 10px;
}

.table {
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0;
}

.table-header {
    background-color: #f0f0f0;
    font-weight: bold;
    padding: 8px;
}

.table-cell {
    padding: 8px;
    border: 1px solid #ddd;
}
"""
    
    def _generate_print_css(self) -> str:
        """Generate print-optimized CSS styles."""
        return """
@media print {
    body {
        font-family: "Times New Roman", serif;
        font-size: 12pt;
        line-height: 1.4;
        margin: 0;
        padding: 0;
    }
    
    .document {
        max-width: none;
        margin: 0;
        padding: 0;
        box-shadow: none;
    }
    
    .document-title {
        font-size: 18pt;
        font-weight: bold;
        margin-bottom: 12pt;
    }
    
    .paragraph {
        margin-bottom: 6pt;
        text-align: justify;
    }
    
    .heading {
        font-weight: bold;
        margin-top: 12pt;
        margin-bottom: 6pt;
    }
    
    .table {
        width: 100%;
        border-collapse: collapse;
        margin: 6pt 0;
    }
    
    .table-header {
        background-color: #f0f0f0;
        font-weight: bold;
        padding: 3pt;
    }
    
    .table-cell {
        padding: 3pt;
        border: 1px solid #000;
    }
}

@media screen {
    body {
        font-family: Arial, sans-serif;
        line-height: 1.6;
        margin: 20px;
        background-color: #ffffff;
    }
    
    .document {
        max-width: 800px;
        margin: 0 auto;
        background-color: #ffffff;
        padding: 20px;
    }
}
"""
    
    def export_to_string(self) -> str:
        """
        Export document to HTML string.
        
        Returns:
            HTML string representation
        """
        return self._generate_html()
    
    def validate_html(self, html_content: str) -> bool:
        """
        Validate HTML content.
        
        Args:
            html_content: HTML content to validate
            
        Returns:
            True if valid HTML, False otherwise
        """
        try:
            # Basic validation - check for common HTML syntax
            if not html_content.strip().startswith('<!DOCTYPE html>') and not html_content.strip().startswith('<html>'):
                return False
            
            # Check for required tags
            required_tags = ['<html>', '<body>']
            for tag in required_tags:
                if tag not in html_content:
                    return False
            
            # Check for balanced tags (basic check)
            open_tags = html_content.count('<')
            close_tags = html_content.count('>')
            if open_tags != close_tags:
                return False
            
            # Check for proper tag closure
            if html_content.count('<p>') != html_content.count('</p>'):
                return False
            if html_content.count('<body>') != html_content.count('</body>'):
                return False
            if html_content.count('<html>') != html_content.count('</html>'):
                return False
            
            return True
            
        except Exception:
            return False
    
    def get_export_info(self) -> Dict[str, Any]:
        """Get export information."""
        return {
            'exporter_type': 'HTML',
            'include_css': self.include_css,
            'include_metadata': self.include_metadata,
            'css_style': self.css_style,
            'document_type': type(self.document).__name__ if self.document else None
        }
