"""
Unified layout model — końcowa reprezentacja dokumentu gotowa do renderowania.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any
from .geometry import Rect, Size, Margins


@dataclass(slots=True)
class LayoutBlock:
    """Pojedynczy blok tekstu, obrazu, tabeli itp. w gotowym układzie."""
    frame: Rect
    block_type: str
    content: Any
    style: dict
    page_number: Optional[int] = None
    source_uid: Optional[str] = None
    sequence: Optional[int] = None


@dataclass(slots=True)
class LayoutPage:
    """Strona z gotowymi blokami."""
    number: int
    size: Size
    margins: Margins
    blocks: List[LayoutBlock] = field(default_factory=list)
    skip_headers_footers: bool = False  # Flaga do pomijania nagłówków i stopek

    def add_block(self, block: LayoutBlock) -> None:
        self.blocks.append(block)


@dataclass
class UnifiedLayout:
    """Zunifikowany układ całego dokumentu — pozycje, paginacja, style."""
    pages: List[LayoutPage] = field(default_factory=list)
    current_page: int = 1

    def add_block(self, block: LayoutBlock) -> None:
        if not self.pages:
            raise RuntimeError("Brak aktywnej strony — wywołaj new_page() przed dodaniem bloków.")
        self.pages[-1].add_block(block)

    def new_page(self, size: Size, margins: Margins) -> LayoutPage:
        page = LayoutPage(number=self.current_page, size=size, margins=margins)
        self.pages.append(page)
        self.current_page += 1
        return page
