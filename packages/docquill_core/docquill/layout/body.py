"""
Body model for DOCX documents.

Handles main document content, paragraphs, tables, and sections.
"""

from typing import List, Dict, Any, Optional
import logging
from .section import Section

logger = logging.getLogger(__name__)

class Body:
    """
    Represents the main body of the document.
    
    Handles content management, paragraphs, tables, and sections.
    """
    
    def __init__(self):
        """
        Initialize body.
        
        Sets up content collection and sections.
        """
        # Content collections
        self.paragraphs = []
        self.tables = []
        self.images = []
        self.other_elements = []
        
        # Sections
        self.sections = []
        self.current_section = None
        
        # Content order
        self.content_order = []
        
        logger.debug("Body initialized")
    
    def add_paragraph(self, paragraph) -> None:
        """
        Add paragraph to body.
        
        Args:
            paragraph: Paragraph content (dict or object)
        """
        if isinstance(paragraph, dict):
            paragraph['type'] = 'paragraph'
            paragraph['body_index'] = len(self.paragraphs)
            self.paragraphs.append(paragraph)
        else:
            # Handle object paragraph - add directly
            self.paragraphs.append(paragraph)
        
        self.content_order.append(paragraph)
        
        logger.debug(f"Paragraph added: {paragraph.get('text', '') if isinstance(paragraph, dict) else 'object'}")
    
    def add_table(self, table) -> None:
        """
        Add table to body.
        
        Args:
            table: Table content (dict or object)
        """
        if isinstance(table, dict):
            table['type'] = 'table'
            table['body_index'] = len(self.tables)
            self.tables.append(table)
        else:
            # Handle object table - add directly
            self.tables.append(table)
        
        self.content_order.append(table)
        
        logger.debug(f"Table added: {table.get('rows', 0) if isinstance(table, dict) else 'object'}")
    
    def add_image(self, image) -> None:
        """
        Add image to body.
        
        Args:
            image: Image content (dict or object)
        """
        if isinstance(image, dict):
            image['type'] = 'image'
            image['body_index'] = len(self.images)
            self.images.append(image)
        else:
            # Handle object image - add directly
            self.images.append(image)
        
        self.content_order.append(image)
        
        logger.debug(f"Image added: {image.get('filename', 'unknown') if isinstance(image, dict) else 'object'}")
    
    def add_element(self, element: Dict[str, Any]) -> None:
        """
        Add other element to body.
        
        Args:
            element: Element content
        """
        # Handle both dict and object inputs
        if isinstance(element, dict):
            element['type'] = element.get('type', 'unknown')
            element['body_index'] = len(self.other_elements)
            self.other_elements.append(element)
        else:
            # Handle object element - add directly
            self.other_elements.append(element)
        
        self.content_order.append(element)
        
        logger.debug(f"Element added: {element.get('type', 'unknown') if isinstance(element, dict) else 'object'}")
    
    def set_section_properties(self, section_props: Dict[str, Any]) -> None:
        """
        Set section properties.
        
        Args:
            section_props: Section properties
        """
        if self.current_section is None:
            self.current_section = Section(len(self.sections) + 1)
            self.sections.append(self.current_section)
        
        # Apply section properties
        if 'page_size' in section_props:
            width, height = section_props['page_size']
            self.current_section.set_page_size(width, height)
        elif 'page_width_mm' in section_props and 'page_height_mm' in section_props:
            width = section_props['page_width_mm']
            height = section_props['page_height_mm']
            self.current_section.set_page_size(height, width)
        
        if 'margins' in section_props:
            margins = section_props['margins']
            self.current_section.set_page_margins(margins)
        
        if 'orientation' in section_props:
            from .page import Orientation
            orientation = Orientation(section_props['orientation'])
            self.current_section.set_orientation(orientation)
        
        if 'columns' in section_props:
            columns = section_props['columns']
            self.current_section.set_columns(
                columns.get('count', 1),
                columns.get('spacing', 6.35)
            )
        
        logger.debug(f"Section properties set: {section_props}")
    
    def get_paragraphs(self, filter_text: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all paragraphs in body.
        
        Args:
            filter_text: Optional text filter
            
        Returns:
            List of paragraphs
        """
        if filter_text:
            return [p for p in self.paragraphs if filter_text.lower() in p.get('text', '').lower()]
        return self.paragraphs.copy()
    
    def get_tables(self, min_rows: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all tables in body.
        
        Args:
            min_rows: Optional minimum row count filter
            
        Returns:
            List of tables
        """
        if min_rows:
            return [t for t in self.tables if t.get('rows', 0) >= min_rows]
        return self.tables.copy()
    
    def get_images(self, image_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all images in body.
        
        Args:
            image_type: Optional image type filter
            
        Returns:
            List of images
        """
        if image_type:
            return [i for i in self.images if i.get('image_type') == image_type]
        return self.images.copy()
    
    def get_text(self, include_formatting: bool = False) -> str:
        """
        Get text content from all elements.
        
        Args:
            include_formatting: Whether to include formatting markers
            
        Returns:
            Combined text content
        """
        text_parts = []
        
        for element in self.content_order:
            # Check if element is a paragraph
            if element in self.paragraphs:
                if isinstance(element, dict):
                    text = element.get('text', '')
                    if include_formatting and element.get('style'):
                        text = f"[{element['style']}]{text}[/{element['style']}]"
                else:
                    # Handle object paragraph
                    if hasattr(element, 'get_text'):
                        text = element.get_text()
                    else:
                        text = str(element)
                text_parts.append(text)
            # Check if element is a table
            elif element in self.tables:
                table_text = self._extract_table_text(element)
                if include_formatting:
                    table_text = f"[TABLE]{table_text}[/TABLE]"
                text_parts.append(table_text)
            # Check if element is an image
            elif element in self.images:
                if isinstance(element, dict):
                    image_text = f"[IMAGE: {element.get('filename', 'unknown')}]"
                else:
                    # Handle object image
                    if hasattr(element, 'get_src'):
                        image_text = f"[IMAGE: {element.get_src()}]"
                    else:
                        image_text = f"[IMAGE: {str(element)}]"
                text_parts.append(image_text)
            # Check if element is other element
            elif element in self.other_elements:
                if isinstance(element, dict):
                    element_text = element.get('text', '')
                    if include_formatting and element.get('type'):
                        element_text = f"[{element['type']}]{element_text}[/{element['type']}]"
                else:
                    # Handle object element
                    if hasattr(element, 'get_text'):
                        element_text = element.get_text()
                    else:
                        element_text = str(element)
                text_parts.append(element_text)
        
        return '\n'.join(text_parts)
    
    def _extract_table_text(self, table) -> str:
        """Extract text from table."""
        if isinstance(table, dict):
            rows = table.get('rows', [])
            text_rows = []
            
            for row in rows:
                cells = row.get('cells', [])
                cell_texts = [cell.get('text', '') for cell in cells]
                text_rows.append(' | '.join(cell_texts))
            
            return '\n'.join(text_rows)
        else:
            # Handle object table
            if hasattr(table, 'get_text'):
                return table.get_text()
            else:
                return str(table)
    
    def get_content_by_type(self, content_type: str) -> List[Dict[str, Any]]:
        """
        Get content by type.
        
        Args:
            content_type: Type of content to retrieve
            
        Returns:
            List of content elements
        """
        if content_type == 'paragraph':
            return self.paragraphs.copy()
        elif content_type == 'table':
            return self.tables.copy()
        elif content_type == 'image':
            return self.images.copy()
        elif content_type == 'other':
            return self.other_elements.copy()
        else:
            return []
    
    def get_all_content(self) -> List[Dict[str, Any]]:
        """Get all content in order."""
        all_content = []
        
        for element in self.content_order:
            # Check if element is a paragraph
            if element in self.paragraphs:
                all_content.append(element)
            # Check if element is a table
            elif element in self.tables:
                all_content.append(element)
            # Check if element is an image
            elif element in self.images:
                all_content.append(element)
            # Check if element is other element
            elif element in self.other_elements:
                all_content.append(element)
        
        return all_content
    
    def get_body_info(self) -> Dict[str, Any]:
        """Get complete body information."""
        return {
            'paragraph_count': len(self.paragraphs),
            'table_count': len(self.tables),
            'image_count': len(self.images),
            'other_element_count': len(self.other_elements),
            'section_count': len(self.sections),
            'total_content': len(self.content_order),
            'total_elements': len(self.paragraphs) + len(self.tables) + len(self.images) + len(self.other_elements),
            'current_section': self.current_section.section_number if self.current_section else None
        }
    
    def clear_content(self) -> None:
        """Clear all content from body."""
        self.paragraphs.clear()
        self.tables.clear()
        self.images.clear()
        self.other_elements.clear()
        self.content_order.clear()
        logger.debug("Body content cleared")
    
    def get_sections(self) -> List[Section]:
        """Get all sections."""
        return self.sections.copy()
    
    def create_new_section(self) -> Section:
        """Create a new section."""
        new_section = Section(len(self.sections) + 1)
        self.sections.append(new_section)
        self.current_section = new_section
        logger.debug(f"New section created: {new_section.section_number}")
        return new_section
