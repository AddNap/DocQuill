"""Rendering routines for image blocks."""

from __future__ import annotations

from typing import Any, Dict

from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from ..engine.unified_layout import LayoutBlock
from ..engine.geometry import Margins


class ImageRenderer:
    """Render image blocks using ReportLab's drawing primitives."""

    def __init__(self, canvas: Canvas, margins: Margins | None = None) -> None:
        self.canvas = canvas
        self.margins = margins

    def draw(self, block: LayoutBlock) -> None:
        payload = block.content or {}

        if isinstance(payload, dict):
            path = payload.get("path") or payload.get("src")
        else:
            path = getattr(payload, "path", None)

        if not path:
            return

        try:
            image = ImageReader(path)
        except Exception:
            return

        left_margin = self.margins.left if self.margins else 0.0
        bottom_margin = self.margins.bottom if self.margins else 0.0

        self.canvas.drawImage(
            image,
            block.frame.x - left_margin,
            block.frame.y - bottom_margin,
            width=block.frame.width,
            height=block.frame.height,
            preserveAspectRatio=True,
            mask="auto",
        )

