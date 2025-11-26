"""

Standardized data structures describing LayoutAssembler output.

Eventually all blocks in UnifiedLayout should have `payload`/`content`
referring to one of the following types, so that renderer (PDF/HTML/debug)
doesn't need to perform additional heuristics or source model interpretation.

"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Union, Literal, Dict, Any

from .geometry import Rect

###############################################################################
# Common abstractions
###############################################################################


@dataclass(slots=True)
class ColorSpec:
    """Prosty opis koloru (RGB w zakresie 0-1)."""

    r: float
    g: float
    b: float
    a: float = 1.0


@dataclass(slots=True)
class BorderSpec:
    """Specyfikacja pojedynczej ramki."""

    side: Literal["left", "right", "top", "bottom"]
    width: float
    color: ColorSpec
    style: Literal["solid", "dashed", "dotted"] = "solid"


@dataclass(slots=True)
class BoxStyle:
    """Styles common to blocks (background, borders, padding)."""

    background: Optional[ColorSpec] = None
    borders: List[BorderSpec] = field(default_factory=list)
    padding: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)


###############################################################################
# Inline items
###############################################################################


InlineKind = Literal["text_run", "field", "inline_image", "inline_textbox"]


@dataclass(slots=True)
class InlineBox:
    """

    Base representation of inline element within paragraph line.

    All positional fields are relative to line start (x = 0 at left
    edge of text area, y = 0 at text baseline).

    """

    kind: InlineKind
    x: float
    width: float
    ascent: float
    descent: float
    data: Dict[str, Any] = field(default_factory=dict)


###############################################################################
# Overlay items
###############################################################################


OverlayKind = Literal["image", "textbox", "shape"]


@dataclass(slots=True)
class OverlayBox:
    """

    Element rendered absolutely relative to page / margin / column.

    LayoutAssembler is responsible for providing already calculated frame.

    """

    kind: OverlayKind
    frame: Rect
    payload: Dict[str, Any] = field(default_factory=dict)


###############################################################################
# Paragraph layout
###############################################################################


@dataclass(slots=True)
class ParagraphLine:
    """Single text line with list of inline elements."""

    baseline_y: float
    height: float
    items: List[InlineBox] = field(default_factory=list)
    offset_x: float = 0.0
    available_width: float = 0.0
    block_height: float = 0.0


@dataclass(slots=True)
class ParagraphLayout:
    """

    Materialized paragraph - result of line breaker + decorations.

    Paragraph height is `lines[-1].baseline_y + lines[-1].height` plus padding.

    """

    lines: List[ParagraphLine] = field(default_factory=list)
    overlays: List[OverlayBox] = field(default_factory=list)
    style: BoxStyle = field(default_factory=BoxStyle)
    metadata: Dict[str, Any] = field(default_factory=dict)


###############################################################################
# Textbox layout
###############################################################################


@dataclass(slots=True)
class TextboxLayout:
    """

    Textbox can be inline or absolutely positioned. If inline,
    LayoutAssembler should treat it as separate ParagraphLayout and
    flatten to InlineBox (type `inline_textbox`). For anchor variant,
    TextboxLayout goes to OverlayBox.

    """

    rect: Rect
    content: ParagraphLayout
    style: BoxStyle = field(default_factory=BoxStyle)
    anchor_mode: Literal["inline", "anchor"] = "inline"
    metadata: Dict[str, Any] = field(default_factory=dict)


###############################################################################
# Tabele, obrazy blokowe, generics
###############################################################################


@dataclass(slots=True)
class TableCellLayout:
    """Description of ready cell - has its own ParagraphLayout / list of blocks."""

    frame: Rect
    blocks: List["BlockPayload"] = field(default_factory=list)
    style: BoxStyle = field(default_factory=BoxStyle)


@dataclass(slots=True)
class TableLayout:
    """Complex table with already calculated cell dimensions."""

    frame: Rect
    rows: List[List[TableCellLayout]] = field(default_factory=list)
    grid_lines: List[BorderSpec] = field(default_factory=list)
    style: BoxStyle = field(default_factory=BoxStyle)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ImageLayout:
    """Blokowy obraz (inline/table cell/paragraph background)."""

    frame: Rect
    path: str
    preserve_aspect: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class GenericLayout:
    """Fallback for elements that don't have their own model yet."""

    frame: Rect
    data: Dict[str, Any] = field(default_factory=dict)
    overlays: List[OverlayBox] = field(default_factory=list)


BlockPayload = Union[
    ParagraphLayout,
    TableLayout,
    ImageLayout,
    TextboxLayout,
    GenericLayout,
]


@dataclass(slots=True)
class BlockContent:
    """Wrapper for block payloads along with original source dictionary."""

    payload: BlockPayload
    raw: Dict[str, Any] = field(default_factory=dict)



