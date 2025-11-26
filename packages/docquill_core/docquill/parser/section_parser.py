"""Section parser for DOCX documents."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional


class SectionParser:
    """Parse Word section properties (sectPr blocks)."""

    DOCUMENT_PATH = "word/document.xml"
    NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    def __init__(self, package_reader: Any, xml_mapper: Any = None) -> None:
        self.package_reader = package_reader
        self.xml_mapper = xml_mapper

    def parse_sections(self) -> List[Dict[str, Any]]:
        doc_root = self._load_xml(self.DOCUMENT_PATH)
        if doc_root is None:
            return [self._default_section()]

        sections: List[Dict[str, Any]] = []
        for sect_pr in doc_root.findall(".//w:sectPr", self.NS):
            sections.append(self.parse_section_properties(sect_pr))

        if not sections:
            sections.append(self._default_section())
        return sections

    def parse_section_properties(self, sect_pr_element: ET.Element) -> Dict[str, Any]:
        props = self._default_section()

        page_size = sect_pr_element.find("w:pgSz", self.NS)
        if page_size is not None:
            props["page_size"] = {
                "width": self._parse_int_attr(page_size.get("w")),
                "height": self._parse_int_attr(page_size.get("h")),
                "orient": page_size.get("orient", "portrait"),
            }

        page_margin = sect_pr_element.find("w:pgMar", self.NS)
        if page_margin is not None:
            props["margins"] = {
                side: self._parse_int_attr(page_margin.get(side))
                for side in ("top", "bottom", "left", "right", "header", "footer", "gutter")
            }

        columns = sect_pr_element.find("w:cols", self.NS)
        if columns is not None:
            props["columns"] = {
                "num": self._parse_int_attr(columns.get("num"), 1),
                "space": self._parse_int_attr(columns.get("space")),
                "equal_width": columns.get("equalWidth", "1") == "1",
            }

        page_numbers = sect_pr_element.find("w:pgNumType", self.NS)
        if page_numbers is not None:
            props["page_numbering"] = {
                "start": self._parse_int_attr(page_numbers.get("start")),
                "format": page_numbers.get("fmt"),
            }

        return props

    # ------------------------------------------------------------------
    def _load_xml(self, part: str) -> Optional[ET.Element]:
        try:
            if hasattr(self.package_reader, "read"):
                data = self.package_reader.read(part)
            elif hasattr(self.package_reader, "open"):
                with self.package_reader.open(part) as fp:  # type: ignore[call-arg]
                    data = fp.read()
            else:
                raise AttributeError("package_reader must expose read() or open()")
        except FileNotFoundError:
            return None
        if not data:
            return None
        return ET.fromstring(data)

    def _default_section(self) -> Dict[str, Any]:
        return {
            "page_size": {"width": None, "height": None, "orient": "portrait"},
            "margins": {"top": None, "bottom": None, "left": None, "right": None, "header": None, "footer": None, "gutter": None},
            "columns": {"num": 1, "space": None, "equal_width": True},
            "page_numbering": {"start": None, "format": None},
        }

    def _parse_int_attr(self, value: Optional[str], default: Optional[int] = None) -> Optional[int]:
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return default