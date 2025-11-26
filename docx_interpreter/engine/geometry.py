"""Geometry primitives and helpers for layout calculations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


TWIPS_PER_POINT = 20
EMU_PER_PIXEL = 914400 / 96  # Word uses 914400 EMUs per inch


@dataclass(slots=True)
class Point:
    x: float
    y: float


@dataclass(slots=True)
class Size:
    width: float
    height: float

    @classmethod
    def from_tuple(cls, value: Iterable[float]) -> "Size":
        width, height = value
        return cls(float(width), float(height))


@dataclass(slots=True)
class Rect:
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self):
        """Ensure non-negative dimensions."""
        if self.width < 0:
            self.width = abs(self.width)
        if self.height < 0:
            self.height = abs(self.height)

    @property
    def left(self) -> float:
        return self.x

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y

    @property
    def top(self) -> float:
        return self.y + self.height

    def intersects(self, other: "Rect") -> bool:
        """Check if this rectangle intersects with another rectangle.
        
        Args:
            other: Another Rect object
            
        Returns:
            True if rectangles intersect, False otherwise
        """
        return not (
            self.right < other.left or
            self.left > other.right or
            self.top < other.bottom or
            self.bottom > other.top
        )

    def union(self, other: "Rect") -> "Rect":
        """Calculate the bounding rectangle that contains both rectangles.
        
        Args:
            other: Another Rect object
            
        Returns:
            New Rect that contains both rectangles
        """
        left = min(self.left, other.left)
        right = max(self.right, other.right)
        bottom = min(self.bottom, other.bottom)
        top = max(self.top, other.top)
        return Rect(x=left, y=bottom, width=right - left, height=top - bottom)


@dataclass(slots=True)
class Margins:
    top: float = 0.0
    bottom: float = 0.0
    left: float = 0.0
    right: float = 0.0

    @classmethod
    def uniform(cls, value: float) -> "Margins":
        return cls(value, value, value, value)

    def __add__(self, other: "Margins") -> "Margins":
        """Add two margins together (sum corresponding sides).
        
        Args:
            other: Another Margins object
            
        Returns:
            New Margins with summed values
        """
        return Margins(
            top=self.top + other.top,
            bottom=self.bottom + other.bottom,
            left=self.left + other.left,
            right=self.right + other.right,
        )


def twips_to_points(value: float | None) -> float:
    if value is None:
        return 0.0
    return float(value) / TWIPS_PER_POINT


def emu_to_points(value: float | None) -> float:
    if value is None:
        return 0.0
    # 1 inch = 72 pt, 1 inch = 914400 EMU
    return float(value) * 72.0 / 914400.0


def px_to_points(value: float | None, dpi: float = 96.0) -> float:
    if value is None:
        return 0.0
    return float(value) * 72.0 / dpi

