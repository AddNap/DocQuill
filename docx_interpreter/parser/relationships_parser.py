"""Relationships parser for DOCX documents."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import PurePosixPath
from typing import Any, Dict, Optional


class RelationshipsParser:
    """Parse the `_rels/*.rels` parts from the DOCX package."""

    NAMESPACE = "http://schemas.openxmlformats.org/package/2006/relationships"

    def __init__(self, package_reader: Any):
        self.package_reader = package_reader

    def parse_relationships(self, rels_path: str) -> Dict[str, Dict[str, Any]]:
        xml_bytes = self._read_part(rels_path)
        if not xml_bytes:
            return {}

        root = ET.fromstring(xml_bytes)
        relationships: Dict[str, Dict[str, Any]] = {}
        for rel_element in root.findall(f"{{{self.NAMESPACE}}}Relationship"):
            rel = self.parse_relationship(rel_element)
            if rel and rel.get("id"):
                relationships[rel["id"]] = rel
        return relationships

    def parse_relationship(self, rel_element: ET.Element) -> Dict[str, Any]:
        rel_id = rel_element.get("Id", "")
        rel_type = rel_element.get("Type", "")
        target = rel_element.get("Target", "")
        mode = rel_element.get("TargetMode", "Internal")
        return {
            "id": rel_id,
            "type": rel_type,
            "target": target,
            "target_mode": mode,
        }

    def resolve_relationship_target(self, target: str, source_path: str) -> str:
        if not target:
            return ""
        target_path = PurePosixPath(target)
        if target_path.is_absolute():
            return str(target_path)
        base = PurePosixPath(source_path).parent
        return str(base.joinpath(target_path).as_posix())

    def _read_part(self, rels_path: str) -> Optional[bytes]:
        if hasattr(self.package_reader, "read"):
            return self.package_reader.read(rels_path)
        if hasattr(self.package_reader, "open"):
            with self.package_reader.open(rels_path) as fp:  # type: ignore[call-arg]
                return fp.read()
        raise AttributeError("package_reader must expose read() or open()")
