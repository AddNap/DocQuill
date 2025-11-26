from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

from ..layout_tree import BaseNode, LeafNode, LayoutNode, Dispatcher, Engine


def _get_type_name(element: Any) -> str:
    if isinstance(element, dict):
        t = element.get("type") or element.get("kind")
        if t:
            return str(t).lower()
    if hasattr(element, "type") and getattr(element, "type"):
        return str(getattr(element, "type")).lower()
    return type(element).__name__.lower()


def _get_style_dict(element: Any) -> Dict[str, Any]:
    if isinstance(element, dict):
        return dict(element.get("style") or {})
    style = getattr(element, "style", None)
    return dict(style) if isinstance(style, dict) else {}


def _iter_children(element: Any) -> Iterable[Any]:
    if isinstance(element, dict):
        children = element.get("children") or []
    else:
        children = getattr(element, "children", []) or []
    if not children:
        return []
    return children if isinstance(children, list) else [children]


def _iter_runs(element: Any) -> Iterable[Any]:
    if isinstance(element, dict):
        runs = element.get("runs") or []
    else:
        runs = getattr(element, "runs", []) or []
    if not runs:
        return []
    return runs if isinstance(runs, list) else [runs]


def _iter_images(element: Any) -> Iterable[Any]:
    if isinstance(element, dict):
        images = element.get("images") or []
    else:
        images = getattr(element, "images", []) or []
    if not images:
        return []
    return images if isinstance(images, list) else [images]


def _iter_table_rows(element: Any) -> Iterable[Any]:
    rows = getattr(element, "rows", None)
    if rows is None and isinstance(element, dict):
        rows = element.get("rows")
    if not rows:
        return []
    return rows if isinstance(rows, list) else [rows]


def _iter_row_cells(row: Any) -> Iterable[Any]:
    cells = getattr(row, "cells", None)
    if cells is None and isinstance(row, dict):
        cells = row.get("cells")
    if not cells:
        # Some implementations keep row as list
        cells = row if isinstance(row, list) else []
    return cells if isinstance(cells, list) else [cells]


def _iter_cell_content(cell: Any) -> Iterable[Any]:
    content = getattr(cell, "content", None)
    if content is None and isinstance(cell, dict):
        content = cell.get("content")
    if not content:
        content = getattr(cell, "children", None)
        if content is None and isinstance(cell, dict):
            content = cell.get("children")
    if not content:
        return []
    return content if isinstance(content, list) else [content]


@dataclass(slots=True)
class ParagraphEngine(Engine):
    supported_kinds: Sequence[str] = ("paragraph",)

    def can_handle(self, element: Any) -> bool:
        return _get_type_name(element) == "paragraph"

    def build(self, element: Any, dispatcher: Dispatcher, **context: Any) -> LayoutNode:
        node = BaseNode(
            kind="paragraph",
            source=element,
            style=_get_style_dict(element),
            metadata={"origin": type(element).__name__},
        )
        dispatched_ids: List[int] = []
        for run in _iter_runs(element):
            dispatched_ids.append(id(run))
            node.append(dispatcher.dispatch(run, parent=node))
        for child in _iter_children(element):
            if id(child) in dispatched_ids:
                continue
            node.append(dispatcher.dispatch(child, parent=node))
        return node


@dataclass(slots=True)
class RunEngine(Engine):
    supported_kinds: Sequence[str] = ("run",)

    def can_handle(self, element: Any) -> bool:
        return _get_type_name(element) == "run"

    def build(self, element: Any, dispatcher: Dispatcher, **context: Any) -> LayoutNode:
        node = BaseNode(
            kind="run",
            source=element,
            style=_get_style_dict(element),
            metadata={"origin": type(element).__name__},
        )

        text_value = getattr(element, "text", None)
        if text_value is None and isinstance(element, dict):
            text_value = element.get("text")
        if text_value:
            node.append(
                LeafNode(
                    kind="text",
                    source=text_value,
                    metadata={"content": text_value},
                )
            )

        for image in _iter_images(element):
            node.append(dispatcher.dispatch(image, parent=node))

        for child in _iter_children(element):
            node.append(dispatcher.dispatch(child, parent=node))

        return node


@dataclass(slots=True)
class ImageEngine(Engine):
    supported_kinds: Sequence[str] = ("image",)

    def can_handle(self, element: Any) -> bool:
        t = _get_type_name(element)
        return t == "image" or hasattr(element, "image_path") or hasattr(element, "path")

    def build(self, element: Any, dispatcher: Dispatcher, **context: Any) -> LayoutNode:
        width = getattr(element, "width", None)
        height = getattr(element, "height", None)
        if isinstance(element, dict):
            width = element.get("width", width)
            height = element.get("height", height)
        metadata = {"width": width, "height": height}
        if isinstance(element, dict):
            metadata.update({k: element.get(k) for k in ("anchor_type", "relationship_id", "path") if element.get(k) is not None})
        else:
            for attr in ("anchor_type", "relationship_id", "path", "image_path"):
                if hasattr(element, attr):
                    metadata[attr] = getattr(element, attr)
        return LeafNode(kind="image", source=element, metadata=metadata)


@dataclass(slots=True)
class TextEngine(Engine):
    supported_kinds: Sequence[str] = ("text", "string")

    def can_handle(self, element: Any) -> bool:
        return isinstance(element, str)

    def build(self, element: Any, dispatcher: Dispatcher, **context: Any) -> LayoutNode:
        return LeafNode(kind="text", source=element, metadata={"content": element})


@dataclass(slots=True)
class TableCellEngine(Engine):
    supported_kinds: Sequence[str] = ("tablecell", "cell", "tc")

    def can_handle(self, element: Any) -> bool:
        t = _get_type_name(element)
        return t in {"tablecell", "cell", "tc"}

    def build(self, element: Any, dispatcher: Dispatcher, **context: Any) -> LayoutNode:
        node = BaseNode(
            kind="table_cell",
            source=element,
            style=_get_style_dict(element),
            metadata={"origin": type(element).__name__},
        )
        for image in _iter_images(element):
            node.append(dispatcher.dispatch(image, parent=node))
        for item in _iter_cell_content(element):
            node.append(dispatcher.dispatch(item, parent=node))
        return node


@dataclass(slots=True)
class TableRowEngine(Engine):
    supported_kinds: Sequence[str] = ("tablerow", "row", "table_row", "tr")

    def can_handle(self, element: Any) -> bool:
        t = _get_type_name(element)
        return t in {"tablerow", "row", "table_row", "tr"}

    def build(self, element: Any, dispatcher: Dispatcher, **context: Any) -> LayoutNode:
        node = BaseNode(
            kind="table_row",
            source=element,
            style=_get_style_dict(element),
            metadata={"origin": type(element).__name__},
        )
        for cell in _iter_row_cells(element):
            node.append(dispatcher.dispatch(cell, parent=node))
        return node


@dataclass(slots=True)
class TableEngine(Engine):
    supported_kinds: Sequence[str] = ("table",)

    def can_handle(self, element: Any) -> bool:
        return _get_type_name(element) == "table"

    def build(self, element: Any, dispatcher: Dispatcher, **context: Any) -> LayoutNode:
        node = BaseNode(
            kind="table",
            source=element,
            style=_get_style_dict(element),
            metadata={"origin": type(element).__name__},
        )
        for row in _iter_table_rows(element):
            node.append(dispatcher.dispatch(row, parent=node))
        return node


DEFAULT_ENGINES: List[Engine] = [
    TableEngine(),
    TableRowEngine(),
    TableCellEngine(),
    ParagraphEngine(),
    RunEngine(),
    ImageEngine(),
    TextEngine(),
]


def create_default_dispatcher(additional_engines: Optional[Sequence[Engine]] = None) -> Dispatcher:
    engines: List[Engine] = list(DEFAULT_ENGINES)
    if additional_engines:
        engines.extend(additional_engines)
    return Dispatcher(engines)


