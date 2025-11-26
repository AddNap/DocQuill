"""Theme parser for DOCX documents."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional


class ThemeParser:
    """Parse Word theme XML into simple dictionaries."""

    THEME_PATH = "word/theme/theme1.xml"
    NS = {
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    }

    def __init__(self, package_reader: Any, xml_mapper: Any = None) -> None:
        self.package_reader = package_reader
        self.xml_mapper = xml_mapper

    def parse_theme(self) -> Dict[str, Any]:
        root = self._load_xml(self.THEME_PATH)
        if root is None:
            return {}

        clr_scheme = root.find(".//a:clrScheme", self.NS)
        font_scheme = root.find(".//a:fontScheme", self.NS)
        return {
            "color_scheme": self.parse_color_scheme(clr_scheme) if clr_scheme is not None else {},
            "font_scheme": self.parse_font_scheme(font_scheme) if font_scheme is not None else {},
        }

    def parse_color_scheme(self, color_scheme_element: ET.Element) -> Dict[str, str]:
        colors: Dict[str, str] = {}
        for color in color_scheme_element:
            tag = self._strip_namespace(color.tag)
            srgb = color.find("a:srgbClr", self.NS)
            if srgb is not None and srgb.get("val"):
                colors[tag] = srgb.get("val")  # hex string without '#'
                continue
            scheme = color.find("a:schemeClr", self.NS)
            if scheme is not None and scheme.get("val"):
                colors[tag] = scheme.get("val")
        return colors

    def parse_font_scheme(self, font_scheme_element: ET.Element) -> Dict[str, Dict[str, str]]:
        font_info: Dict[str, Dict[str, str]] = {}
        for branch in ("majorFont", "minorFont"):  # major/minor sets
            branch_element = font_scheme_element.find(f"a:{branch}", self.NS)
            if branch_element is None:
                continue
            branch_fonts: Dict[str, str] = {}
            latin = branch_element.find("a:latin", self.NS)
            if latin is not None and latin.get("typeface"):
                branch_fonts["latin"] = latin.get("typeface")
            east = branch_element.find("a:ea", self.NS)
            if east is not None and east.get("typeface"):
                branch_fonts["east_asian"] = east.get("typeface")
            cs = branch_element.find("a:cs", self.NS)
            if cs is not None and cs.get("typeface"):
                branch_fonts["complex_script"] = cs.get("typeface")
            font_info[branch] = branch_fonts
        return font_info

    # ------------------------------------------------------------------
    def _load_xml(self, path: str) -> Optional[ET.Element]:
        try:
            if hasattr(self.package_reader, "read"):
                data = self.package_reader.read(path)
            elif hasattr(self.package_reader, "open"):
                with self.package_reader.open(path) as fp:  # type: ignore[call-arg]
                    data = fp.read()
            else:
                raise AttributeError("package_reader must expose read() or open()")
        except FileNotFoundError:
            return None
        if not data:
            return None
        return ET.fromstring(data)

    def _strip_namespace(self, tag: str) -> str:
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag
