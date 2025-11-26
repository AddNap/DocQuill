"""Properties parser for DOCX documents."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any, Dict, Optional


class PropertiesParser:
    """Parse core, app, and custom document properties."""

    CORE_PATH = "docProps/core.xml"
    APP_PATH = "docProps/app.xml"
    CUSTOM_PATH = "docProps/custom.xml"

    DATE_FIELDS = {
        "created",
        "modified",
        "lastprinted",
    }

    def __init__(self, package_reader: Any, xml_mapper: Any = None) -> None:
        self.package_reader = package_reader
        self.xml_mapper = xml_mapper

    def parse_core_properties(self) -> Dict[str, Any]:
        root = self._load_xml(self.CORE_PATH)
        if root is None:
            return {}

        props: Dict[str, Any] = {}
        for child in root:
            tag = self._strip_namespace(child.tag)
            text = (child.text or "").strip()
            if tag.lower() in self.DATE_FIELDS and text:
                props[tag] = self._parse_datetime(text)
            else:
                props[tag] = text
        return props

    def parse_app_properties(self) -> Dict[str, Any]:
        root = self._load_xml(self.APP_PATH)
        if root is None:
            return {}

        props: Dict[str, Any] = {}
        for child in root:
            tag = self._strip_namespace(child.tag)
            text = (child.text or "").strip()
            if text.isdigit():
                props[tag] = int(text)
            else:
                props[tag] = text
        return props

    def parse_custom_properties(self) -> Dict[str, Any]:
        root = self._load_xml(self.CUSTOM_PATH)
        if root is None:
            return {}

        ns = {
            "cp": "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties",
            "vt": "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes",
        }

        properties: Dict[str, Any] = {}
        for prop in root.findall("cp:property", ns):
            name = prop.get("name")
            if not name:
                continue
            value_element = next(iter(prop), None)
            if value_element is None:
                continue
            value_text = (value_element.text or "").strip()
            properties[name] = self._coerce_value(value_element.tag, value_text)
        return properties

    # ------------------------------------------------------------------
    def _load_xml(self, path: str) -> Optional[ET.Element]:
        try:
            if hasattr(self.package_reader, "read"):
                data = self.package_reader.read(path)
            elif hasattr(self.package_reader, "open"):
                with self.package_reader.open(path) as fp:  # type: ignore[call-arg]
                    data = fp.read()
            else:
                raise AttributeError("package_reader must provide read() or open()")
        except FileNotFoundError:
            return None
        if not data:
            return None
        return ET.fromstring(data)

    def _strip_namespace(self, tag: str) -> str:
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    def _parse_datetime(self, value: str) -> Any:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value

    def _coerce_value(self, tag: str, value: str) -> Any:
        local_tag = self._strip_namespace(tag).lower()
        if local_tag in {"i4", "int"}:
            try:
                return int(value)
            except ValueError:
                return value
        if local_tag in {"r4", "r8", "float", "double"}:
            try:
                return float(value)
            except ValueError:
                return value
        if local_tag == "bool" or local_tag == "boolean":
            return value.lower() in {"true", "1"}
        if local_tag in {"filetime", "date"}:
            return self._parse_datetime(value)
        return value
