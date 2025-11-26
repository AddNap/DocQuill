"""Pre-compute header/footer variants for pages to reuse during layout."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional


def _to_float(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@dataclass(slots=True)
class Placement:
    element: Dict[str, Any]
    height: float
    y: float


@dataclass(slots=True)
class HeaderVariantData:
    placements: List[Placement]
    used_offset: float


@dataclass(slots=True)
class FooterVariantData:
    placements: List[Placement]
    used_offset: float


@dataclass(slots=True)
class PageVariant:
    header_placements: List[Placement]
    footer_placements: List[Placement]
    body_top_offset: float
    body_bottom_offset: float
    header_distance: float
    footer_distance: float


class PageVariator:
    """Prepare header/footer variants once and reuse them for each page."""

    def __init__(
        self,
        layout_structure: Any,
        layout_assembler: Any,
        page_config: Any,
        header_distance: Optional[float] = None,
        footer_distance: Optional[float] = None,
    ) -> None:
        self.layout_assembler = layout_assembler
        self.page_config = page_config
        self.page_height = page_config.page_size.height
        self.header_distance = header_distance if header_distance is not None else page_config.base_margins.top
        self.footer_distance = footer_distance if footer_distance is not None else page_config.base_margins.bottom

        headers = getattr(layout_structure, "headers", {}) or {"default": []}
        footers = getattr(layout_structure, "footers", {}) or {"default": []}

        self.header_variants: Dict[str, HeaderVariantData] = {
            key: self._build_header_variant(items) for key, items in headers.items()
        }
        self.footer_variants: Dict[str, FooterVariantData] = {
            key: self._build_footer_variant(items) for key, items in footers.items()
        }

    def get_variant(self, page_number: int) -> PageVariant:
        header_data = self._select_header_variant(page_number)
        footer_data = self._select_footer_variant(page_number)

        body_top = max(self.page_config.base_margins.top, header_data.used_offset)
        body_bottom = max(self.page_config.base_margins.bottom, footer_data.used_offset)

        return PageVariant(
            header_placements=header_data.placements,
            footer_placements=footer_data.placements,
            body_top_offset=body_top,
            body_bottom_offset=body_bottom,
            header_distance=self.header_distance,
            footer_distance=self.footer_distance,
        )

    # ------------------------------------------------------------------
    def _build_header_variant(self, items: List[Dict[str, Any]]) -> HeaderVariantData:
        placements: List[Placement] = []
        cursor = self.page_height - self.header_distance

        for element in items:
            style = element.get("style", {}) if isinstance(element, dict) else {}
            spacing_before = _to_float(style.get("spacing_before"))
            spacing_after = _to_float(style.get("spacing_after"))

            height = self._measure_height(element)

            cursor -= spacing_before
            y = cursor - height
            placements.append(Placement(element=element, height=height, y=y))
            cursor = y - spacing_after

        used_offset = self.page_height - cursor
        return HeaderVariantData(placements=placements, used_offset=used_offset)

    def _build_footer_variant(self, items: List[Dict[str, Any]]) -> FooterVariantData:
        reversed_items = list(reversed(items))
        placements_reversed: List[Placement] = []
        cursor = self.footer_distance

        for element in reversed_items:
            style = element.get("style", {}) if isinstance(element, dict) else {}
            spacing_before = _to_float(style.get("spacing_before"))
            spacing_after = _to_float(style.get("spacing_after"))

            height = self._measure_height(element)

            cursor += spacing_after
            y = cursor
            placements_reversed.append(Placement(element=element, height=height, y=y))
            cursor += height + spacing_before

        placements = list(reversed(placements_reversed))
        used_offset = cursor
        return FooterVariantData(placements=placements, used_offset=used_offset)

    def _measure_height(self, element: Dict[str, Any]) -> float:
        try:
            height = self.layout_assembler._measure_block_height(element)
        except Exception:
            height = 20.0
        if height <= 0:
            height = 20.0
        return height

    def _select_header_variant(self, page_number: int) -> HeaderVariantData:
        key = self._select_variant_key(self.header_variants, page_number)
        return self.header_variants.get(key) or HeaderVariantData([], self.header_distance)

    def _select_footer_variant(self, page_number: int) -> FooterVariantData:
        key = self._select_variant_key(self.footer_variants, page_number)
        return self.footer_variants.get(key) or FooterVariantData([], self.footer_distance)

    def _select_variant_key(self, variants: Mapping[str, Any], page_number: int) -> str:
        if page_number == 1 and "first" in variants:
            return "first"
        if page_number % 2 == 0 and "even" in variants:
            return "even"
        if page_number % 2 == 1 and page_number != 1 and "odd" in variants:
            return "odd"
        if "default" in variants:
            return "default"
        # fallback – take any available
        for key in variants.keys():
            return key
        return "default"


