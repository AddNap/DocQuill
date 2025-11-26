"""Base classes and interfaces for document renderers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from io import BytesIO
from typing import Iterable, Optional, Sequence, Union

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdf_canvas

from ..engine.unified_layout import LayoutPage
from ..engine.geometry import Margins, Size
from .render_utils import ensure_margins, ensure_page_size, register_default_fonts


LayoutPages = Sequence[LayoutPage]
CanvasTarget = Union[str, BytesIO]


class IRenderer(ABC):
    """Interface for renderer implementations."""

    @abstractmethod
    def render(self, layout_pages: LayoutPages, output: CanvasTarget) -> None:
        """Render layout pages into the provided output."""


class BaseRenderer(IRenderer):
    """Common functionality shared by concrete renderer implementations."""

    def __init__(
        self,
        page_size: Union[str, Size, Iterable[float]] = A4,
        margins: Union[Margins, Iterable[float]] = (50, 50, 50, 50),
        dpi: float = 72.0,
    ) -> None:
        width, height = ensure_page_size(page_size)
        self.page_size = (width, height)
        self.page_size_obj = Size(width=width, height=height)
        self.page_width = width
        self.page_height = height
        self.margins = ensure_margins(margins)
        self.dpi = dpi
        self.canvas: Optional[pdf_canvas.Canvas] = None

    def render(self, layout_pages: LayoutPages, output: CanvasTarget) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Canvas helpers
    # ------------------------------------------------------------------
    def _init_canvas(self, output: CanvasTarget) -> None:
        register_default_fonts()
        if hasattr(output, "write"):
            self.canvas = pdf_canvas.Canvas(output, pagesize=self.page_size)
        else:
            self.canvas = pdf_canvas.Canvas(str(output), pagesize=self.page_size)

    def _finish(self) -> None:
        if self.canvas is not None:
            self.canvas.save()

    def _apply_margins_transform(self) -> None:
        if self.canvas is None:
            return
        self.canvas.translate(self.margins.left, self.margins.bottom)

    @property
    def content_width(self) -> float:
        return max(self.page_width - self.margins.left - self.margins.right, 0.0)

    @property
    def content_height(self) -> float:
        return max(self.page_height - self.margins.top - self.margins.bottom, 0.0)


