from __future__ import annotations

from typing import Optional

STANDARD_FONT_VARIANTS = {
    "Helvetica",
    "Helvetica-Bold",
    "Helvetica-Oblique",
    "Helvetica-BoldOblique",
    "Times-Roman",
    "Times-Bold",
    "Times-Italic",
    "Times-BoldItalic",
    "Courier",
    "Courier-Bold",
    "Courier-Oblique",
    "Courier-BoldOblique",
}

STANDARD_FONT_VARIANTS.update(
    {
        "DejaVuSans",
        "DejaVuSans-Bold",
        "DejaVuSans-Oblique",
        "DejaVuSans-BoldOblique",
        "DejaVuSerif",
        "DejaVuSerif-Bold",
        "DejaVuSerif-Italic",
        "DejaVuSerif-BoldItalic",
    }
)

FONT_FALLBACKS = {
    "arial": "DejaVuSans",
    "arial mt": "DejaVuSans",
    "arialmt": "DejaVuSans",
    "calibri": "DejaVuSans",
    "candara": "DejaVuSans",
    "dejavu sans": "DejaVuSans",
    "helvetica": "Helvetica",
    "lucida sans": "DejaVuSans",
    "malgun gothic": "DejaVuSans",
    "microsoft sans serif": "DejaVuSans",
    "sans-serif": "DejaVuSans",
    "segoe ui": "DejaVuSans",
    "tahoma": "DejaVuSans",
    "trebuchet ms": "DejaVuSans",
    "verdana": "DejaVuSans",
    "cambria": "DejaVuSerif",
    "georgia": "DejaVuSerif",
    "serif": "DejaVuSerif",
    "times": "DejaVuSerif",
    "times new roman": "DejaVuSerif",
    "courier new": "Courier",
    "consolas": "Courier",
    "lucida console": "Courier",
    "monospace": "Courier",
}


def _normalize_base_font(font_name: Optional[str]) -> str:
    if not font_name:
        return "Helvetica"

    cleaned = font_name.strip()
    if not cleaned:
        return "Helvetica"

    if cleaned in STANDARD_FONT_VARIANTS:
        return cleaned

    lowered = cleaned.lower()
    base = FONT_FALLBACKS.get(lowered, cleaned)

    if base.lower() == "times":
        return "Times-Roman"
    if base.lower() == "courier new":
        return "Courier"
    if base.lower() == "times new roman":
        return "Times-Roman"
    if base.lower() == "helvetica":
        return "Helvetica"
    if base.lower() == "dejavusans":
        return "DejaVuSans"
    if base.lower() == "dejavuserif":
        return "DejaVuSerif"

    return base


def resolve_font_variant(font_name: Optional[str], bold: bool, italic: bool) -> str:
    base = _normalize_base_font(font_name)
    if base in STANDARD_FONT_VARIANTS:
        # If the base name already encodes weight/style (e.g. Helvetica-Bold),
        # keep it as-is. Otherwise treat it as plain family and apply flags.
        if base not in {"Helvetica", "Times-Roman", "Courier"}:
            if any(
                base.endswith(suffix)
                for suffix in ("-Bold", "-Italic", "-Oblique", "-BoldItalic", "-BoldOblique")
            ):
                return base
            if bold or italic:
                # fall through to flag-based selection below
                pass
            else:
                return base

    normalized = base.lower()

    if normalized in {
        "helvetica",
        "arial mt",
        "arialmt",
        "arial",
        "verdana",
        "tahoma",
        "calibri",
        "segoe ui",
        "trebuchet ms",
        "candara",
        "microsoft sans serif",
        "dejavu sans",
        "dejavusans",
    }:
        base = "DejaVuSans"
    elif normalized in {
        "times",
        "times-roman",
        "times new roman",
        "cambria",
        "georgia",
        "serif",
        "dejavu serif",
        "dejavuserif",
    }:
        base = "DejaVuSerif"
    elif normalized in {"courier new", "courier", "consolas", "lucida console", "monospace"}:
        base = "Courier"

    if normalized in {"dejavu sans", "dejavusans"}:
        base = "DejaVuSans"
    if normalized in {"dejavu serif", "dejavuserif"}:
        base = "DejaVuSerif"

    if base == "Helvetica":
        if bold and italic:
            return "Helvetica-BoldOblique"
        if bold:
            return "Helvetica-Bold"
        if italic:
            return "Helvetica-Oblique"
        return "Helvetica"

    if base == "Times-Roman":
        if bold and italic:
            return "Times-BoldItalic"
        if bold:
            return "Times-Bold"
        if italic:
            return "Times-Italic"
        return "Times-Roman"

    if base == "Courier":
        if bold and italic:
            return "Courier-BoldOblique"
        if bold:
            return "Courier-Bold"
        if italic:
            return "Courier-Oblique"
        return "Courier"

    if base == "DejaVuSans":
        if bold and italic:
            return "DejaVuSans-BoldOblique"
        if bold:
            return "DejaVuSans-Bold"
        if italic:
            return "DejaVuSans-Oblique"
        return "DejaVuSans"

    if base == "DejaVuSerif":
        if bold and italic:
            return "DejaVuSerif-BoldItalic"
        if bold:
            return "DejaVuSerif-Bold"
        if italic:
            return "DejaVuSerif-Italic"
        return "DejaVuSerif"

    if bold and italic:
        return f"{base}-BoldItalic"
    if bold:
        return f"{base}-Bold"
    if italic:
        return f"{base}-Italic"
    return base

