from __future__ import annotations

"""
Unified tree representation for layout assembly.

Each LayoutNode mirrors the logical structure of the DOCX document.  Engines
should produce nodes recursively: a container node is responsible for creating
child nodes by delegating to the dispatcher, while leaves describe atomic
elements such as text runs or images.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence, Type

from .geometry import Rect


class LayoutNode(Protocol):
    """Common protocol for all nodes."""

    kind: str
    source: Any
    children: List["LayoutNode"]


@dataclass(slots=True)
class BaseNode:
    kind: str
    source: Any
    box: Optional[Rect] = None
    style: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    children: List["LayoutNode"] = field(default_factory=list)

    def append(self, child: "LayoutNode") -> None:
        self.children.append(child)

    def extend(self, nodes: Iterable["LayoutNode"]) -> None:
        self.children.extend(nodes)


@dataclass(slots=True)
class LeafNode(BaseNode):
    """Leaf nodes do not accept children."""

    def append(self, child: "LayoutNode") -> None:  # pragma: no cover
        raise RuntimeError(f"Leaf node '{self.kind}' cannot accept children")

    def extend(self, nodes: Iterable["LayoutNode"]) -> None:  # pragma: no cover
        raise RuntimeError(f"Leaf node '{self.kind}' cannot accept children")


class Engine(Protocol):
    """
    Engine interface used by the dispatcher to build nodes recursively.
    """

    supported_kinds: Sequence[str]

    def can_handle(self, element: Any) -> bool:
        ...

    def build(self, element: Any, dispatcher: "Dispatcher", **context: Any) -> LayoutNode:
        ...


class Dispatcher:
    """Maps model elements to the appropriate engine."""

    def __init__(self, engines: Sequence[Engine]) -> None:
        self._engines: List[Engine] = list(engines)

    def register(self, engine: Engine) -> None:
        self._engines.append(engine)

    def dispatch(self, element: Any, **context: Any) -> LayoutNode:
        for engine in self._engines:
            try:
                if engine.can_handle(element):
                    return engine.build(element, self, **context)
            except Exception as exc:  # pragma: no cover - defensive
                raise RuntimeError(f"Engine {engine!r} failed for {element!r}") from exc
        raise LookupError(f"No layout engine registered for element {type(element)!r}")


def walk(node: LayoutNode) -> Iterable[LayoutNode]:
    """Simple DFS walk over the layout tree."""
    yield node
    for child in node.children:
        yield from walk(child)


