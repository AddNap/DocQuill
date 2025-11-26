"""XML mapper for DOCX documents."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional, Type

from ..models.base import Models
from ..models.body import Body
from ..models.paragraph import Paragraph
from ..models.run import Run
from ..models.textbox import TextBox
from ..models.image import Image
from ..models.hyperlink import Hyperlink

ModelType = Type[Models]


class XMLMapper:
    """Map WordprocessingML elements onto semantic models."""

    def __init__(self, namespace_map: Optional[Dict[str, str]] = None) -> None:
        self.ns: Dict[str, str] = {
            "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
            "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
        }
        if namespace_map:
            self.ns.update(namespace_map)

        self._registry: Dict[str, ModelType] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register_model("body", Body)
        self.register_model("p", Paragraph)
        self.register_model("r", Run)
        self.register_model("txbxContent", TextBox)
        self.register_model("drawing", Image)
        self.register_model("hyperlink", Hyperlink)

    def register_model(self, tag: str, model_class: ModelType) -> None:
        self._registry[tag] = model_class

    def map_element(self, element: ET.Element, model_class: ModelType) -> Models:
        model = model_class()
        model.xml_node = element
        self.map_attributes(element, model)
        self.map_child_elements(element, model)
        return model

    def map_attributes(self, element: ET.Element, model: Models) -> None:
        for attr, value in element.attrib.items():
            model._attributes[self._strip_namespace(attr)] = value

        text = (element.text or "").strip()
        if text:
            model._attributes.setdefault("text", text)

    def map_child_elements(self, element: ET.Element, model: Models) -> None:
        for child in element:
            tag_name = self._strip_namespace(child.tag)
            model_class = self._registry.get(tag_name)
            if model_class:
                child_model = self.map_element(child, model_class)
                model.add_child(child_model)
            else:
                model._attributes.setdefault("unmapped_children", []).append(child)

    def _strip_namespace(self, tag: str) -> str:
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag
