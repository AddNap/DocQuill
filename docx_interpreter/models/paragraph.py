"""Paragraph model for DOCX documents."""

from typing import List, Dict, Any, Optional, Tuple, Type, Union
from .base import Models
from .run import Run

class Paragraph(Models):
    """Represents a paragraph with runs, numbering, and formatting data."""
    
    def __init__(self):
        """Initialize paragraph."""
        super().__init__()
        self.runs: List[Run] = []
        self.style: Optional[Dict[str, Any]] = None
        self.numbering: Optional[Dict[str, Any]] = None
        self.tables: List[Any] = []  # inline tables
        # Paragraph formatting properties
        self.alignment: Optional[str] = None
        self.spacing_before: Optional[float] = None
        self.spacing_after: Optional[float] = None
        self.line_spacing: Optional[float] = None
        self.line_spacing_rule: Optional[str] = None
        self.spacing_before_lines: Optional[float] = None
        self.spacing_after_lines: Optional[float] = None
        self.spacing_before_auto: bool = False
        self.spacing_after_auto: bool = False
        self.left_indent: Optional[float] = None
        self.right_indent: Optional[float] = None
        self.first_line_indent: Optional[float] = None
        self.hanging_indent: Optional[float] = None
        self.borders: Optional[Dict[str, Any]] = None
        self.background: Optional[Dict[str, Any]] = None
        self.effect: Optional[Dict[str, Any]] = None
        self.outline: Optional[Dict[str, Any]] = None
        self.shadow: Optional[Dict[str, Any]] = None
        self.highlight: Optional[Dict[str, Any]] = None
        self.allowed_models: Tuple[Type[Models], ...] = (
            Run,  # Will be imported when needed
        )
    
    def add_run(self, run: Run):
        """Add run to paragraph."""
        # Accept both Run objects and dict representations
        if isinstance(run, dict):
            # Convert dict to Run object
            from .run import Run as RunClass
            run_obj = RunClass(
                text=run.get("text", ""),
                style=run.get("style"),
                space=run.get("space", "default"),
                has_break=run.get("has_break", False),
                has_tab=run.get("has_tab", False),
                has_drawing=run.get("has_drawing", False),
                break_type=run.get("break_type"),
            )
            # Copy footnote/endnote references if present
            if "footnote_refs" in run:
                run_obj.footnote_refs = run["footnote_refs"]
            if "endnote_refs" in run:
                run_obj.endnote_refs = run["endnote_refs"]
            self.runs.append(run_obj)
            self.add_child(run_obj)
        elif isinstance(run, Run):
            self.runs.append(run)
            self.add_child(run)
    
    def add_table(self, table):
        """Add inline table to paragraph."""
        self.tables.append(table)
        self.add_child(table)
    
    def add_field(self, field):
        """Add field to paragraph."""
        self.add_child(field)
    
    def add_hyperlink(self, hyperlink):
        """Add hyperlink to paragraph."""
        self.add_child(hyperlink)
    
    def set_style(self, style):
        """Set paragraph style."""
        self.style = style
    
    def set_numbering(self, numbering_ref):
        """Set paragraph numbering."""
        self.numbering = numbering_ref
    
    def set_list(self, level: int = 0, numbering_id: Optional[Union[str, int]] = None) -> None:
        """
        Ustawia paragraf jako element listy.
        
        Args:
            level: Poziom listy (0 = pierwszy poziom, 1 = drugi poziom, etc.)
            numbering_id: ID numeracji (może być string lub int, lub NumberingGroup)
            
        Examples:
            >>> para = Paragraph()
            >>> para.set_list(level=0, numbering_id="1")
            >>> # Lub z NumberingGroup
            >>> numbered_list = doc.create_numbered_list()
            >>> para.set_list(level=0, numbering_id=numbered_list.group_id)
        """
        if numbering_id is None:
            # Jeśli nie podano numbering_id, użyj domyślnego
            # W przyszłości można dodać domyślny numbering_id z dokumentu
            raise ValueError("numbering_id is required")
        
        # Konwertuj numbering_id na string jeśli potrzeba
        if isinstance(numbering_id, int):
            numbering_id = str(numbering_id)
        elif hasattr(numbering_id, 'group_id'):
            # Jeśli to NumberingGroup, użyj jego group_id
            numbering_id = str(numbering_id.group_id)
        elif hasattr(numbering_id, 'num_id'):
            # Jeśli to ma num_id (instancja numeracji)
            numbering_id = str(numbering_id.num_id)
        
        # Ustaw numbering jako dict zgodny z formatem DOCX
        self.numbering = {
            'id': numbering_id,
            'level': str(level)
        }
        
        # Ustaw również w style jeśli istnieje
        if self.style is None:
            self.style = {}
        
        if not isinstance(self.style, dict):
            self.style = {}
        
        self.style['numbering'] = {
            'id': numbering_id,
            'level': str(level)
        }
    
    def get_text(self, preserve_format=False):
        """Get text content from all runs."""
        text_parts = []
        for run in self.runs:
            run_text = run.get_text()
            if run_text:
                text_parts.append(run_text)
        return ' '.join(text_parts)
    
    def _merge_runs_plain(self):
        """Merge runs into plain text (like Word/py-docx)."""
        parts = []
        for run in self.runs:
            run_text = run.get_text()
            if run_text:
                parts.append(run_text)
        return " ".join(parts)
    
    def _merge_runs_formatted(self):
        """Merge runs into fragments that preserve formatting metadata."""
        fragments = []
        for run in self.runs:
            run_text = run.get_text()
            if run_text:
                fragments.append({
                    "text": run_text,
                    "style": getattr(run, 'style', {}),
                    "is_bold": getattr(run, 'is_bold', lambda: False)(),
                    "is_italic": getattr(run, 'is_italic', lambda: False)(),
                    "is_underline": getattr(run, 'is_underline', lambda: False)(),
                    "color": getattr(run, 'color', None)
                })
        return fragments
    
    def get_fragments(self):
        """Get formatted fragments for rich text export."""
        return self._merge_runs_formatted()
    
    def _normalize_runs(self):
        """Merge neighbouring runs when their style dictionaries match."""
        merged = []
        for run in self.runs:
            if merged and getattr(run, 'style', None) == getattr(merged[-1], 'style', None):
                merged[-1].text = (getattr(merged[-1], 'text', '') or '') + (getattr(run, 'text', '') or '')
            else:
                merged.append(run)
        self.runs = merged
    
    def create_inline_fragments(self):
        """Group runs into fragments with consistent style metadata."""
        fragments = []
        current_fragment = None
        
        for run in self.runs:
            if current_fragment is None or not self._runs_have_same_style(current_fragment, run):
                current_fragment = {
                    'runs': [],
                    'style': getattr(run, 'style', {})
                }
                fragments.append(current_fragment)
            
            current_fragment['runs'].append(run)
        
        return fragments
    
    def _runs_have_same_style(self, run1, run2):
        """Check if two runs have the same style."""
        style1 = getattr(run1, 'style', {})
        style2 = getattr(run2, 'style', {})
        return style1 == style2
    
    def get_runs(self):
        """Get all runs in paragraph."""
        return self.runs.copy()
    
    def is_list_item(self):
        """Check if paragraph is a list item."""
        return self.numbering is not None
    
    @property
    def text(self):
        """Return merged plain text similar to Word/py-docx interfaces."""
        return self._merge_runs_plain()
    
    def set_text(self, text: str):
        """
        Set text content for paragraph.
        
        Args:
            text: Text to set
        """
        # Clear existing runs
        self.runs.clear()
        self.children.clear()
        
        # Create a new run with the text
        run = Run()
        run.text = text
        self.add_run(run)