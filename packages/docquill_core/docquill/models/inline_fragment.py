"""InlineFragment model for DOCX documents."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import Models


class InlineFragment(Models):
    """Groups consecutive runs that share stylistic properties."""

    def __init__(self) -> None:
        super().__init__()
        self.runs: List[Any] = []
        self._style: Optional[Dict[str, Any]] = None

    def add_run(self, run: Any) -> None:
        if run is None:
            raise ValueError("Cannot add None run to InlineFragment")
        if self.runs and not self._styles_match(self.runs[-1], run):
            raise ValueError("Run style differs from existing fragment style")
        if hasattr(run, "style") and isinstance(run.style, dict):
            if self._style is None:
                self._style = run.style.copy()
        self.runs.append(run)
        self.add_child(run)

    def _styles_match(self, run_a: Any, run_b: Any) -> bool:
        style_a = getattr(run_a, "style", None)
        style_b = getattr(run_b, "style", None)
        if isinstance(style_a, dict) and isinstance(style_b, dict):
            return style_a == style_b
        return style_a == style_b

    def get_text(self) -> str:
        parts: List[str] = []
        for run in self.runs:
            if hasattr(run, "get_text"):
                parts.append(run.get_text() or "")
            elif hasattr(run, "text"):
                parts.append(str(run.text))
        return "".join(parts)

    def get_style(self) -> Optional[Dict[str, Any]]:
        return self._style.copy() if self._style else None

    def is_style_consistent(self) -> bool:
        if not self.runs:
            return True
        reference = getattr(self.runs[0], "style", None)
        for run in self.runs[1:]:
            if getattr(run, "style", None) != reference:
                return False
        return True
