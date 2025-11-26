"""Optional diagnostics helpers for renderers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterable, Iterator, Optional


@contextmanager
def render_phase(name: str) -> Iterator[None]:  # pragma: no cover - debug helper
    try:
        yield
    finally:
        pass


def describe_layout_pages(pages: Iterable) -> str:
    count = 0
    blocks = 0
    for page in pages:
        count += 1
        blocks += len(getattr(page, "blocks", []))
    return f"LayoutPages(pages={count}, blocks={blocks})"

