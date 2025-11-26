"""
Footnote renderer for DOCX documents.

Handles rendering of footnotes in HTML and PDF output.
"""

from typing import Dict, Any, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)


class FootnoteRenderer:
    """
    Renderer for footnotes and endnotes.
    
    Converts footnote/endnote references and content to HTML/PDF format.
    """
    
    def __init__(self, footnotes: Optional[Dict[str, Any]] = None, endnotes: Optional[Dict[str, Any]] = None):
        """
        Initialize footnote renderer.
        
        Args:
            footnotes: Dictionary of footnotes {footnote_id: footnote_data}
            endnotes: Dictionary of endnotes {endnote_id: endnote_data}
        """
        self.footnotes = footnotes or {}
        self.endnotes = endnotes or {}
        self.footnote_counter = 0
        self.endnote_counter = 0
        self.footnote_map = {}  # Maps footnote_id to display number
        self.endnote_map = {}  # Maps endnote_id to display number
    
    def register_footnote(self, footnote_id: str, footnote_data: Any) -> int:
        """
        Register a footnote and return its display number.
        
        Args:
            footnote_id: Footnote identifier
            footnote_data: Footnote data (dict or Footnote object)
            
        Returns:
            Display number for this footnote (1-based)
        """
        if footnote_id not in self.footnote_map:
            self.footnote_counter += 1
            self.footnote_map[footnote_id] = self.footnote_counter
            self.footnotes[footnote_id] = footnote_data
        
        return self.footnote_map[footnote_id]
    
    def get_footnote_number(self, footnote_id: str) -> Optional[int]:
        """
        Get display number for a footnote.
        Automatically registers the footnote if it exists in self.footnotes but is not yet registered.
        
        Args:
            footnote_id: Footnote identifier
            
        Returns:
            Display number or None if not found
        """
        # If footnote is not registered but exists in self.footnotes, register it...
        if footnote_id not in self.footnote_map and footnote_id in self.footnotes:
            footnote_data = self.footnotes[footnote_id]
            self.register_footnote(footnote_id, footnote_data)
        
        return self.footnote_map.get(footnote_id)
    
    def render_footnote_reference(self, footnote_id: str, format_type: str = "number") -> str:
        """
        Render footnote reference marker.
        
        Args:
            footnote_id: Footnote identifier
            format_type: Format type ("number", "symbol", "letter")
            
        Returns:
            HTML string for footnote reference
        """
        number = self.get_footnote_number(footnote_id)
        if number is None:
            number = self.register_footnote(footnote_id, {})
        
        if format_type == "symbol":
            # Use symbols: *, †, ‡, §, etc.
            symbols = ['*', '†', '‡', '§', '¶', '**', '††', '‡‡']
            symbol_index = (number - 1) % len(symbols)
            marker = symbols[symbol_index]
        elif format_type == "letter":
            # Use letters: a, b, c, etc.
            marker = chr(ord('a') + (number - 1) % 26)
        else:  # number (default)
            marker = str(number)
        
        return f'<sup><a href="#footnote-{footnote_id}" id="footnote-ref-{footnote_id}" class="footnote-ref">{marker}</a></sup>'
    
    def render_footnote_content(self, footnote_id: str, footnote_data: Any = None) -> str:
        """
        Render footnote content.
        
        Args:
            footnote_id: Footnote identifier
            footnote_data: Footnote data (dict or Footnote object)
            
        Returns:
            HTML string for footnote content
        """
        if footnote_data is None:
            footnote_data = self.footnotes.get(footnote_id)
        
        if footnote_data is None:
            return f'<li id="footnote-{footnote_id}"><span class="footnote-marker">{self.get_footnote_number(footnote_id) or "?"}</span> [Footnote not found]</li>'
        
        number = self.get_footnote_number(footnote_id) or "?"
        
        # Extract content - improved full text extraction
        content = ""
        if isinstance(footnote_data, dict):
            content_list = footnote_data.get('content', [])
            if isinstance(content_list, list):
                # Content is a list of paragraphs
                content_parts = []
                for para in content_list:
                    if isinstance(para, dict):
                        # First try to get full paragraph text
                        para_text = para.get('text', '')
                        # If no text, collect from runs
                        if not para_text and para.get('runs'):
                            para_text = ' '.join([
                                run.get('text', '') 
                                for run in para.get('runs', []) 
                                if isinstance(run, dict) and run.get('text')
                            ])
                        if para_text:
                            content_parts.append(para_text)
                    elif isinstance(para, str):
                        content_parts.append(para)
                    else:
                        content_parts.append(str(para))
                content = ' '.join(content_parts)
            elif isinstance(content_list, str):
                content = content_list
            else:
                content = str(content_list) if content_list else ""
        elif hasattr(footnote_data, 'content'):
            content = str(footnote_data.content)
        elif hasattr(footnote_data, 'get_content'):
            content = str(footnote_data.get_content())
        else:
            content = str(footnote_data)
        
        # Escape HTML in content
        from html import escape
        content_escaped = escape(content) if content else "[Empty footnote]"
        
        return f'<li id="footnote-{footnote_id}"><span class="footnote-marker">{number}</span> {content_escaped} <a href="#footnote-ref-{footnote_id}" class="footnote-backref">↩</a></li>'
    
    def render_footnotes_section(self) -> str:
        """
        Render all footnotes as a section.
        
        Returns:
            HTML string for footnotes section
        """
        if not self.footnotes:
            return ""
        
        # Register all footnotes if not already registered
        for footnote_id in self.footnotes.keys():
            if footnote_id not in self.footnote_map:
                self.register_footnote(footnote_id, self.footnotes.get(footnote_id))
        
        footnote_items = []
        for footnote_id in sorted(self.footnote_map.keys(), key=lambda x: self.footnote_map.get(x, 0)):
            footnote_data = self.footnotes.get(footnote_id)
            footnote_html = self.render_footnote_content(footnote_id, footnote_data)
            footnote_items.append(footnote_html)
        
        if not footnote_items:
            return ""
        
        return f'<div class="footnotes"><hr/><ol class="footnotes-list">{chr(10).join(footnote_items)}</ol></div>'
    
    def get_footnote_css(self) -> str:
        """
        Get CSS styles for footnotes.
        
        Returns:
            CSS string
        """
        return """
        <style>
        .footnote-ref {
            text-decoration: none;
            color: #0066cc;
            font-weight: bold;
        }
        .footnote-ref:hover {
            text-decoration: underline;
        }
        .footnotes {
            margin-top: 2em;
            padding-top: 1em;
            border-top: 1px solid #ccc;
        }
        .footnotes-list {
            list-style: none;
            padding-left: 0;
        }
        .footnotes-list li {
            margin-bottom: 0.5em;
            padding-left: 2em;
            text-indent: -2em;
        }
        .footnote-marker {
            font-weight: bold;
            margin-right: 0.5em;
        }
        .footnote-backref {
            text-decoration: none;
            color: #0066cc;
            margin-left: 0.5em;
        }
        .footnote-backref:hover {
            text-decoration: underline;
        }
        .endnote-ref {
            text-decoration: none;
            color: #0066cc;
            font-weight: bold;
        }
        .endnote-ref:hover {
            text-decoration: underline;
        }
        .endnotes {
            margin-top: 2em;
            padding-top: 1em;
            border-top: 1px solid #ccc;
        }
        .endnotes-list {
            list-style: none;
            padding-left: 0;
        }
        .endnotes-list li {
            margin-bottom: 0.5em;
            padding-left: 2em;
            text-indent: -2em;
        }
        .endnote-marker {
            font-weight: bold;
            margin-right: 0.5em;
        }
        .endnote-backref {
            text-decoration: none;
            color: #0066cc;
            margin-left: 0.5em;
        }
        .endnote-backref:hover {
            text-decoration: underline;
        }
        </style>
        """
    
    def render_footnote_reference_pdf(self, footnote_id: str, format_type: str = "number") -> tuple[str, int]:
        """
        Render footnote reference for PDF.
        
        Args:
            footnote_id: Footnote identifier
            format_type: Format type ("number", "symbol", "letter")
            
        Returns:
            Tuple of (marker_text, display_number)
        """
        number = self.get_footnote_number(footnote_id)
        if number is None:
            number = self.register_footnote(footnote_id, {})
        
        if format_type == "symbol":
            symbols = ['*', '†', '‡', '§', '¶', '**', '††', '‡‡']
            symbol_index = (number - 1) % len(symbols)
            marker = symbols[symbol_index]
        elif format_type == "letter":
            marker = chr(ord('a') + (number - 1) % 26)
        else:  # number (default)
            marker = str(number)
        
        return (marker, number)
    
    def get_all_footnotes(self) -> List[tuple[str, Any, int]]:
        """
        Get all footnotes with their display numbers.
        
        Returns:
            List of tuples (footnote_id, footnote_data, display_number)
        """
        result = []
        for footnote_id in sorted(self.footnote_map.keys(), key=lambda x: self.footnote_map.get(x, 0)):
            footnote_data = self.footnotes.get(footnote_id)
            display_number = self.footnote_map.get(footnote_id, 0)
            result.append((footnote_id, footnote_data, display_number))
        return result
    
    def register_footnote_for_page(self, page_number: int, footnote_id: str):
        """
        Register a footnote for a specific page (for PDF rendering).
        
        Args:
            page_number: Page number (1-based)
            footnote_id: Footnote identifier
        """
        # Ensure footnote is registered
        if footnote_id not in self.footnote_map:
            self.register_footnote(footnote_id, self.footnotes.get(footnote_id))
        
        # Store page association if needed
        if not hasattr(self, 'footnotes_per_page'):
            self.footnotes_per_page = {}
        if page_number not in self.footnotes_per_page:
            self.footnotes_per_page[page_number] = []
        if footnote_id not in self.footnotes_per_page[page_number]:
            self.footnotes_per_page[page_number].append(footnote_id)
    
    def register_endnote(self, endnote_id: str, endnote_data: Any) -> int:
        """
        Register an endnote and return its display number.
        
        Args:
            endnote_id: Endnote identifier
            endnote_data: Endnote data (dict or Endnote object)
            
        Returns:
            Display number for this endnote (1-based)
        """
        if endnote_id not in self.endnote_map:
            self.endnote_counter += 1
            self.endnote_map[endnote_id] = self.endnote_counter
            self.endnotes[endnote_id] = endnote_data
        
        return self.endnote_map[endnote_id]
    
    def get_endnote_number(self, endnote_id: str) -> Optional[int]:
        """
        Get display number for an endnote.
        Automatically registers the endnote if it exists in self.endnotes but is not yet registered.
        
        Args:
            endnote_id: Endnote identifier
            
        Returns:
            Display number or None if not found
        """
        # If endnote is not registered but exists in self.endnotes, register it...
        if endnote_id not in self.endnote_map and endnote_id in self.endnotes:
            endnote_data = self.endnotes[endnote_id]
            self.register_endnote(endnote_id, endnote_data)
        
        return self.endnote_map.get(endnote_id)
    
    def render_endnote_reference(self, endnote_id: str, format_type: str = "number") -> str:
        """
        Render endnote reference marker.
        
        Args:
            endnote_id: Endnote identifier
            format_type: Format type ("number", "symbol", "letter")
            
        Returns:
            HTML string for endnote reference
        """
        number = self.get_endnote_number(endnote_id)
        if number is None:
            number = self.register_endnote(endnote_id, {})
        
        if format_type == "symbol":
            symbols = ['*', '†', '‡', '§', '¶', '**', '††', '‡‡']
            symbol_index = (number - 1) % len(symbols)
            marker = symbols[symbol_index]
        elif format_type == "letter":
            marker = chr(ord('a') + (number - 1) % 26)
        else:  # number (default)
            marker = str(number)
        
        return f'<sup><a href="#endnote-{endnote_id}" id="endnote-ref-{endnote_id}" class="endnote-ref">{marker}</a></sup>'
    
    def render_endnote_content(self, endnote_id: str, endnote_data: Any = None) -> str:
        """
        Render endnote content.
        
        Args:
            endnote_id: Endnote identifier
            endnote_data: Endnote data (dict or Endnote object)
            
        Returns:
            HTML string for endnote content
        """
        if endnote_data is None:
            endnote_data = self.endnotes.get(endnote_id)
        
        if endnote_data is None:
            return f'<li id="endnote-{endnote_id}"><span class="endnote-marker">{self.get_endnote_number(endnote_id) or "?"}</span> [Endnote not found]</li>'
        
        number = self.get_endnote_number(endnote_id) or "?"
        
        # Extract content - use same logic as for footnotes
        content = ""
        if isinstance(endnote_data, dict):
            content_list = endnote_data.get('content', [])
            if isinstance(content_list, list):
                content_parts = []
                for para in content_list:
                    if isinstance(para, dict):
                        para_text = para.get('text', '')
                        if not para_text and para.get('runs'):
                            para_text = ' '.join([
                                run.get('text', '') 
                                for run in para.get('runs', []) 
                                if isinstance(run, dict) and run.get('text')
                            ])
                        if para_text:
                            content_parts.append(para_text)
                    elif isinstance(para, str):
                        content_parts.append(para)
                    else:
                        content_parts.append(str(para))
                content = ' '.join(content_parts)
            elif isinstance(content_list, str):
                content = content_list
            else:
                content = str(content_list) if content_list else ""
        elif hasattr(endnote_data, 'content'):
            content = str(endnote_data.content)
        elif hasattr(endnote_data, 'get_content'):
            content = str(endnote_data.get_content())
        else:
            content = str(endnote_data)
        
        from html import escape
        content_escaped = escape(content) if content else "[Empty endnote]"
        
        return f'<li id="endnote-{endnote_id}"><span class="endnote-marker">{number}</span> {content_escaped} <a href="#endnote-ref-{endnote_id}" class="endnote-backref">↩</a></li>'
    
    def render_endnotes_section(self) -> str:
        """
        Render all endnotes as a section.
        
        Returns:
            HTML string for endnotes section
        """
        if not self.endnotes:
            return ""
        
        # Register all endnotes if not already registered
        for endnote_id in self.endnotes.keys():
            if endnote_id not in self.endnote_map:
                self.register_endnote(endnote_id, self.endnotes.get(endnote_id))
        
        endnote_items = []
        for endnote_id in sorted(self.endnote_map.keys(), key=lambda x: self.endnote_map.get(x, 0)):
            endnote_data = self.endnotes.get(endnote_id)
            endnote_html = self.render_endnote_content(endnote_id, endnote_data)
            endnote_items.append(endnote_html)
        
        if not endnote_items:
            return ""
        
        return f'<div class="endnotes"><hr/><ol class="endnotes-list">{chr(10).join(endnote_items)}</ol></div>'

