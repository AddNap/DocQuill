"""Run model for DOCX documents."""

from typing import List, Dict, Any, Optional, Tuple, Type
from .base import Models

class Run(Models):
    """Represents a run of text with consistent formatting."""
    
    def __init__(
        self,
        text="",
        style=None,
        space="default",
        has_break=False,
        has_tab=False,
        has_drawing=False,
        from_sdt=False,
        break_type: Optional[str] = None,
    ):
        """Initialize run with text, style and space handling."""
        super().__init__()
        self.text: str = text
        self.style: Optional[Dict[str, Any]] = style or {}
        self.space: str = space  # "default" or "preserve"
        self.allowed_models: Tuple[Type[Models], ...] = (
            # Field, Hyperlink  # inline fragments - will be imported when needed
        )
        
        # Special elements
        self.has_break: bool = has_break
        self.has_tab: bool = has_tab
        self.has_drawing: bool = has_drawing
        self.from_sdt: bool = from_sdt  # Marks runs that came from SDT elements
        self.break_type: Optional[str] = break_type  # e.g. textWrapping, page, column, line
        
        # Drawing content
        self.textbox: Optional[List['Run']] = None  # Textbox content as list of Run objects
        self.image: Optional[Any] = None  # Image object
        
        # Formatting attributes
        self.bold: bool = False
        self.italic: bool = False
        self.underline: bool = False
        self.font_name: Optional[str] = None
        self.font_size: Optional[int] = None
        self.color: Optional[str] = None
        self.highlight: Optional[str] = None
        self.superscript: bool = False
        self.subscript: bool = False
        self.strike_through: bool = False
        # Advanced formatting attributes
        self.strikethrough: bool = False
        self.double_strikethrough: bool = False
        self.vertical_align: Optional[str] = None
        self.background: Optional[str] = None
        self.effect: Optional[Dict[str, Any]] = None
        self.outline: Optional[Dict[str, Any]] = None
        self.shadow: Optional[Dict[str, Any]] = None
        self.emboss: bool = False
        self.imprint: bool = False
        self.no_proof: bool = False
        self.web_hidden: bool = False
        
        # Footnote and endnote references
        self.footnote_refs: List[str] = []
        self.endnote_refs: List[str] = []
    
    def add_text(self, text: str):
        """Add text to run."""
        self.text += text
    
    def add_field(self, field):
        """Add field to run."""
        self.add_child(field)
    
    def add_hyperlink(self, hyperlink):
        """Add hyperlink to run."""
        self.add_child(hyperlink)
    
    def set_style(self, style):
        """Set run style."""
        self.style = style
    
    def get_text(self):
        """Return stored text respecting the run's xml:space behaviour."""
        # Always return text as-is to preserve spacing
        # Empty runs with space should return space, not empty string
        return self.text
    
    def is_bold(self):
        """Check if run is bold."""
        if isinstance(self.style, dict):
            return self.style.get('bold', False)
        return 'bold' in str(self.style).lower() if self.style else False
    
    def is_italic(self):
        """Check if run is italic."""
        if isinstance(self.style, dict):
            return self.style.get('italic', False)
        return 'italic' in str(self.style).lower() if self.style else False
    
    def is_underline(self):
        """Check if run is underlined."""
        if isinstance(self.style, dict):
            return self.style.get('underline', False)
        return 'underline' in str(self.style).lower() if self.style else False
    
    def set_bold(self, bold: bool):
        """Set bold formatting."""
        self.bold = bold
    
    def set_italic(self, italic: bool):
        """Set italic formatting."""
        self.italic = italic
    
    def set_underline(self, underline: bool):
        """Set underline formatting."""
        self.underline = underline
    
    def set_font_name(self, font_name: str):
        """Set font name."""
        self.font_name = font_name
    
    def set_font_size(self, font_size: int):
        """Set font size in points."""
        self.font_size = font_size
    
    def set_color(self, color: str):
        """Set text color."""
        self.color = color
    
    def set_highlight(self, highlight: str):
        """Set highlight color."""
        self.highlight = highlight
    
    def set_superscript(self, superscript: bool):
        """Set superscript formatting."""
        self.superscript = superscript
        if superscript:
            self.subscript = False
    
    def set_subscript(self, subscript: bool):
        """Set subscript formatting."""
        self.subscript = subscript
        if subscript:
            self.superscript = False
    
    def set_strike_through(self, strike_through: bool):
        """Set strike-through formatting."""
        self.strike_through = strike_through
    
    def apply_formatting(self, formatting: Dict[str, Any]):
        """Apply formatting from dictionary."""
        if 'bold' in formatting:
            self.set_bold(formatting['bold'])
        if 'italic' in formatting:
            self.set_italic(formatting['italic'])
        if 'underline' in formatting:
            self.set_underline(formatting['underline'])
        if 'font_name' in formatting:
            self.set_font_name(formatting['font_name'])
        if 'font_size' in formatting:
            self.set_font_size(formatting['font_size'])
        if 'color' in formatting:
            self.set_color(formatting['color'])
        if 'highlight' in formatting:
            self.set_highlight(formatting['highlight'])
        if 'superscript' in formatting:
            self.set_superscript(formatting['superscript'])
        if 'subscript' in formatting:
            self.set_subscript(formatting['subscript'])
        if 'strike_through' in formatting:
            self.set_strike_through(formatting['strike_through'])
    
    def get_formatting(self) -> Dict[str, Any]:
        """Get formatting as dictionary."""
        return {
            'bold': self.bold,
            'italic': self.italic,
            'underline': self.underline,
            'font_name': self.font_name,
            'font_size': self.font_size,
            'color': self.color,
            'highlight': self.highlight,
            'superscript': self.superscript,
            'subscript': self.subscript,
            'strike_through': self.strike_through
        }
    
    def clone(self):
        """Clone run with all formatting preserved."""
        cloned = super().clone()
        cloned.text = self.text
        cloned.style = self.style.copy() if self.style else None
        cloned.space = self.space
        cloned.bold = self.bold
        cloned.italic = self.italic
        cloned.underline = self.underline
        cloned.font_name = self.font_name
        cloned.font_size = self.font_size
        cloned.color = self.color
        cloned.highlight = self.highlight
        cloned.superscript = self.superscript
        cloned.subscript = self.subscript
        cloned.strike_through = self.strike_through
        cloned.break_type = self.break_type
        return cloned
    
    def to_html(self) -> str:
        """Convert run to HTML representation."""
        if not self.text:
            return ""
        
        html_text = self.text
        html_tags = []
        
        # Apply formatting tags
        if self.bold:
            html_tags.append(('b', '</b>'))
        if self.italic:
            html_tags.append(('i', '</i>'))
        if self.underline:
            html_tags.append(('u', '</u>'))
        if self.strike_through:
            html_tags.append(('s', '</s>'))
        if self.superscript:
            html_tags.append(('sup', '</sup>'))
        if self.subscript:
            html_tags.append(('sub', '</sub>'))
        
        # Apply style attributes
        style_parts = []
        if self.font_name:
            style_parts.append(f"font-family: {self.font_name}")
        if self.font_size:
            style_parts.append(f"font-size: {self.font_size}pt")
        if self.color:
            style_parts.append(f"color: {self.color}")
        if self.highlight:
            style_parts.append(f"background-color: {self.highlight}")
        
        # Build HTML
        if style_parts:
            style_attr = f' style="{"; ".join(style_parts)}"'
        else:
            style_attr = ""
        
        # Wrap with tags
        for open_tag, close_tag in html_tags:
            html_text = f"<{open_tag}>{html_text}</{open_tag}>"
        
        # Add span with style if needed
        if style_attr:
            html_text = f'<span{style_attr}>{html_text}</span>'
        
        return html_text
