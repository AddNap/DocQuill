"""Revision and track changes metadata helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Revision:
    """Single tracked change entry."""

    revision_id: str = ""
    revision_type: str = ""
    author: str = ""
    date: Optional[datetime] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def set_revision_id(self, revision_id: str) -> None:
        if not revision_id:
            raise ValueError("revision_id cannot be empty")
        self.revision_id = str(revision_id)

    def set_revision_type(self, revision_type: str) -> None:
        self.revision_type = revision_type or "unknown"

    def set_revision_author(self, author: str) -> None:
        self.author = author or ""

    def set_revision_date(self, date: datetime) -> None:
        if not isinstance(date, datetime):
            raise TypeError("date must be datetime")
        self.date = date

    def get_revision_id(self) -> str:
        return self.revision_id


class TrackChanges:
    """Collection of `Revision` objects with basic querying helpers."""

    def __init__(self) -> None:
        self._revisions: List[Revision] = []

    def add_revision(self, revision: Revision) -> None:
        if not isinstance(revision, Revision):
            raise TypeError("revision must be a Revision instance")
        if not revision.revision_id:
            raise ValueError("revision requires revision_id")
        self._revisions.append(revision)

    def get_revision_history(self) -> List[Revision]:
        return list(self._revisions)

    def get_revision_by_id(self, revision_id: str) -> Optional[Revision]:
        for revision in self._revisions:
            if revision.revision_id == revision_id:
                return revision
        return None
