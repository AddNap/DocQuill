"""SmartArt parser for DOCX documents."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional


class SmartArtParser:
    """Provide minimal SmartArt XML to dictionary conversion."""

    NS = {
        "dgm": "http://schemas.openxmlformats.org/drawingml/2006/diagram",
        "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    }

    def __init__(self, package_reader: Any = None, xml_mapper: Any = None) -> None:
        self.package_reader = package_reader
        self.xml_mapper = xml_mapper

    def parse_smartart(self, smartart_element: ET.Element) -> Dict[str, Any]:
        if smartart_element is None:
            return {}
        diagram = smartart_element.find("dgm:diagram", self.NS)
        if diagram is None:
            diagram = smartart_element
        return self.parse_diagram(diagram)

    def parse_diagram(self, diagram_element: ET.Element) -> Dict[str, Any]:
        nodes = []
        for node in diagram_element.findall(".//dgm:pt", self.NS):
            nodes.append(self.parse_diagram_node(node))
        connections = []
        for conn in diagram_element.findall(".//dgm:cxn", self.NS):
            connections.append(
                {
                    "model_id": conn.get("modelId"),
                    "src_id": conn.get("srcId"),
                    "dest_id": conn.get("destId"),
                }
            )
        return {"nodes": nodes, "connections": connections}

    def parse_diagram_node(self, node_element: ET.Element) -> Dict[str, Any]:
        node_id = node_element.get("modelId") or node_element.get("id")
        node_type = node_element.get("type")
        text = self._extract_text(node_element)
        children: List[Dict[str, Any]] = []
        for child in node_element.findall("dgm:pt", self.NS):
            children.append(self.parse_diagram_node(child))
        return {
            "id": node_id,
            "type": node_type,
            "text": text,
            "children": children,
        }

    def _extract_text(self, element: ET.Element) -> str:
        texts = []
        for text_node in element.findall(".//a:t", self.NS):
            if text_node.text:
                texts.append(text_node.text.strip())
        return " ".join(filter(None, texts))
