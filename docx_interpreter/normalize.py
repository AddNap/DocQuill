"""
Utilities for normalizing DOCX documents using the Docling Forge interpreter stack.

The main entry point is :func:`normalize_docx`, which reads a DOCX file, analyses it
using the existing layout pipeline and rewrites document content with consistent
styling and indentation data.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import shutil
import zipfile
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

from .engine.geometry import Margins, Size, twips_to_points
from .engine.layout_pipeline import LayoutPipeline
from .engine.layout_primitives import BlockContent, ParagraphLayout
from .engine.page_engine import PageConfig
from .engine.unified_layout import LayoutBlock, UnifiedLayout
from .export.xml_exporter import XMLExporter
from .models.paragraph import Paragraph
from .models.run import Run
from .parser.package_reader import PackageReader
from .parser.xml_parser import XMLParser
from .parser.relationships_parser import RelationshipsParser


DEFAULT_PAGE_SIZE = Size(595.0, 842.0)  # A4 in points
DEFAULT_MARGINS = Margins(top=72.0, bottom=72.0, left=72.0, right=72.0)
TWIPS_PER_POINT = 20
W_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

def _w(tag: str) -> str:
    return f"{{{W_NAMESPACE}}}{tag}"


@dataclass
class _DocumentAdapter:
    """
    Lightweight adapter that exposes the attributes expected by the layout pipeline
    and XML exporter.
    """

    body: Any
    parser: XMLParser
    sections: List[dict[str, Any]]

    def __post_init__(self) -> None:
        self.elements = self.body.children if hasattr(self.body, "children") else []
        self._body = self.body
        self._sections = self.sections
        self._package_reader = self.parser.package_reader
        self._header_footer_parser = getattr(self.parser, "header_footer_parser", None)

    def get_body(self) -> Any:
        return self._body


class NumberingNormalizer:
    """
    Collects numbering usage inside a document and rebuilds a sanitized numbering.xml.
    """

    def __init__(self, numbering_parser: Any, original_xml: Optional[str]) -> None:
        self._parser = numbering_parser
        self._original_xml = original_xml
        self._abstract_counter = 1
        self._num_counter = 1
        self._abstracts: Dict[str, Dict[str, Any]] = {}
        self._abstract_order: List[str] = []
        self._num_map: Dict[str, Tuple[str, str]] = {}
        self._used = False

    def register_paragraph(self, paragraph: Paragraph) -> Optional[Dict[str, Any]]:
        info = getattr(paragraph, "numbering", None)

        style_numbering = None
        if isinstance(paragraph.style, dict):
            style_numbering = paragraph.style.get("numbering")
            if isinstance(style_numbering, dict) and not info:
                info = dict(style_numbering)
                paragraph.numbering = info

        if not isinstance(info, dict):
            return None

        num_id_original = str(info.get("id") or "")
        if not num_id_original:
            return None

        level = str(info.get("level") or "0")
        mapping = self._num_map.get(num_id_original)

        if mapping is None:
            definition = self._parser.get_numbering_definition(num_id_original)
            if not definition:
                return None

            abstract_id = str(self._abstract_counter)
            self._abstract_counter += 1

            sanitized_levels: Dict[str, Dict[str, Any]] = {}
            for level_key, level_data in definition.get("levels", {}).items():
                sanitized_levels[str(level_key)] = self._sanitize_level(level_data)
            
            # Store original abstract_id -> level -> indent_metrics mapping for later updates
            # This will be updated when we process paragraphs with calculated indents
            self._abstracts[abstract_id] = {"levels": sanitized_levels, "original_num_id": num_id_original}
            self._abstract_order.append(abstract_id)

            new_num_id = str(self._num_counter)
            self._num_counter += 1
            mapping = (new_num_id, abstract_id)
            self._num_map[num_id_original] = mapping

        new_num_id, abstract_id = mapping
        info["id"] = new_num_id
        info["level"] = level

        paragraph.numbering = {"id": new_num_id, "level": level}

        if not isinstance(paragraph.style, dict):
            paragraph.style = {}
        numbering_style = paragraph.style.get("numbering")
        if not isinstance(numbering_style, dict):
            numbering_style = {}
        numbering_style["id"] = new_num_id
        numbering_style["level"] = level
        paragraph.style["numbering"] = numbering_style

        self._used = True
        return self._abstracts[abstract_id]["levels"].get(level)

    def _sanitize_level(self, level_data: Dict[str, Any]) -> Dict[str, Any]:
        level_index = str(level_data.get("level", "0"))
        indent_left = _coerce_twips(level_data.get("indent_left"))
        indent_right = _coerce_twips(level_data.get("indent_right"))
        indent_first_line = _coerce_twips(level_data.get("indent_first_line"))
        indent_hanging = _coerce_twips(level_data.get("indent_hanging"))

        sanitized = {
            "level": level_index,
            "format": level_data.get("format") or "decimal",
            "text": level_data.get("text") or f"%{int(level_index) + 1}.",
            "start": level_data.get("start") or "1",
            "suffix": level_data.get("suffix") or "tab",
            "alignment": level_data.get("alignment") or "left",
            "indent_left": indent_left,
            "indent_right": indent_right,
            "indent_first_line": indent_first_line,
            "indent_hanging": indent_hanging,
            "tabs": level_data.get("tabs") or [],
            "font": level_data.get("font") or {},
        }

        if sanitized["indent_hanging"]:
            sanitized["indent_first_line"] = None

        return sanitized

    def has_custom_numbering(self) -> bool:
        return self._used

    def to_xml(self) -> Optional[str]:
        if not self._used:
            return self._original_xml

        root = ET.Element(_w("numbering"))

        for abstract_id in self._abstract_order:
            data = self._abstracts[abstract_id]
            abstract_el = ET.SubElement(root, _w("abstractNum"), {_w("abstractNumId"): abstract_id})
            ET.SubElement(abstract_el, _w("multiLevelType"), {_w("val"): "hybridMultilevel"})

            for level_key in sorted(data["levels"].keys(), key=lambda value: int(value)):
                level = data["levels"][level_key]
                lvl_el = ET.SubElement(abstract_el, _w("lvl"), {_w("ilvl"): level_key})

                ET.SubElement(lvl_el, _w("start"), {_w("val"): level.get("start", "1")})
                ET.SubElement(lvl_el, _w("numFmt"), {_w("val"): level["format"]})
                ET.SubElement(lvl_el, _w("lvlText"), {_w("val"): level["text"]})
                ET.SubElement(lvl_el, _w("suff"), {_w("val"): level.get("suffix", "tab")})
                ET.SubElement(lvl_el, _w("lvlJc"), {_w("val"): level.get("alignment", "left")})

                p_pr = ET.SubElement(lvl_el, _w("pPr"))
                ind_attrs: Dict[str, str] = {}
                left_val = level.get("indent_left")
                if left_val not in (None, 0):
                    ind_attrs[_w("left")] = str(left_val)
                right_val = level.get("indent_right")
                if right_val not in (None, 0):
                    ind_attrs[_w("right")] = str(right_val)
                hanging_val = level.get("indent_hanging")
                first_val = level.get("indent_first_line")
                if hanging_val not in (None, 0):
                    ind_attrs[_w("hanging")] = str(hanging_val)
                elif first_val not in (None, 0):
                    ind_attrs[_w("firstLine")] = str(first_val)

                if ind_attrs:
                    ET.SubElement(p_pr, _w("ind"), ind_attrs)

                tabs = level.get("tabs") or []
                if tabs:
                    tabs_el = ET.SubElement(p_pr, _w("tabs"))
                    for tab in tabs:
                        attrs: Dict[str, str] = {}
                        if tab.get("val"):
                            attrs[_w("val")] = str(tab["val"])
                        if tab.get("pos"):
                            attrs[_w("pos")] = str(tab["pos"])
                        if tab.get("leader"):
                            attrs[_w("leader")] = str(tab["leader"])
                        if attrs:
                            ET.SubElement(tabs_el, _w("tab"), attrs)

                font = level.get("font") or {}
                if font:
                    r_pr = ET.SubElement(lvl_el, _w("rPr"))
                    name = font.get("name")
                    if name:
                        ET.SubElement(r_pr, _w("rFonts"), {_w("ascii"): name, _w("hAnsi"): name})
                    size = font.get("size")
                    if size:
                        ET.SubElement(r_pr, _w("sz"), {_w("val"): str(size)})
                        ET.SubElement(r_pr, _w("szCs"), {_w("val"): str(size)})
                    if font.get("bold"):
                        ET.SubElement(r_pr, _w("b"))
                    if font.get("italic"):
                        ET.SubElement(r_pr, _w("i"))

        for original_id, (new_id, abstract_id) in self._num_map.items():
            num_el = ET.SubElement(root, _w("num"), {_w("numId"): new_id})
            ET.SubElement(num_el, _w("abstractNumId"), {_w("val"): abstract_id})

        # Generate XML with proper declaration matching original DOCX format
        xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=False, method='xml')
        xml_str = xml_bytes.decode("utf-8")
        # Add XML declaration matching original DOCX format: UTF-8 uppercase, standalone="yes"
        return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + xml_str


class StyleNormalizer:
    """
    Collects formatting signatures from paragraphs and runs, groups them,
    and creates styles for each unique signature.
    """

    def __init__(self, original_styles_xml: Optional[str]) -> None:
        self._original_xml = original_styles_xml
        self._para_signatures: Dict[Tuple, List[Paragraph]] = {}
        self._run_signatures: Dict[Tuple, List[Run]] = {}
        self._para_style_map: Dict[str, str] = {}  # paragraph.id -> style_id
        self._run_style_map: Dict[str, str] = {}  # run.id -> style_id
        self._style_counter = 1
        self._used = False

    def register_paragraph(self, paragraph: Paragraph, numbering_normalizer: Optional[Any] = None) -> None:
        """Register paragraph and extract its formatting signature."""
        sig = self._extract_paragraph_signature(paragraph, numbering_normalizer)
        if sig not in self._para_signatures:
            self._para_signatures[sig] = []
        self._para_signatures[sig].append(paragraph)
        self._used = True

    def register_run(self, run: Run) -> None:
        """Register run and extract its formatting signature."""
        sig = self._extract_run_signature(run)
        if sig not in self._run_signatures:
            self._run_signatures[sig] = []
        self._run_signatures[sig].append(run)
        self._used = True

    def _extract_paragraph_signature(self, paragraph: Paragraph, numbering_normalizer: Optional[Any] = None) -> Tuple:
        """Extract formatting signature from paragraph (ignoring style_name for grouping).
        
        For numbered paragraphs: groups by marker format and level (ignoring indent differences).
        For non-numbered paragraphs: groups by all formatting including indent.
        """
        style = paragraph.style if isinstance(paragraph.style, dict) else {}
        
        spacing = style.get("spacing", {})
        if not isinstance(spacing, dict):
            spacing = {}
        
        indent = style.get("indent", {})
        if not isinstance(indent, dict):
            indent = {}
        
        # Check if paragraph has numbering
        numbering_info = style.get("numbering") or paragraph.numbering
        has_numbering = isinstance(numbering_info, dict) and numbering_info.get("id")
        
        # Get numbering format (marker type) if available
        numbering_format = None
        numbering_level = None
        if has_numbering and numbering_normalizer:
            num_id = numbering_info.get("id")
            level = str(numbering_info.get("level") or "0")
            # Try to get format from numbering definition
            try:
                definition = numbering_normalizer._parser.get_numbering_definition(num_id) if hasattr(numbering_normalizer, '_parser') else None
                if definition:
                    level_data = definition.get("levels", {}).get(level)
                    if level_data:
                        numbering_format = level_data.get("format") or "decimal"
                        numbering_level = level
            except Exception:
                pass
        
        # Convert borders to hashable format
        borders = style.get("borders", {})
        borders_sig = None
        if isinstance(borders, dict) and borders:
            borders_sig = tuple(sorted((k, str(v) if isinstance(v, dict) else v) for k, v in borders.items()))
        
        # Convert tabs to hashable format
        tabs = style.get("tabs", [])
        tabs_sig = None
        if isinstance(tabs, list) and tabs:
            tabs_sig = tuple(sorted(str(tab) if isinstance(tab, dict) else tab for tab in tabs))
        
        # For numbered paragraphs: group by format and level, ignore indent differences
        # Indents will be set globally from numbering level definition
        if has_numbering and numbering_format:
            return (
                style.get("justification"),
                spacing.get("before"),
                spacing.get("after"),
                spacing.get("line"),
                spacing.get("lineRule"),
                None,  # Ignore indent.left for numbering
                None,  # Ignore indent.right for numbering
                None,  # Ignore indent.first_line for numbering
                None,  # Ignore indent.hanging for numbering
                numbering_format,  # Use format instead of id
                numbering_level,   # Use level
                borders_sig,
                str(style.get("shading")) if style.get("shading") else None,
                tabs_sig,
            )
        
        # For non-numbered paragraphs: group by all formatting including indent
        return (
            style.get("justification"),
            spacing.get("before"),
            spacing.get("after"),
            spacing.get("line"),
            spacing.get("lineRule"),
            indent.get("left"),
            indent.get("right"),
            indent.get("first_line"),
            indent.get("hanging"),
            None,  # No numbering
            None,  # No numbering level
            borders_sig,
            str(style.get("shading")) if style.get("shading") else None,
            tabs_sig,
        )

    def _extract_run_signature(self, run: Run) -> Tuple:
        """Extract formatting signature from run."""
        style = run.style if isinstance(run.style, dict) else {}
        return (
            style.get("font_name"),
            style.get("font_size"),
            style.get("bold"),
            style.get("italic"),
            style.get("underline"),
            style.get("color"),
            style.get("highlight"),
            style.get("strike_through"),
            style.get("superscript"),
            style.get("subscript"),
        )

    def apply_styles(self, numbering_normalizer: Optional[Any] = None, list_tree_builder: Optional[Any] = None) -> None:
        """Assign style IDs to paragraphs and runs based on their signatures.
        
        For numbered paragraphs: groups by format and level, then applies shared indents
        from numbering level definition to all paragraphs with same level (regardless of marker).
        """
        # First, collect indent sources by (format, level) from numbering definitions
        # This ensures all paragraphs with same format and level share the same indents
        indent_sources_by_format_level: Dict[Tuple[str, str], Dict[str, Any]] = {}  # (format, level) -> indent dict
        format_level_counts: Dict[Tuple[str, str], int] = {}  # Track usage count to pick most common
        
        if numbering_normalizer:
            # Collect indents from normalized numbering level definitions
            # Use _abstracts which already contain normalized indents from layout engine
            # These indents are updated in _normalize_paragraphs with calculated values from layout engine
            # 
            # Similar to ListTreeBuilder.marker_indent_registry, we group by (format, level)
            # and use the indent from layout engine calculations (which already account for tree context)
            for abstract_id, abstract_data in getattr(numbering_normalizer, '_abstracts', {}).items():
                levels = abstract_data.get("levels", {})
                for level_key, level_data in levels.items():
                    format_val = level_data.get("format") or "decimal"
                    key = (format_val, level_key)
                    
                    # Count how many times this (format, level) combination appears
                    format_level_counts[key] = format_level_counts.get(key, 0) + 1
                    
                    # Similar to ListTreeBuilder: use baseline indent for same (format, level)
                    # If multiple abstracts have same format/level, prefer the one with calculated indents
                    # (indents from layout engine are already normalized and account for tree hierarchy)
                    if key not in indent_sources_by_format_level:
                        indent_sources_by_format_level[key] = {
                            "left": level_data.get("indent_left"),
                            "right": level_data.get("indent_right"),
                            "first_line": level_data.get("indent_first_line"),
                            "hanging": level_data.get("indent_hanging"),
                        }
                    else:
                        # Like ListTreeBuilder.marker_indent_registry: if new indent is smaller, update baseline
                        # This ensures all paragraphs with same format+level share the same (minimum) indent
                        existing_left = indent_sources_by_format_level[key].get("left") or 0
                        new_left = level_data.get("indent_left") or 0
                        # Use the smaller indent (like ListTreeBuilder does with baseline)
                        if new_left + 1e-3 < existing_left:
                            indent_sources_by_format_level[key] = {
                                "left": level_data.get("indent_left"),
                                "right": level_data.get("indent_right"),
                                "first_line": level_data.get("indent_first_line"),
                                "hanging": level_data.get("indent_hanging"),
                            }
            
            # For each (format, level), find the most common indent by checking which abstract is used most
            # Collect abstracts by (format, level) and their usage
            abstracts_by_format_level: Dict[Tuple[str, str], List[Tuple[str, Dict[str, Any]]]] = {}
            for abstract_id, abstract_data in getattr(numbering_normalizer, '_abstracts', {}).items():
                levels = abstract_data.get("levels", {})
                for level_key, level_data in levels.items():
                    format_val = level_data.get("format") or "decimal"
                    key = (format_val, level_key)
                    if key not in abstracts_by_format_level:
                        abstracts_by_format_level[key] = []
                    abstracts_by_format_level[key].append((abstract_id, level_data))
            
            # For each (format, level), pick the indent from the most commonly used abstract
            # Count usage by checking which num_id map to which abstract
            abstract_usage_count: Dict[str, int] = {}
            for num_id_orig, (new_num_id, abstract_id) in getattr(numbering_normalizer, '_num_map', {}).items():
                abstract_usage_count[abstract_id] = abstract_usage_count.get(abstract_id, 0) + 1
            
            # Update indent_sources_by_format_level to use most common abstract
            # For (format, level) combinations with multiple abstracts, pick the one with most usage
            # This ensures all paragraphs with same format+level share the same indents
            for (format_val, level_key), abstracts_list in abstracts_by_format_level.items():
                if len(abstracts_list) > 1:
                    # Multiple abstracts with same format/level - pick the most used one
                    # If tied, prefer the one with calculated indents (typically larger/more accurate)
                    most_used_abstract = max(abstracts_list, key=lambda x: (
                        abstract_usage_count.get(x[0], 0),  # Primary: usage count
                        x[1].get("indent_left", 0) or 0  # Secondary: prefer larger indent (from layout engine)
                    ))
                    abstract_id, level_data = most_used_abstract
                    indent_sources_by_format_level[(format_val, level_key)] = {
                        "left": level_data.get("indent_left"),
                        "right": level_data.get("indent_right"),
                        "first_line": level_data.get("indent_first_line"),
                        "hanging": level_data.get("indent_hanging"),
                    }
                    logger.debug(f"Selected indent for ({format_val}, {level_key}) from abstract_id={abstract_id}: left={level_data.get('indent_left')}")
        
        # Also create level-only mapping for backward compatibility
        indent_sources_by_level: Dict[str, Dict[str, Any]] = {}
        for (format_val, level_key), indents in indent_sources_by_format_level.items():
            # Use the most common format for each level, or first encountered
            if level_key not in indent_sources_by_level:
                indent_sources_by_level[level_key] = indents
            elif format_level_counts.get((format_val, level_key), 0) > format_level_counts.get((indent_sources_by_level[level_key].get("_format"), level_key), 0):
                indent_sources_by_level[level_key] = indents
        
        # Debug: Log numbered paragraph groups
        numbered_groups: Dict[Tuple[str, str], List[Paragraph]] = {}  # (format, level) -> paragraphs
        
        # Assign paragraph styles
        for sig, paragraphs in self._para_signatures.items():
            if len(paragraphs) < 2:
                continue  # Only create styles for groups with 2+ paragraphs
            
            # Check if this is a numbered paragraph group
            is_numbered = len(sig) > 10 and sig[9] is not None  # numbering_format is not None
            numbering_format = sig[9] if len(sig) > 9 else None
            numbering_level = str(sig[10]) if len(sig) > 10 and sig[10] is not None else None
            
            if is_numbered and numbering_format and numbering_level:
                key = (numbering_format, numbering_level)
                if key not in numbered_groups:
                    numbered_groups[key] = []
                numbered_groups[key].extend(paragraphs)
            
            style_id = f"ParaStyle{self._style_counter}"
            self._style_counter += 1
            
            for para in paragraphs:
                self._para_style_map[para.id] = style_id
                if not isinstance(para.style, dict):
                    para.style = {}
                para.style["style_name"] = style_id
                
                # For numbered paragraphs, ALWAYS use ListTreeBuilder's resolved indent if available
                # This handles all edge cases already solved in the tree builder, including different
                # indents for same format+level but different contexts (scope_id, parent hierarchy)
                if is_numbered and numbering_format and numbering_level:
                    # Use the indent already calculated by ListTreeBuilder during processing
                    # This indent already accounts for tree hierarchy, marker matching, and all edge cases
                    # Different paragraphs with same format+level may have different indents based on context
                    if hasattr(para, '_list_tree_indent'):
                        resolved_indent = para._list_tree_indent
                        # Convert IndentSpec to dict and apply
                        if "indent" not in para.style:
                            para.style["indent"] = {}
                        para.style["indent"]["left"] = _twips_from_points(resolved_indent.left)
                        para.style["indent"]["right"] = _twips_from_points(resolved_indent.right)
                        if resolved_indent.hanging:
                            para.style["indent"]["hanging"] = _twips_from_points(resolved_indent.hanging)
                            para.style["indent"]["first_line"] = None
                        elif resolved_indent.first_line:
                            para.style["indent"]["first_line"] = _twips_from_points(resolved_indent.first_line)
                            para.style["indent"]["hanging"] = None
                        # Skip the fallback indent logic below - we've already applied the correct indent
                        continue
                    else:
                        # Debug: log if _list_tree_indent is missing for numbered paragraph
                        if numbering_level == "1":  # Only log for level 1 to reduce noise
                            logger.debug(f"Paragraph level 1 missing _list_tree_indent: para.id={para.id}, format={numbering_format}, level={numbering_level}")
                    
                    # Fallback: try to find indent from marker_indent_registry using marker_token
                    if list_tree_builder:
                        # Get marker_token from numbering definition
                        numbering_info = para.style.get("numbering") or para.numbering
                        marker_token = None
                        if numbering_info:
                            num_id = str(numbering_info.get("id", ""))
                            definition = numbering_normalizer._parser.get_numbering_definition(num_id) if numbering_normalizer and hasattr(numbering_normalizer, '_parser') else None
                            if definition:
                                level_data = definition.get("levels", {}).get(numbering_level)
                                if level_data:
                                    marker_text = level_data.get("text", "") or ""
                                    # Normalize marker token like ListTreeBuilder does
                                    import re
                                    cleaned = re.sub(r"%(\d+)", r"\1", marker_text or "").strip()
                                    if cleaned:
                                        token = []
                                        for ch in cleaned:
                                            if ch.isspace():
                                                break
                                            token.append(ch)
                                        marker_token = "".join(token).strip().rstrip(").,:;")
                        
                        # Try to find indent from marker_indent_registry
                        if marker_token:
                            # ListTreeBuilder uses (marker_token, level, scope_id) as key
                            # Try with scope_id=None first (root level)
                            marker_key = (marker_token, int(numbering_level), None)
                            baseline_indent = list_tree_builder.marker_indent_registry.get(marker_key)
                            
                            if baseline_indent:
                                # Convert IndentSpec to dict and apply
                                if "indent" not in para.style:
                                    para.style["indent"] = {}
                                para.style["indent"]["left"] = _twips_from_points(baseline_indent.left)
                                para.style["indent"]["right"] = _twips_from_points(baseline_indent.right)
                                if baseline_indent.hanging:
                                    para.style["indent"]["hanging"] = _twips_from_points(baseline_indent.hanging)
                                    para.style["indent"]["first_line"] = None
                                elif baseline_indent.first_line:
                                    para.style["indent"]["first_line"] = _twips_from_points(baseline_indent.first_line)
                                    para.style["indent"]["hanging"] = None
                                continue
                    
                    # Final fallback: use format+level mapping
                    format_level_key = (numbering_format, numbering_level)
                    if format_level_key in indent_sources_by_format_level:
                        shared_indents = indent_sources_by_format_level[format_level_key]
                        if "indent" not in para.style:
                            para.style["indent"] = {}
                        # Update with shared indents (only non-None values)
                        for key, value in shared_indents.items():
                            if value is not None:
                                para.style["indent"][key] = value
                    elif numbering_level in indent_sources_by_level:
                        # Fallback to level-only mapping
                        shared_indents = indent_sources_by_level[numbering_level]
                        if "indent" not in para.style:
                            para.style["indent"] = {}
                        for key, value in shared_indents.items():
                            if value is not None and key != "_format":
                                para.style["indent"][key] = value
        
        # Debug: Log numbered groups
        if numbered_groups:
            logger.info("=== Numbered paragraph groups ===")
            for (format, level), paras in sorted(numbered_groups.items()):
                # Get sample text from first few paragraphs
                sample_texts = []
                for para in paras[:3]:
                    text = getattr(para, 'text', '') or ''.join(getattr(run, 'text', '') for run in getattr(para, 'runs', []))
                    if text:
                        sample_texts.append(text[:50])
                
                logger.info(f"Format: {format}, Level: {level}, Count: {len(paras)}")
                logger.info(f"  Sample texts: {sample_texts}")
                format_level_key = (format, level)
                if format_level_key in indent_sources_by_format_level:
                    indents = indent_sources_by_format_level[format_level_key]
                    logger.info(f"  Shared indents (from format+level): {indents}")
                elif level in indent_sources_by_level:
                    indents = indent_sources_by_level[level]
                    logger.info(f"  Shared indents (from level only): {indents}")
                logger.info("")
        
        # Assign run styles
        for sig, runs in self._run_signatures.items():
            if len(runs) < 2:
                continue  # Only create styles for groups with 2+ runs
            
            style_id = f"CharStyle{self._style_counter}"
            self._style_counter += 1
            
            for run in runs:
                self._run_style_map[run.id] = style_id
                if not isinstance(run.style, dict):
                    run.style = {}
                run.style["style_name"] = style_id

    def has_custom_styles(self) -> bool:
        return self._used and (len(self._para_signatures) > 0 or len(self._run_signatures) > 0)

    def to_xml(self, used_style_ids: Optional[set[str]] = None) -> Optional[str]:
        if not self.has_custom_styles():
            return self._original_xml

        # Parse original styles to preserve base styles (Normal, DefaultParagraphFont, etc.)
        root = ET.Element(_w("styles"))
        
        # If used_style_ids is None, copy all styles from original...
        if used_style_ids is None:
            keep_styles = None  # None oznacza "kopiuj wszystkie"
        else:
            used_styles = used_style_ids or set()
            base_styles = {"Normal", "DefaultParagraphFont", "Heading1", "Heading2", "Heading3", "ListParagraph"}
            keep_styles = used_styles | base_styles
        
        if self._original_xml:
            try:
                original_root = ET.fromstring(self._original_xml)
                # Copy docDefaults from original
                doc_defaults_orig = original_root.find(f".//{_w('docDefaults')}")
                if doc_defaults_orig is not None:
                    root.append(doc_defaults_orig)
                # Copy base styles and used styles only (or all if keep_styles...)
                for style_el in original_root.findall(f".//{_w('style')}"):
                    if keep_styles is None:
                        # Kopiuj wszystkie style
                        root.append(style_el)
                    else:
                        style_id = style_el.get(_w("styleId")) or style_el.get("styleId", "")
                        if style_id in keep_styles:
                            root.append(style_el)
            except Exception:
                # If parsing fails, add minimal defaults
                doc_defaults = ET.SubElement(root, _w("docDefaults"))
                r_pr_default = ET.SubElement(doc_defaults, _w("rPrDefault"))
                r_pr = ET.SubElement(r_pr_default, _w("rPr"))
                ET.SubElement(r_pr, _w("rFonts"), {
                    _w("ascii"): "Calibri",
                    _w("hAnsi"): "Calibri",
                })
                ET.SubElement(r_pr, _w("sz"), {_w("val"): "22"})
                ET.SubElement(r_pr, _w("szCs"), {_w("val"): "22"})
        else:
            # Add minimal defaults if no original XML
            doc_defaults = ET.SubElement(root, _w("docDefaults"))
            r_pr_default = ET.SubElement(doc_defaults, _w("rPrDefault"))
            r_pr = ET.SubElement(r_pr_default, _w("rPr"))
            ET.SubElement(r_pr, _w("rFonts"), {
                _w("ascii"): "Calibri",
                _w("hAnsi"): "Calibri",
            })
            ET.SubElement(r_pr, _w("sz"), {_w("val"): "22"})
            ET.SubElement(r_pr, _w("szCs"), {_w("val"): "22"})

        # Add paragraph styles
        for sig, paragraphs in self._para_signatures.items():
            if len(paragraphs) < 2:
                continue
            
            style_id = self._para_style_map.get(paragraphs[0].id)
            if not style_id:
                continue

            style_el = ET.SubElement(root, _w("style"), {
                _w("type"): "paragraph",
                _w("styleId"): style_id,
            })
            ET.SubElement(style_el, _w("name"), {_w("val"): style_id})
            
            # Based on Normal style
            ET.SubElement(style_el, _w("basedOn"), {_w("val"): "Normal"})
            
            p_pr = ET.SubElement(style_el, _w("pPr"))
            self._add_paragraph_properties_to_xml(p_pr, paragraphs[0])

        # Add character (run) styles
        for sig, runs in self._run_signatures.items():
            if len(runs) < 2:
                continue
            
            style_id = self._run_style_map.get(runs[0].id)
            if not style_id:
                continue

            style_el = ET.SubElement(root, _w("style"), {
                _w("type"): "character",
                _w("styleId"): style_id,
            })
            ET.SubElement(style_el, _w("name"), {_w("val"): style_id})
            
            # Based on Default Paragraph Font
            ET.SubElement(style_el, _w("basedOn"), {_w("val"): "DefaultParagraphFont"})
            
            r_pr = ET.SubElement(style_el, _w("rPr"))
            self._add_run_properties_to_xml(r_pr, runs[0])

        # Generate XML with proper declaration matching original DOCX format
        xml_bytes = ET.tostring(root, encoding="utf-8", xml_declaration=False, method='xml')
        xml_str = xml_bytes.decode("utf-8")
        # Add XML declaration matching original DOCX format: UTF-8 uppercase, standalone="yes"
        return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + xml_str

    def _add_paragraph_properties_to_xml(self, p_pr: ET.Element, paragraph: Paragraph) -> None:
        """Add paragraph properties to XML element."""
        style = paragraph.style if isinstance(paragraph.style, dict) else {}
        
        # Alignment
        alignment = style.get("justification")
        if alignment:
            ET.SubElement(p_pr, _w("jc"), {_w("val"): str(alignment)})
        
        # Spacing
        spacing = style.get("spacing", {})
        if isinstance(spacing, dict) and any(spacing.values()):
            spacing_el = ET.SubElement(p_pr, _w("spacing"))
            if spacing.get("before"):
                spacing_el.set(_w("before"), str(spacing["before"]))
            if spacing.get("after"):
                spacing_el.set(_w("after"), str(spacing["after"]))
            if spacing.get("line"):
                spacing_el.set(_w("line"), str(spacing["line"]))
            if spacing.get("lineRule"):
                spacing_el.set(_w("lineRule"), str(spacing["lineRule"]))
        
        # Indentation
        indent = style.get("indent", {})
        if isinstance(indent, dict) and any(indent.values()):
            ind_el = ET.SubElement(p_pr, _w("ind"))
            if indent.get("left"):
                ind_el.set(_w("left"), str(indent["left"]))
            if indent.get("right"):
                ind_el.set(_w("right"), str(indent["right"]))
            if indent.get("hanging"):
                ind_el.set(_w("hanging"), str(indent["hanging"]))
            elif indent.get("first_line"):
                ind_el.set(_w("firstLine"), str(indent["first_line"]))
        
        # Numbering
        numbering = style.get("numbering")
        if isinstance(numbering, dict) and numbering.get("id"):
            num_pr = ET.SubElement(p_pr, _w("numPr"))
            ET.SubElement(num_pr, _w("ilvl"), {_w("val"): str(numbering.get("level", "0"))})
            ET.SubElement(num_pr, _w("numId"), {_w("val"): str(numbering["id"])})

    def _add_run_properties_to_xml(self, r_pr: ET.Element, run: Run) -> None:
        """Add run properties to XML element."""
        style = run.style if isinstance(run.style, dict) else {}
        
        # Font
        font_name = style.get("font_name")
        if font_name:
            ET.SubElement(r_pr, _w("rFonts"), {
                _w("ascii"): font_name,
                _w("hAnsi"): font_name,
            })
        
        # Font size
        font_size = style.get("font_size")
        if font_size:
            ET.SubElement(r_pr, _w("sz"), {_w("val"): str(int(float(font_size)) * 2)})
            ET.SubElement(r_pr, _w("szCs"), {_w("val"): str(int(float(font_size)) * 2)})
        
        # Bold
        if style.get("bold"):
            ET.SubElement(r_pr, _w("b"))
        
        # Italic
        if style.get("italic"):
            ET.SubElement(r_pr, _w("i"))
        
        # Underline
        underline = style.get("underline")
        if underline:
            ET.SubElement(r_pr, _w("u"), {_w("val"): str(underline)})
        
        # Color
        color = style.get("color")
        if color:
            ET.SubElement(r_pr, _w("color"), {_w("val"): str(color).replace("#", "")})
        
        # Highlight
        highlight = style.get("highlight")
        if highlight:
            ET.SubElement(r_pr, _w("highlight"), {_w("val"): str(highlight)})


class StyleCleaner:
    """Removes unused styles and merges identical styles."""
    
    def __init__(self, style_normalizer: StyleNormalizer):
        self._style_normalizer = style_normalizer
        self._used_style_ids: set[str] = set()
    
    def register_used_style(self, style_id: str) -> None:
        """Register a style ID that is used in the document."""
        if style_id:
            self._used_style_ids.add(style_id)
    
    def get_unused_styles(self, styles_xml: Optional[str]) -> set[str]:
        """Get set of unused style IDs."""
        if not styles_xml:
            return set()
        
        try:
            root = ET.fromstring(styles_xml)
            all_style_ids = set()
            for style_el in root.findall(f".//{_w('style')}"):
                style_id = style_el.get(_w("styleId")) or style_el.get("styleId", "")
                if style_id:
                    all_style_ids.add(style_id)
            
            # Always keep base styles
            base_styles = {"Normal", "DefaultParagraphFont", "Heading1", "Heading2", "Heading3", "ListParagraph"}
            return all_style_ids - self._used_style_ids - base_styles
        except Exception:
            return set()


class LocalOverrideRemover:
    """Removes local style overrides that are already defined in the style."""
    
    def __init__(self, style_normalizer: StyleNormalizer):
        self._style_normalizer = style_normalizer
        self._style_definitions: Dict[str, Dict[str, Any]] = {}
    
    def register_style_definition(self, style_id: str, properties: Dict[str, Any]) -> None:
        """Register style definition for comparison."""
        self._style_definitions[style_id] = properties
    
    def remove_overrides(self, paragraph: Paragraph) -> None:
        """Remove local overrides from paragraph if it has a style."""
        if not isinstance(paragraph.style, dict):
            return
        
        style_name = paragraph.style.get("style_name")
        if not style_name or style_name not in self._style_definitions:
            return
        
        style_def = self._style_definitions[style_name]
        local_style = dict(paragraph.style)
        
        # Remove properties that match the style definition (deep comparison)
        # BUT: preserve "indent" if it was set by ListTreeBuilder (even if it matches style_def)
        # ListTreeBuilder indents are context-aware and should not be removed
        for key in list(local_style.keys()):
            if key == "style_name":
                continue
            # Skip "indent" - it will be handled separately below
            if key == "indent":
                continue
            if key in style_def:
                if self._values_equal(local_style[key], style_def[key]):
                    del local_style[key]
        
        # Remove inline indentation formatting - indents should come from styles only
        # This ensures consistency and prevents conflicts between style and inline formatting
        # BUT: ALWAYS preserve indents that were set by ListTreeBuilder (stored in para.style["indent"])
        # These indents are already normalized and account for tree hierarchy, and are context-aware
        # Even if style_def has indent, ListTreeBuilder indents take precedence as they account for tree context
        indent_keys = ['indent', 'left_indent', 'right_indent', 'first_line_indent', 'hanging_indent']
        
        # Check if paragraph has ListTreeBuilder indent - if so, ALWAYS preserve it
        # ListTreeBuilder indent is stored in para.style["indent"] and was set by apply_styles
        # We check if indent exists and has values (not empty dict)
        indent_dict = local_style.get("indent", {})
        has_list_tree_indent = isinstance(indent_dict, dict) and any(
            indent_dict.get(key) is not None and indent_dict.get(key) != 0
            for key in ['left', 'right', 'hanging', 'first_line']
        )
        
        if not has_list_tree_indent:
            # Only remove indent keys if ListTreeBuilder indent is not available
            style_has_indent = 'indent' in style_def or any(key in style_def for key in indent_keys)
            if style_has_indent:
                # Remove indent keys from local style
                for indent_key in indent_keys:
                    if indent_key in local_style:
                        del local_style[indent_key]
                
                # Also clear direct paragraph indent properties
                paragraph.left_indent = None
                paragraph.right_indent = None
                paragraph.first_line_indent = None
                paragraph.hanging_indent = None
        # else: keep para.style["indent"] that was set by apply_styles from _list_tree_indent
        
        paragraph.style = local_style
    
    @staticmethod
    def _values_equal(val1: Any, val2: Any) -> bool:
        """Deep comparison of values."""
        if val1 == val2:
            return True
        
        # Compare dicts recursively
        if isinstance(val1, dict) and isinstance(val2, dict):
            if set(val1.keys()) != set(val2.keys()):
                return False
            return all(LocalOverrideRemover._values_equal(val1[k], val2[k]) for k in val1.keys())
        
        # Compare lists
        if isinstance(val1, list) and isinstance(val2, list):
            if len(val1) != len(val2):
                return False
            return all(LocalOverrideRemover._values_equal(v1, v2) for v1, v2 in zip(val1, val2))
        
        return False


class WhitespaceNormalizer:
    """Normalizes whitespace in runs - removes multiple spaces."""
    
    @staticmethod
    def normalize_run_text(run: Run) -> None:
        """Normalize whitespace in run text - remove multiple consecutive spaces."""
        if not hasattr(run, 'text') or not run.text:
            return
        
        import re
        # Replace multiple spaces (2+) with single space
        # Preserve single spaces and newlines
        normalized = re.sub(r' +', ' ', run.text)
        
        run.text = normalized


class SpacingNormalizer:
    """Normalizes spacing values according to Microsoft recommendations."""
    
    @staticmethod
    def normalize_spacing(spacing: Dict[str, Any], preserve_existing: bool = False) -> Dict[str, Any]:
        """Normalize spacing values.
        
        Args:
            spacing: Spacing dictionary to normalize
            preserve_existing: If True, only normalize if spacing already exists (don't add new)
        """
        if not isinstance(spacing, dict):
            return spacing
        
        normalized = {}
        
        # Normalize before/after spacing - round to nearest 6pt (120 twips)
        for key in ['before', 'after']:
            if key in spacing:
                value = spacing[key]
                try:
                    # Convert to twips if needed
                    if isinstance(value, str):
                        twips = int(value)
                    else:
                        twips = int(float(value))
                    
                    # Round to nearest 120 twips (6pt)
                    rounded = round(twips / 120) * 120
                    if rounded > 0:
                        normalized[key] = str(rounded)
                except (ValueError, TypeError):
                    normalized[key] = str(value)
        
        # Normalize line spacing
        if 'line' in spacing:
            normalized['line'] = str(spacing['line'])
        if 'lineRule' in spacing:
            normalized['lineRule'] = spacing['lineRule']
        
        return normalized


class ColorNormalizer:
    """Normalizes color values to standard format."""
    
    @staticmethod
    def normalize_color(color: Any) -> Optional[str]:
        """Normalize color to standard format (RRGGBB without #)."""
        if not color:
            return None
        
        color_str = str(color).strip()
        
        # Remove # if present
        if color_str.startswith('#'):
            color_str = color_str[1:]
        
        # Validate hex color (6 hex digits)
        if len(color_str) == 6 and all(c in '0123456789ABCDEFabcdef' for c in color_str):
            return color_str.upper()
        
        # Return as-is if not valid hex
        return color_str


class IndentNormalizer:
    """Validates and corrects indentation values."""
    
    @staticmethod
    def normalize_indent(indent: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize indent values - ensure hanging and firstLine are mutually exclusive."""
        if not isinstance(indent, dict):
            return indent
        
        normalized = dict(indent)
        
        # hanging and firstLine are mutually exclusive - prefer hanging
        if normalized.get('hanging') and normalized.get('first_line'):
            # Remove first_line if hanging exists
            del normalized['first_line']
        
        # Ensure values are strings
        for key in ['left', 'right', 'hanging', 'first_line']:
            if key in normalized:
                normalized[key] = str(normalized[key])
        
        return normalized


class FontNormalizer:
    """Normalizes font names and sizes."""
    
    @staticmethod
    def normalize_font_name(font_name: Any) -> Optional[str]:
        """Normalize font name - ensure consistent casing."""
        if not font_name:
            return None
        
        font_str = str(font_name).strip()
        if not font_str:
            return None
        
        # Capitalize first letter of each word (Title Case)
        # But preserve common patterns like "Times New Roman"
        words = font_str.split()
        normalized_words = []
        for word in words:
            if word.lower() in ['new', 'of', 'the'] and normalized_words:
                normalized_words.append(word.lower())
            else:
                normalized_words.append(word.capitalize())
        
        return ' '.join(normalized_words)
    
    @staticmethod
    def normalize_font_size(font_size: Any) -> Optional[str]:
        """Normalize font size - ensure it's in half-points (as Word expects)."""
        if not font_size:
            return None
        
        try:
            size_float = float(font_size)
            # Convert to half-points (Word format)
            half_points = int(size_float * 2)
            return str(half_points)
        except (ValueError, TypeError):
            return str(font_size)


class TabStopNormalizer:
    """Normalizes tab stop definitions."""
    
    @staticmethod
    def normalize_tabs(tabs: List[Any]) -> List[Dict[str, Any]]:
        """Normalize tab stops - ensure consistent format."""
        if not isinstance(tabs, list):
            return []
        
        normalized = []
        for tab in tabs:
            if isinstance(tab, dict):
                normalized_tab = {}
                # Ensure position is a string
                if 'pos' in tab:
                    normalized_tab['pos'] = str(tab['pos'])
                if 'val' in tab:
                    normalized_tab['val'] = str(tab['val'])
                if 'leader' in tab:
                    normalized_tab['leader'] = str(tab['leader'])
                normalized.append(normalized_tab)
        
        return normalized


def normalize_docx(
    input_path: Union[str, Path],
    *,
    output_path: Optional[Union[str, Path]] = None,
) -> Path:
    """
    Normalize a DOCX document in place.

    The routine performs the following steps:

    1. Parse the document into the semantic model.
    2. Run the layout pipeline to collect measured metrics (indents, spacing).
    3. Merge adjacent runs with identical formatting.
    4. Clean paragraph and run style dictionaries from stale/noisy values.
    5. Rewrite paragraph indentation metadata based on the layout metrics.
    6. Regenerate ``word/document.xml`` and produce a normalized DOCX package.

    Args:
        input_path: Path to the source DOCX file.
        output_path: Optional path for the normalized document. When omitted, a file
            with ``_normalized`` suffix will be created next to the original.

    Returns:
        Path to the normalized DOCX file.
    """

    source_path = Path(input_path).expanduser().resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"DOCX file not found: {source_path}")

    target_path = (
        Path(output_path).expanduser().resolve()
        if output_path
        else source_path.with_name(f"{source_path.stem}_normalized{source_path.suffix}")
    )

    package_reader = PackageReader(source_path)
    parser = XMLParser(package_reader)
    body = parser.parse_body()
    sections = parser.parse_sections()
    numbering_original_xml = package_reader.get_xml_content("word/numbering.xml")
    styles_original_xml = package_reader.get_xml_content("word/styles.xml")

    adapter = _DocumentAdapter(body=body, parser=parser, sections=sections)
    page_config = _build_page_config(sections)

    pipeline = LayoutPipeline(page_config, target="html")
    unified_layout = pipeline.process(adapter, apply_headers_footers=False, validate=False)

    paragraph_metrics = _collect_paragraph_metrics(unified_layout)
    
    # Collect calculated image positions from layout pipeline and header/footer files
    image_positions = _collect_image_positions(unified_layout, page_config, package_reader)

    numbering_normalizer = NumberingNormalizer(parser.numbering_parser, numbering_original_xml)
    style_normalizer = StyleNormalizer(styles_original_xml)
    
    # Use ListTreeBuilder to group numbered paragraphs and get shared indents
    # This handles all edge cases that are already solved in the tree builder
    from .engine.list_tree import ListTreeBuilder, ParagraphEntry, IndentSpec
    from .engine.geometry import twips_to_points
    
    # Get numbering data for ListTreeBuilder
    # NumberingParser stores data in abstract_numberings and numbering_instances attributes
    # We need to format it like ListTreeBuilder expects
    numbering_data = {
        "abstract_numberings": getattr(parser.numbering_parser, 'abstract_numberings', {}),
        "numbering_instances": getattr(parser.numbering_parser, 'numbering_instances', {}),
    }
    list_tree_builder = ListTreeBuilder(numbering_data)
    list_tree_builder.reset()
    
    # Build marker_indent_registry using ListTreeBuilder
    paragraphs_list = list(getattr(body, "get_paragraphs_recursive", lambda: [])())
    for paragraph in paragraphs_list:
        # Skip header/footer paragraphs
        is_header_footer = False
        if hasattr(paragraph, 'raw_xml') and paragraph.raw_xml:
            raw_lower = paragraph.raw_xml.lower()
            if 'header' in raw_lower or 'footer' in raw_lower or 'word/header' in raw_lower or 'word/footer' in raw_lower:
                is_header_footer = True
        if is_header_footer:
            continue
        
        # Get paragraph metrics
        para_id = getattr(paragraph, 'id', None) or getattr(paragraph, 'source_id', None) or f"para_{id(paragraph)}"
        metric = paragraph_metrics.get(str(para_id), {})
        indent_metrics = metric.get("indent_metrics") or {}
        
        # Create ParagraphEntry similar to layout_engine
        style = paragraph.style if isinstance(paragraph.style, dict) else {}
        numbering_info = style.get("numbering") or paragraph.numbering
        
        # Extract indents
        style_indent_dict = style.get("indent", {})
        paragraph_indent_dict = {
            "left": getattr(paragraph, 'left_indent', None),
            "right": getattr(paragraph, 'right_indent', None),
            "first_line": getattr(paragraph, 'first_line_indent', None),
            "hanging": getattr(paragraph, 'hanging_indent', None),
        }
        
        def _dict_to_indent_spec(indent_dict: Dict[str, Any]) -> IndentSpec:
            """Convert indent dict to IndentSpec."""
            if not isinstance(indent_dict, dict):
                return IndentSpec()
            return IndentSpec(
                left=twips_to_points(indent_dict.get("left") or 0),
                right=twips_to_points(indent_dict.get("right") or 0),
                first_line=twips_to_points(indent_dict.get("first_line") or 0),
                hanging=twips_to_points(indent_dict.get("hanging") or 0),
            )
        
        style_indent = _dict_to_indent_spec(style_indent_dict)
        paragraph_indent = _dict_to_indent_spec(paragraph_indent_dict)
        
        # Get numbering info
        num_id = None
        level = None
        if numbering_info and isinstance(numbering_info, dict):
            num_id = str(numbering_info.get("id", "")) if numbering_info.get("id") else None
            level = int(numbering_info.get("level", 0)) if numbering_info.get("level") is not None else None
        
        # Get marker text (we'll use format from numbering definition as fallback)
        marker_text = ""
        if num_id and level is not None:
            definition = parser.numbering_parser.get_numbering_definition(num_id)
            if definition:
                level_data = definition.get("levels", {}).get(str(level))
                if level_data:
                    marker_text = level_data.get("text", "") or ""
        
        # Create ParagraphEntry
        entry = ParagraphEntry(
            block_ref={"id": para_id, "paragraph": paragraph},
            style_name=style.get("style_name") or "",
            paragraph_indent=paragraph_indent,
            style_indent=style_indent,
            num_id=num_id,
            level=level,
            marker_text=marker_text,
            marker_visible=bool(num_id),
            style_is_list=bool(style.get("numbering")),
            marker_like_text=False,  # We'll detect this if needed
            has_border=bool(style.get("borders")),
            number_override=False,
            auto_correction=True,
            explicit_indent=False,
            inline_indent=None,
        )
        
        # Process paragraph through ListTreeBuilder to populate marker_indent_registry
        try:
            resolved_indent, text_start, number_start, effective_num_id, effective_level, meta = list_tree_builder.process_paragraph(entry)
            # Store the resolved indent for later use
            paragraph._list_tree_indent = resolved_indent
            paragraph._list_tree_meta = meta
        except Exception as e:
            logger.debug(f"Failed to process paragraph {para_id} through ListTreeBuilder: {e}")
    
    # First pass: collect formatting signatures
    # NOTE: This must be called AFTER ListTreeBuilder processing so that _list_tree_indent is available
    # Pass paragraphs_list to ensure we use the same paragraph objects
    _normalize_paragraphs(body, paragraph_metrics, numbering_normalizer, style_normalizer, paragraphs_list)
    
    # Apply style assignments (with numbering normalizer for indent sharing)
    # Now use marker_indent_registry from ListTreeBuilder instead of our own logic
    # _list_tree_indent should be available on all paragraphs that were processed above
    style_normalizer.apply_styles(numbering_normalizer, list_tree_builder)
    
    # Second pass: ensure style_name is preserved and apply normalizations
    paragraphs: Iterable[Paragraph] = getattr(body, "get_paragraphs_recursive", lambda: [])()
    
    # Initialize normalizers
    style_cleaner = StyleCleaner(style_normalizer)
    local_override_remover = LocalOverrideRemover(style_normalizer)
    
    # Collect used styles and build style definitions
    for paragraph in paragraphs:
        # Skip paragraphs from headers/footers
        is_header_footer = False
        if hasattr(paragraph, 'raw_xml') and paragraph.raw_xml:
            raw_lower = paragraph.raw_xml.lower()
            is_header_footer = (
                'header' in raw_lower or 
                'footer' in raw_lower or
                'word/header' in raw_lower or
                'word/footer' in raw_lower
            )
        if hasattr(paragraph, 'metadata') and isinstance(paragraph.metadata, dict):
            is_header_footer = is_header_footer or paragraph.metadata.get('is_header') or paragraph.metadata.get('is_footer')
        
        if is_header_footer:
            continue
        
        assigned_style = style_normalizer._para_style_map.get(paragraph.id)
        if assigned_style:
            if not isinstance(paragraph.style, dict):
                paragraph.style = {}
            paragraph.style["style_name"] = assigned_style
            style_cleaner.register_used_style(assigned_style)
        
        # Also register style_name if already present
        if isinstance(paragraph.style, dict):
            style_name = paragraph.style.get("style_name")
            if style_name:
                style_cleaner.register_used_style(style_name)
        
        for run in paragraph.runs:
            assigned_run_style = style_normalizer._run_style_map.get(run.id)
            if assigned_run_style:
                if not isinstance(run.style, dict):
                    run.style = {}
                run.style["style_name"] = assigned_run_style
                style_cleaner.register_used_style(assigned_run_style)
            
            # Normalize whitespace in run text
            WhitespaceNormalizer.normalize_run_text(run)
            
            # Normalize colors in run style
            if isinstance(run.style, dict):
                if run.style.get("color"):
                    normalized_color = ColorNormalizer.normalize_color(run.style["color"])
                    if normalized_color:
                        run.style["color"] = normalized_color
                
                # Normalize font name
                if run.style.get("font_name"):
                    normalized_font = FontNormalizer.normalize_font_name(run.style["font_name"])
                    if normalized_font:
                        run.style["font_name"] = normalized_font
                
                # Normalize font size
                if run.style.get("font_size"):
                    normalized_size = FontNormalizer.normalize_font_size(run.style["font_size"])
                    if normalized_size:
                        run.style["font_size"] = normalized_size
    
    # Build style definitions for override removal
    for sig, paragraphs_group in style_normalizer._para_signatures.items():
        if len(paragraphs_group) >= 2:
            style_id = style_normalizer._para_style_map.get(paragraphs_group[0].id)
            if style_id and paragraphs_group[0].style:
                local_override_remover.register_style_definition(style_id, dict(paragraphs_group[0].style))
    
    # Third pass: apply normalizations
    # Check if paragraph is in header/footer by checking metadata or raw_xml
    for paragraph in paragraphs:
        # Check if paragraph is from header/footer
        # Method 1: Check metadata if available
        is_header_footer = False
        if hasattr(paragraph, 'metadata') and isinstance(paragraph.metadata, dict):
            is_header_footer = paragraph.metadata.get('is_header') or paragraph.metadata.get('is_footer')
        
        # Method 2: Check raw_xml path if available
        if not is_header_footer and hasattr(paragraph, 'raw_xml') and paragraph.raw_xml:
            # Check if raw_xml contains header/footer path indicators
            raw_lower = paragraph.raw_xml.lower()
            is_header_footer = (
                'header' in raw_lower or 
                'footer' in raw_lower or
                'word/header' in raw_lower or
                'word/footer' in raw_lower
            )
        
        # Method 3: Check if paragraph is in a textbox (which might be in header/footer)
        # We'll be conservative and skip aggressive normalization for textboxes
        
        # Check if paragraph contains textbox
        has_textbox = False
        for run in paragraph.runs:
            if hasattr(run, 'textbox') and run.textbox:
                has_textbox = True
                # Register styles from textbox
                if isinstance(run.textbox, list):
                    for textbox_run in run.textbox:
                        if isinstance(textbox_run, Run) and isinstance(textbox_run.style, dict):
                            textbox_style_name = textbox_run.style.get("style_name")
                            if textbox_style_name:
                                style_cleaner.register_used_style(textbox_style_name)
                break
        
        # Normalize spacing - but check if spacing existed in original raw_xml
        if isinstance(paragraph.style, dict) and paragraph.style.get("spacing"):
            # Check if spacing existed in original raw_xml
            spacing_existed = False
            if hasattr(paragraph, 'raw_xml') and paragraph.raw_xml:
                spacing_existed = '<w:spacing' in paragraph.raw_xml or 'spacing' in paragraph.raw_xml.lower()
            
            if is_header_footer and not spacing_existed:
                # In headers/footers, don't add spacing if it didn't exist originally
                del paragraph.style["spacing"]
            else:
                paragraph.style["spacing"] = SpacingNormalizer.normalize_spacing(paragraph.style["spacing"])
        
        # Normalize indent (skip for headers/footers to preserve layout)
        if not is_header_footer and isinstance(paragraph.style, dict) and paragraph.style.get("indent"):
            paragraph.style["indent"] = IndentNormalizer.normalize_indent(paragraph.style["indent"])
        
        # Normalize colors in paragraph style (borders, shading)
        if isinstance(paragraph.style, dict):
            if paragraph.style.get("borders"):
                borders = paragraph.style["borders"]
                if isinstance(borders, dict):
                    for border_key, border_data in borders.items():
                        if isinstance(border_data, dict) and border_data.get("color"):
                            normalized_color = ColorNormalizer.normalize_color(border_data["color"])
                            if normalized_color:
                                border_data["color"] = normalized_color
            
            # Normalize tab stops
            if paragraph.style.get("tabs"):
                paragraph.style["tabs"] = TabStopNormalizer.normalize_tabs(paragraph.style["tabs"])
        
        # Remove local overrides (skip for headers/footers and textboxes to preserve layout)
        if not is_header_footer and not has_textbox:
            local_override_remover.remove_overrides(paragraph)
    
    # Collect styles from headers/footers before export
    # Headers/footers are in separate XML files, so we need to read them directly
    header_footer_styles = set()
    try:
        # Check for header files (typically header1.xml, header2.xml, etc.)
        header_files = []
        for i in range(1, 10):  # Check up to 9 header files
            header_path = f"word/header{i}.xml"
            try:
                header_xml = package_reader.get_xml_content(header_path)
                if header_xml:
                    header_files.append((header_path, header_xml))
            except Exception:
                continue
        
        # Check for footer files (typically footer1.xml, footer2.xml, etc.)
        footer_files = []
        for i in range(1, 10):  # Check up to 9 footer files
            footer_path = f"word/footer{i}.xml"
            try:
                footer_xml = package_reader.get_xml_content(footer_path)
                if footer_xml:
                    footer_files.append((footer_path, footer_xml))
            except Exception:
                continue
        
        # Collect styles from header files
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        for header_path, header_xml in header_files:
            try:
                root = ET.fromstring(header_xml)
                # Find all pStyle elements
                for p_style in root.findall('.//w:pStyle', ns):
                    style_id = p_style.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', '')
                    if style_id:
                        header_footer_styles.add(style_id)
                        style_cleaner.register_used_style(style_id)
            except Exception as e:
                logger.warning(f"Failed to collect styles from {header_path}: {e}")
        
        # Collect styles from footer files
        for footer_path, footer_xml in footer_files:
            try:
                root = ET.fromstring(footer_xml)
                # Find all pStyle elements
                for p_style in root.findall('.//w:pStyle', ns):
                    style_id = p_style.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', '')
                    if style_id:
                        header_footer_styles.add(style_id)
                        style_cleaner.register_used_style(style_id)
            except Exception as e:
                logger.warning(f"Failed to collect styles from {footer_path}: {e}")
    except Exception as e:
        logger.warning(f"Failed to collect styles from headers/footers: {e}")
    
    exporter = XMLExporter(adapter)
    document_xml = exporter.regenerate_wordml(adapter)
    numbering_xml = numbering_normalizer.to_xml()
    # Include header/footer styles in used_style_ids
    used_style_ids = style_cleaner._used_style_ids | header_footer_styles
    styles_xml = style_normalizer.to_xml(used_style_ids=used_style_ids)

    _write_normalized_package(
        source_path,
        target_path,
        document_xml,
        numbering_xml=numbering_xml,
        styles_xml=styles_xml,
        image_positions=image_positions,
        page_config=page_config,
        package_reader=package_reader,
    )

    # Explicitly close resources and clean extracted temp directory that PackageReader
    # keeps around for media access.
    zip_handle = getattr(package_reader, "_zip_file", None)
    if zip_handle is not None:
        try:
            zip_handle.close()
        except Exception:
            pass
    extract_dir = getattr(package_reader, "_extract_to_path", None)
    if extract_dir is not None:
        shutil.rmtree(extract_dir, ignore_errors=True)

    return target_path


def _build_page_config(sections: Iterable[dict[str, Any]]) -> PageConfig:
    section = next(iter(sections), {}) if sections else {}
    page_size_data = section.get("page_size") or {}
    width = _twips_to_points_safe(page_size_data.get("width"), DEFAULT_PAGE_SIZE.width)
    height = _twips_to_points_safe(page_size_data.get("height"), DEFAULT_PAGE_SIZE.height)
    size = Size(width, height)

    margins_data = section.get("margins") or {}
    margins = Margins(
        top=_twips_to_points_safe(margins_data.get("top"), DEFAULT_MARGINS.top),
        bottom=_twips_to_points_safe(margins_data.get("bottom"), DEFAULT_MARGINS.bottom),
        left=_twips_to_points_safe(margins_data.get("left"), DEFAULT_MARGINS.left),
        right=_twips_to_points_safe(margins_data.get("right"), DEFAULT_MARGINS.right),
    )

    return PageConfig(page_size=size, base_margins=margins)


def _twips_to_points_safe(value: Optional[Union[str, int]], default: float) -> float:
    if value in (None, "", False):
        return float(default)
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return float(default)
    return float(twips_to_points(numeric))


def _collect_paragraph_metrics(unified_layout: UnifiedLayout) -> Dict[str, Dict[str, Any]]:
    metrics: Dict[str, Dict[str, Any]] = {}
    block_index = 0  # Fallback index if no ID available

    for page in unified_layout.pages:
        for block in page.blocks:
            payload = _resolve_block_payload(block)
            if not isinstance(payload, ParagraphLayout):
                continue
            meta = getattr(payload, "metadata", None)
            if not isinstance(meta, dict):
                continue
            
            # Try multiple ways to get paragraph ID
            paragraph_id = (
                meta.get("source_id") or 
                meta.get("id") or 
                meta.get("element_id") or 
                meta.get("uid") or
                getattr(block, "source_uid", None) or
                f"para_{block_index}"  # Fallback to index
            )
            
            block_index += 1
            
            metrics[str(paragraph_id)] = {
                "indent_metrics": meta.get("indent_metrics") or {},
                "raw_style": meta.get("raw_style") or {},
                "line_height": getattr(payload, "style", None),
            }
    return metrics


def _points_to_emu(points: float) -> int:
    """Convert points to EMU (1 point = 12700 EMU)."""
    return int(round(points * 12700))


def _collect_image_positions(
    unified_layout: UnifiedLayout,
    page_config: PageConfig,
    package_reader: Optional[Any] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Collect calculated image positions from layout pipeline and header/footer parsers.
    
    Returns a dict mapping relationship IDs to their calculated positions.
    """
    from .engine.layout_primitives import GenericLayout, OverlayBox
    from .engine.assembler.utils import resolve_overlay_frame, extract_anchor_info
    from .engine.geometry import Rect
    
    image_positions: Dict[str, Dict[str, Any]] = {}
    
    # Collect from unified_layout (body images)
    for page in unified_layout.pages:
        for block in page.blocks:
            payload = _resolve_block_payload(block)
            
            # Collect overlays (images) from GenericLayout
            if isinstance(payload, GenericLayout):
                overlays = getattr(payload, "overlays", [])
                for overlay in overlays:
                    if not isinstance(overlay, OverlayBox):
                        continue
                    if overlay.kind != "image":
                        continue
                    
                    # Get image source to identify it
                    overlay_payload = overlay.payload if isinstance(overlay.payload, dict) else {}
                    image_source = overlay_payload.get("image") or overlay_payload.get("source")
                    
                    # Get relationship ID
                    rel_id = None
                    if isinstance(image_source, dict):
                        rel_id = image_source.get("relationship_id") or image_source.get("rel_id")
                    
                    if rel_id:
                        frame = overlay.frame
                        margins = page_config.base_margins
                        
                        # Calculate position relative to page edge
                        x_pt = frame.x
                        y_pt = page_config.page_size.height - frame.y - frame.height
                        
                        # Determine relativeFrom based on calculated position
                        if abs(x_pt - margins.left) < 1.0:
                            x_rel = "margin"
                            x_offset_emu = 0
                        elif abs(x_pt) < 1.0:
                            x_rel = "page"
                            x_offset_emu = 0
                        else:
                            x_rel = "page"
                            x_offset_emu = _points_to_emu(x_pt)
                        
                        y_rel = "page"
                        y_offset_emu = _points_to_emu(y_pt)
                        
                        image_positions[rel_id] = {
                            "x": x_offset_emu,
                            "x_rel": x_rel,
                            "y": y_offset_emu,
                            "y_rel": y_rel,
                            "is_header_footer": False,
                        }
    
    # Collect from header/footer files directly
    if package_reader:
        try:
            # Check header files
            for i in range(1, 10):
                header_path = f"word/header{i}.xml"
                try:
                    header_xml = package_reader.get_xml_content(header_path)
                    if header_xml:
                        _collect_image_positions_from_xml(
                            header_xml, header_path, page_config, image_positions, is_header=True
                        )
                except Exception:
                    continue
            
            # Check footer files
            for i in range(1, 10):
                footer_path = f"word/footer{i}.xml"
                try:
                    footer_xml = package_reader.get_xml_content(footer_path)
                    if footer_xml:
                        _collect_image_positions_from_xml(
                            footer_xml, footer_path, page_config, image_positions, is_header=False
                        )
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Failed to collect image positions from headers/footers: {e}")
    
    return image_positions


def _collect_image_positions_from_xml(
    xml_content: str,
    file_path: str,
    page_config: PageConfig,
    image_positions: Dict[str, Dict[str, Any]],
    is_header: bool,
) -> None:
    """Collect image positions from header/footer XML and calculate using resolve_overlay_frame."""
    from .engine.assembler.utils import resolve_overlay_frame, extract_anchor_info, extract_dimension
    from .engine.geometry import Rect
    
    try:
        root = ET.fromstring(xml_content)
        wp_ns = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
        ns_w = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        
        # Find all drawings with anchors
        for drawing in root.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing'):
            anchor = drawing.find(f'.//{wp_ns}anchor')
            if anchor is None:
                continue
            
            # Get blip to find relationship ID
            blip = drawing.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}blip')
            if blip is None:
                continue
            
            rel_id = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
            if not rel_id:
                continue
            
            # Extract anchor info from XML
            pos_h = anchor.find(f'.//{wp_ns}positionH', {})
            pos_v = anchor.find(f'.//{wp_ns}positionV', {})
            extent = anchor.find(f'.//{wp_ns}extent', {})
            
            if pos_h is None or pos_v is None or extent is None:
                continue
            
            # Build position dict
            position = {}
            x_rel = pos_h.get('relativeFrom', 'column')
            x_offset_emu = 0
            pos_offset_h = pos_h.find(f'.//{wp_ns}posOffset', {})
            if pos_offset_h is not None and pos_offset_h.text:
                try:
                    x_offset_emu = int(pos_offset_h.text)
                except (ValueError, TypeError):
                    pass
            
            y_rel = pos_v.get('relativeFrom', 'page')
            y_offset_emu = 0
            pos_offset_v = pos_v.find(f'.//{wp_ns}posOffset', {})
            if pos_offset_v is not None and pos_offset_v.text:
                try:
                    y_offset_emu = int(pos_offset_v.text)
                except (ValueError, TypeError):
                    pass
            
            position = {
                "x": x_offset_emu,
                "x_rel": x_rel,
                "y": y_offset_emu,
                "y_rel": y_rel,
            }
            
            # Get extent (size)
            width_emu = int(extent.get('cx', 0))
            height_emu = int(extent.get('cy', 0))
            width_pt = width_emu / 12700.0
            height_pt = height_emu / 12700.0
            
            # Create a block_rect for header/footer
            # Headers are at top, footers at bottom
            margins = page_config.base_margins
            if is_header:
                # Header block rect - approximate position
                block_rect = Rect(
                    x=margins.left,
                    y=page_config.page_size.height - margins.top,
                    width=page_config.page_size.width - margins.left - margins.right,
                    height=margins.top,
                )
            else:
                # Footer block rect - approximate position
                block_rect = Rect(
                    x=margins.left,
                    y=margins.bottom,
                    width=page_config.page_size.width - margins.left - margins.right,
                    height=margins.bottom,
                )
            
            # Calculate frame using resolve_overlay_frame
            try:
                frame = resolve_overlay_frame(position, width_pt, height_pt, block_rect, page_config)
                
                # Convert calculated frame back to EMU and relativeFrom
                x_pt = frame.x
                y_pt = page_config.page_size.height - frame.y - frame.height
                
                # Determine relativeFrom based on calculated position
                if abs(x_pt - margins.left) < 1.0:
                    x_rel = "margin"
                    x_offset_emu = 0
                elif abs(x_pt) < 1.0:
                    x_rel = "page"
                    x_offset_emu = 0
                else:
                    x_rel = "page"
                    x_offset_emu = _points_to_emu(x_pt)
                
                y_rel = "page"
                y_offset_emu = _points_to_emu(y_pt)
                
                image_positions[rel_id] = {
                    "x": x_offset_emu,
                    "x_rel": x_rel,
                    "y": y_offset_emu,
                    "y_rel": y_rel,
                    "is_header_footer": True,
                }
            except Exception as e:
                logger.debug(f"Failed to calculate frame for image {rel_id}: {e}")
    except Exception as e:
        logger.warning(f"Failed to collect image positions from {file_path}: {e}")


def _resolve_block_payload(block: LayoutBlock) -> Any:
    if isinstance(block.content, BlockContent):
        return block.content.payload
    return block.content


def _normalize_paragraphs(
    body: Any,
    metrics: Dict[str, Dict[str, Any]],
    numbering_normalizer: Optional[NumberingNormalizer],
    style_normalizer: Optional[StyleNormalizer],
    paragraphs_list: Optional[Any] = None,  # List[Paragraph] but avoiding import
) -> None:
    # Use provided paragraphs_list if available, otherwise get from body
    # This ensures we use the same paragraph objects that were processed by ListTreeBuilder
    if paragraphs_list is not None:
        paragraphs: Iterable[Paragraph] = paragraphs_list
    else:
        paragraphs: Iterable[Paragraph] = getattr(body, "get_paragraphs_recursive", lambda: [])()
    metric_map = {str(pid): data for pid, data in metrics.items()}

    for paragraph in paragraphs:
        # Skip paragraphs from headers/footers - they are in separate XML files
        # Check if paragraph is from header/footer by checking raw_xml or metadata
        is_header_footer = False
        if hasattr(paragraph, 'raw_xml') and paragraph.raw_xml:
            raw_lower = paragraph.raw_xml.lower()
            is_header_footer = (
                'header' in raw_lower or 
                'footer' in raw_lower or
                'word/header' in raw_lower or
                'word/footer' in raw_lower
            )
        if hasattr(paragraph, 'metadata') and isinstance(paragraph.metadata, dict):
            is_header_footer = is_header_footer or paragraph.metadata.get('is_header') or paragraph.metadata.get('is_footer')
        
        # Skip normalization for header/footer paragraphs
        if is_header_footer:
            continue
        
        metric = metric_map.get(paragraph.id, {})
        indent_values = _derive_initial_indent(paragraph, metric.get("indent_metrics") or {})

        level_data = None
        if numbering_normalizer is not None:
            level_data = numbering_normalizer.register_paragraph(paragraph)
            
            # Update level_data with calculated indents from layout engine
            # This ensures numbering levels use normalized indents
            if level_data and metric.get("indent_metrics"):
                indent_metrics = metric.get("indent_metrics")
                # Convert calculated indents (in points) to twips for level_data
                if indent_metrics.get("left") is not None:
                    level_data["indent_left"] = _twips_from_points(indent_metrics["left"])
                if indent_metrics.get("right") is not None:
                    level_data["indent_right"] = _twips_from_points(indent_metrics["right"])
                if indent_metrics.get("hanging") is not None:
                    level_data["indent_hanging"] = _twips_from_points(indent_metrics["hanging"])
                    level_data["indent_first_line"] = None  # hanging and first_line are mutually exclusive
                elif indent_metrics.get("first_line") is not None:
                    level_data["indent_first_line"] = _twips_from_points(indent_metrics["first_line"])
                    level_data["indent_hanging"] = None
                
                # Also update the stored level in abstracts for this numbering
                # Get the abstract_id and level from paragraph numbering info
                numbering_info = getattr(paragraph, "numbering", None)
                if isinstance(numbering_info, dict):
                    num_id = str(numbering_info.get("id", ""))
                    level = str(numbering_info.get("level", "0"))
                    # Find the abstract_id for this num_id
                    mapping = numbering_normalizer._num_map.get(num_id)
                    if mapping:
                        _, abstract_id = mapping
                        if abstract_id in numbering_normalizer._abstracts:
                            abstracts_data = numbering_normalizer._abstracts[abstract_id]
                            if "levels" in abstracts_data and level in abstracts_data["levels"]:
                                # Update the stored level data
                                abstracts_data["levels"][level].update({
                                    "indent_left": level_data.get("indent_left"),
                                    "indent_right": level_data.get("indent_right"),
                                    "indent_hanging": level_data.get("indent_hanging"),
                                    "indent_first_line": level_data.get("indent_first_line"),
                                })

        if level_data:
            indent_values = _merge_indent_with_level(indent_values, level_data)

        _apply_indent(paragraph, indent_values)
        _apply_raw_style(paragraph, metric.get("raw_style") or {})
        paragraph._normalize_runs()
        
        # Register paragraph for style normalization
        if style_normalizer is not None:
            style_normalizer.register_paragraph(paragraph, numbering_normalizer)
        
        for run in paragraph.runs:
            _normalize_run(run)
            # Register run for style normalization
            if style_normalizer is not None:
                style_normalizer.register_run(run)
        
        if isinstance(paragraph.style, dict):
            paragraph.style = _clean_style_dict(paragraph.style)


def _derive_initial_indent(
    paragraph: Paragraph,
    indent_metrics: Dict[str, Any],
) -> Dict[str, Optional[float]]:
    result: Dict[str, Optional[float]] = {
        "left": _as_float(indent_metrics.get("left"), paragraph.left_indent),
        "right": _as_float(indent_metrics.get("right"), paragraph.right_indent),
        "first_line": _as_float(indent_metrics.get("first_line"), paragraph.first_line_indent),
        "hanging": _as_float(indent_metrics.get("hanging"), paragraph.hanging_indent),
    }

    style_indent: Dict[str, Any] = {}
    if isinstance(paragraph.style, dict):
        candidate = paragraph.style.get("indent")
        if isinstance(candidate, dict):
            style_indent = candidate

    result["left"] = _coalesce_indent_value(result["left"], style_indent.get("left"))
    result["right"] = _coalesce_indent_value(result["right"], style_indent.get("right"))
    result["first_line"] = _coalesce_indent_value(result["first_line"], style_indent.get("first_line"))
    result["hanging"] = _coalesce_indent_value(result["hanging"], style_indent.get("hanging"))

    return result


def _merge_indent_with_level(
    indent_values: Dict[str, Optional[float]],
    level_data: Dict[str, Any],
) -> Dict[str, Optional[float]]:
    merged = dict(indent_values)

    left = _points_from_twips(level_data.get("indent_left"))
    if left is not None:
        merged["left"] = left

    right = _points_from_twips(level_data.get("indent_right"))
    if right is not None:
        merged["right"] = right

    hanging = _points_from_twips(level_data.get("indent_hanging"))
    first_line = _points_from_twips(level_data.get("indent_first_line"))

    if hanging:
        merged["hanging"] = hanging
        merged["first_line"] = None
    elif first_line:
        merged["first_line"] = first_line
        merged["hanging"] = None

    return merged


def _apply_indent(paragraph: Paragraph, indent_values: Dict[str, Optional[float]]) -> None:
    left = indent_values.get("left")
    right = indent_values.get("right")
    first_line = indent_values.get("first_line")
    hanging = indent_values.get("hanging")

    paragraph.left_indent = left
    paragraph.right_indent = right
    paragraph.first_line_indent = first_line
    paragraph.hanging_indent = hanging

    if not isinstance(paragraph.style, dict):
        paragraph.style = {}

    indent_dict: Dict[str, str] = {}
    left_twips = _twips_from_points(left)
    if left_twips not in (None, 0):
        indent_dict["left"] = str(left_twips)
    right_twips = _twips_from_points(right)
    if right_twips not in (None, 0):
        indent_dict["right"] = str(right_twips)

    hanging_twips = _twips_from_points(hanging)
    first_line_twips = _twips_from_points(first_line)

    if hanging_twips not in (None, 0):
        indent_dict["hanging"] = str(hanging_twips)
    elif first_line_twips not in (None, 0):
        indent_dict["first_line"] = str(first_line_twips)

    if indent_dict:
        paragraph.style["indent"] = indent_dict
    else:
        paragraph.style.pop("indent", None)


def _coalesce_indent_value(
    current_value: Optional[float],
    fallback: Any,
) -> Optional[float]:
    if current_value is not None:
        return current_value
    return _points_from_twips(fallback)


def _points_from_twips(value: Any) -> Optional[float]:
    if value in (None, "", False):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        try:
            numeric = float(str(value).strip())
        except Exception:
            return None
    return numeric / TWIPS_PER_POINT


def _twips_from_points(value: Optional[float]) -> Optional[int]:
    if value in (None, "", False):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return int(round(numeric * TWIPS_PER_POINT))


def _coerce_twips(value: Any) -> Optional[int]:
    if value in (None, "", False):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        try:
            numeric = float(str(value).strip())
        except Exception:
            return None
    return int(round(numeric))


def _apply_raw_style(paragraph: Paragraph, raw_style: Dict[str, Any]) -> None:
    spacing = raw_style.get("spacing")
    if isinstance(spacing, dict):
        paragraph.spacing_before = _as_float(
            spacing.get("before_pt") or spacing.get("before"),
            paragraph.spacing_before,
        )
        paragraph.spacing_after = _as_float(
            spacing.get("after_pt") or spacing.get("after"),
            paragraph.spacing_after,
        )
        paragraph.line_spacing = _as_float(
            spacing.get("line_height_pt") or spacing.get("line"),
            paragraph.line_spacing,
        )


def _normalize_run(run: Run) -> None:
    """
    Clean run style dictionaries and synchronize primitive attributes.
    """
    if isinstance(run.style, dict):
        cleaned_style = _clean_style_dict(run.style)
    else:
        cleaned_style = {}

    if cleaned_style.get("bold") is not None:
        run.set_bold(bool(cleaned_style["bold"]))
    if cleaned_style.get("italic") is not None:
        run.set_italic(bool(cleaned_style["italic"]))
    if cleaned_style.get("underline") is not None:
        run.set_underline(bool(cleaned_style["underline"]))
    if cleaned_style.get("font_name"):
        run.set_font_name(str(cleaned_style["font_name"]))
    if cleaned_style.get("font_size") is not None:
        try:
            run.set_font_size(int(float(cleaned_style["font_size"])))
        except (TypeError, ValueError):
            pass
    if cleaned_style.get("color"):
        run.set_color(str(cleaned_style["color"]))
    if cleaned_style.get("highlight"):
        run.set_highlight(str(cleaned_style["highlight"]))

    run.style = cleaned_style or None


def _clean_style_dict(style: Dict[str, Any]) -> Dict[str, Any]:
    cleaned: Dict[str, Any] = {}
    for key, value in style.items():
        # Always preserve style_name even if empty (needed for style assignment)
        if key == "style_name":
            cleaned[key] = value
            continue
        if value in (None, "", [], {}, False):
            continue
        cleaned[key] = value
    return cleaned


def _as_float(value: Any, fallback: Optional[float]) -> Optional[float]:
    if value in (None, "", False):
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _add_wmf_fallback_to_header_footer(
    header_footer_xml: str,
    file_path: str,
    package_reader: Any,
    converted_images: Dict[str, str],
) -> Tuple[str, Dict[str, bytes]]:
    """
    Add PNG fallback for WMF images in header/footer by converting WMF to PNG
    and wrapping in AlternateContent structure.
    
    Returns:
        Tuple of (modified XML, dict of new PNG files to add: {media_path: png_data})
    """
    try:
        from docx_interpreter.media.converters import MediaConverter
        
        root = ET.fromstring(header_footer_xml)
        wp_ns = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
        mc_ns = '{http://schemas.openxmlformats.org/markup-compatibility/2006}'
        ns_w = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        ns_r = {"r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
        
        new_png_files: Dict[str, bytes] = {}
        converter = MediaConverter()
        
        # First, check if original XML already has AlternateContent with fallback
        # If so, preserve it and extract PNG files from relationships
        existing_alt_contents = root.findall(f'.//{mc_ns}AlternateContent')
        for alt_content in existing_alt_contents:
            fallback = alt_content.find(f'.//{mc_ns}Fallback')
            if fallback is not None:
                # Original already has AlternateContent with fallback
                # Extract PNG files from relationships and preserve them
                blip = fallback.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}blip')
                if blip is not None:
                    png_rel_id = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                    
                    # Get relationship file path
                    rels_file = file_path.replace('word/', 'word/_rels/') + '.rels'
                    try:
                        rels_xml = package_reader.get_xml_content(rels_file) if package_reader else None
                        if rels_xml:
                            rels_root = ET.fromstring(rels_xml)
                            ns = {'r': RelationshipsParser.NAMESPACE}
                            rel_elem = rels_root.find(f'.//{{{ns["r"]}}}Relationship[@Id="{png_rel_id}"]')
                            if rel_elem is not None:
                                target = rel_elem.get('Target')
                                png_path = f'word/{target}' if not target.startswith('word/') else target
                                
                                # Try to read PNG from original package
                                try:
                                    png_data = package_reader.zip_file.read(png_path)
                                    new_png_files[png_path] = png_data
                                    logger.debug(f"Preserved existing PNG fallback from original: {png_path} ({len(png_data)} bytes)")
                                    
                                    # Store relationship info to preserve it
                                    converted_images[f"{file_path}:{png_rel_id}"] = {
                                        "target": rel_target,
                                        "type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
                                        "rels_file": rels_file,
                                    }
                                except Exception as e:
                                    logger.debug(f"Could not read PNG from original package: {e}")
                    except Exception as e:
                        logger.debug(f"Could not read relationships file: {e}")
        
        # If we found existing fallbacks, return original XML unchanged
        if existing_alt_contents and new_png_files:
            logger.debug(f"Preserved existing AlternateContent with fallback in {file_path}")
            return header_footer_xml, new_png_files
        
        # Find all drawings with WMF images
        drawings = root.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing')
        
        # Track which drawings are already in AlternateContent
        alt_content_drawings = set()
        for alt_content in root.findall(f'.//{mc_ns}AlternateContent'):
            for drawing in alt_content.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing'):
                alt_content_drawings.add(id(drawing))
        
        for drawing in drawings:
            # Skip if already in AlternateContent
            if id(drawing) in alt_content_drawings:
                continue
            
            # Find blip to check if it's WMF
            blip = drawing.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}blip')
            if blip is None:
                continue
            
            rel_id = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
            if not rel_id:
                continue
            
            # Get relationship to find WMF file
            # Convert word/header1.xml -> word/_rels/header1.xml.rels
            rels_file = file_path.replace('word/', 'word/_rels/') + '.rels'
            rels_xml = package_reader.get_xml_content(rels_file) if package_reader else None
            if not rels_xml:
                continue
            
            rels_root = ET.fromstring(rels_xml)
            rel_elem = rels_root.find(f'.//{{{RelationshipsParser.NAMESPACE}}}Relationship[@Id="{rel_id}"]')
            if rel_elem is None:
                continue
            
            rel_target = rel_elem.get('Target', '')
            if not rel_target.endswith('.wmf'):
                continue
            
            # Read WMF file
            # Ensure rel_target has 'word/' prefix for package path
            if rel_target.startswith('word/'):
                wmf_path = rel_target
            elif rel_target.startswith('media/'):
                wmf_path = f'word/{rel_target}'
            else:
                wmf_path = f'word/media/{rel_target}' if 'media' not in rel_target else f'word/{rel_target}'
            wmf_data = package_reader.get_binary_content(wmf_path) if package_reader else None
            if not wmf_data:
                continue
            
            # Check if it's really WMF
            if not (wmf_data[:2] == b'\xd7\xcd' or wmf_data[:4] == b'\x01\x00\x00\x00'):
                continue
            
            # Get image dimensions from extent
            anchor = drawing.find(f'.//{wp_ns}anchor')
            if anchor is None:
                continue
            
            extent = anchor.find(f'.//{wp_ns}extent')
            if extent is None:
                continue
            
            cx_emu = int(extent.get('cx', 0))
            cy_emu = int(extent.get('cy', 0))
            width_pt = cx_emu / 12700.0 if cx_emu else None
            height_pt = cy_emu / 12700.0 if cy_emu else None
            width_px = int(width_pt * 96 / 72) if width_pt else None
            height_px = int(height_pt * 96 / 72) if height_pt else None
            
            # Convert WMF to PNG
            png_data = converter.convert_emf_to_png(wmf_data, width_px, height_px)
            if not png_data:
                logger.warning(f"Failed to convert WMF to PNG for {wmf_path}")
                continue
            
            # Create PNG filename
            png_filename = rel_target.replace('.wmf', '.png')
            png_media_path = f'word/{png_filename}' if not png_filename.startswith('word/') else png_filename
            
            # Always add PNG to media folder if conversion succeeded (even if it's a placeholder)
            # This ensures PNG versions are available in the package
            new_png_files[png_media_path] = png_data
            
            # Check if PNG is a placeholder (very small file indicates placeholder)
            # Placeholders are typically < 500 bytes, real images are much larger
            # Only create AlternateContent if PNG is valid (not placeholder)
            is_placeholder = len(png_data) < 500
            if is_placeholder:
                logger.warning(f"WMF to PNG conversion returned placeholder ({len(png_data)} bytes) for {wmf_path}, PNG added to media but skipping AlternateContent")
                continue
            
            # Create new relationship ID for PNG
            # Find next available rId
            existing_rIds = set()
            for rel in rels_root.findall(f'.//{{{RelationshipsParser.NAMESPACE}}}Relationship'):
                existing_rIds.add(rel.get('Id', ''))
            
            png_rel_id = None
            for i in range(1, 100):
                candidate = f'rId{i}'
                if candidate not in existing_rIds:
                    png_rel_id = candidate
                    break
            
            if not png_rel_id:
                logger.warning(f"Could not find available relationship ID for PNG fallback")
                continue
            
            # Store relationship info to add later
            # Use the same filename as in png_media_path but without 'word/' prefix for relationship target
            # This ensures consistency between the file path and relationship target
            converted_images[f"{file_path}:{png_rel_id}"] = {
                "target": png_filename,  # Already without 'word/' prefix (e.g., "media/image1.png")
                "type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
                "rels_file": rels_file,
            }
            
            # Wrap drawing in AlternateContent
            # Choice: original WMF drawing
            # Fallback: PNG drawing
            
            # Create AlternateContent structure
            alt_content = ET.Element(f'{mc_ns}AlternateContent')
            
            # Choice: WMF (original)
            choice = ET.SubElement(alt_content, f'{mc_ns}Choice')
            choice.set('Requires', 'wps')
            choice.append(drawing)
            
            # Fallback: PNG (converted)
            fallback = ET.SubElement(alt_content, f'{mc_ns}Fallback')
            
            # Create PNG drawing (copy of WMF drawing but with PNG blip)
            png_drawing = ET.fromstring(ET.tostring(drawing, encoding='unicode'))
            
            # Update blip to use PNG relationship
            png_blip = png_drawing.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}blip')
            if png_blip is not None:
                png_blip.set('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed', png_rel_id)
            
            # Fix anchor attributes for PNG fallback to ensure visibility
            wp_ns = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
            png_anchor = png_drawing.find(f'.//{wp_ns}anchor')
            if png_anchor is not None:
                # Set behindDoc to 0 to ensure PNG is visible
                png_anchor.set('behindDoc', '0')
                logger.debug(f"Set behindDoc=0 for PNG fallback in {file_path}")
            
            fallback.append(png_drawing)
            
            # Replace drawing with AlternateContent
            # Find parent by searching through all elements
            parent = None
            for elem in root.iter():
                if drawing in list(elem):
                    parent = elem
                    break
            
            if parent is not None:
                # Remove drawing and insert AlternateContent at same position
                parent.remove(drawing)
                # Find position to insert
                children = list(parent)
                try:
                    idx = children.index(drawing) if drawing in children else len(children)
                except ValueError:
                    idx = len(children)
                parent.insert(idx, alt_content)
            else:
                # If no parent found, just append to root (shouldn't happen)
                logger.warning(f"Could not find parent for drawing in {file_path}")
                root.append(alt_content)
            
            logger.debug(f"Added AlternateContent with PNG fallback for WMF in {file_path}")
        
        if new_png_files:
            return ET.tostring(root, encoding='unicode', method='xml'), new_png_files
        return header_footer_xml, {}
        
    except Exception as e:
        logger.warning(f"Failed to add WMF fallback in {file_path}: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return header_footer_xml, {}


def _fix_header_footer_image_positioning(
    header_footer_xml: str,
    image_positions: Dict[str, Dict[str, Any]],
    page_config: PageConfig,
    file_path: str,
) -> str:
    """
    Fix image positioning in header/footer XML using calculated positions from layout pipeline.
    
    Uses the calculated positions from unified_layout instead of preserving original values.
    Preserves AlternateContent (WMF/PNG fallback) structure.
    """
    try:
        root = ET.fromstring(header_footer_xml)
        wp_ns = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
        mc_ns = '{http://schemas.openxmlformats.org/markup-compatibility/2006}'
        ns_w = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        ns_r = {"r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
        modified = False
        
        # Handle AlternateContent (WMF/PNG fallback) first
        alt_contents = root.findall(f'.//{mc_ns}AlternateContent')
        for alt_content in alt_contents:
            # Find Choice (WMF) and Fallback (PNG)
            choice = alt_content.find(f'.//{mc_ns}Choice')
            fallback = alt_content.find(f'.//{mc_ns}Fallback')
            
            # Process Choice (WMF)
            if choice is not None:
                drawing = choice.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing')
                if drawing is not None:
                    anchor = drawing.find(f'.//{wp_ns}anchor')
                    if anchor is not None:
                        blip = drawing.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}blip')
                        rel_id = None
                        if blip is not None:
                            rel_id = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                        
                        if rel_id and rel_id in image_positions:
                            calculated_pos = image_positions[rel_id]
                            if calculated_pos.get("is_header_footer"):
                                _update_anchor_position(anchor, calculated_pos, wp_ns)
                                modified = True
            
            # Process Fallback (PNG) - preserve structure but also update if needed
            if fallback is not None:
                drawing = fallback.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing')
                if drawing is not None:
                    anchor = drawing.find(f'.//{wp_ns}anchor')
                    if anchor is not None:
                        blip = drawing.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}blip')
                        rel_id = None
                        if blip is not None:
                            rel_id = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                        
                        if rel_id and rel_id in image_positions:
                            calculated_pos = image_positions[rel_id]
                            if calculated_pos.get("is_header_footer"):
                                _update_anchor_position(anchor, calculated_pos, wp_ns)
                                modified = True
        
        # Handle direct drawings (without AlternateContent)
        # Collect all drawings that are NOT inside AlternateContent
        all_drawings = root.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing')
        processed_drawings = set()
        
        # Mark drawings inside AlternateContent as processed
        for alt_content in alt_contents:
            for drawing in alt_content.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing'):
                processed_drawings.add(id(drawing))
        
        for drawing in all_drawings:
            # Skip if already processed (inside AlternateContent)
            if id(drawing) in processed_drawings:
                continue
            
            # Find anchor in this drawing
            anchor = drawing.find(f'.//{wp_ns}anchor')
            if anchor is None:
                continue
            
            # Find blip in this drawing
            blip = drawing.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}blip')
            rel_id = None
            if blip is not None:
                rel_id = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
            
            # For WMF images in headers/footers, preserve ALL original attributes
            # Word caches WMF images and changing any attribute might break rendering
            # Only make minimal changes if absolutely necessary for visibility
            behind_doc = anchor.get('behindDoc')
            layout_in_cell = anchor.get('layoutInCell', '0')
            
            # Only change behindDoc if it's causing visibility issues
            # But preserve original if it was working before
            # For now, let's preserve original behindDoc value to maintain Word's cache compatibility
            # if behind_doc == '1':
            #     anchor.set('behindDoc', '0')
            #     modified = True
            #     logger.debug(f"Fixed behindDoc for image {rel_id} in header/footer")
            
            # Don't change layoutInCell - preserve original value
            # Word's WMF rendering depends on exact attribute values
            # if relative_from == 'column' and layout_in_cell == '0':
            #     anchor.set('layoutInCell', '1')
            #     modified = True
            
            # For WMF images, preserve everything exactly as original
            logger.debug(f"Preserving original WMF image attributes for {rel_id} in header/footer")
            
            # Optionally update position if we have calculated position AND user wants it
            # But for now, we preserve original positioning to avoid breaking WMF images
            # if rel_id and rel_id in image_positions:
            #     calculated_pos = image_positions[rel_id]
            #     if calculated_pos.get("is_header_footer"):
            #         _update_anchor_position(anchor, calculated_pos, wp_ns)
            #         modified = True
        
        if modified:
            return ET.tostring(root, encoding='unicode', method='xml')
        return header_footer_xml
    except Exception as e:
        logger.warning(f"Failed to fix image positioning in header/footer: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return header_footer_xml


def _update_anchor_position(anchor: ET.Element, calculated_pos: Dict[str, Any], wp_ns: str) -> None:
    """Update anchor position using calculated values."""
    pos_h = anchor.find(f'.//{wp_ns}positionH', {})
    if pos_h is not None:
        # Update relativeFrom and offset
        pos_h.set('relativeFrom', calculated_pos["x_rel"])
        pos_offset = pos_h.find(f'.//{wp_ns}posOffset', {})
        if pos_offset is not None:
            pos_offset.text = str(calculated_pos["x"])
        else:
            # Create posOffset if it doesn't exist
            pos_offset = ET.SubElement(pos_h, f'{wp_ns}posOffset')
            pos_offset.text = str(calculated_pos["x"])
        logger.debug(f"Updated PositionH using calculated position: {calculated_pos['x_rel']}, offset={calculated_pos['x']}")
    
    pos_v = anchor.find(f'.//{wp_ns}positionV', {})
    if pos_v is not None:
        # Update relativeFrom and offset
        pos_v.set('relativeFrom', calculated_pos["y_rel"])
        pos_offset = pos_v.find(f'.//{wp_ns}posOffset', {})
        if pos_offset is not None:
            pos_offset.text = str(calculated_pos["y"])
        else:
            # Create posOffset if it doesn't exist
            pos_offset = ET.SubElement(pos_v, f'{wp_ns}posOffset')
            pos_offset.text = str(calculated_pos["y"])
        logger.debug(f"Updated PositionV using calculated position: {calculated_pos['y_rel']}, offset={calculated_pos['y']}")
    
    # Fix behindDoc - set to '0' for headers/footers to ensure image is visible
    behind_doc = anchor.get('behindDoc')
    if behind_doc == '1':
        anchor.set('behindDoc', '0')
        logger.debug(f"Fixed behindDoc: 1 -> 0 (image now in front of text)")


def _write_normalized_package(
    source: Path,
    target: Path,
    document_xml: str,
    *,
    numbering_xml: Optional[str] = None,
    styles_xml: Optional[str] = None,
    image_positions: Optional[Dict[str, Dict[str, Any]]] = None,
    page_config: Optional[PageConfig] = None,
    package_reader: Optional[Any] = None,
) -> None:
    """
    Write normalized package, preserving headers/footers and other files unchanged.
    
    Headers and footers are preserved as-is to avoid breaking positioning and layout,
    but image positioning is fixed to ensure images are visible.
    """
    target.parent.mkdir(parents=True, exist_ok=True)

    numbering_replaced = False
    styles_replaced = False
    converted_images: Dict[str, Dict[str, Any]] = {}  # Store new PNG relationships to add
    new_png_files: Dict[str, bytes] = {}  # Store new PNG files to add
    
    # First pass: collect all entries and process headers/footers to populate converted_images
    entries_data: Dict[str, bytes] = {}
    with zipfile.ZipFile(source, "r") as src_zip:
        for entry in src_zip.infolist():
            entries_data[entry.filename] = src_zip.read(entry.filename)
            
            # Process headers/footers first to populate converted_images
            # TEMPORARILY DISABLED: Skip PNG fallback to test if it causes LibreOffice I/O error
            # if entry.filename.startswith("word/header") and entry.filename.endswith(".xml"):
            #     header_xml = entries_data[entry.filename].decode("utf-8")
            #     if package_reader:
            #         header_xml, png_files = _add_wmf_fallback_to_header_footer(
            #             header_xml,
            #             entry.filename,
            #             package_reader,
            #             converted_images,
            #         )
            #         new_png_files.update(png_files)
            #         entries_data[entry.filename] = header_xml.encode("utf-8")
            # elif entry.filename.startswith("word/footer") and entry.filename.endswith(".xml"):
            #     footer_xml = entries_data[entry.filename].decode("utf-8")
            #     if package_reader:
            #         footer_xml, png_files = _add_wmf_fallback_to_header_footer(
            #             footer_xml,
            #             entry.filename,
            #             package_reader,
            #             converted_images,
            #         )
            #         new_png_files.update(png_files)
            #         entries_data[entry.filename] = footer_xml.encode("utf-8")
        
        # Also copy PNG files from original that are referenced in existing fallbacks
        # This ensures we preserve all PNG files from original AlternateContent
        # Note: PNG files from _add_wmf_fallback_to_header_footer are already in new_png_files
        # This loop handles PNG files that might be referenced but not yet collected
        for filename in list(entries_data.keys()):
            if filename.startswith("word/media/") and filename.endswith(".png"):
                # Skip if already added (to avoid duplicates)
                if filename in new_png_files:
                    continue
                
                # Check if this PNG is referenced in any header/footer fallback relationship
                png_name = filename.split('/')[-1]
                for rel_file in [f for f in entries_data.keys() if f.endswith('.rels') and 'header' in f or 'footer' in f]:
                    try:
                        rels_xml = entries_data[rel_file].decode('utf-8')
                        rels_root = ET.fromstring(rels_xml)
                        ns = {'r': RelationshipsParser.NAMESPACE}
                        # Check if any relationship points to this PNG
                        for rel in rels_root.findall(f'.//{{{ns["r"]}}}Relationship'):
                            rel_target = rel.get('Target', '')
                            rel_type = rel.get('Type', '')
                            # Check if it's an image relationship pointing to this PNG
                            if 'image' in rel_type.lower():
                                # Normalize rel_target path
                                if not rel_target.startswith('word/'):
                                    target_path = f'word/{rel_target}'
                                else:
                                    target_path = rel_target
                                
                                if target_path == filename or png_name in rel_target:
                                    # This PNG is referenced in a fallback, copy it
                                    new_png_files[filename] = entries_data[filename]
                                    logger.debug(f"Preserved PNG file from original fallback: {filename}")
                                    break
                    except Exception:
                        continue
    
    # Update Content_Types.xml before writing if we have new PNG files
    # DISABLED: PNG fallback is not needed - Word will generate WMF cache automatically when opening the file
    # Adding PNG fallback was causing LibreOffice I/O errors, and Word doesn't require it
    if False and new_png_files and '[Content_Types].xml' in entries_data:
        try:
            content_types_xml = entries_data['[Content_Types].xml'].decode('utf-8')
            content_types_root = ET.fromstring(content_types_xml)
            ct_ns = 'http://schemas.openxmlformats.org/package/2006/content-types'
            
            modified_ct = False
            for png_path in new_png_files.keys():
                # Extract filename from path (e.g., "word/media/image1.png" -> "/word/media/image1.png")
                part_name = '/' + png_path if not png_path.startswith('/') else png_path
                
                # Check if override already exists by iterating through all Override elements
                existing = None
                for override in content_types_root.findall(f'.//{{{ct_ns}}}Override'):
                    if override.get('PartName') == part_name:
                        existing = override
                        break
                
                if existing is None:
                    # Add new Override for PNG
                    override = ET.SubElement(content_types_root, f'{{{ct_ns}}}Override')
                    override.set('PartName', part_name)
                    override.set('ContentType', 'image/png')
                    modified_ct = True
                    logger.debug(f"Added ContentType override for {part_name}")
            
            if modified_ct:
                # Update entries_data with modified Content_Types.xml
                updated_ct_xml = ET.tostring(content_types_root, encoding='unicode', method='xml')
                # Preserve XML declaration
                if not updated_ct_xml.startswith('<?xml'):
                    updated_ct_xml = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + updated_ct_xml
                entries_data['[Content_Types].xml'] = updated_ct_xml.encode('utf-8')
                logger.debug("Updated [Content_Types].xml with PNG entries")
        except Exception as e:
            logger.warning(f"Failed to update Content_Types.xml: {e}")
    
    # Second pass: write all files, updating relationships and applying fixes
    # Use ZIP_DEFLATED compression to match original DOCX format
    written_files = set()  # Track written files to avoid duplicates
    
    # Ensure [Content_Types].xml is written first (DOCX spec requirement)
    # Then write other files in original order
    file_order = []
    if '[Content_Types].xml' in entries_data:
        file_order.append('[Content_Types].xml')
    for filename in entries_data.keys():
        if filename != '[Content_Types].xml':
            file_order.append(filename)
    
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as dst_zip:
        for filename in file_order:
            data = entries_data[filename]
            # Skip if already written (avoid duplicates)
            if filename in written_files:
                continue
            written_files.add(filename)
            
            # Replace document.xml with normalized version
            if filename == "word/document.xml":
                data = document_xml.encode("utf-8")
            # Replace numbering.xml with normalized version
            elif numbering_xml is not None and filename == "word/numbering.xml":
                data = numbering_xml.encode("utf-8")
                numbering_replaced = True
            # Replace styles.xml with normalized version
            elif styles_xml is not None and filename == "word/styles.xml":
                data = styles_xml.encode("utf-8")
                styles_replaced = True
            # Preserve headers/footers exactly as-is to maintain WMF cache compatibility
            # Headers/footers with WMF images are not modified to avoid breaking Word's cache
            # Only WMF fallback (AlternateContent) is added in first pass if conversion succeeds
            # No positioning fixes are applied to preserve original WMF rendering
            # elif filename.startswith("word/header") and filename.endswith(".xml"):
            #     header_xml = data.decode("utf-8")
            #     fixed_xml = _fix_header_footer_image_positioning(
            #         header_xml,
            #         image_positions or {},
            #         page_config or PageConfig(Size(595.0, 842.0), Margins()),
            #         filename
            #     )
            #     data = fixed_xml.encode("utf-8")
            # elif filename.startswith("word/footer") and filename.endswith(".xml"):
            #     footer_xml = data.decode("utf-8")
            #     fixed_xml = _fix_header_footer_image_positioning(
            #         footer_xml,
            #         image_positions or {},
            #         page_config or PageConfig(Size(595.0, 842.0), Margins()),
            #         filename
            #     )
            #     data = fixed_xml.encode("utf-8")
            # Update relationship files to add PNG relationships
            # DISABLED: PNG fallback is not needed - Word will generate WMF cache automatically when opening the file
            # elif filename.endswith('.rels') and filename.startswith('word/_rels/'):
            #     rels_xml = data.decode("utf-8")
            #     rels_root = ET.fromstring(rels_xml)
            #     ns = {'r': RelationshipsParser.NAMESPACE}
            #     
            #     # Add new relationships for converted PNG files
            #     modified_rels = False
            #     for key, rel_info in converted_images.items():
            #         # Key format: "file_path:rel_id"
            #         if ':' not in key:
            #             continue
            #         file_path_part, rel_id = key.split(':', 1)
            #         rels_file = rel_info.get("rels_file", "")
            #         
            #         if filename == rels_file:
            #             # Check if relationship already exists
            #             existing_rel = rels_root.find(f'.//{{{RelationshipsParser.NAMESPACE}}}Relationship[@Id="{rel_id}"]')
            #             if existing_rel is None:
            #                 # Add new relationship for PNG
            #                 rel_elem = ET.SubElement(rels_root, f'{{{RelationshipsParser.NAMESPACE}}}Relationship')
            #                 rel_elem.set('Id', rel_id)
            #                 rel_elem.set('Type', rel_info["type"])
            #                 rel_elem.set('Target', rel_info["target"])
            #                 modified_rels = True
            #                 logger.debug(f"Added relationship {rel_id} -> {rel_info['target']} in {filename}")
            #     
            #     if modified_rels:
            #         # Preserve XML declaration if present
            #         if rels_xml.startswith('<?xml'):
            #             data = ET.tostring(rels_root, encoding='utf-8', method='xml')
            #             # Re-add XML declaration
            #             data = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + data
            #         else:
            #             data = ET.tostring(rels_root, encoding='utf-8', method='xml')
            #             data = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + data
            # Preserve all other files (images, relationships, etc.)
            
            # Use ZipInfo to ensure proper file metadata
            zip_info = zipfile.ZipInfo(filename)
            zip_info.compress_type = zipfile.ZIP_DEFLATED
            # Set date_time to current time (some ZIP readers require valid timestamps)
            zip_info.date_time = (2024, 1, 1, 0, 0, 0)  # Use a fixed date for reproducibility
            
            dst_zip.writestr(zip_info, data)
        
        # Add new PNG files to package (skip if already written)
        # DISABLED: PNG fallback is not needed - Word will generate WMF cache automatically when opening the file
        # for png_path, png_data in new_png_files.items():
        #     if png_path not in written_files:
        #         # Use ZipInfo for PNG files too
        #         zip_info = zipfile.ZipInfo(png_path)
        #         zip_info.compress_type = zipfile.ZIP_DEFLATED
        #         zip_info.date_time = (2024, 1, 1, 0, 0, 0)
        #         dst_zip.writestr(zip_info, png_data)
        #         written_files.add(png_path)
        #         logger.debug(f"Added converted PNG file: {png_path} ({len(png_data)} bytes)")
        #     else:
        #         logger.debug(f"Skipped duplicate PNG file: {png_path}")
        
        # Note: Content_Types.xml is already updated before writing (see line 2120)
        # No need to update it again here

        if numbering_xml is not None and not numbering_replaced:
            dst_zip.writestr("word/numbering.xml", numbering_xml.encode("utf-8"))
        
        if styles_xml is not None and not styles_replaced:
            dst_zip.writestr("word/styles.xml", styles_xml.encode("utf-8"))

