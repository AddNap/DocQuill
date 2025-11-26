"""
Ustandaryzowane struktury danych opisujące wynik działania LayoutAssemblera.

Docelowo wszystkie bloki w UnifiedLayout powinny posiadać `payload`/`content`
odwołujący się do jednego z poniższych typów, tak aby renderer (PDF/HTML/debug)
nie musiał wykonywać dodatkowych heurystyk ani interpretacji modelu źródłowego.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Union, Literal, Dict, Any

from .geometry import Rect

###############################################################################
# Wspólne abstrakcje
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
    """Style wspólne dla bloków (tło, ramki, padding)."""

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
    Bazowa reprezentacja inline elementu w ramach linii paragrafu.

    Wszystkie pola pozycyjne są względne względem początku linii (x = 0 na lewym
    krańcu obszaru tekstu, y = 0 na bazowej linii tekstu).
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
    Element renderowany absolutnie względem strony / marginesu / kolumny.

    LayoutAssembler jest odpowiedzialny za dostarczenie już przeliczonej ramki.
    """

    kind: OverlayKind
    frame: Rect
    payload: Dict[str, Any] = field(default_factory=dict)


###############################################################################
# Paragraph layout
###############################################################################


@dataclass(slots=True)
class ParagraphLine:
    """Pojedyncza linia tekstu z listą elementów inline."""

    baseline_y: float
    height: float
    items: List[InlineBox] = field(default_factory=list)
    offset_x: float = 0.0
    available_width: float = 0.0
    block_height: float = 0.0


@dataclass(slots=True)
class ParagraphLayout:
    """
    Zmaterializowany paragraf – wynik działania line breaker + dekoracje.

    Wysokość paragrafu to `lines[-1].baseline_y + lines[-1].height` plus padding.
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
    Textbox może być inline lub absolutnie pozycjonowany. Jeżeli jest inline,
    LayoutAssembler powinien potraktować go jak osobny ParagraphLayout i
    spłaszczyć do InlineBox (typ `inline_textbox`). Dla wariantu anchor,
    TextboxLayout trafia do OverlayBox.
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
    """Opis gotowej komórki – posiada własny ParagraphLayout / listę bloków."""

    frame: Rect
    blocks: List["BlockPayload"] = field(default_factory=list)
    style: BoxStyle = field(default_factory=BoxStyle)


@dataclass(slots=True)
class TableLayout:
    """Złożona tabela z już policzonymi wymiarami komórek."""

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
    """Fallback dla elementów, które nie mają jeszcze własnego modelu."""

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
    """Opakowanie na payload bloków wraz z oryginalnym słownikiem źródłowym."""

    payload: BlockPayload
    raw: Dict[str, Any] = field(default_factory=dict)



