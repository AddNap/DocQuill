"""Helpers for resolving font file paths across platforms."""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Optional, Tuple


FONT_SEARCH_DIRS = [
    Path("/usr/share/fonts"),
    Path("/usr/local/share/fonts"),
    Path.home() / ".fonts",
    Path.home() / ".local/share/fonts",
]

FONT_EXTENSIONS = (".ttf", ".ttc", ".otf")


def _fc_match(pattern: str) -> Optional[Path]:
    try:
        result = subprocess.run(
            ["fc-match", "-f", "%{file}\n", pattern],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    output = (result.stdout or "").strip().splitlines()
    if not output:
        return None

    path = Path(output[0]).expanduser()
    return path if path.exists() else None


def _candidate_filenames(font_name: str, bold: bool, italic: bool) -> Tuple[str, ...]:
    base = font_name.replace(" ", "")
    variants = [font_name, base]

    suffixes = ["", "-Regular", "_Regular", "-regular", "_regular"]
    if bold and italic:
        style_suffixes = ["BoldItalic", "BoldOblique", "BI", "bolditalic"]
    elif bold:
        style_suffixes = ["Bold", "BD", "bold"]
    elif italic:
        style_suffixes = ["Italic", "Oblique", "I", "italic"]
    else:
        style_suffixes = [""]

    candidates = set()
    for prefix in variants:
        for style_suffix in style_suffixes:
            for suffix in suffixes:
                name = f"{prefix}{suffix}{style_suffix}" if style_suffix else f"{prefix}{suffix}"
                if name:
                    candidates.add(name.lower())

    result = []
    for candidate in candidates:
        for ext in FONT_EXTENSIONS:
            result.append(candidate + ext)

    return tuple(result)


@lru_cache(maxsize=256)
def resolve_font_path(font_name: str, bold: bool = False, italic: bool = False) -> Optional[Tuple[str, str]]:
    if not font_name:
        return None

    style_parts = []
    if bold:
        style_parts.append("Bold")
    if italic:
        style_parts.append("Italic")

    pattern = font_name
    if style_parts:
        pattern = f"{font_name}:style={' '.join(style_parts)}"

    path = _fc_match(pattern)
    if path and path.suffix.lower() in FONT_EXTENSIONS:
        variant_name = _variant_name(font_name, bold, italic)
        return variant_name, str(path)

    candidates = _candidate_filenames(font_name, bold, italic)
    for search_dir in FONT_SEARCH_DIRS:
        if not search_dir.exists():
            continue
        for candidate in candidates:
            candidate_path = search_dir / candidate
            if candidate_path.exists():
                variant_name = _variant_name(font_name, bold, italic)
                return variant_name, str(candidate_path)

    # Fallback: exhaustive search if nothing else worked
    for search_dir in FONT_SEARCH_DIRS:
        if not search_dir.exists():
            continue
        for ext in FONT_EXTENSIONS:
            for path in search_dir.rglob(f"*{ext}"):
                if font_name.lower() in path.stem.lower():
                    variant_name = _variant_name(font_name, bold, italic)
                    return variant_name, str(path)

    return None


def _variant_name(font_name: str, bold: bool, italic: bool) -> str:
    variant = font_name
    if bold and italic:
        variant += "-BoldItalic"
    elif bold:
        variant += "-Bold"
    elif italic:
        variant += "-Italic"
    return variant

