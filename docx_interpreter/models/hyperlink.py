"""Hyperlink model for DOCX documents."""

from __future__ import annotations

from urllib.parse import urlparse

from .base import Models


class Hyperlink(Models):
    """Represents a hyperlink inside a run."""

    def __init__(self) -> None:
        super().__init__()
        self.target: str = ""
        self.text: str = ""
        self.anchor: str = ""
        self.relationship_id: str = ""

    def set_target(self, target: str) -> None:
        target = target.strip()
        self.target = target
        if target.startswith("#"):
            self.anchor = target[1:]
        else:
            self.anchor = ""

    def set_text(self, text: str) -> None:
        self.text = text or ""

    def set_relationship_id(self, rel_id: str) -> None:
        self.relationship_id = rel_id

    def get_target(self) -> str:
        return self.target

    def get_text(self) -> str:
        return self.text or self.target

    def is_external_link(self) -> bool:
        if not self.target or self.target.startswith("#"):
            return False
        parsed = urlparse(self.target)
        return bool(parsed.scheme and parsed.netloc)

    def is_internal_link(self) -> bool:
        return bool(self.anchor)
