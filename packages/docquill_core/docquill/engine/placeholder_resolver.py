"""Utilities for resolving placeholder fields in text content."""

from __future__ import annotations

import re
from typing import Any, Dict, Mapping, Optional


class PlaceholderResolver:
    """Resolve placeholders of the form ``{{ TYPE:Key }}`` within text."""

    _pattern = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*:?\s*([^\}]+?)\s*\}\}")

    def __init__(self, values: Optional[Mapping[str, Any]] = None) -> None:
        self.values: Dict[str, Any] = dict(values or {})

    def set_values(self, values: Mapping[str, Any]) -> None:
        self.values = dict(values)

    def resolve_text(self, text: str) -> str:
        if not text or "{{" not in text:
            return text

        def replacer(match: re.Match[str]) -> str:
            namespace = match.group(1) or ""
            key = (match.group(2) or "").strip()
            candidates = [f"{namespace}:{key}", key]
            for candidate in candidates:
                if candidate in self.values:
                    return str(self.values[candidate])
            return match.group(0)

        return self._pattern.sub(replacer, text)

    def resolve_payload(self, payload: Any) -> Any:
        if isinstance(payload, str):
            return self.resolve_text(payload)

        if isinstance(payload, dict):
            return {k: self.resolve_payload(v) for k, v in payload.items()}

        if isinstance(payload, list):
            return [self.resolve_payload(item) for item in payload]

        return payload

