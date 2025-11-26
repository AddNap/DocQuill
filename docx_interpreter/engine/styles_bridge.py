"""Bridge between the layout engine and the style resolver subsystem."""

from __future__ import annotations

import logging
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional

from ..styles.style_resolver import StyleResolver

logger = logging.getLogger(__name__)


class StyleBridge:
    """Thin wrapper around :class:`StyleResolver` tailored for layout usage."""

    def __init__(self, resolver: Optional[StyleResolver] = None) -> None:
        self.resolver = resolver or StyleResolver()

    def resolve(self, element: Any, fallback_type: str = "paragraph") -> Dict[str, Any]:
        """Resolve the effective style dictionary for the provided element."""

        if element is None:
            return {}

        style_type = self._detect_style_type(element, fallback_type)

        try:
            resolved = self.resolver.resolve_style(element, style_type)  # type: ignore[attr-defined]
        except AttributeError:
            # Older implementations might expose `resolve`
            style_ref = self._extract_style_ref(element)
            if style_ref:
                resolved = self.resolver.resolve(style_ref)  # type: ignore[attr-defined]
            else:
                resolved = {}

        resolved = self._normalize_mapping(resolved)
        inline_props = self._extract_inline_properties(element)
        if inline_props:
            resolved = {**resolved, **inline_props}

        return resolved

    def _detect_style_type(self, element: Any, fallback: str) -> str:
        if isinstance(element, dict):
            return element.get("type", fallback)

        type_hint = getattr(element, "type", None)
        if isinstance(type_hint, str):
            return type_hint

        class_name = element.__class__.__name__.lower()
        for candidate in ("paragraph", "table", "image", "run"):
            if candidate in class_name:
                return candidate

        return fallback

    def _extract_style_ref(self, element: Any) -> Optional[str]:
        if isinstance(element, dict):
            ref = element.get("style_ref") or element.get("styleId") or element.get("style")
            return ref if isinstance(ref, str) else None

        for attr in ("style_ref", "style_id", "styleId"):
            value = getattr(element, attr, None)
            if isinstance(value, str):
                return value

        return None

    def _extract_inline_properties(self, element: Any) -> Dict[str, Any]:
        properties: Dict[str, Any] = {}

        if isinstance(element, dict):
            for key in ("style", "properties", "formatting"):
                value = element.get(key)
                normalized = self._normalize_mapping(value)
                if normalized:
                    properties.update(normalized)
            return properties

        for attr in ("style", "properties", "formatting"):
            value = getattr(element, attr, None)
            normalized = self._normalize_mapping(value)
            if normalized:
                properties.update(normalized)

        return properties

    def _normalize_mapping(self, value: Any) -> Dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return dict(value)
        if is_dataclass(value):
            return {k: v for k, v in asdict(value).items() if v is not None}
        if hasattr(value, "to_dict") and callable(value.to_dict):
            try:
                result = value.to_dict()
                return dict(result) if isinstance(result, dict) else {}
            except Exception as e:
                logger.debug(f"Failed to convert value to dict using to_dict() method: {e}")
                return {}
        if hasattr(value, "__dict__"):
            return {
                k: v
                for k, v in value.__dict__.items()
                if not k.startswith("_") and v is not None
            }
        return {}


class InlineStyleApplier:
    """
    Klasa do łączenia stylów inline z globalnymi stylami.
    
    Umożliwia mieszanie stylów inline (<b>, <i>, w:rPr) z globalnymi stylami paragrafów.
    """
    
    @staticmethod
    def merge_inline_styles(base_style: Dict[str, Any], inline_style: Dict[str, Any]) -> Dict[str, Any]:
        """
        Łączy style inline z bazowym stylem.
        
        Args:
            base_style: Bazowy styl (np. z paragrafu)
            inline_style: Style inline (np. z run, w:rPr)
            
        Returns:
            Połączony styl z nadpisanymi właściwościami inline
        """
        # Twórz kopię bazowego stylu
        merged = dict(base_style)
        
        # Nadpisz właściwości inline
        merged.update(inline_style)
        
        # Obsługa specjalnych przypadków - łączenie boolean
        if "bold" in inline_style:
            merged["bold"] = inline_style["bold"]
        if "italic" in inline_style:
            merged["italic"] = inline_style["italic"]
        if "underline" in inline_style:
            merged["underline"] = inline_style["underline"]
        
        # Obsługa kolorów
        if "color" in inline_style:
            merged["color"] = inline_style["color"]
        if "font_color" in inline_style:
            merged["font_color"] = inline_style["font_color"]
        
        # Obsługa fontów
        if "font_name" in inline_style:
            merged["font_name"] = inline_style["font_name"]
        if "font_family" in inline_style:
            merged["font_family"] = inline_style["font_family"]
        if "font_size" in inline_style:
            merged["font_size"] = inline_style["font_size"]
        
        return merged
    
    @staticmethod
    def extract_run_style(run: Any) -> Dict[str, Any]:
        """
        Ekstraktuje style inline z run.
        
        Args:
            run: Obiekt run (np. z Paragraph.runs)
            
        Returns:
            Dict ze stylami inline
        """
        style = {}
        
        if isinstance(run, dict):
            # Jeśli run jest dict, wyciągnij style bezpośrednio
            style = run.get("style", {})
            if isinstance(style, dict):
                return dict(style)
            return {}
        
        # Jeśli run jest obiektem, wyciągnij właściwości
        if hasattr(run, "bold"):
            style["bold"] = bool(run.bold)
        if hasattr(run, "italic"):
            style["italic"] = bool(run.italic)
        if hasattr(run, "underline"):
            style["underline"] = bool(run.underline)
        if hasattr(run, "font_name") or hasattr(run, "font_family"):
            style["font_name"] = getattr(run, "font_name", None) or getattr(run, "font_family", None)
        if hasattr(run, "font_size"):
            style["font_size"] = getattr(run, "font_size", None)
        if hasattr(run, "color") or hasattr(run, "font_color"):
            style["color"] = getattr(run, "color", None) or getattr(run, "font_color", None)
        
        # Jeśli run ma styl jako dict
        if hasattr(run, "style") and isinstance(run.style, dict):
            style.update(run.style)
        
        return style
    
    @staticmethod
    def apply_to_runs(paragraph_style: Dict[str, Any], runs: list) -> List[Dict[str, Any]]:
        """
        Stosuje style inline do listy runs.
        
        Args:
            paragraph_style: Bazowy styl paragrafu
            runs: Lista runs (obiektów lub dictów)
            
        Returns:
            Lista stylów dla każdego run
        """
        result = []
        
        for run in runs:
            inline_style = InlineStyleApplier.extract_run_style(run)
            merged_style = InlineStyleApplier.merge_inline_styles(paragraph_style, inline_style)
            result.append(merged_style)
        
        return result

