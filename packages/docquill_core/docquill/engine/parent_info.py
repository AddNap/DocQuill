"""Parent information for nested element processing.

This module provides utilities for tracking parent elements when processing
nested structures (e.g., paragraphs in table cells, elements in textboxes).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional


@dataclass(slots=True)
class ParentInfo:
    """Information about parent element for nested processing.
    
    This tells the engine where to append the result of processing a nested element.
    Context includes parent-specific information like margins, padding, indents.
    """
    parent_element: Any  # The parent element (e.g., TableCell, TextBox)
    parent_type: str  # Type of parent ("cell", "textbox", "header", "footer", etc.)
    append_target: Callable[[Any], None]  # Function to append result to parent
    context: Dict[str, Any]  # Additional context (e.g., cell_width, cell_height, cell_margins, parent_indents)
    
    def append(self, item: Any) -> None:
        """Append processed item to parent.
        
        Args:
            item: Processed element (LayoutBlock or dict)
        """
        self.append_target(item)
    
    @classmethod
    def for_cell(
        cls,
        cell: Any,
        append_target: Callable[[Any], None],
        context: Optional[Dict[str, Any]] = None,
    ) -> ParentInfo:
        """Create ParentInfo for table cell.
        
        Args:
            cell: Table cell element
            append_target: Function to append to cell's element list
            context: Cell context (width, height, margins, etc.)
            
        Returns:
            ParentInfo for cell
        """
        return cls(
            parent_element=cell,
            parent_type="cell",
            append_target=append_target,
            context=context or {},
        )
    
    @classmethod
    def for_textbox(
        cls,
        textbox: Any,
        append_target: Callable[[Any], None],
        context: Optional[Dict[str, Any]] = None,
    ) -> ParentInfo:
        """Create ParentInfo for textbox.
        
        Args:
            textbox: TextBox element
            append_target: Function to append to textbox's content
            context: Textbox context (width, height, margins, etc.)
            
        Returns:
            ParentInfo for textbox
        """
        return cls(
            parent_element=textbox,
            parent_type="textbox",
            append_target=append_target,
            context=context or {},
        )
    
    @classmethod
    def for_header(
        cls,
        header: Any,
        append_target: Callable[[Any], None],
        context: Optional[Dict[str, Any]] = None,
    ) -> ParentInfo:
        """Create ParentInfo for header.
        
        Args:
            header: Header element
            append_target: Function to append to header's content
            context: Header context
            
        Returns:
            ParentInfo for header
        """
        return cls(
            parent_element=header,
            parent_type="header",
            append_target=append_target,
            context=context or {},
        )
    
    @classmethod
    def for_footer(
        cls,
        footer: Any,
        append_target: Callable[[Any], None],
        context: Optional[Dict[str, Any]] = None,
    ) -> ParentInfo:
        """Create ParentInfo for footer.
        
        Args:
            footer: Footer element
            append_target: Function to append to footer's content
            context: Footer context
            
        Returns:
            ParentInfo for footer
        """
        return cls(
            parent_element=footer,
            parent_type="footer",
            append_target=append_target,
            context=context or {},
        )

