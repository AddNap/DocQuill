"""TextBox model for DOCX documents."""

from __future__ import annotations

from typing import Tuple

from .body import Body
from .base import Models


class TextBox(Body):
    """Container for positioned content, inheriting Body capabilities."""

    def __init__(self) -> None:
        super().__init__()
        self.rel_id: str = ""
        self.width: float = 0.0
        self.height: float = 0.0
        self.position: Tuple[float, float] = (0.0, 0.0)
        self.anchor_type: str = "inline"  # inline / anchor

    def add_model(self, model: Models) -> Models:
        return super().add_model(model)

    # Position & size --------------------------------------------------
    def set_position(self, x: float, y: float) -> None:
        self.position = (float(x), float(y))

    def set_size(self, width: float, height: float) -> None:
        self.width = float(width)
        self.height = float(height)

    def get_position(self) -> Tuple[float, float]:
        return self.position

    def get_size(self) -> Tuple[float, float]:
        return self.width, self.height

    # Text -------------------------------------------------------------
    def get_text(self) -> str:
        return super().get_text()
