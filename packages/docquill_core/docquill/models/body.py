"""Body model for DOCX documents."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple, Type

from .base import Models


class Body(Models):
    """Represents the main document container (body or textbox content)."""

    def __init__(self) -> None:
        super().__init__()
        self.sections: List[Any] = []

    # ------------------------------------------------------------------
    def _allowed_types(self) -> Tuple[Type[Models], ...]:
        from .paragraph import Paragraph
        from .table import Table
        from .image import Image
        from .textbox import TextBox

        return (Paragraph, Table, Image, TextBox)

    def _attach_child(self, model: Models) -> Models:
        self.add_child(model)
        return model

    def add_model(self, model: Models) -> Models:
        if not isinstance(model, Models):
            raise TypeError(f"Body can only contain Models instances, got {type(model)!r}")
        if not isinstance(model, self._allowed_types()):
            allowed = ", ".join(t.__name__ for t in self._allowed_types())
            raise TypeError(f"Unsupported model type {type(model).__name__}; allowed: {allowed}")
        return self._attach_child(model)

    def add_paragraph(self, paragraph: Models) -> Models:
        return self.add_model(paragraph)

    def add_table(self, table: Models) -> Models:
        return self.add_model(table)

    def add_image(self, image: Models) -> Models:
        return self.add_model(image)

    def add_textbox(self, textbox: Models) -> Models:
        return self.add_model(textbox)

    # ------------------------------------------------------------------
    def _filter_children(self, type_: Type[Models]) -> List[Models]:
        return [child for child in self.children if isinstance(child, type_)]

    def get_paragraphs(self) -> List[Models]:
        from .paragraph import Paragraph

        return self._filter_children(Paragraph)

    def get_tables(self) -> List[Models]:
        from .table import Table

        return self._filter_children(Table)

    def get_images(self) -> List[Models]:
        from .image import Image

        return self._filter_children(Image)

    def get_textboxes(self) -> List[Models]:
        from .textbox import TextBox

        return self._filter_children(TextBox)

    def _iter_text_sources(self) -> Iterable[str]:
        for child in self.children:
            if hasattr(child, "get_text"):
                text = child.get_text()
                if text:
                    yield text
            elif hasattr(child, "text"):
                text = getattr(child, "text")
                if text:
                    yield str(text)

    def get_text(self) -> str:
        return "\n".join(self._iter_text_sources()) if self.children else ""

    # ------------------------------------------------------------------
    def get_paragraphs_recursive(self) -> List[Models]:
        from .paragraph import Paragraph

        result: List[Models] = []
        for child in self.children:
            if isinstance(child, Paragraph):
                result.append(child)
            elif hasattr(child, "get_paragraphs_recursive"):
                result.extend(child.get_paragraphs_recursive())
            elif hasattr(child, "get_paragraphs"):
                result.extend(child.get_paragraphs())
        return result

    def get_tables_recursive(self) -> List[Models]:
        from .table import Table

        result: List[Models] = []
        for child in self.children:
            if isinstance(child, Table):
                result.append(child)
                if hasattr(child, "get_tables_recursive"):
                    result.extend(child.get_tables_recursive())
            elif hasattr(child, "get_tables_recursive"):
                result.extend(child.get_tables_recursive())
            elif hasattr(child, "get_tables"):
                result.extend(child.get_tables())
        return result

    def get_images_recursive(self) -> List[Models]:
        from .image import Image

        result: List[Models] = []
        for child in self.children:
            if isinstance(child, Image):
                result.append(child)
            elif hasattr(child, "get_images_recursive"):
                result.extend(child.get_images_recursive())
            elif hasattr(child, "get_images"):
                result.extend(child.get_images())
        return result
    
    def search(self, search_text: str, case_sensitive: bool = False, 
               search_in_tables: bool = True, search_in_textboxes: bool = True) -> List[Dict[str, Any]]:
        """
        Search for text in body content.
        
        Args:
            search_text: Text to search for
            case_sensitive: Whether search should be case sensitive
            search_in_tables: Whether to search in table content
            search_in_textboxes: Whether to search in textbox content
            
        Returns:
            List of search results with context information
        """
        import re
        
        results = []
        search_pattern = search_text if case_sensitive else search_text.lower()
        
        for i, child in enumerate(self.children):
            if hasattr(child, 'get_text'):
                text = child.get_text()
                if text:
                    search_text_content = text if case_sensitive else text.lower()
                    
                    # Find all occurrences
                    for match in re.finditer(re.escape(search_pattern), search_text_content):
                        results.append({
                            'element_index': i,
                            'element_type': type(child).__name__,
                            'element': child,
                            'match_start': match.start(),
                            'match_end': match.end(),
                            'context': text[max(0, match.start() - 50):match.end() + 50],
                            'full_text': text
                        })
            
            # Search in tables if enabled
            if search_in_tables and hasattr(child, 'get_tables_recursive'):
                for table in child.get_tables_recursive():
                    table_results = self._search_in_table(table, search_pattern, case_sensitive)
                    results.extend(table_results)
            
            # Search in textboxes if enabled
            if search_in_textboxes and hasattr(child, 'get_textboxes_recursive'):
                for textbox in child.get_textboxes_recursive():
                    textbox_results = self._search_in_textbox(textbox, search_pattern, case_sensitive)
                    results.extend(textbox_results)
        
        return results
    
    def _search_in_table(self, table, search_pattern: str, case_sensitive: bool) -> List[Dict[str, Any]]:
        """Search for text in table content."""
        results = []
        
        for row_idx, row in enumerate(table.rows):
            for cell_idx, cell in enumerate(row.cells):
                if hasattr(cell, 'get_text'):
                    text = cell.get_text()
                    if text:
                        search_text_content = text if case_sensitive else text.lower()
                        
                        for match in re.finditer(re.escape(search_pattern), search_text_content):
                            results.append({
                                'element_index': f"table_row_{row_idx}_cell_{cell_idx}",
                                'element_type': 'TableCell',
                                'element': cell,
                                'match_start': match.start(),
                                'match_end': match.end(),
                                'context': text[max(0, match.start() - 50):match.end() + 50],
                                'full_text': text,
                                'table_info': {
                                    'table': table,
                                    'row_index': row_idx,
                                    'cell_index': cell_idx
                                }
                            })
        
        return results
    
    def _search_in_textbox(self, textbox, search_pattern: str, case_sensitive: bool) -> List[Dict[str, Any]]:
        """Search for text in textbox content."""
        results = []
        
        if hasattr(textbox, 'get_text'):
            text = textbox.get_text()
            if text:
                search_text_content = text if case_sensitive else text.lower()
                
                for match in re.finditer(re.escape(search_pattern), search_text_content):
                    results.append({
                        'element_index': f"textbox_{id(textbox)}",
                        'element_type': 'TextBox',
                        'element': textbox,
                        'match_start': match.start(),
                        'match_end': match.end(),
                        'context': text[max(0, match.start() - 50):match.end() + 50],
                        'full_text': text
                    })
        
        return results
    
    def replace(self, search_text: str, replace_text: str, case_sensitive: bool = False,
                replace_in_tables: bool = True, replace_in_textboxes: bool = True) -> int:
        """
        Replace text in body content.
        
        Args:
            search_text: Text to search for
            replace_text: Text to replace with
            case_sensitive: Whether search should be case sensitive
            replace_in_tables: Whether to replace in table content
            replace_in_textboxes: Whether to replace in textbox content
            
        Returns:
            Number of replacements made
        """
        import re
        
        total_replacements = 0
        search_pattern = search_text if case_sensitive else search_text.lower()
        
        for child in self.children:
            if hasattr(child, 'get_text') and hasattr(child, 'set_text'):
                text = child.get_text()
                if text:
                    search_text_content = text if case_sensitive else text.lower()
                    
                    # Count occurrences
                    matches = list(re.finditer(re.escape(search_pattern), search_text_content))
                    if matches:
                        # Replace text
                        new_text = text
                        for match in reversed(matches):  # Replace from end to avoid index issues
                            new_text = new_text[:match.start()] + replace_text + new_text[match.end():]
                        
                        child.set_text(new_text)
                        total_replacements += len(matches)
            
            # Replace in tables if enabled
            if replace_in_tables and hasattr(child, 'get_tables_recursive'):
                for table in child.get_tables_recursive():
                    table_replacements = self._replace_in_table(table, search_pattern, replace_text, case_sensitive)
                    total_replacements += table_replacements
            
            # Replace in textboxes if enabled
            if replace_in_textboxes and hasattr(child, 'get_textboxes_recursive'):
                for textbox in child.get_textboxes_recursive():
                    textbox_replacements = self._replace_in_textbox(textbox, search_pattern, replace_text, case_sensitive)
                    total_replacements += textbox_replacements
        
        return total_replacements
    
    def _replace_in_table(self, table, search_pattern: str, replace_text: str, case_sensitive: bool) -> int:
        """Replace text in table content."""
        total_replacements = 0
        
        for row in table.rows:
            for cell in row.cells:
                if hasattr(cell, 'get_text') and hasattr(cell, 'set_text'):
                    text = cell.get_text()
                    if text:
                        search_text_content = text if case_sensitive else text.lower()
                        
                        # Count occurrences
                        matches = list(re.finditer(re.escape(search_pattern), search_text_content))
                        if matches:
                            # Replace text
                            new_text = text
                            for match in reversed(matches):  # Replace from end to avoid index issues
                                new_text = new_text[:match.start()] + replace_text + new_text[match.end():]
                            
                            cell.set_text(new_text)
                            total_replacements += len(matches)
        
        return total_replacements
    
    def _replace_in_textbox(self, textbox, search_pattern: str, replace_text: str, case_sensitive: bool) -> int:
        """Replace text in textbox content."""
        total_replacements = 0
        
        if hasattr(textbox, 'get_text') and hasattr(textbox, 'set_text'):
            text = textbox.get_text()
            if text:
                search_text_content = text if case_sensitive else text.lower()
                
                # Count occurrences
                matches = list(re.finditer(re.escape(search_pattern), search_text_content))
                if matches:
                    # Replace text
                    new_text = text
                    for match in reversed(matches):  # Replace from end to avoid index issues
                        new_text = new_text[:match.start()] + replace_text + new_text[match.end():]
                    
                    textbox.set_text(new_text)
                    total_replacements += len(matches)
        
        return total_replacements
    
    def find_by_style(self, style_name: str) -> List[Any]:
        """
        Find elements by style name.
        
        Args:
            style_name: Name of the style to search for
            
        Returns:
            List of elements with the specified style
        """
        elements = []
        
        for child in self.children:
            if hasattr(child, 'style') and child.style == style_name:
                elements.append(child)
            
            # Search in tables
            if hasattr(child, 'get_tables_recursive'):
                for table in child.get_tables_recursive():
                    for row in table.rows:
                        for cell in row.cells:
                            if hasattr(cell, 'style') and cell.style == style_name:
                                elements.append(cell)
            
            # Search in textboxes
            if hasattr(child, 'get_textboxes_recursive'):
                for textbox in child.get_textboxes_recursive():
                    if hasattr(textbox, 'style') and textbox.style == style_name:
                        elements.append(textbox)
        
        return elements