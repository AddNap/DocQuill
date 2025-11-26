"""
Table model for DOCX documents.

Enhanced implementation with full WordprocessingML support.
"""

from typing import List, Dict, Any, Optional, Tuple, Type, Union
from .base import Models
from .body import Body
import logging

logger = logging.getLogger(__name__)

class TableProperties:
    """
    Table properties for styling and formatting.
    
    Handles tblPr, tblGrid, tblBorders, tblLook, tblStyle, w:tblW etc.
    """
    
    def __init__(self, borders: Optional[Dict[str, Any]] = None, 
                 cell_spacing: Optional[float] = None, 
                 style: Optional[str] = None, 
                 alignment: Optional[str] = None,
                 width: Optional[Union[int, str]] = None,
                 width_type: Optional[str] = None,
                 indent: Optional[Dict[str, Any]] = None,
                 look: Optional[Dict[str, Any]] = None,
                 grid: Optional[List[Dict[str, Any]]] = None,
                 shading: Optional[Dict[str, Any]] = None,
                 cell_margins: Optional[Dict[str, Any]] = None,
                 style_id: Optional[str] = None):
        """
        Initialize table properties.
        
        Args:
            borders: Table borders configuration
            cell_spacing: Cell spacing in twips
            style: Table style name
            alignment: Table alignment (left, center, right)
            width: Table width
            look: Table look properties
            grid: Table grid configuration
            shading: Table shading dictionary (w:shd attributes)
            cell_margins: Table cell margins configuration
            style_id: Table style identifier (from w:tblStyle)
        """
        self.borders = borders or {}
        self.cell_spacing = cell_spacing
        self.style = style
        self.style_id = style_id
        self.alignment = alignment
        self.width = width
        self.width_type = width_type
        self.indent = indent or {}
        self.look = look or {}
        self.grid = grid or []
        self.shading = shading
        self.cell_margins = cell_margins or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'borders': self.borders,
            'cell_spacing': self.cell_spacing,
            'style': self.style,
            'style_id': self.style_id,
            'alignment': self.alignment,
            'width': self.width,
            'width_type': self.width_type,
            'indent': self.indent,
            'look': self.look,
            'grid': self.grid,
            'shading': self.shading,
            'cell_margins': self.cell_margins
        }

class Table(Body):
    """
    Represents a table with rows and cells.
    Inherits from Body, so can contain: Paragraph, Table, Image, TextBox, etc.
    
    Enhanced implementation with full WordprocessingML support.
    """
    
    def __init__(self):
        """Initialize table."""
        super().__init__()
        self.rows: List['TableRow'] = []
        self.properties: Optional[TableProperties] = None
        self.grid: List[Dict[str, Any]] = []  # column widths and properties
        self._table_id: Optional[str] = None
        self.cant_split: bool = False
        self.header_repeat: bool = False
    
    @property
    def style(self) -> Optional[str]:
        """Get table style (compatibility property)."""
        return self.properties.style if self.properties else None
    
    @style.setter
    def style(self, value: str):
        """Set table style (compatibility property)."""
        self.set_style(value)
    
    def add_row(self, row: 'TableRow'):
        """Add row to table."""
        if isinstance(row, TableRow):
            self.rows.append(row)
            self.add_child(row)
            logger.debug(f"Added row to table. Total rows: {len(self.rows)}")
    
    def set_properties(self, properties: TableProperties):
        """Set table properties."""
        self.properties = properties
        logger.debug("Table properties set")
    
    def set_style(self, style: str):
        """Set table style."""
        if self.properties is None:
            self.properties = TableProperties()
        self.properties.style = style
        logger.debug(f"Table style set to: {style}")
    
    def set_grid(self, grid: List[Dict[str, Any]]):
        """Set table grid (column widths and properties)."""
        self.grid = grid
        if self.properties is None:
            self.properties = TableProperties()
        self.properties.grid = grid
        logger.debug(f"Table grid set with {len(grid)} columns")
    
    def get_rows(self) -> List['TableRow']:
        """Get all rows in table."""
        return self.rows.copy()
    
    def get_cell(self, row_index: int, col_index: int) -> Optional['TableCell']:
        """Get cell at specific position."""
        if 0 <= row_index < len(self.rows):
            row = self.rows[row_index]
            if 0 <= col_index < len(row.cells):
                return row.cells[col_index]
        return None
    
    def get_dimensions(self) -> Tuple[int, int]:
        """Get table dimensions (rows, columns)."""
        if not self.rows:
            return (0, 0)
        
        max_cols = max(len(row.cells) for row in self.rows)
        return (len(self.rows), max_cols)
    
    def get_text(self) -> str:
        """Get text content from all cells."""
        text_parts = []
        for row in self.rows:
            row_text = row.get_text()
            if row_text:
                text_parts.append(row_text)
        return '\n'.join(text_parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert table to dictionary representation."""
        return {
            'type': 'table',
            'id': self._table_id,
            'rows': [row.to_dict() for row in self.rows],
            'properties': self.properties.to_dict() if self.properties else {},
            'grid': self.grid,
            'dimensions': self.get_dimensions()
        }
    
    def to_html(self) -> str:
        """Convert table to HTML representation."""
        html_parts = ['<table>']
        
        # Add table properties as attributes
        if self.properties:
            if self.properties.style:
                html_parts[0] = f'<table class="{self.properties.style}">'
        
        # Add rows
        for row in self.rows:
            html_parts.append(row.to_html())
        
        html_parts.append('</table>')
        return '\n'.join(html_parts)
    
    def validate_structure(self) -> bool:
        """Validate table structure."""
        if not self.rows:
            return True
        
        # Check if all rows have the same number of cells
        first_row_cells = len(self.rows[0].cells)
        for row in self.rows[1:]:
            if len(row.cells) != first_row_cells:
                logger.warning(f"Table structure inconsistent: row has {len(row.cells)} cells, expected {first_row_cells}")
                return False
        
        return True


class TableRow(Models):
    """
    Represents a table row.
    
    Enhanced implementation with full WordprocessingML support.
    """
    
    def __init__(self):
        """Initialize table row."""
        super().__init__()
        self.cells: List['TableCell'] = []
        self.height: Optional[int] = None
        self.style: Optional[Dict[str, Any]] = None
        self.is_header_row: bool = False
        self.row_cant_split: bool = False
        self.grid_after: Optional[int] = None
        self.grid_before: Optional[int] = None
        self.shading: Optional[Dict[str, Any]] = None
        self.cant_split: bool = False
        self.header: bool = False
        self.repeat: bool = False
    
    def add_cell(self, cell: 'TableCell'):
        """Add cell to row."""
        if isinstance(cell, TableCell):
            self.cells.append(cell)
            self.add_child(cell)
            logger.debug(f"Added cell to row. Total cells: {len(self.cells)}")
    
    def set_height(self, height: int):
        """Set row height."""
        self.height = height
        logger.debug(f"Row height set to: {height}")
    
    def set_header_row(self, is_header: bool):
        """Set if row is header row (w:tblHeader)."""
        self.is_header_row = is_header
        logger.debug(f"Row header status set to: {is_header}")
    
    def set_cant_split(self, cant_split: bool):
        """Set row cant split property."""
        self.row_cant_split = cant_split
        logger.debug(f"Row cant split set to: {cant_split}")
    
    def set_grid_after(self, grid_after: int):
        """Set grid after property."""
        self.grid_after = grid_after
        logger.debug(f"Grid after set to: {grid_after}")
    
    def set_grid_before(self, grid_before: int):
        """Set grid before property."""
        self.grid_before = grid_before
        logger.debug(f"Grid before set to: {grid_before}")
    
    def set_shading(self, shading: Dict[str, Any]):
        """Set row shading."""
        self.shading = shading
        logger.debug(f"Row shading set: {shading}")
    
    def get_cells(self) -> List['TableCell']:
        """Get all cells in row."""
        return self.cells.copy()
    
    def get_text(self) -> str:
        """Get text content from all cells."""
        text_parts = []
        for cell in self.cells:
            cell_text = cell.get_text()
            if cell_text:
                text_parts.append(cell_text)
        return '\t'.join(text_parts)  # Tab-separated for row text
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert row to dictionary representation."""
        return {
            'type': 'table_row',
            'cells': [cell.to_dict() for cell in self.cells],
            'height': self.height,
            'style': self.style,
            'is_header_row': self.is_header_row,
            'row_cant_split': self.row_cant_split,
            'grid_after': self.grid_after,
            'grid_before': self.grid_before
        }
    
    def to_html(self) -> str:
        """Convert row to HTML representation."""
        html_parts = ['<tr>']
        
        for cell in self.cells:
            # Get cell HTML content without the outer <td> tags
            cell_html = cell.to_html()
            # Remove the outer <td> tags and use appropriate tag for row
            if cell_html.startswith('<td'):
                # Extract content between <td> and </td>
                start = cell_html.find('>') + 1
                end = cell_html.rfind('</td>')
                cell_content = cell_html[start:end].strip()
                
                # Use appropriate tag based on row type
                tag = 'th' if self.is_header_row else 'td'
                html_parts.append(f'  <{tag}>{cell_content}</{tag}>')
            else:
                # Fallback if cell HTML doesn't have expected structure
                tag = 'th' if self.is_header_row else 'td'
                html_parts.append(f'  <{tag}>{cell_html}</{tag}>')
        
        html_parts.append('</tr>')
        return '\n'.join(html_parts)


class TableCell(Body):
    """
    Represents a table cell.
    Inherits from Body, so can contain: Paragraph, Table, Image, TextBox, etc.
    
    Enhanced implementation with full WordprocessingML support.
    """
    
    def __init__(self):
        """Initialize table cell."""
        super().__init__()
        self.width: Optional[int] = None
        self.width_spec: Optional[Dict[str, Any]] = None
        self.vertical_merge: bool = False
        self.vertical_merge_type: Optional[str] = None
        self.grid_span: int = 1
        self.content: List[Union[Models, str]] = []
        self.style: Optional[Dict[str, Any]] = None
        self.shading: Optional[Dict[str, Any]] = None
        self.vertical_align: Optional[str] = None
        self.text_direction: Optional[str] = None
        self.cell_borders: Optional[Dict[str, Any]] = None
        self.cell_margins: Optional[Dict[str, Any]] = None
        self.horizontal_align: Optional[str] = None
    
    def set_width(self, width: int):
        """Set cell width."""
        self.width = width
        logger.debug(f"Cell width set to: {width}")
    
    def set_width_spec(self, width_spec: Dict[str, Any]):
        """Store preferred width specification (tcW attributes)."""
        self.width_spec = width_spec
        width_value = width_spec.get('w') or width_spec.get('val')
        if width_value:
            try:
                self.width = int(width_value)
            except (TypeError, ValueError):
                pass
    
    def set_vertical_merge(self, merge: Union[bool, str, Dict[str, Any]]):
        """Set vertical merge property.
        Accepts either boolean, raw string value (restart/continue), or attribute dict from XML.
        """
        merge_type = None
        if isinstance(merge, dict):
            merge_type = merge.get('val') or merge.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
        elif isinstance(merge, str):
            merge_type = merge
        else:
            merge_type = 'continue' if merge else None

        self.vertical_merge_type = merge_type
        self.vertical_merge = merge_type not in (None, 'restart')
        logger.debug(f"Vertical merge set to: {self.vertical_merge} (type={merge_type})")
    
    def set_grid_span(self, span: int):
        """Set grid span (column span)."""
        self.grid_span = span
        logger.debug(f"Grid span set to: {span}")
    
    def set_shading(self, shading: Dict[str, Any]):
        """Set cell shading (w:shd)."""
        self.shading = shading
        logger.debug(f"Cell shading set: {shading}")
    
    def set_vertical_align(self, align: str):
        """Set vertical alignment (w:vAlign)."""
        self.vertical_align = align
        logger.debug(f"Vertical alignment set to: {align}")
    
    def set_horizontal_align(self, align: str):
        """Set horizontal alignment (w:jc)."""
        self.horizontal_align = align
        logger.debug(f"Horizontal alignment set to: {align}")
    
    def set_text_direction(self, direction: str):
        """Set text direction."""
        self.text_direction = direction
        logger.debug(f"Text direction set to: {direction}")
    
    def set_cell_borders(self, borders: Dict[str, Any]):
        """Set cell borders."""
        self.cell_borders = borders
        logger.debug(f"Cell borders set: {borders}")
    
    def set_borders(self, borders: Dict[str, Any]):
        """Set cell borders (alias for set_cell_borders)."""
        self.set_cell_borders(borders)
    
    def set_margins(self, margins: Dict[str, Any]):
        """Set cell margins."""
        self.cell_margins = margins
        logger.debug(f"Cell margins set: {margins}")
    
    def add_model(self, model: Models):
        """Add model to cell (inherits from Body)."""
        self.add_child(model)
        self.content.append(model)
        logger.debug(f"Added model to cell: {type(model).__name__}")
    
    def add_content(self, content: Union[Models, str]):
        """Add content to cell."""
        self.content.append(content)
        if isinstance(content, Models):
            self.add_child(content)
        logger.debug(f"Added content to cell: {type(content).__name__}")
    
    def get_content(self) -> List[Union[Models, str]]:
        """Get all content in cell."""
        return self.content.copy()
    
    def get_text(self) -> str:
        """Get text content from cell."""
        text_parts = []
        for content in self.content:
            if hasattr(content, 'get_text'):
                text = content.get_text()
                if text:
                    text_parts.append(text)
        return '\n'.join(text_parts)
    
    def set_text(self, text: str):
        """
        Set text content for cell.
        
        Args:
            text: Text to set
        """
        # Clear existing content
        self.content.clear()
        self.children.clear()
        
        # Create a paragraph with the text
        from .paragraph import Paragraph
        paragraph = Paragraph()
        paragraph.set_text(text)
        self.add_content(paragraph)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert cell to dictionary representation."""
        return {
            'type': 'table_cell',
            'width': self.width,
            'vertical_merge': self.vertical_merge,
            'grid_span': self.grid_span,
            'content': [content.to_dict() if hasattr(content, 'to_dict') else str(content) for content in self.content],
            'style': self.style,
            'shading': self.shading,
            'vertical_align': self.vertical_align,
            'text_direction': self.text_direction,
            'cell_borders': self.cell_borders
        }
    
    def to_html(self) -> str:
        """Convert cell to HTML representation."""
        html_parts = []
        
        # Add cell attributes
        attrs = []
        if self.grid_span > 1:
            attrs.append(f'colspan="{self.grid_span}"')
        if self.vertical_align:
            attrs.append(f'valign="{self.vertical_align}"')
        if self.shading and 'color' in self.shading:
            attrs.append(f'style="background-color: {self.shading["color"]}"')
        
        attr_str = ' ' + ' '.join(attrs) if attrs else ''
        
        html_parts.append(f'<td{attr_str}>')
        
        # Add content
        for content in self.content:
            if hasattr(content, 'to_html'):
                html_parts.append(content.to_html())
            elif hasattr(content, 'get_text'):
                html_parts.append(content.get_text())
            else:
                html_parts.append(str(content))
        
        html_parts.append('</td>')
        return '\n'.join(html_parts)
