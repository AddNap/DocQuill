"""Style cascade engine for DOCX documents."""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, Optional


StyleDict = Dict[str, Any]


class StyleCascadeEngine:
    """Compose final style dictionaries from theme, referenced, and local styles."""

    def __init__(self) -> None:
        self._cache: Dict[int, StyleDict] = {}

    # ------------------------------------------------------------------
    def cascade_styles(
        self,
        element: Any,
        theme: Optional[Any] = None,
        global_styles: Optional[Any] = None,
        local_styles: Optional[StyleDict] = None,
    ) -> StyleDict:
        style: StyleDict = {}

        if theme:
            style = self.merge_style_properties(style, self.apply_theme_styles(element, theme))

        referenced_style = self._resolve_referenced_style(element, global_styles)
        if referenced_style:
            style = self.merge_style_properties(style, referenced_style)

        if local_styles:
            style = self.merge_style_properties(style, local_styles)

        self._cache[id(element)] = style
        return style

    # ------------------------------------------------------------------
    def resolve_style_inheritance(self, style: StyleDict, parent_styles: Iterable[StyleDict]) -> StyleDict:
        merged: StyleDict = {}
        for parent in parent_styles:
            if not parent:
                continue
            merged = self.merge_style_properties(merged, parent)
        merged = self.merge_style_properties(merged, style)
        return merged

    # ------------------------------------------------------------------
    def merge_style_properties(self, base_style: StyleDict, override_style: StyleDict) -> StyleDict:
        if not override_style:
            return dict(base_style)

        result = dict(base_style)
        for key, value in override_style.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = self.merge_style_properties(result[key], value)  # type: ignore[arg-type]
            else:
                result[key] = value
        return result

    # ------------------------------------------------------------------
    def apply_theme_styles(self, element: Any, theme: Any) -> StyleDict:
        if theme is None:
            return {}

        if isinstance(theme, dict):
            family = getattr(element, "style_type", None) or getattr(element, "type", None)
            if isinstance(family, str) and family.lower() in theme:
                candidate = theme[family.lower()]
                return dict(candidate) if isinstance(candidate, dict) else {}
            default_style = theme.get("default")
            return dict(default_style) if isinstance(default_style, dict) else {}

        if callable(theme):
            computed = theme(element)
            return dict(computed) if isinstance(computed, dict) else {}

        return {}

    # ------------------------------------------------------------------
    def get_final_style(self, element: Any) -> StyleDict:
        return dict(self._cache.get(id(element), {}))

    # ------------------------------------------------------------------
    def _resolve_referenced_style(self, element: Any, global_styles: Any) -> StyleDict:
        if not global_styles:
            return {}

        if isinstance(global_styles, dict):
            style_ref = getattr(element, "style", None)
            if isinstance(style_ref, str) and style_ref in global_styles:
                referenced = global_styles[style_ref]
                if isinstance(referenced, dict):
                    inheritance = referenced.get("based_on")
                    inherited = []
                    if isinstance(inheritance, (list, tuple)):
                        inherited = [global_styles.get(name, {}) for name in inheritance if name in global_styles]
                    elif isinstance(inheritance, str) and inheritance in global_styles:
                        inherited = [global_styles.get(inheritance, {})]
                    return self.resolve_style_inheritance(referenced, inherited)
                return {}
            default_style = global_styles.get("default")
            if isinstance(default_style, dict):
                return dict(default_style)
        elif callable(global_styles):
            result = global_styles(element)
            return dict(result) if isinstance(result, dict) else {}

        return {}
