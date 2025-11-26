"""Style inheritance tree for DOCX documents."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set


class StyleInheritanceTree:
    """Maintain and validate style inheritance relationships (basedOn / next)."""

    def __init__(self) -> None:
        self._styles: Dict[str, Dict[str, Any]] = {}
        self._based_on: Dict[str, str] = {}
        self._next: Dict[str, str] = {}

    def add_style(self, style_id: str, style_properties: Optional[Dict[str, Any]] = None) -> None:
        if not style_id:
            raise ValueError("style_id is required")
        self._styles[style_id] = dict(style_properties or {})

    def set_style_inheritance(
        self,
        style_id: str,
        based_on: Optional[str] = None,
        next_style: Optional[str] = None,
    ) -> None:
        if style_id not in self._styles:
            self.add_style(style_id)
        if based_on:
            self._based_on[style_id] = based_on
        if next_style:
            self._next[style_id] = next_style

    def get_style_hierarchy(self, style_id: str) -> List[str]:
        chain: List[str] = []
        visited: Set[str] = set()
        current = style_id
        while current and current not in visited:
            visited.add(current)
            chain.append(current)
            current = self._based_on.get(current)
        return chain

    def resolve_style_chain(self, style_id: str) -> List[Dict[str, Any]]:
        chain_ids = self.get_style_hierarchy(style_id)
        return [self._styles.get(s_id, {}) for s_id in reversed(chain_ids)]

    def get_next_style(self, style_id: str) -> Optional[str]:
        return self._next.get(style_id)

    def validate_inheritance_tree(self) -> bool:
        return self._detect_cycles() is None

    def _detect_cycles(self) -> Optional[List[str]]:
        visited: Set[str] = set()
        stack: Set[str] = set()

        def dfs(node: str) -> Optional[List[str]]:
            visited.add(node)
            stack.add(node)
            next_node = self._based_on.get(node)
            if next_node:
                if next_node in stack:
                    return [next_node, node]
                if next_node not in visited:
                    cycle = dfs(next_node)
                    if cycle:
                        return cycle
            stack.remove(node)
            return None

        for style_id in self._styles:
            if style_id not in visited:
                cycle = dfs(style_id)
                if cycle:
                    return cycle
        return None
