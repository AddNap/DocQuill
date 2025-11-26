"""

Optimized JSON exporter for pipeline (UnifiedLayout).

Generates compact...
"""

import json
import copy
import hashlib
import logging
import re
from typing import Any, Dict, List, Optional, Set
from dataclasses import is_dataclass
from pathlib import Path

from ..engine.unified_layout import UnifiedLayout, LayoutPage, LayoutBlock
from ..engine.geometry import twips_to_points

logger = logging.getLogger(__name__)


class OptimizedPipelineJSONExporter:
    """

    JSON Exporter with optimizations:
    - Style deduplication (separate list, ...
    """
    
    HEADING_STYLE_RE = re.compile(r"(?:^|[\s_\-])heading\s*([0-9]+)", re.IGNORECASE)
    
    def __init__(self, include_raw_content: bool = False, max_content_depth: int = 3, package_reader: Any = None, 
                 xml_parser: Any = None, document: Any = None):
        """

        Args:
        include_raw_content: Whether to include raw content data...
        """
        self.include_raw_content = include_raw_content
        self.max_content_depth = max_content_depth
        self.package_reader = package_reader
        self.xml_parser = xml_parser
        self.document = document
        self.numbering_data = {}
        if self.xml_parser:
            self.numbering_data = getattr(self.xml_parser, 'numbering_data', {}) or {}
        self._style_cache: Dict[str, int] = {}  # hash -> style_id
        self._styles_list: List[Dict[str, Any]] = []
        self._style_counter = 0
        self._media_cache: Dict[str, int] = {}  # media_key -> media_id
        self._media_list: List[Dict[str, Any]] = []
        self._media_counter = 0
    
    def export_from_layout_structure(self, layout_structure, unified_layout: UnifiedLayout, output_path: Optional[Path] = None) -> Dict[str, Any]:
        """

        Exports LayoutStructure to optimized JSON.
        Uses Layout...
        """
        # Reset cache
        self._style_cache.clear()
        self._styles_list.clear()
        self._style_counter = 0
        self._media_cache.clear()
        self._media_list.clear()
        self._media_counter = 0
        
        # Build structure
        result = {
            "version": "2.0",
            "format": "optimized_pipeline",
            "metadata": {
                "total_pages": len(unified_layout.pages),
                "current_page": unified_layout.current_page,
                "source": "DocQuill LayoutPipeline (LayoutStructure)"
            },
            "styles": [],
            "media": [],
            "body": [],  # Body elementy (paragrafy, tabele, obrazy)
            "headers": {},  # Headers per typ (default, first, odd, even)
            "footers": {},  # Footers per typ (default, first, odd, even)
            "pages": [],  # Pages with geometry (without headers/footers)
            "sections": [],
            "footnotes": {},
            "endnotes": {}
        }
        
        # Eksportuj body elementy z LayoutStructure
        for element in layout_structure.body:
            element_data = self._serialize_layout_element(element)
            if element_data:
                result["body"].append(element_data)
        
        # Eksportuj headers z LayoutStructure
        # ALTERNATIVELY: If document has _json_headers (from round-trip), use them
        if self.document and hasattr(self.document, '_json_headers') and self.document._json_headers:
            # Use headers from JSON (for documents from round-trip)
            result["headers"] = self.document._json_headers
        else:
            # Eksportuj z LayoutStructure
            for header_type, header_elements in layout_structure.headers.items():
                if header_elements:
                    result["headers"][header_type] = [
                        self._serialize_layout_element(elem) for elem in header_elements
                        if self._serialize_layout_element(elem) is not None
                    ]
        
        # Eksportuj footers z LayoutStructure
        # ALTERNATIVELY: If document has _json_footers (from round-trip), use them
        if self.document and hasattr(self.document, '_json_footers') and self.document._json_footers:
            # Use footers from JSON (for documents from round-trip)
            result["footers"] = self.document._json_footers
        else:
            # Eksportuj z LayoutStructure
            for footer_type, footer_elements in layout_structure.footers.items():
                if footer_elements:
                    result["footers"][footer_type] = [
                        self._serialize_layout_element(elem) for elem in footer_elements
                        if self._serialize_layout_element(elem) is not None
                    ]
        
        # Extract sections if parser is available
        # IMPORTANT: Fill sections with full headers/footers info from LayoutStructure
        # ALTERNATIVELY: If document has _json_sections (from round-trip), use them
        sections = None
        if self.document and hasattr(self.document, '_json_sections') and self.document._json_sections:
            # Use sections from JSON (for documents from round-trip)
            sections = self.document._json_sections
            # Fill headers/footers from LayoutStructure if available
            if layout_structure:
                for section in sections:
                    section_headers_refs = section.get("headers", {})
                    section_footers_refs = section.get("footers", {})
                    
                    # Mapuj headers/footers z LayoutStructure do sekcji
                    if section_headers_refs:
                        if isinstance(section_headers_refs, list):
                            mapped_headers = {}
                            for hdr_ref in section_headers_refs:
                                hdr_type = hdr_ref.get("type", "default")
                                source_type = hdr_type if hdr_type in layout_structure.headers else "default"
                                if source_type in layout_structure.headers:
                                    if hdr_type not in mapped_headers:
                                        mapped_headers[hdr_type] = []
                                    mapped_headers[hdr_type].extend([
                                        self._serialize_layout_element(elem)
                                        for elem in layout_structure.headers[source_type]
                                        if self._serialize_layout_element(elem) is not None
                                    ])
                            if mapped_headers:
                                section["headers"] = mapped_headers
                        elif isinstance(section_headers_refs, dict):
                            for hdr_type, hdr_refs in section_headers_refs.items():
                                if isinstance(hdr_refs, list):
                                    source_type = hdr_type if hdr_type in layout_structure.headers else "default"
                                    if source_type in layout_structure.headers:
                                        section_headers_refs[hdr_type] = [
                                            self._serialize_layout_element(elem)
                                            for elem in layout_structure.headers[source_type]
                                            if self._serialize_layout_element(elem) is not None
                                        ]
                    
                    if section_footers_refs:
                        if isinstance(section_footers_refs, list):
                            mapped_footers = {}
                            for ftr_ref in section_footers_refs:
                                ftr_type = ftr_ref.get("type", "default")
                                source_type = ftr_type if ftr_type in layout_structure.footers else "default"
                                if source_type in layout_structure.footers:
                                    if ftr_type not in mapped_footers:
                                        mapped_footers[ftr_type] = []
                                    mapped_footers[ftr_type].extend([
                                        self._serialize_layout_element(elem)
                                        for elem in layout_structure.footers[source_type]
                                        if self._serialize_layout_element(elem) is not None
                                    ])
                            if mapped_footers:
                                section["footers"] = mapped_footers
                        elif isinstance(section_footers_refs, dict):
                            for ftr_type, ftr_refs in section_footers_refs.items():
                                if isinstance(ftr_refs, list):
                                    source_type = ftr_type if ftr_type in layout_structure.footers else "default"
                                    if source_type in layout_structure.footers:
                                        section_footers_refs[ftr_type] = [
                                            self._serialize_layout_element(elem)
                                            for elem in layout_structure.footers[source_type]
                                            if self._serialize_layout_element(elem) is not None
                                        ]
        
        if not sections and self.xml_parser:
            sections = self._extract_sections()
            if sections:
                # Fill sections with full headers/footers info from LayoutStructure
                for section in sections:
                    # Mapuj headers/footers z LayoutStructure do sekcji
                    section_headers_refs = section.get("headers", {})
                    section_footers_refs = section.get("footers", {})
                    
                    # If section has references (rId), find corresponding elements from LayoutStructure...
                    # and add full information
                    if section_headers_refs:
                        if isinstance(section_headers_refs, list):
                            # section_headers_refs to lista referencji {type, id}
                            # Map to full elements from layout_structure.headers
                            # IMPORTANT: If section has reference to type not in layout_structure,
                            # use fallback to 'default'
                            mapped_headers = {}
                            for hdr_ref in section_headers_refs:
                                hdr_type = hdr_ref.get("type", "default")
                                # Check if type exists in layout_structure, if not use 'default'
                                source_type = hdr_type if hdr_type in layout_structure.headers else "default"
                                if source_type in layout_structure.headers:
                                    if hdr_type not in mapped_headers:
                                        mapped_headers[hdr_type] = []
                                    mapped_headers[hdr_type].extend([
                                        self._serialize_layout_element(elem)
                                        for elem in layout_structure.headers[source_type]
                                        if self._serialize_layout_element(elem) is not None
                                    ])
                            if mapped_headers:
                                section["headers"] = mapped_headers
                        elif isinstance(section_headers_refs, dict):
                            # section_headers_refs to dict z typami (default, first, odd, even)
                            for hdr_type, hdr_refs in section_headers_refs.items():
                                if isinstance(hdr_refs, list) and hdr_type in layout_structure.headers:
                                    section_headers_refs[hdr_type] = [
                                        self._serialize_layout_element(elem)
                                        for elem in layout_structure.headers[hdr_type]
                                        if self._serialize_layout_element(elem) is not None
                                    ]
                    
                    if section_footers_refs:
                        if isinstance(section_footers_refs, list):
                            # section_footers_refs to lista referencji
                            # IMPORTANT: If section has reference to type not in layout_structure,
                            # use fallback to 'default'
                            mapped_footers = {}
                            for ftr_ref in section_footers_refs:
                                ftr_type = ftr_ref.get("type", "default")
                                # Check if type exists in layout_structure, if not use 'default'
                                source_type = ftr_type if ftr_type in layout_structure.footers else "default"
                                if source_type in layout_structure.footers:
                                    if ftr_type not in mapped_footers:
                                        mapped_footers[ftr_type] = []
                                    mapped_footers[ftr_type].extend([
                                        self._serialize_layout_element(elem)
                                        for elem in layout_structure.footers[source_type]
                                        if self._serialize_layout_element(elem) is not None
                                    ])
                            if mapped_footers:
                                section["footers"] = mapped_footers
                        elif isinstance(section_footers_refs, dict):
                            # section_footers_refs to dict z typami
                            for ftr_type, ftr_refs in section_footers_refs.items():
                                if isinstance(ftr_refs, list) and ftr_type in layout_structure.footers:
                                    section_footers_refs[ftr_type] = [
                                        self._serialize_layout_element(elem)
                                        for elem in layout_structure.footers[ftr_type]
                                        if self._serialize_layout_element(elem) is not None
                                        ]
                
                result["sections"] = sections
        elif sections:
            # Sections from JSON (without filling from LayoutStructure)
            result["sections"] = sections
        
        # Extract footnotes and endnotes if parser is available
        if self.xml_parser or self.package_reader:
            footnotes, endnotes = self._extract_notes()
            if footnotes:
                result["footnotes"] = footnotes
            if endnotes:
                result["endnotes"] = endnotes
        
        # Eksportuj strony z UnifiedLayout (tylko geometria, bez headers/footers)
        for page in unified_layout.pages:
            # Filter blocks - skip header and footer blocks
            body_blocks = [
                block for block in page.blocks
                if block.block_type not in ("header", "footer", "decorator")
            ]
            if body_blocks:
                page_data = {
                    "n": page.number,
                    "size": [page.size.width, page.size.height],
                    "margins": [page.margins.top, page.margins.right, page.margins.bottom, page.margins.left],
                    "blocks": [self._serialize_block(block) for block in body_blocks]
                }
                result["pages"].append(page_data)
        
        # Add styles and media at the end
        result["styles"] = self._styles_list
        
        # Zbierz wszystkie obrazy z PackageReader
        if self.package_reader:
            self._collect_all_images_from_package()
        
        # Resolve rel_id to paths
        if self.package_reader:
            self._resolve_media_paths()
        
        # Zdeduplikuj media
        self._deduplicate_media_by_path()
        
        result["media"] = self._media_list
        
        # Zapisz do pliku
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
        
        return result
    
    def _serialize_layout_element(self, element: Any) -> Optional[Dict[str, Any]]:
        """
        Serializuje element z LayoutStructure (dict z layout_payload).
        
        Args:
            element: Element z LayoutStructure (dict z type, layout_payload, style, etc.)
            
        Returns:
            Zserializowany element lub None
        """
        if not isinstance(element, dict):
            return None
        
        element_type = element.get("type")
        if not element_type:
            return None
        
        # Serialize depending on type
        if element_type == "paragraph":
            # Element from LayoutStructure has layout_payload (ParagraphLayout) or direct...
            layout_payload = element.get("layout_payload")
            if layout_payload:
                paragraph_data = self._serialize_paragraph_layout(layout_payload, depth=0)
                return self._merge_paragraph_metadata(paragraph_data, element)
            else:
                # Fallback - use data directly from element
                return self._serialize_paragraph_from_dict(element)
        elif element_type == "table":
            return self._serialize_table_layout_from_structure(element)
        elif element_type == "image":
            return self._serialize_image_info(element)
        else:
            # Default serialize as generic
            return {
                "type": element_type,
                "style": self._get_style_id(element.get("style", {})),
                "data": element.get("layout_payload") or element
            }
    
    def _serialize_paragraph_from_dict(self, element: Dict[str, Any]) -> Dict[str, Any]:
        """Serializuje paragraf z dict (gdy nie ma layout_payload)."""
        if not isinstance(element, dict):
            return {
                "type": "paragraph",
                "text": self._simplify_value(element)
            }
        
        style_dict = element.get("style", {}) or {}
        result: Dict[str, Any] = {
            "type": "paragraph",
            "text": element.get("text", "") or "",
            "style": self._get_style_id(style_dict)
        }
        
        return self._merge_paragraph_metadata(result, element)

    def _merge_paragraph_metadata(self, result: Dict[str, Any], element: Dict[str, Any]) -> Dict[str, Any]:
        """Merges paragraph metadata from LayoutStructure with base structure."""
        if not isinstance(element, dict):
            return result
        
        if "style" not in result or result.get("style") is None:
            result["style"] = self._get_style_id(element.get("style", {}))
        if not result.get("text") and element.get("text"):
            result["text"] = element.get("text") or ""
        
        # Runs: prefer runs_payload (bogatsze informacje o formatowaniu)
        runs_payload = element.get("runs_payload")
        if runs_payload:
            runs = self._serialize_runs_from_payload(runs_payload)
            if runs:
                result["runs"] = runs
        elif element.get("runs"):
            result["runs"] = element.get("runs")
        
        if result.get("runs"):
            hyperlinks = self._extract_hyperlinks_from_runs(result["runs"])
            if hyperlinks:
                result["hyperlinks"] = hyperlinks
        
        # Paragraph-level properties
        if element.get("paragraph_properties"):
            result["paragraph_properties"] = element["paragraph_properties"]
        
        spacing = element.get("spacing")
        if spacing:
            result["spacing"] = spacing
        if element.get("spacing_metrics"):
            result["spacing_metrics"] = element["spacing_metrics"]
        if element.get("indent"):
            result["indent"] = element["indent"]
        if element.get("inline_indent"):
            result["inline_indent"] = element["inline_indent"]
        if element.get("line_spacing") is not None:
            result["line_spacing"] = element["line_spacing"]
        if element.get("line_spacing_rule"):
            result["line_spacing_rule"] = element["line_spacing_rule"]
        
        # Pagination / keep controls
        if element.get("keep_with_next"):
            result["keep_with_next"] = True
        if element.get("keep_together"):
            result["keep_together"] = True
        if element.get("page_break_before"):
            result["page_break_before"] = element["page_break_before"]
        if element.get("page_break_after"):
            result["page_break_after"] = element["page_break_after"]
        
        # Numbering / list metadata
        numbering = element.get("numbering") or result.get("numbering")
        if numbering:
            result["numbering"] = numbering
        marker = element.get("marker") or result.get("marker")
        if marker:
            result["marker"] = marker
        list_info = element.get("list")
        computed_list = self._build_list_metadata(numbering, marker, result.get("indent"), element.get("meta"))
        if list_info and isinstance(list_info, dict):
            if computed_list:
                merged = dict(computed_list)
                merged.update(list_info)
                computed_list = merged
            else:
                computed_list = list_info
        if computed_list:
            result["list"] = computed_list
        
        # Media + embedded objects
        media_refs = []
        if element.get("images"):
            for image in element.get("images", []):
                media_id = self._find_and_register_media(image, "paragraph", context="paragraph_inline")
                if media_id is not None:
                    media_refs.append(media_id)
        if media_refs:
            result["media_refs"] = media_refs
        
        if element.get("textboxes"):
            result["textboxes"] = self._simplify_value(element["textboxes"])
        if element.get("vml_shapes"):
            result["vml_shapes"] = self._simplify_value(element["vml_shapes"])
        if element.get("fields"):
            result["fields"] = element["fields"]
        if element.get("bookmarks"):
            result["bookmarks"] = element["bookmarks"]
        
        # Meta information (list builder, numbering overrides, etc.)
        if element.get("meta"):
            result["meta"] = element["meta"]
        
        # Section break information (sectPr na paragrafie)
        section_props = element.get("section_properties")
        if section_props:
            result["section_properties"] = section_props
            section_break = self._serialize_section_break(section_props)
            if section_break:
                result["section_break"] = section_break
        
        effective_format = self._build_effective_format(result, element, computed_list)
        if effective_format:
            result["effective_format"] = effective_format
        
        return result

    def _serialize_section_break(self, section_props: Dict[str, Any]) -> Dict[str, Any]:
        """Simplified structure describing section assigned to paragraph."""
        if not isinstance(section_props, dict):
            return {}
        
        section_break: Dict[str, Any] = {}
        section_type = section_props.get("type") or section_props.get("break_type")
        if section_type:
            section_break["type"] = section_type
        
        for key in (
            "page_size",
            "margins",
            "columns",
            "doc_grid",
            "title_page",
            "different_first_page",
            "different_odd_even",
            "headers",
            "footers",
        ):
            value = section_props.get(key)
            if value not in (None, {}, []):
                section_break[key] = value
        
        return section_break

    def _build_table_properties_dict(
        self,
        table_entry: Dict[str, Any],
        raw_props: Any,
        style_dict: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        props: Dict[str, Any] = {}
        raw = raw_props if isinstance(raw_props, dict) else {}
        style = style_dict if isinstance(style_dict, dict) else {}
        
        def include(key: str, value: Any) -> None:
            if value in (None, {}, [], ""):
                return
            props[key] = value
        
        include("style_name", style.get("style_name"))
        include("style_id", style.get("style_id") or style.get("style"))
        include("borders", raw.get("borders") or style.get("borders"))
        include("cell_margins", raw.get("cell_margins") or style.get("cell_margins"))
        include("cell_spacing", raw.get("cell_spacing") or style.get("cell_spacing"))
        include("alignment", raw.get("alignment") or style.get("alignment"))
        include("table_alignment", raw.get("table_alignment") or style.get("table_alignment"))
        include("table_vertical_alignment", raw.get("table_vertical_alignment") or style.get("table_vertical_alignment"))
        include("width", raw.get("width") or style.get("width"))
        include("width_type", raw.get("width_type") or style.get("width_type"))
        include("indent", raw.get("indent") or style.get("indent"))
        include("look", raw.get("look") or style.get("look"))
        include("shading", raw.get("shading") or style.get("shading"))
        include("spacing_before", raw.get("spacing_before") or style.get("spacing_before"))
        include("spacing_after", raw.get("spacing_after") or style.get("spacing_after"))
        include("spacing_between_rows", style.get("spacing_between_rows"))
        include("cell_padding", style.get("cell_padding"))
        include("cant_split", raw.get("cant_split"))
        include("header_repeat", raw.get("header_repeat"))
        include("columns", table_entry.get("columns"))
        include("grid", table_entry.get("grid"))
        
        return props

    def _build_effective_format(
        self,
        paragraph: Dict[str, Any],
        source_element: Dict[str, Any],
        list_info: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        effective: Dict[str, Any] = {}
        
        style_dict = source_element.get("style") or {}
        meta_dict = source_element.get("meta") or {}
        heading_level = self._detect_heading_level(style_dict, meta_dict)
        if heading_level is not None:
            effective["is_heading"] = True
            effective["heading_level"] = heading_level
        
        if list_info:
            effective["is_list_item"] = True
            if list_info.get("level") is not None:
                effective["list_level"] = list_info.get("level")
            if list_info.get("type"):
                effective["list_type"] = list_info.get("type")
            elif list_info.get("is_ordered") is not None:
                effective["list_type"] = "ordered" if list_info["is_ordered"] else "bullet"
            marker_text = (
                list_info.get("marker_text")
                or (list_info.get("marker") or {}).get("text")
                or (paragraph.get("marker") or {}).get("text")
            )
            if marker_text:
                effective["list_marker"] = marker_text
            if list_info.get("num_id"):
                effective["list_num_id"] = list_info["num_id"]
            if list_info.get("start"):
                effective["list_start"] = list_info["start"]
            if list_info.get("format"):
                effective["list_format"] = list_info["format"]
            if list_info.get("suffix"):
                effective["list_suffix"] = list_info["suffix"]
            applied_indent = list_info.get("applied_indent") or paragraph.get("indent")
            if isinstance(applied_indent, dict):
                indent_left = applied_indent.get("left_pt") or applied_indent.get("left")
                if indent_left is not None:
                    effective["list_indent_pt"] = indent_left
            if list_info.get("level_indents"):
                effective["list_level_indents"] = list_info["level_indents"]
        
        text_value = paragraph.get("text") or ""
        runs = paragraph.get("runs") or []
        has_text = bool(text_value.strip()) or any((run.get("text") or "").strip() for run in runs)
        if not has_text and not list_info:
            effective["is_empty"] = True
        
        page_break_before = bool(paragraph.get("page_break_before"))
        page_break_after = bool(paragraph.get("page_break_after"))
        has_page_break_run = self._runs_have_break(runs, {"page"})
        if page_break_before or page_break_after or has_page_break_run:
            effective["is_page_break"] = True
        
        section_break_info = paragraph.get("section_break") or source_element.get("section_break")
        has_section_break_run = self._runs_have_break(runs, {"section"})
        if section_break_info or has_section_break_run:
            effective["is_section_break"] = True
            if section_break_info and section_break_info.get("type"):
                effective["section_break_type"] = section_break_info.get("type")
        
        has_manual_break = self._runs_have_break(runs, {"line", "textwrapping"})
        if has_manual_break and not effective.get("is_page_break"):
            effective["has_line_break"] = True
        
        if not effective.get("is_page_break") and not effective.get("is_section_break"):
            if "is_empty" in effective and not effective["is_empty"]:
                del effective["is_empty"]
        
        return {k: v for k, v in effective.items() if v not in (None, {})}

    def _detect_heading_level(self, style_dict: Dict[str, Any], meta_dict: Dict[str, Any]) -> Optional[int]:
        candidate = style_dict.get("heading_level") or style_dict.get("outline_level")
        if candidate is not None:
            try:
                return int(candidate)
            except (TypeError, ValueError):
                pass
        style_name = (
            style_dict.get("style_name")
            or style_dict.get("style")
            or style_dict.get("style_id")
            or ""
        )
        if isinstance(style_name, str):
            match = self.HEADING_STYLE_RE.search(style_name)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    pass
        meta_level = meta_dict.get("heading_level") or meta_dict.get("outline_level")
        if meta_level is not None:
            try:
                return int(meta_level)
            except (TypeError, ValueError):
                return None
        return None

    def _runs_have_break(self, runs: List[Dict[str, Any]], kinds: Set[str]) -> bool:
        if not isinstance(runs, list):
            return False
        for run in runs:
            break_type = str(run.get("break_type") or "").lower()
            if break_type in kinds:
                return True
        return False

    def _build_list_metadata(
        self,
        numbering: Optional[Dict[str, Any]],
        marker: Optional[Dict[str, Any]],
        indent: Optional[Dict[str, Any]],
        meta: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not numbering or not isinstance(numbering, dict):
            return None
        num_id = numbering.get("id") or numbering.get("num_id") or numbering.get("numId")
        if num_id in (None, "", {}):
            return None
        level = numbering.get("level") or numbering.get("ilvl") or numbering.get("lvl") or 0
        level_key = str(level)
        
        list_info: Dict[str, Any] = {
            "num_id": str(num_id),
            "level": int(level) if isinstance(level, (int, float)) or str(level).isdigit() else level,
        }
        
        abstract_id = self._get_abstract_num_id(str(num_id))
        if abstract_id:
            list_info["abstract_num_id"] = abstract_id
        
        level_def = self._resolve_numbering_level(str(num_id), level_key)
        if level_def:
            for key in ("format", "text", "start", "suffix", "alignment", "html_type"):
                if level_def.get(key) is not None:
                    list_info[key] = level_def[key]
            if "is_ordered" in level_def:
                list_info["is_ordered"] = bool(level_def["is_ordered"])
                list_info["type"] = "ordered" if level_def["is_ordered"] else "bullet"
            elif "format" in level_def:
                fmt = str(level_def["format"]).lower()
                list_info["type"] = "bullet" if fmt in ("bullet", "none", "nothing") else "ordered"
            indent_info: Dict[str, Any] = {}
            for key in ("indent_left", "indent_right", "indent_first_line", "indent_hanging"):
                raw = level_def.get(key)
                if raw not in (None, ""):
                    indent_info.setdefault(key + "_twips", raw)
                    pt = self._twips_to_points(raw)
                    if pt is not None:
                        indent_info[key + "_pt"] = pt
            if indent_info:
                list_info["level_indents"] = indent_info
            tabs = level_def.get("tabs")
            if tabs:
                list_info["tabs"] = tabs
            font = level_def.get("font")
            if font:
                list_info["font"] = font
        
        if marker and isinstance(marker, dict):
            marker_text = marker.get("text")
            if marker_text:
                list_info["marker_text"] = marker_text
            marker_copy = marker.copy()
            list_info["marker"] = marker_copy
        hidden_marker = numbering.get("hidden_marker")
        if hidden_marker:
            list_info["hidden_marker"] = True
        if indent and isinstance(indent, dict):
            list_info["applied_indent"] = indent
        if meta and isinstance(meta, dict):
            for key in ("numbering_override", "explicit_indent", "explicit_numbering"):
                if key in meta:
                    list_info[key] = meta[key]
        
        return list_info

    def _resolve_numbering_level(self, num_id: str, level: str) -> Optional[Dict[str, Any]]:
        if not self.numbering_data:
            return None
        numbering_instances = self.numbering_data.get("numbering_instances") or {}
        abstract_numberings = self.numbering_data.get("abstract_numberings") or {}
        instance = numbering_instances.get(str(num_id))
        if not instance:
            return None
        abstract_id = instance.get("abstractNumId")
        level_key = str(level)
        level_data = {}
        if abstract_id and abstract_id in abstract_numberings:
            base_levels = abstract_numberings[abstract_id].get("levels") or {}
            if level_key in base_levels:
                level_data = copy.deepcopy(base_levels[level_key])
        overrides = instance.get("levels") or {}
        override_level = overrides.get(level_key)
        if override_level:
            if not level_data:
                level_data = {}
            for key, value in override_level.items():
                if value is not None:
                    level_data[key] = value
        return level_data or None

    def _get_abstract_num_id(self, num_id: str) -> Optional[str]:
        if not self.numbering_data:
            return None
        numbering_instances = self.numbering_data.get("numbering_instances") or {}
        instance = numbering_instances.get(str(num_id))
        if not instance:
            return None
        abstract_id = instance.get("abstractNumId") or instance.get("abstract_num_id")
        if abstract_id in (None, "", {}):
            return None
        return str(abstract_id)

    def _extract_hyperlinks_from_runs(self, runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        hyperlinks: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None
        
        for idx, run in enumerate(runs):
            link = run.get("hyperlink")
            if not self._is_valid_hyperlink(link):
                current = None
                continue
            
            identity = self._hyperlink_identity(link)
            run_copy = copy.deepcopy(run)
            if current and identity == current.get("_identity"):
                current["runs"].append(run_copy)
                current["run_indices"].append(idx)
                text_fragment = run.get("text")
                if text_fragment:
                    current.setdefault("text", "")
                    current["text"] += text_fragment
            else:
                hyperlink_entry = {
                    "type": "hyperlink",
                    "id": link.get("id"),
                    "target": link.get("target"),
                    "target_mode": link.get("target_mode"),
                    "anchor": link.get("anchor") or link.get("bookmark"),
                    "runs": [run_copy],
                    "run_indices": [idx],
                    "_identity": identity,
                }
                text_fragment = run.get("text")
                if text_fragment:
                    hyperlink_entry["text"] = text_fragment
                hyperlinks.append(hyperlink_entry)
                current = hyperlink_entry
        
        for entry in hyperlinks:
            entry.pop("_identity", None)
            if "text" not in entry:
                display_text = "".join(run.get("text") or "" for run in entry.get("runs", []))
                if display_text:
                    entry["text"] = display_text
        return hyperlinks

    def _is_valid_hyperlink(self, link: Any) -> bool:
        if not isinstance(link, dict):
            return False
        return bool(link.get("target") or link.get("id") or link.get("anchor"))

    def _hyperlink_identity(self, link: Dict[str, Any]) -> str:
        target = link.get("target") or ""
        link_id = link.get("id") or ""
        anchor = link.get("anchor") or link.get("bookmark") or ""
        target_mode = link.get("target_mode") or ""
        return f"{link_id}::{anchor}::{target}::{target_mode}"
    
    def _serialize_table_layout_from_structure(self, element: Dict[str, Any]) -> Dict[str, Any]:
        """Serializes table from LayoutStructure."""
        # Element from LayoutStructure may have:
        # 1. layout_payload (TableLayout) - use _serialize_table_layout
        # 2. rows directly in dict - serialize from dict
        # 3. raw Table model - use _serialize_table_from_raw
        
        layout_payload = element.get("layout_payload")
        if layout_payload and hasattr(layout_payload, "rows"):
            return self._serialize_table_layout(layout_payload, depth=0)
        
        # Check if element has rows directly (from LayoutStructure)
        if "rows" in element:
            # Serialize from dict - use _serialize_table_from_raw with dict
            return self._serialize_table_from_dict(element)
        
        # W przeciwnym razie serializuj z raw Table model
        raw_table = element.get("raw")
        if raw_table:
            return self._serialize_table_from_raw(raw_table)
        
        # Fallback - return basic structure
        return {
            "type": "table",
            "style": self._get_style_id(element.get("style", {})),
            "rows": []
        }
    
    def _serialize_table_from_dict(self, element: Dict[str, Any]) -> Dict[str, Any]:
        """Serializes table from dict (when rows are directly in dict)."""
        result = {
            "type": "table",
            "style": self._get_style_id(element.get("style", {})),
            "rows": []
        }
        row_props: List[Dict[str, Any]] = []
        
        # Serializuj rows
        rows = element.get("rows", []) or []
        for row in rows:
            row_data: List[Dict[str, Any]] = []
            props: Dict[str, Any] = {}
            
            if isinstance(row, dict) and "cells" in row:
                for cell in row.get("cells", []):
                    cell_data = self._serialize_cell_from_dict(cell)
                    if cell_data:
                        row_data.append(cell_data)
                props = row.get("properties") or {}
            elif hasattr(row, "cells") and getattr(row, "cells", None):
                for cell in getattr(row, "cells", []):
                    cell_data = self._serialize_cell_from_raw(cell)
                    if cell_data:
                        row_data.append(cell_data)
                props = self._extract_row_properties(row)
            elif isinstance(row, (list, tuple)):
                for cell in row:
                    cell_data = self._serialize_cell_from_raw(cell)
                    if cell_data:
                        row_data.append(cell_data)
            
            if row_data:
                result["rows"].append(row_data)
                row_props.append(props or {})
        
        # Add grid if available
        if "grid" in element:
            result["grid"] = element.get("grid")
            result["columns"] = self._serialize_table_grid(element.get("grid"))
        
        # Add borders if available
        if "borders" in element:
            result["borders"] = element.get("borders")
        
        # Add cell_margins if available
        if "cell_margins" in element:
            result["cell_margins"] = element.get("cell_margins")
        
        if row_props and any(row_props):
            while len(row_props) < len(result["rows"]):
                row_props.append({})
            result["row_properties"] = row_props
        table_properties = self._build_table_properties_dict(result, element, element.get("style"))
        if table_properties:
            result["properties"] = table_properties
        
        return result
    
    def _serialize_cell_from_dict(self, cell: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Serializes cell from dict."""
        result = {
            "blocks": []
        }
        
        # Serialize blocks in cell
        blocks = cell.get("blocks", [])
        for block in blocks:
            if isinstance(block, dict):
                block_type = block.get("type")
                if block_type == "paragraph":
                    block_data = self._serialize_paragraph_from_dict(block)
                elif block_type == "table":
                    block_data = self._serialize_table_from_dict(block)
                else:
                    block_data = block
                result["blocks"].append(block_data)
        
        # Add colspan/rowspan if available
        if "colspan" in cell:
            result["colspan"] = cell.get("colspan")
        if "rowspan" in cell:
            result["rowspan"] = cell.get("rowspan")
        
        # Add borders if available
        if "borders" in cell:
            result["borders"] = cell.get("borders")
        
        # Add margins if available
        if "margins" in cell:
            result["margins"] = cell.get("margins")
        
        return result
    
    def export(self, unified_layout: UnifiedLayout, output_path: Optional[Path] = None) -> Dict[str, Any]:
        """

        Exports UnifiedLayout to optimized JSON.

        """
        # Reset cache
        self._style_cache.clear()
        self._styles_list.clear()
        self._style_counter = 0
        self._media_cache.clear()
        self._media_list.clear()
        self._media_counter = 0
        
        # Build structure
        result = {
            "version": "2.0",
            "format": "optimized_pipeline",
            "metadata": {
                "total_pages": len(unified_layout.pages),
                "current_page": unified_layout.current_page,
                "source": "DocQuill LayoutPipeline"
            },
            "styles": [],  # Will be filled at the end
            "media": [],  # Will be filled at the end
            "pages": [],
            "sections": [],  # Sekcje dokumentu
            "footnotes": {},  # Footnotes
            "endnotes": {}  # Endnotes
        }
        
        # Extract sections if parser is available
        if self.xml_parser:
            sections = self._extract_sections()
            if sections:
                result["sections"] = sections
        
        # Extract footnotes and endnotes if parser is available
        if self.xml_parser or self.package_reader:
            footnotes, endnotes = self._extract_notes()
            if footnotes:
                result["footnotes"] = footnotes
            if endnotes:
                result["endnotes"] = endnotes
        
        # Process pages
        for page in unified_layout.pages:
            page_data = self._serialize_page(page)
            result["pages"].append(page_data)
        
        # Add styles and media at the end
        result["styles"] = self._styles_list
        
        # IMPORTANT: Before resolving path, collect all images from PackageReader...
        # (to ensure we have all images, even those not in pipeline...)
        if self.package_reader:
            self._collect_all_images_from_package()
        
        # Resolve rel_id to paths if PackageReader is available
        if self.package_reader:
            self._resolve_media_paths()
        
        # After resolving path, deduplicate again (may be duplicates with different...
        self._deduplicate_media_by_path()
        
        result["media"] = self._media_list
        
        # Zapisz do pliku
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
        
        return result
    
    def _serialize_page(self, page: LayoutPage) -> Dict[str, Any]:
        """Serializes page."""
        # Serializuj wszystkie bloki
        blocks = [self._serialize_block(block) for block in page.blocks]
        
        # Zidentyfikuj header i footer bloki
        header_indices = []
        footer_indices = []
        
        for i, block in enumerate(page.blocks):
            if block.block_type == "header":
                header_indices.append(i)
            elif block.block_type == "footer":
                footer_indices.append(i)
        
        result = {
            "n": page.number,  # Shortcut: number
            "size": [page.size.width, page.size.height],  # [width, height]
            "margins": [page.margins.top, page.margins.right, page.margins.bottom, page.margins.left],  # [top, right, bottom, left]
            "blocks": blocks
        }
        
        # Add header and footer mapping only if present
        if header_indices:
            result["h"] = header_indices  # Shortcut: headers (block indices)
        if footer_indices:
            result["f"] = footer_indices  # Shortcut: footers (block indices)
        
        return result
    
    def _serialize_block(self, block: LayoutBlock) -> Dict[str, Any]:
        """Serializes block with style deduplication and full information."""
        # Frame jako [x, y, width, height]
        frame = [block.frame.x, block.frame.y, block.frame.width, block.frame.height]
        
        # Style ID (deduplikacja)
        style_id = self._get_style_id(block.style)
        
        # Content (uproszczony)
        content = self._serialize_content(block.content, depth=0, block_type=block.block_type)
        
        result = {
            "t": block.block_type,  # Shortcut: type
            "f": frame,  # Shortcut: frame
            "s": style_id,  # Shortcut: style_id
        }
        
        # Optional fields only if set
        if block.page_number is not None:
            result["p"] = block.page_number  # Shortcut: page
        if block.source_uid:
            result["uid"] = block.source_uid
        if block.sequence is not None:
            result["seq"] = block.sequence  # Shortcut: sequence
        
        # For images - add media reference (check all blocks, not...
        # Images can be in different places: as "image", "drawing", in paragraph...
        # Pass context (block_type) for better deduplication
        media_id = self._find_and_register_media(block.content, block.block_type, context=block.block_type)
        if media_id is not None:
            result["m"] = media_id  # Shortcut: media_id
        
        # Content
        if content:
            result["c"] = content  # Shortcut: content
        
        # IMPORTANT: For images - ensure they are exported as blocks with full...
        if block.block_type == 'image' and isinstance(result.get("c"), dict):
            # If content doesn't have type="image", add it
            if result["c"].get("type") != "image":
                result["c"]["type"] = "image"
            
            # If we have media_id, ensure rel_id, width, height are in content...
            if result.get("m") is not None:
                media_id = result["m"]
                if media_id < len(self._media_list):
                    media_info = self._media_list[media_id]
                    if "rel_id" in media_info and "rel_id" not in result["c"]:
                        result["c"]["rel_id"] = media_info["rel_id"]
                    if "width" in media_info and "width" not in result["c"]:
                        result["c"]["width"] = media_info["width"]
                    if "height" in media_info and "height" not in result["c"]:
                        result["c"]["height"] = media_info["height"]
                    if "anchor" in media_info and "anchor" not in result["c"]:
                        result["c"]["anchor"] = media_info["anchor"]
                    if "path" in media_info and "path" not in result["c"]:
                        result["c"]["path"] = media_info["path"]
        
        # IMPORTANT: For paragraphs - ensure runs are directly in content...
        if block.block_type == 'paragraph' and isinstance(result.get("c"), dict):
            # If runs are in payload, move them to main content
            if 'payload' in result["c"] and isinstance(result["c"]["payload"], dict):
                payload = result["c"]["payload"]
                if 'runs' in payload and 'runs' not in result["c"]:
                    result["c"]["runs"] = payload["runs"]
                # Also move list and paragraph_properties
                if 'list' in payload and 'list' not in result["c"]:
                    result["c"]["list"] = payload["list"]
                if 'paragraph_properties' in payload and 'paragraph_properties' not in result["c"]:
                    result["c"]["paragraph_properties"] = payload["paragraph_properties"]
            
            # Also check raw with runs_payload
            if hasattr(block.content, 'raw'):
                raw = block.content.raw
                if isinstance(raw, dict) and 'runs_payload' in raw:
                    runs = self._serialize_runs_from_payload(raw['runs_payload'])
                    if runs:
                        if "runs" not in result["c"]:
                            result["c"]["runs"] = runs
            
            # Check numbering (list) - first in raw, then in payload, then in model...
            numbering = None
            raw_obj = None
            if hasattr(block.content, 'raw'):
                raw_obj = block.content.raw
            
            if raw_obj:
                if isinstance(raw_obj, dict) and 'numbering' in raw_obj:
                    numbering = raw_obj['numbering']
                elif hasattr(raw_obj, 'numbering') and raw_obj.numbering:
                    numbering = raw_obj.numbering
                    if not isinstance(numbering, dict):
                        # Convert to dict if needed
                        numbering = {
                            'id': getattr(numbering, 'id', None),
                            'level': getattr(numbering, 'level', None)
                        }
            elif isinstance(raw, dict) and 'numbering' in raw:
                numbering = raw['numbering']
            elif raw_obj:
                if isinstance(raw_obj, dict) and 'numbering' in raw_obj:
                    numbering = raw_obj['numbering']
                elif hasattr(raw_obj, 'numbering') and raw_obj.numbering:
                    numbering = raw_obj.numbering
                    if not isinstance(numbering, dict):
                        # Convert to dict if needed
                        numbering = {
                            'id': getattr(numbering, 'id', None),
                            'level': getattr(numbering, 'level', None)
                        }
            
            if numbering and isinstance(numbering, dict) and numbering.get('id') and numbering.get('id') != '0':
                list_info = self._serialize_list_info(numbering, raw if isinstance(raw, dict) else (raw_obj if isinstance(raw_obj, dict) else {}))
                if list_info:
                    if not content:
                        result["c"] = {}
                    elif not isinstance(result["c"], dict):
                        result["c"] = {"text": result["c"].get("text", "") if isinstance(result["c"], dict) else ""}
                    result["c"]["list"] = list_info
        
        return result
    
    def _get_style_id(self, style: Dict[str, Any]) -> int:
        """Returns style ID (with deduplication)."""
        if not style:
            return 0
        
        # Hash stylu dla deduplikacji
        style_hash = self._hash_style(style)
        
        if style_hash in self._style_cache:
            return self._style_cache[style_hash]
        
        # Nowy styl
        style_id = self._style_counter
        self._style_counter += 1
        self._style_cache[style_hash] = style_id
        
        # Normalize style (remove None, simplify)
        normalized_style = self._normalize_style(style)
        self._styles_list.append(normalized_style)
        
        return style_id
    
    def _hash_style(self, style: Dict[str, Any]) -> str:
        """Tworzy hash stylu dla deduplikacji."""
        # Sortuj klucze i serializuj
        sorted_items = sorted(style.items())
        style_str = json.dumps(sorted_items, sort_keys=True, default=str)
        return hashlib.md5(style_str.encode()).hexdigest()
    
    def _normalize_style(self, style: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes style (remove None, simplify values)."""
        result = {}
        
        for key, value in style.items():
            if value is None:
                continue
            
            # Simplify values
            if isinstance(value, dict):
                simplified = self._simplify_value(value)
                if simplified:
                    result[key] = simplified
            elif isinstance(value, (list, tuple)):
                if value:
                    result[key] = [self._simplify_value(v) for v in value if v is not None]
            else:
                simplified = self._simplify_value(value)
                if simplified is not None:
                    result[key] = simplified
        
        return result
    
    def _simplify_value(self, value: Any) -> Any:
        """Simplifies value (remove unnecessary nesting)."""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict):
            # If dict has only one value, simplify
            if len(value) == 1:
                return list(value.values())[0]
            # Simplify nested dict
            return {k: self._simplify_value(v) for k, v in value.items() if v is not None}
        if isinstance(value, (list, tuple)):
            return [self._simplify_value(v) for v in value if v is not None]
        if hasattr(value, '__dict__'):
            return {k: self._simplify_value(v) for k, v in value.__dict__.items() 
                   if not k.startswith('_') and v is not None}
        return str(value)
    
    def _find_and_register_media(self, content: Any, block_type: str, context: str = "") -> Optional[int]:
        """

        Searches content for images and registers them in...
        """
        if content is None:
            return None
        
        # Check directly in content
        image_info = self._extract_image_info(content)
        if image_info:
            # Dodaj kontekst do image_info dla lepszej deduplikacji
            if context:
                image_info['_context'] = context
            return self._register_media(image_info, context=context)
        
        # Przeszukaj rekurencyjnie
        return self._search_media_recursive(content, depth=0, max_depth=5, context=context)
    
    def _search_media_recursive(self, obj: Any, depth: int, max_depth: int, context: str = "") -> Optional[int]:
        """Recursively searches object for images."""
        if depth >= max_depth:
            return None
        
        if obj is None:
            return None
        
        # Check if this is image
        image_info = self._extract_image_info(obj)
        if image_info:
            if context:
                image_info['_context'] = context
            return self._register_media(image_info, context=context)
        
        # Przeszukaj dict
        if isinstance(obj, dict):
            for key, value in obj.items():
                # Also check keys - may contain image information
                if isinstance(key, str) and ('image' in key.lower() or 'drawing' in key.lower() or 'media' in key.lower()):
                    media_id = self._search_media_recursive(value, depth + 1, max_depth, context)
                    if media_id is not None:
                        return media_id
                
                media_id = self._search_media_recursive(value, depth + 1, max_depth, context)
                if media_id is not None:
                    return media_id
        
        # Przeszukaj list/tuple
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                media_id = self._search_media_recursive(item, depth + 1, max_depth, context)
                if media_id is not None:
                    return media_id
        
        # Przeszukaj obiekt z atrybutami
        elif hasattr(obj, '__dict__'):
            for key, value in obj.__dict__.items():
                # Also check attribute names
                if isinstance(key, str) and ('image' in key.lower() or 'drawing' in key.lower() or 'media' in key.lower()):
                    media_id = self._search_media_recursive(value, depth + 1, max_depth, context)
                    if media_id is not None:
                        return media_id
                
                if not str(value).startswith('_') and not key.startswith('_'):  # Skip private attributes
                    media_id = self._search_media_recursive(value, depth + 1, max_depth, context)
                    if media_id is not None:
                        return media_id
        
        # Check special attributes
        if hasattr(obj, 'payload'):
            media_id = self._search_media_recursive(obj.payload, depth + 1, max_depth, context)
            if media_id is not None:
                return media_id
        
        if hasattr(obj, 'raw'):
            media_id = self._search_media_recursive(obj.raw, depth + 1, max_depth, context)
            if media_id is not None:
                return media_id
        
        # Check other possible attributes
        for attr_name in ['image', 'drawing', 'media', 'picture', 'graphic']:
            if hasattr(obj, attr_name):
                attr_value = getattr(obj, attr_name)
                media_id = self._search_media_recursive(attr_value, depth + 1, max_depth, context)
                if media_id is not None:
                    return media_id
        
        return None
    
    def _register_media(self, image_info: Dict[str, Any], context: str = "") -> int:
        """Registers image in media (with deduplication)."""
        # Remove context from image_info before saving (we use it only for dedup...
        context_value = image_info.pop('_context', context)
        
        path = image_info.get('path')
        rel_id = image_info.get('rel_id')
        
        # If we have path, use it as key (best deduplication)
        if path and path != 'N/A':
            # Normalizuj path dla deduplikacji
            normalized_path = path
            if '/tmp/' in path and 'word/' in path:
                word_idx = path.find('word/')
                if word_idx >= 0:
                    normalized_path = path[word_idx:]
            media_key = f"path::{normalized_path}"
        elif rel_id:
            # If no path, use rel_id + context (to distinguish rId1 in header...
            # This will allow registering different images with same rel_id in different...
            if context_value:
                media_key = f"rel::{rel_id}::{context_value}"
            else:
                media_key = f"rel::{rel_id}"
        else:
            # No path and rel_id - use hash of entire object
            media_key = self._hash_media(image_info)
        
        if media_key in self._media_cache:
            return self._media_cache[media_key]
        
        # Nowy media
        media_id = self._media_counter
        self._media_counter += 1
        self._media_cache[media_key] = media_id
        
        # Dodaj do listy
        self._media_list.append(image_info)
        
        return media_id
    
    def _extract_image_info(self, content: Any) -> Optional[Dict[str, Any]]:
        """Extracts image information from content."""
        if content is None:
            return None
        
        image_info = {}
        
        # Check object type
        content_type = type(content).__name__.lower()
        is_image_type = ('image' in content_type or 'drawing' in content_type or 
                        'layout' in content_type and hasattr(content, 'path'))
        
        # Extract path/rel_id from various possible locations
        path = None
        rel_id = None
        width = None
        height = None
        
        # Dict
        if isinstance(content, dict):
            path = (content.get("path") or content.get("src") or 
                   content.get("image_path") or content.get("image_src"))
            rel_id = (content.get("relationship_id") or content.get("rel_id") or
                     content.get("relationshipId"))
            width = content.get("width")
            height = content.get("height")
            
            # Check if this is drawing/image in dict
            if not path and not rel_id:
                # May be nested
                if "image" in content:
                    return self._extract_image_info(content["image"])
                if "drawing" in content:
                    return self._extract_image_info(content["drawing"])
        
        # Obiekt
        else:
            # Check various possible attributes
            path = (getattr(content, "path", None) or 
                   getattr(content, "image_path", None) or
                   getattr(content, "src", None) or
                   getattr(content, "image_src", None))
            
            rel_id = (getattr(content, "relationship_id", None) or
                     getattr(content, "rel_id", None) or
                     getattr(content, "relationshipId", None))
            
            width = getattr(content, "width", None)
            height = getattr(content, "height", None)
            
            # If not directly, check if this is ImageLayout or similar
            if not path and not rel_id and is_image_type:
                # Try to extract from other attributes
                if hasattr(content, 'get_src'):
                    path = content.get_src()
                if hasattr(content, 'get_rel_id'):
                    rel_id = content.get_rel_id()
        
        # If not found, but looks like image (has width/height), try...
        if not path and not rel_id:
            # Check if payload has image
            if hasattr(content, 'payload'):
                nested_info = self._extract_image_info(content.payload)
                if nested_info:
                    return nested_info
            
            # If no path/rel_id but has dimensions, may be image without path...
            # (e.g. placeholder) - skip
            return None
        
        # IMPORTANT: If we have only rel_id without path, but rel_id is valid,
        # register it as media (path can be resolved later by PackageReader...)
        # But only if rel_id looks valid (e.g. rId1, rId2, etc.)
        if not path and rel_id and rel_id.startswith('rId'):
            # Register only rel_id - path can be resolved later
            image_info["rel_id"] = rel_id
            if width is not None:
                image_info["width"] = width
            if height is not None:
                image_info["height"] = height
            
            # Extract anchor and scaling information
            anchor_info = self._extract_image_anchor_info(content)
            if anchor_info:
                image_info.update(anchor_info)
            scale_info = self._extract_image_scale_info(content)
            if scale_info:
                image_info.update(scale_info)
            
            return image_info if image_info else None
        
        # Create image_info
        if path:
            image_info["path"] = path
        if rel_id:
            image_info["rel_id"] = rel_id
        if width is not None:
            image_info["width"] = width
        if height is not None:
            image_info["height"] = height
        
        # Extract anchor and scaling information
        anchor_info = self._extract_image_anchor_info(content)
        if anchor_info:
            image_info.update(anchor_info)
        scale_info = self._extract_image_scale_info(content)
        if scale_info:
            image_info.update(scale_info)
        
        return image_info if image_info else None
    
    def _extract_image_anchor_info(self, content: Any) -> Dict[str, Any]:
        """Extracts image anchor information (floating, inline, etc.)."""
        anchor_info = {}
        
        # Check if image is floating/anchored
        if isinstance(content, dict):
            anchor = content.get("anchor") or content.get("anchor_type") or content.get("positioning")
            if anchor:
                anchor_info["anchor"] = anchor
            
            # Check position (for floating images)
            if "x" in content and "y" in content:
                anchor_info["position"] = {
                    "x": content.get("x"),
                    "y": content.get("y")
                }
            
            # Check relation to paragraph/table
            if "anchor_to" in content:
                anchor_info["anchor_to"] = content.get("anchor_to")
            
            # Check anchor_info if available
            if "anchor_info" in content:
                anchor_data = content.get("anchor_info")
                if isinstance(anchor_data, dict):
                    if "anchor_type" in anchor_data:
                        anchor_info["anchor"] = anchor_data.get("anchor_type")
                    if "position" in anchor_data:
                        anchor_info["position"] = anchor_data.get("position")
        elif hasattr(content, 'anchor') or hasattr(content, 'anchor_type'):
            anchor = getattr(content, 'anchor', None) or getattr(content, 'anchor_type', None)
            if anchor:
                anchor_info["anchor"] = anchor
            
            # Check position
            if hasattr(content, 'x') and hasattr(content, 'y'):
                anchor_info["position"] = {
                    "x": getattr(content, 'x'),
                    "y": getattr(content, 'y')
                }
            
            # Check anchor_info
            if hasattr(content, 'anchor_info'):
                anchor_data = getattr(content, 'anchor_info')
                if isinstance(anchor_data, dict):
                    if "anchor_type" in anchor_data:
                        anchor_info["anchor"] = anchor_data.get("anchor_type")
                    if "position" in anchor_data:
                        anchor_info["position"] = anchor_data.get("position")
        
        return anchor_info
    
    def _extract_image_scale_info(self, content: Any) -> Dict[str, Any]:
        """Extracts image scaling information."""
        scale_info = {}
        
        if isinstance(content, dict):
            # Check scale/zoom
            if "scale" in content:
                scale_info["scale"] = content.get("scale")
            if "zoom" in content:
                scale_info["zoom"] = content.get("zoom")
            
            # Check crop
            if "crop" in content:
                crop = content.get("crop")
                if isinstance(crop, dict):
                    scale_info["crop"] = crop
        elif hasattr(content, 'scale') or hasattr(content, 'zoom'):
            scale = getattr(content, 'scale', None) or getattr(content, 'zoom', None)
            if scale:
                scale_info["scale"] = scale
        
        return scale_info
    
    def _collect_all_images_from_package(self):
        """Collects all images from PackageReader (even those not in pipeline..."""
        if not self.package_reader:
            return
        
        # Check all relationship files
        sources = ['word/_rels/document.xml.rels', 'document']
        for i in range(1, 10):
            sources.extend([
                f'word/_rels/header{i}.xml.rels',
                f'word/_rels/footer{i}.xml.rels'
            ])
        
        # Zbierz wszystkie obrazy ze wszystkich relacji
        all_images = {}  # path -> {rel_id, sources}
        
        for source in sources:
            try:
                rels = self.package_reader.get_relationships(source)
                if rels and isinstance(rels, dict):
                    for rel_id, rel_data in rels.items():
                        target = rel_data.get('target') or rel_data.get('Target', '')
                        if target and 'media' in target.lower():
                            # Normalizuj target
                            if not target.startswith('word/'):
                                target = f'word/{target}'
                            
                            # Check if file exists
                            try:
                                if hasattr(self.package_reader, 'extract_to'):
                                    extract_to = self.package_reader.extract_to
                                    from pathlib import Path
                                    full_path = Path(extract_to) / target
                                    if full_path.exists():
                                        full_path_str = str(full_path)
                                        
                                        if full_path_str not in all_images:
                                            all_images[full_path_str] = {
                                                'rel_id': rel_id,
                                                'sources': []
                                            }
                                        all_images[full_path_str]['sources'].append(source)
                            except Exception:
                                pass
            except Exception:
                continue
        
        # Also check directly in _relationships
        if hasattr(self.package_reader, '_relationships'):
            for rels_key, rels_dict in self.package_reader._relationships.items():
                if isinstance(rels_dict, dict):
                    for rel_id, rel_data in rels_dict.items():
                        target = rel_data.get('target') or rel_data.get('Target', '')
                        if target and 'media' in target.lower():
                            if not target.startswith('word/'):
                                target = f'word/{target}'
                            try:
                                if hasattr(self.package_reader, 'extract_to'):
                                    extract_to = self.package_reader.extract_to
                                    from pathlib import Path
                                    full_path = Path(extract_to) / target
                                    if full_path.exists():
                                        full_path_str = str(full_path)
                                        
                                        if full_path_str not in all_images:
                                            all_images[full_path_str] = {
                                                'rel_id': rel_id,
                                                'sources': []
                                            }
                                        all_images[full_path_str]['sources'].append(rels_key)
                            except Exception:
                                pass
        
        # Add all found images to media_list (if not already there)
        for full_path_str, image_data in all_images.items():
            # Check if media with this path already exists
            exists = False
            for existing_media in self._media_list:
                if existing_media.get('path') == full_path_str:
                    exists = True
                    break
            
            if not exists:
                # Dodaj nowy wpis
                new_media = {
                    'path': full_path_str,
                    'rel_id': image_data['rel_id']
                }
                # Use unique context for each source
                context = f"package_{len(image_data['sources'])}"
                self._register_media(new_media, context=context)
    
    def _hash_media(self, media_info: Dict[str, Any]) -> str:
        """Tworzy hash media dla deduplikacji."""
        sorted_items = sorted(media_info.items())
        media_str = json.dumps(sorted_items, sort_keys=True, default=str)
        return hashlib.md5(media_str.encode()).hexdigest()
    
    def _resolve_media_paths(self):
        """Resolves rel_id to paths using PackageReader."""
        if not self.package_reader:
            return
        
        # Check all possible relationship sources
        # PackageReader stores relationships under keys being paths to parts...
        sources = ['word/_rels/document.xml.rels', 'document']
        
        # Add headers and footers
        for i in range(1, 10):  # Check up to 10 headers/footers
            sources.extend([
                f'word/_rels/header{i}.xml.rels',
                f'word/_rels/footer{i}.xml.rels'
            ])
        
        # IMPORTANT: Search all relationships and create media for all images...
        # (not only for those already in _media_list)
        all_image_paths = {}  # rel_id -> {source -> target}
        
        # Collect all image relationships from all sources
        for source in sources:
            try:
                rels = self.package_reader.get_relationships(source)
                if rels and isinstance(rels, dict):
                    for rel_id, rel_data in rels.items():
                        target = rel_data.get('target') or rel_data.get('Target', '')
                        if target and 'media' in target.lower():
                            if rel_id not in all_image_paths:
                                all_image_paths[rel_id] = {}
                            all_image_paths[rel_id][source] = target
            except Exception:
                continue
        
        # Also check directly in _relationships
        if hasattr(self.package_reader, '_relationships'):
            for rels_key, rels_dict in self.package_reader._relationships.items():
                if isinstance(rels_dict, dict):
                    for rel_id, rel_data in rels_dict.items():
                        target = rel_data.get('target') or rel_data.get('Target', '')
                        if target and 'media' in target.lower():
                            if rel_id not in all_image_paths:
                                all_image_paths[rel_id] = {}
                            all_image_paths[rel_id][rels_key] = target
        
        # For each found image, check if already in media_list
        # If not, add it. If yes but has different path, add as new entry...
        for rel_id, sources_dict in all_image_paths.items():
            # Take first target (or check if all are the same)
            targets = list(sources_dict.values())
            if targets:
                target = targets[0]
                # Normalizuj target
                if not target.startswith('word/'):
                    target = f'word/{target}'
                
                # Check if file exists
                try:
                    if hasattr(self.package_reader, 'extract_to'):
                        extract_to = self.package_reader.extract_to
                        from pathlib import Path
                        full_path = Path(extract_to) / target
                        if full_path.exists():
                            full_path_str = str(full_path)
                            
                            # Check if media with this path already exists
                            exists_with_path = False
                            for existing_media in self._media_list:
                                existing_path = existing_media.get('path', '')
                                if existing_path == full_path_str:
                                    exists_with_path = True
                                    break
                            
                            # If doesn't exist, add new entry
                            if not exists_with_path:
                                # Check if media with this rel_id but different path exists
                                exists_with_same_rel_id = False
                                for existing_media in self._media_list:
                                    if existing_media.get('rel_id') == rel_id:
                                        existing_path = existing_media.get('path', '')
                                        if existing_path and existing_path != full_path_str:
                                            # This is different image with same rel_id (different context)
                                            # Dodaj jako nowy wpis
                                            new_media = {
                                                'rel_id': rel_id,
                                                'path': full_path_str
                                            }
                                            media_id = self._register_media(new_media, context=f"resolved_{rel_id}")
                                            exists_with_same_rel_id = True
                                            break
                                        elif existing_path == full_path_str:
                                            exists_with_same_rel_id = True
                                            break
                                
                                # If doesn't exist with this rel_id, add new
                                if not exists_with_same_rel_id:
                                    new_media = {
                                        'rel_id': rel_id,
                                        'path': full_path_str
                                    }
                                    self._register_media(new_media, context=f"resolved_{rel_id}")
                except Exception:
                    pass
        
        # Now update existing media without path
        for media in self._media_list:
            if 'path' not in media or not media.get('path') or media.get('path') == 'N/A':
                rel_id = media.get('rel_id')
                if rel_id and rel_id in all_image_paths:
                    targets = list(all_image_paths[rel_id].values())
                    if targets:
                        target = targets[0]
                        if not target.startswith('word/'):
                            target = f'word/{target}'
                        try:
                            if hasattr(self.package_reader, 'extract_to'):
                                extract_to = self.package_reader.extract_to
                                from pathlib import Path
                                full_path = Path(extract_to) / target
                                if full_path.exists():
                                    # Check if this path is not already used by other media
                                    path_exists = False
                                    for other_media in self._media_list:
                                        if other_media.get('path') == str(full_path):
                                            path_exists = True
                                            break
                                    
                                    if not path_exists:
                                        media['path'] = str(full_path)
                        except Exception:
                            pass
        
        # After resolving path, update cache for media with path
        # (because now we have path, we can use it as key)
        for i, media in enumerate(self._media_list):
            path = media.get('path')
            if path and path != 'N/A':
                # Normalizuj path
                normalized_path = path
                if '/tmp/' in path and 'word/' in path:
                    word_idx = path.find('word/')
                    if word_idx >= 0:
                        normalized_path = path[word_idx:]
                media_key = f"path::{normalized_path}"
                # Update cache if not already there
                if media_key not in self._media_cache:
                    self._media_cache[media_key] = i
    
    def _deduplicate_media_by_path(self):
        """Deduplicates media by path (after resolving rel_id)."""
        # Grupuj media po path
        media_by_path = {}
        for i, media in enumerate(self._media_list):
            path = media.get('path')
            if path and path != 'N/A':
                # Normalize path (remove /tmp/... if present)
                normalized_path = path
                if '/tmp/' in path and 'word/' in path:
                    word_idx = path.find('word/')
                    if word_idx >= 0:
                        normalized_path = path[word_idx:]
                elif not normalized_path.startswith('word/'):
                    normalized_path = f'word/{normalized_path}' if 'media' in normalized_path else normalized_path
                
                if normalized_path not in media_by_path:
                    media_by_path[normalized_path] = []
                media_by_path[normalized_path].append((i, media))
        
        # If there are duplicates (same path, different rel_id), keep only one
        # i zaktualizuj cache
        duplicates_to_remove = []
        for normalized_path, entries in media_by_path.items():
            if len(entries) > 1:
                # Keep first, remove rest
                first_idx, first_media = entries[0]
                for other_idx, other_media in entries[1:]:
                    duplicates_to_remove.append(other_idx)
                    # Zaktualizuj cache - przekieruj ID duplikatu na pierwszy
                    other_media_id = None
                    for key, media_id in self._media_cache.items():
                        if media_id == other_idx:
                            other_media_id = media_id
                            # Przekieruj na pierwszy
                            self._media_cache[key] = first_idx
                            break
        
        # Remove duplicates (in reverse order to not change indices)
        for idx in sorted(duplicates_to_remove, reverse=True):
            self._media_list.pop(idx)
            # Update cache - decrease ID for all after removed
            for key in list(self._media_cache.keys()):
                if self._media_cache[key] > idx:
                    self._media_cache[key] -= 1
                elif self._media_cache[key] == idx:
                    # Przekieruj na pierwszy z grupy
                    del self._media_cache[key]
    
    def _serialize_content(self, content: Any, depth: int = 0, block_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """

        Serializes content with simplification.

        Priority...
        """
        if content is None:
            return None
        
        if depth >= self.max_content_depth:
            return {"type": "truncated", "depth": depth}
        
        # BEFORE serialization - check if content has images and register them
        # (this is important because images can be in nested structures)
        self._find_and_register_media(content, block_type or "", context=block_type or "")
        
        # BlockContent wrapper
        if hasattr(content, 'payload') and hasattr(content, 'raw'):
            return self._serialize_block_content(content, depth)
        
        # ParagraphLayout - extract text
        if hasattr(content, 'lines'):
            return self._serialize_paragraph_layout(content, depth)
        
        # TableLayout - extract table structure
        if hasattr(content, 'rows'):
            return self._serialize_table_layout(content, depth)
        
        # Check if payload is TableLayout
        if hasattr(content, 'payload') and hasattr(content.payload, 'rows'):
            return self._serialize_table_layout(content.payload, depth)
        
        # ImageLayout - extract image information
        if hasattr(content, 'path') or hasattr(content, 'image_path') or hasattr(content, 'rel_id'):
            # This may be ImageLayout - extract image information
            image_info = self._extract_image_info(content)
            if image_info:
                # Zarejestruj obraz w media_list
                media_id = self._register_media(image_info, context="serialize_content")
                result = {
                    "type": "image",
                    "rel_id": image_info.get("rel_id"),
                    "width": image_info.get("width"),
                    "height": image_info.get("height"),
                    "anchor": image_info.get("anchor"),
                    "path": image_info.get("path"),
                    "media_id": media_id
                }
                return result
        
        # GenericLayout - extract data
        if hasattr(content, 'data'):
            return self._serialize_generic_layout(content, depth)
        
        # Obiekt z __dict__
        if hasattr(content, '__dict__'):
            return self._serialize_object(content, depth)
        
        # Podstawowe typy
        if isinstance(content, (str, int, float, bool)):
            return {"value": content}
        
        # Last resort - but DON'T use str() for complex objects
        # Instead try to extract important fields
        if hasattr(content, '__dict__'):
            # Try to extract important fields from __dict__
            obj_dict = content.__dict__
            result = {"type": type(content).__name__}
            for key in ['text', 'data', 'content', 'style', 'blocks', 'payload', 'raw']:
                if key in obj_dict:
                    value = obj_dict[key]
                    if value is not None:
                        serialized = self._serialize_content(value, depth + 1)
                        if serialized:
                            result[key] = serialized
            if len(result) > 1:  # Has more than just 'type'
                return result
        
        # If everything else failed, return minimal object
        return {"type": type(content).__name__}
    
    def _serialize_block_content(self, block_content: Any, depth: int) -> Dict[str, Any]:
        """Serializes BlockContent with full information about runs, lists, etc."""
        payload = block_content.payload
        raw = block_content.raw
        
        # IMPORTANT: Search raw for images (may be in footers, headers...)
        if raw:
            self._find_and_register_media(raw, "block_content_raw", context="raw")
        
        # IMPORTANT: For tables - ALWAYS check raw BEFORE payload
        # raw contains Table model with rows, payload may be TableLayout with empty...
        # Table inherits from Body, so has children (TableRow), which have cells...
        
        # IMPORTANT: For tables - ALWAYS check raw BEFORE payload
        # raw contains Table model with rows, payload may be TableLayout with empty...
        # Table inherits from Body, so has children (TableRow), which have cells...
        # NOTE: raw may be dict (serialized) with TableRow objects in rows
        if raw:
            # Check if raw is dict (may already be serialized)
            if isinstance(raw, dict):
                # Check if dict has table information
                if 'type' in raw and raw.get('type') == 'table':
                    rows = raw.get('rows', [])
                    # Check if rows are TableRow objects (not dict)
                    if rows and not isinstance(rows[0], dict):
                        # rows to obiekty TableRow - zserializuj je
                        table_data = self._serialize_table_from_raw(raw, depth)
                        if isinstance(table_data, dict):
                            table_data["type"] = "table"
                        if table_data.get("rows"):
                            return table_data
                    elif rows:
                        # rows are already dict - use directly
                        return raw
                elif 'rows' in raw:
                    rows = raw.get('rows', [])
                    if rows:
                        # Check if rows are TableRow objects (not dict)
                        if not isinstance(rows[0], dict):
                            # rows to obiekty TableRow - zserializuj je
                            table_data = self._serialize_table_from_raw(raw, depth)
                            if isinstance(table_data, dict):
                                table_data["type"] = "table"
                            if table_data.get("rows"):
                                return table_data
                        else:
                            # rows are already dict - use directly
                            return raw
            
            # Check if raw is Table model (has rows OR children with TableRow)
            is_table = False
            debug_info = {}
            
            # Check if this is Table model by class name
            if hasattr(raw, '__class__'):
                class_name = raw.__class__.__name__
                debug_info['class_name'] = class_name
                if 'Table' in class_name and class_name != 'TableLayout':
                    is_table = True
                    debug_info['is_table_by_class'] = True
            
            # Check if has rows (standard structure) - even if empty, it may be...
            if hasattr(raw, 'rows'):
                debug_info['has_rows'] = True
                debug_info['rows_value'] = raw.rows
                debug_info['rows_len'] = len(raw.rows) if raw.rows else 0
                is_table = True
            
            # Check if has children which are TableRow (Table inherits from Body)
            if hasattr(raw, 'children'):
                debug_info['has_children'] = True
                debug_info['children_value'] = raw.children
                debug_info['children_len'] = len(raw.children) if raw.children else 0
                if raw.children:
                    first_child = raw.children[0] if raw.children else None
                    if first_child:
                        debug_info['first_child_class'] = first_child.__class__.__name__
                        debug_info['first_child_has_cells'] = hasattr(first_child, 'cells')
                        if hasattr(first_child, 'cells'):
                            debug_info['first_child_cells_len'] = len(first_child.cells) if first_child.cells else 0
                        if first_child and hasattr(first_child, 'cells'):
                            # children are TableRow, which have cells
                            is_table = True
            
            if is_table:
                try:
                    table_data = self._serialize_table_from_raw(raw, depth)
                    # Ensure type is "table"
                    if isinstance(table_data, dict):
                        table_data["type"] = "table"
                    # Check if table_data has rows (cannot be empty)
                    if table_data.get("rows"):
                        return table_data
                except (AttributeError, TypeError, Exception) as e:
                    # If error, try further
                    pass
        
        # Check if payload is TableLayout - serialize directly
        # NOTE: TableLayout.rows may be empty, but check if there is data
        if hasattr(payload, 'rows'):
            rows = payload.rows
            # Check if rows are not empty
            if rows and len(rows) > 0:
                table_data = self._serialize_table_layout(payload, depth)
                # Ensure type is "table"
                if isinstance(table_data, dict):
                    table_data["type"] = "table"
                return table_data
        
        # IMPORTANT: Check if payload is ImageLayout - serialize as image
        if hasattr(payload, 'path') or hasattr(payload, 'image_path') or hasattr(payload, 'rel_id'):
            # This may be ImageLayout - extract image information
            image_info = self._extract_image_info(payload)
            if image_info:
                # Zarejestruj obraz w media_list
                media_id = self._register_media(image_info, context="block_content_payload")
                result = {
                    "type": "image",
                    "rel_id": image_info.get("rel_id"),
                    "width": image_info.get("width"),
                    "height": image_info.get("height"),
                    "anchor": image_info.get("anchor"),
                    "path": image_info.get("path"),
                    "media_id": media_id
                }
                return result
        
        result = {
            "type": "BlockContent"
        }
        
        # Serialize payload (main content)
        payload_data = self._serialize_content(payload, depth + 1)
        if payload_data:
            result["payload"] = payload_data
        
        # For paragraphs - extract runs with formatting from raw
        # Check numbering in different places (raw may be dict or object)
        numbering = None
        if raw:
            if isinstance(raw, dict):
                # Check if raw has runs_payload (from LayoutEngine)
                if 'runs_payload' in raw:
                    runs = self._serialize_runs_from_payload(raw['runs_payload'])
                    if runs:
                        if 'payload' not in result:
                            result["payload"] = {}
                        result["payload"]["runs"] = runs
                
                # Check if raw has numbering (list)
                if 'numbering' in raw:
                    numbering = raw['numbering']
            elif hasattr(raw, 'numbering') and raw.numbering:
                # Raw to obiekt z atrybutem numbering
                numbering = raw.numbering
                if not isinstance(numbering, dict):
                    # Convert to dict if needed
                    numbering = {
                        'id': getattr(numbering, 'id', None),
                        'level': getattr(numbering, 'level', None)
                    }
        
        # If we have numbering, serialize list info
        if numbering and isinstance(numbering, dict):
            list_info = self._serialize_list_info(numbering, raw if isinstance(raw, dict) else {})
            if list_info:
                # Add directly to result, not in payload
                result["list"] = list_info
            
            # Check if raw has paragraph properties (spacing, tabs, etc.)
            if 'style' in raw or 'properties' in raw:
                para_props = self._serialize_paragraph_properties(raw)
                if para_props:
                    if 'payload' not in result:
                        result["payload"] = {}
                    result["payload"]["paragraph_properties"] = para_props
        
        # For tables - always check raw (even if include_raw_content=False)
        # because tables may be stored in raw
        if raw:
            raw_type_name = type(raw).__name__.lower() if hasattr(raw, '__class__') else str(type(raw)).lower()
            if isinstance(raw, dict):
                raw_type_name = raw.get('type', '').lower()
            
            if 'table' in raw_type_name:
                # Check if raw has rows (Table model)
                has_rows = False
                rows_count = 0
                
                if hasattr(raw, 'rows'):
                    rows = raw.rows
                    has_rows = rows and len(rows) > 0
                    if has_rows:
                        rows_count = len(rows)
                
                elif isinstance(raw, dict) and 'rows' in raw:
                    rows = raw['rows']
                    has_rows = rows and len(rows) > 0
                    if has_rows:
                        rows_count = len(rows)
                
                if has_rows:
                    # Table in raw - serialize and add directly to result (not in payload...)
                    table_data = self._serialize_table_from_raw(raw, depth)
                    # Merge with result (override if already exists)
                    if 'rows' in table_data and table_data['rows']:
                        result["rows"] = table_data["rows"]
                    # Add table properties directly to result
                    for key in ['borders', 'columns', 'cell_margins', 'cell_spacing', 'alignment', 'style', 'type']:
                        if key in table_data:
                            result[key] = table_data[key]
                    # Ensure type is "table"
                    result["type"] = "table"
                    # Remove payload if was added earlier (table should be directly...
                    if 'payload' in result:
                        del result["payload"]
                    # Return result instead of continuing (table is already fully serialized...)
                    return result
            elif self.include_raw_content:
                result["raw_type"] = type(raw).__name__ if hasattr(raw, '__class__') else str(type(raw))
                if isinstance(raw, dict) and 'id' in raw:
                    result["raw_id"] = raw['id']
                elif hasattr(raw, 'id'):
                    result["raw_id"] = raw.id
        
        return result
    
    def _serialize_runs_from_payload(self, runs_payload: List[Any]) -> List[Dict[str, Any]]:
        """Serializes runs from runs_payload with full formatting."""
        runs = []
        for run in runs_payload:
            if isinstance(run, dict):
                run_data = {
                    "text": run.get("text", "")
                }
                
                # Run-level formatting
                run_style = run.get("style", {})
                if isinstance(run_style, dict):
                    if run_style.get('bold'):
                        run_data['bold'] = True
                    if run_style.get('italic'):
                        run_data['italic'] = True
                    if run_style.get('underline'):
                        run_data['underline'] = run_style.get('underline')
                    if run_style.get('font_name'):
                        run_data['font_name'] = run_style.get('font_name')
                    # Font fallbacks
                    if run_style.get('font_ascii'):
                        run_data['font_ascii'] = run_style.get('font_ascii')
                    if run_style.get('font_hAnsi'):
                        run_data['font_hAnsi'] = run_style.get('font_hAnsi')
                    if run_style.get('font_cs'):
                        run_data['font_cs'] = run_style.get('font_cs')
                    if run_style.get('font_eastAsia'):
                        run_data['font_eastAsia'] = run_style.get('font_eastAsia')
                    if run_style.get('font_size'):
                        run_data['font_size'] = run_style.get('font_size')
                    if run_style.get('font_size_cs'):
                        run_data['font_size_cs'] = run_style.get('font_size_cs')
                    if run_style.get('color'):
                        run_data['color'] = run_style.get('color')
                    if run_style.get('highlight'):
                        run_data['highlight'] = run_style.get('highlight')
                    if run_style.get('superscript'):
                        run_data['superscript'] = True
                    if run_style.get('subscript'):
                        run_data['subscript'] = True
                    if run_style.get('strike_through') or run_style.get('strikethrough'):
                        run_data['strike_through'] = True
                    # Character spacing and kerning
                    if run_style.get('spacing'):
                        run_data['character_spacing'] = run_style.get('spacing')
                    if run_style.get('kern'):
                        run_data['kerning'] = run_style.get('kern')
                    if run_style.get('position'):
                        run_data['position'] = run_style.get('position')  # Vertical position
                
                # Also check directly in run
                for key in ['bold', 'italic', 'underline', 'font_name', 'font_size', 'color', 'highlight', 'superscript', 'subscript', 'strike_through']:
                    if key in run:
                        run_data[key] = run[key]
                
                # Footnotes/Endnotes
                if run.get('footnote_refs'):
                    run_data['footnote_refs'] = run.get('footnote_refs')
                if run.get('endnote_refs'):
                    run_data['endnote_refs'] = run.get('endnote_refs')
                
                # Hyperlinks
                if run.get('hyperlink'):
                    hyperlink = run.get('hyperlink')
                    if isinstance(hyperlink, dict):
                        run_data['hyperlink'] = {
                            'id': hyperlink.get('id'),
                            'target': hyperlink.get('target'),
                            'target_mode': hyperlink.get('target_mode')
                        }
                    else:
                        # Hyperlink may be object
                        run_data['hyperlink'] = {
                            'id': getattr(hyperlink, 'id', None),
                            'target': getattr(hyperlink, 'target', None),
                            'target_mode': getattr(hyperlink, 'target_mode', None)
                        }
                
                # Also check in children (hyperlinks may be in children)
                if run.get('children'):
                    for child in run.get('children', []):
                        if isinstance(child, dict) and child.get('type') == 'hyperlink':
                            run_data['hyperlink'] = {
                                'id': child.get('id'),
                                'target': child.get('target'),
                                'target_mode': child.get('target_mode')
                            }
                        elif hasattr(child, '__class__') and 'Hyperlink' in child.__class__.__name__:
                            run_data['hyperlink'] = {
                                'id': getattr(child, 'id', None),
                                'target': getattr(child, 'target', None),
                                'target_mode': getattr(child, 'target_mode', None)
                            }
                
                # Fields
                if run.get('fields'):
                    run_data['fields'] = run.get('fields')
                
                # Tabs i breaks
                if run.get('has_tab'):
                    run_data['has_tab'] = True
                if run.get('has_break'):
                    run_data['has_break'] = True
                    if run.get('break_type'):
                        run_data['break_type'] = run.get('break_type')
                
                runs.append(run_data)
            elif hasattr(run, 'text'):
                # Run object
                run_data = {
                    "text": run.text or ""
                }
                
                # Formatting from attributes
                if hasattr(run, 'bold') and run.bold:
                    run_data['bold'] = True
                if hasattr(run, 'italic') and run.italic:
                    run_data['italic'] = True
                if hasattr(run, 'underline') and run.underline:
                    run_data['underline'] = run.underline
                if hasattr(run, 'font_name') and run.font_name:
                    run_data['font_name'] = run.font_name
                if hasattr(run, 'font_size') and run.font_size:
                    run_data['font_size'] = run.font_size
                if hasattr(run, 'color') and run.color:
                    run_data['color'] = run.color
                if hasattr(run, 'highlight') and run.highlight:
                    run_data['highlight'] = run.highlight
                if hasattr(run, 'superscript') and run.superscript:
                    run_data['superscript'] = True
                if hasattr(run, 'subscript') and run.subscript:
                    run_data['subscript'] = True
                if hasattr(run, 'strike_through') and run.strike_through:
                    run_data['strike_through'] = True
                
                # Footnotes/Endnotes
                if hasattr(run, 'footnote_refs') and run.footnote_refs:
                    run_data['footnote_refs'] = run.footnote_refs
                if hasattr(run, 'endnote_refs') and run.endnote_refs:
                    run_data['endnote_refs'] = run.endnote_refs
                
                # Hyperlinks
                if hasattr(run, 'children') and run.children:
                    for child in run.children:
                        if hasattr(child, '__class__') and 'Hyperlink' in child.__class__.__name__:
                            run_data['hyperlink'] = {
                                'id': getattr(child, 'id', None),
                                'target': getattr(child, 'target', None),
                                'target_mode': getattr(child, 'target_mode', None)
                            }
                        elif isinstance(child, dict) and child.get('type') == 'hyperlink':
                            run_data['hyperlink'] = {
                                'id': child.get('id'),
                                'target': child.get('target'),
                                'target_mode': child.get('target_mode')
                            }
                
                runs.append(run_data)
        
        return runs
    
    def _serialize_list_info(self, numbering: Dict[str, Any], raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Serializes list information (numbering)."""
        num_id = numbering.get('id')
        level = numbering.get('level')
        
        if not num_id or num_id == '0':
            return None
        
        list_info = {
            "type": "ordered",  # Default ordered, will check format
            "level": int(level) if level else 0,
            "numbering_id": str(num_id)
        }
        
        # Check marker if available
        if 'marker' in raw:
            marker = raw['marker']
            if isinstance(marker, dict):
                marker_text = marker.get('text', '')
                if marker_text:
                    list_info['marker'] = marker_text
                
                # Check format
                format_type = marker.get('format', 'decimal')
                if format_type in ['bullet', 'none', 'nothing']:
                    list_info['type'] = 'unordered'
                else:
                    list_info['type'] = 'ordered'
                    list_info['format'] = format_type
        
        # Check indent from numbering metrics
        if 'numbering_metrics' in raw:
            metrics = raw['numbering_metrics']
            if isinstance(metrics, dict):
                if metrics.get('indent_left'):
                    list_info['indent_left'] = metrics.get('indent_left')
                if metrics.get('indent_hanging'):
                    list_info['indent_hanging'] = metrics.get('indent_hanging')
        
        return list_info
    
    def _serialize_paragraph_properties(self, raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Serializes paragraph properties (spacing, tabs, page breaks, etc.)."""
        props = {}
        
        # Spacing
        style = raw.get('style', {})
        if isinstance(style, dict):
            spacing = style.get('spacing', {})
            if spacing:
                if spacing.get('before'):
                    props['spacing_before'] = spacing.get('before')
                if spacing.get('after'):
                    props['spacing_after'] = spacing.get('after')
                if spacing.get('line'):
                    props['line_height'] = spacing.get('line')
                if spacing.get('line_rule'):
                    props['line_height_rule'] = spacing.get('line_rule')
                if spacing.get('beforeLines'):
                    props['spacing_before_lines'] = spacing.get('beforeLines')
                if spacing.get('afterLines'):
                    props['spacing_after_lines'] = spacing.get('afterLines')
            
            # Indentation
            indent = style.get('indent', {})
            if indent:
                if indent.get('left'):
                    props['indent_left'] = indent.get('left')
                if indent.get('right'):
                    props['indent_right'] = indent.get('right')
                if indent.get('firstLine'):
                    props['indent_first_line'] = indent.get('firstLine')
                if indent.get('hanging'):
                    props['indent_hanging'] = indent.get('hanging')
        
        # Page breaks
        if raw.get('page_break_before'):
            props['page_break_before'] = True
        if raw.get('page_break_after'):
            props['page_break_after'] = True
        
        # Keep with next/keep together
        if raw.get('keep_with_next'):
            props['keep_with_next'] = True
        if raw.get('keep_together'):
            props['keep_together'] = True
        
        # Tabs
        if 'tabs' in style:
            tabs = style.get('tabs', [])
            if tabs:
                props['tabs'] = tabs
        elif 'tabs' in raw:
            tabs = raw.get('tabs', [])
            if tabs:
                props['tabs'] = tabs
        
        # Alignment
        if 'alignment' in style:
            props['alignment'] = style.get('alignment')
        elif 'alignment' in raw:
            props['alignment'] = raw.get('alignment')
        
        # Widow/orphan control
        if 'widow_control' in style:
            props['widow_control'] = style.get('widow_control')
        if 'orphan_control' in style:
            props['orphan_control'] = style.get('orphan_control')
        
        # Line spacing rule (keep-lines-together)
        if 'keep_lines_together' in raw:
            props['keep_lines_together'] = raw.get('keep_lines_together')
        
        return props if props else None
    
    def _serialize_table_from_raw(self, table: Any, depth: int) -> Dict[str, Any]:
        """Serializes table from raw object (Table model) or dict with full structure..."""
        result = {
            "type": "table",
            "rows": []
        }
        row_props: List[Dict[str, Any]] = []
        
        # Check if table is dict (may already be serialized)
        if isinstance(table, dict):
            # Dict already has table structure - extract rows
            rows = table.get('rows', [])
            
            # Extract table properties from dict
            if 'grid' in table:
                result['columns'] = self._serialize_table_grid(table['grid'])
            if 'style' in table:
                result['style'] = table['style']
            
            # Serialize rows (may be TableRow objects)
            for row in rows:
                row_data = []
                # Check if row is TableRow object or dict
                if hasattr(row, 'cells'):
                    # row to obiekt TableRow
                    for cell in row.cells:
                        cell_content = self._serialize_cell_from_raw(cell)
                        cell_merge_info = self._extract_cell_merge_info(cell)
                        if cell_merge_info:
                            cell_content.update(cell_merge_info)
                        row_data.append(cell_content)
                elif isinstance(row, (list, tuple)):
                    # row to lista cells
                    for cell in row:
                        cell_content = self._serialize_cell_from_raw(cell)
                        cell_merge_info = self._extract_cell_merge_info(cell)
                        if cell_merge_info:
                            cell_content.update(cell_merge_info)
                        row_data.append(cell_content)
                elif isinstance(row, dict):
                    # row is dict - use directly
                    row_data = row.get('cells', [])
                
                if row_data:
                    result["rows"].append(row_data)
                    row_props.append(self._extract_row_properties(row))
            
            if row_props and any(row_props):
                while len(row_props) < len(result["rows"]):
                    row_props.append({})
                result["row_properties"] = row_props
            table_properties = self._build_table_properties_dict(result, table, table.get("style"))
            if table_properties:
                result["properties"] = table_properties
            return result
        
        # Extract table properties
        table_props = self._extract_table_properties_from_raw(table)
        if table_props:
            result.update(table_props)
        style_dict = None
        if isinstance(table, dict):
            style_dict = table.get("style")
        elif hasattr(table, "style") and isinstance(table.style, dict):
            style_dict = table.style
        
        # DEBUG: Check table structure
        debug_info = {
            'has_rows': hasattr(table, 'rows'),
            'has_children': hasattr(table, 'children'),
        }
        if hasattr(table, 'rows'):
            debug_info['rows_value'] = table.rows
            debug_info['rows_len'] = len(table.rows) if table.rows else 0
        if hasattr(table, 'children'):
            debug_info['children_value'] = table.children
            debug_info['children_len'] = len(table.children) if table.children else 0
            if table.children:
                first_child = table.children[0]
                debug_info['first_child_class'] = first_child.__class__.__name__
                debug_info['first_child_has_cells'] = hasattr(first_child, 'cells')
                if hasattr(first_child, 'cells'):
                    debug_info['first_child_cells_len'] = len(first_child.cells) if first_child.cells else 0
        
        logger.debug(f"_serialize_table_from_raw debug: {debug_info}")
        
        # Method 1: Check if table has rows (standard Table.rows structure)
        if hasattr(table, 'rows') and table.rows:
            logger.debug(f"Using method 1: table.rows (len={len(table.rows)})")
            for row in table.rows:
                row_data = []
                if hasattr(row, 'cells') and row.cells:
                    for cell in row.cells:
                        cell_content = self._serialize_cell_from_raw(cell)
                        # Dodaj informacje o merged cells
                        cell_merge_info = self._extract_cell_merge_info(cell)
                        if cell_merge_info:
                            cell_content.update(cell_merge_info)
                        row_data.append(cell_content)
                elif isinstance(row, (list, tuple)):
                    for cell in row:
                        cell_content = self._serialize_cell_from_raw(cell)
                        cell_merge_info = self._extract_cell_merge_info(cell)
                        if cell_merge_info:
                            cell_content.update(cell_merge_info)
                        row_data.append(cell_content)
                if row_data:  # Add only if row has cells
                    result["rows"].append(row_data)
                    row_props.append(self._extract_row_properties(row))
        
        # Method 2: If rows is empty, check children (Table inherits from Body...)
        # Table.children are TableRow, which have cells
        elif hasattr(table, 'children') and table.children:
            # Zbierz wszystkie cells z children (TableRow) i zgrupuj w rows
            for child in table.children:
                # child to TableRow
                if hasattr(child, 'cells') and child.cells:
                    row_data = []
                    for cell in child.cells:
                        cell_content = self._serialize_cell_from_raw(cell)
                        # Dodaj informacje o merged cells
                        cell_merge_info = self._extract_cell_merge_info(cell)
                        if cell_merge_info:
                            cell_content.update(cell_merge_info)
                        row_data.append(cell_content)
                    if row_data:
                        result["rows"].append(row_data)
                        row_props.append(self._extract_row_properties(child))
        
        # Method 3: If children are directly cells (rare case)
        elif hasattr(table, 'children') and table.children:
            # Check if children are TableCell (directly)
            cells = []
            for child in table.children:
                # Check if this is TableCell
                if hasattr(child, 'cells') or (hasattr(child, '__class__') and 'TableCell' in child.__class__.__name__):
                    cells.append(child)
            
            # If we have cells, group them into rows based on position
            # (this requires additional logic, but for now just create one row)
            if cells:
                row_data = []
                for cell in cells:
                    cell_content = self._serialize_cell_from_raw(cell)
                    cell_merge_info = self._extract_cell_merge_info(cell)
                    if cell_merge_info:
                        cell_content.update(cell_merge_info)
                    row_data.append(cell_content)
                if row_data:
                    result["rows"].append(row_data)
        
        if row_props and any(row_props):
            while len(row_props) < len(result["rows"]):
                row_props.append({})
            result["row_properties"] = row_props
        table_properties = self._build_table_properties_dict(result, table_props, style_dict)
        if table_properties:
            result["properties"] = table_properties
        
        return result
    
    def _extract_table_properties_from_raw(self, table: Any) -> Dict[str, Any]:
        """Extracts table properties from raw Table model."""
        props = {}
        
        # Check properties
        if hasattr(table, 'properties') and table.properties:
            table_props = table.properties
            if hasattr(table_props, 'borders') and table_props.borders:
                props['borders'] = self._serialize_borders(table_props.borders)
            if hasattr(table_props, 'cell_margins') and table_props.cell_margins:
                props['cell_margins'] = self._serialize_margins(table_props.cell_margins)
            if hasattr(table_props, 'cell_spacing') and table_props.cell_spacing:
                props['cell_spacing'] = table_props.cell_spacing
            if hasattr(table_props, 'alignment') and table_props.alignment:
                props['alignment'] = table_props.alignment
            if hasattr(table_props, 'style') and table_props.style:
                props['style'] = table_props.style
            if hasattr(table_props, 'grid') and table_props.grid:
                props['columns'] = self._serialize_table_grid(table_props.grid)
        
        # Check grid directly
        if hasattr(table, 'grid') and table.grid:
            props['columns'] = self._serialize_table_grid(table.grid)
        
        # Check style directly
        if hasattr(table, 'style'):
            style = table.style
            if isinstance(style, dict):
                if style.get('borders'):
                    props['borders'] = self._serialize_borders(style.get('borders'))
                if style.get('cell_margins'):
                    props['cell_margins'] = self._serialize_margins(style.get('cell_margins'))
        
        return props
    
    def _serialize_cell_from_raw(self, cell: Any) -> Dict[str, Any]:
        """Serializes cell from raw object (TableCell model)."""
        result = {
            "text": "",
            "blocks": []
        }
        
        # Extract text from cell
        if hasattr(cell, 'get_text'):
            result["text"] = cell.get_text() or ''
        elif hasattr(cell, 'text'):
            result["text"] = str(cell.text) or ''
        
        # Extract content (paragraphs, tables, images)
        if hasattr(cell, 'children'):
            for child in cell.children:
                block_data = self._serialize_cell_element(child)
                if block_data:
                    result["blocks"].append(block_data)
        elif hasattr(cell, 'paragraphs'):
            for para in cell.paragraphs:
                block_data = self._serialize_cell_element(para)
                if block_data:
                    result["blocks"].append(block_data)
        
        # IMPORTANT: Add cell properties (margins, borders, colspan, rowspan)
        cell_merge_info = self._extract_cell_merge_info(cell)
        if cell_merge_info:
            result.update(cell_merge_info)
        
        # Remove empty blocks
        if not result["blocks"]:
            del result["blocks"]
        
        return result
    
    def _serialize_cell_element(self, element: Any) -> Optional[Dict[str, Any]]:
        """Serializes element in cell (paragraph, table, image)."""
        if element is None:
            return None
        
        result = {}
        
        # Check element type
        element_type = type(element).__name__.lower()
        
        if 'paragraph' in element_type:
            result["type"] = "paragraph"
            if hasattr(element, 'get_text'):
                result["text"] = element.get_text() or ''
            elif hasattr(element, 'text'):
                result["text"] = str(element.text) or ''
        elif 'table' in element_type:
            result["type"] = "table"
            if hasattr(element, 'rows'):
                result["rows"] = self._serialize_table_from_raw(element, depth=0)["rows"]
        elif 'image' in element_type or 'drawing' in element_type:
            result["type"] = "image"
            # Extract image information
            if hasattr(element, 'get_src'):
                result["src"] = element.get_src() or ''
            if hasattr(element, 'rel_id'):
                result["rel_id"] = element.rel_id
        
        return result if result else None
    
    def _serialize_paragraph_layout(self, paragraph: Any, depth: int) -> Dict[str, Any]:
        """Serializes ParagraphLayout - extracts text and runs with formatting."""
        result = {
            "type": "paragraph",
            "text": ""
        }
        
        # IMPORTANT: Search paragraph for images (may be inline in runs...)
        self._find_and_register_media(paragraph, "paragraph", context="paragraph")
        
        text_parts = []
        runs = []
        
        if hasattr(paragraph, 'lines'):
            for line in paragraph.lines:
                # Search line
                self._find_and_register_media(line, "paragraph_line", context="paragraph_line")
                
                if hasattr(line, 'items'):
                    for item in line.items:
                        # Search each item (may contain images in runs)
                        self._find_and_register_media(item, "paragraph_item", context="paragraph_item")
                        
                        if hasattr(item, 'data') and isinstance(item.data, dict):
                            item_text = item.data.get('text', '')
                            if item_text:
                                text_parts.append(item_text)
                                
                                # Extract formatting from item.data if available
                                run_data = self._extract_run_from_item(item)
                                if run_data:
                                    runs.append(run_data)
        
        if text_parts:
            result["text"] = ' '.join(text_parts)
        
        # IMPORTANT: Add runs directly to result (not in payload)
        if runs:
            result["runs"] = runs
        
        # Add minimal metadata if needed
        if self.include_raw_content and hasattr(paragraph, 'style'):
            result["style_ref"] = getattr(paragraph.style, 'name', None)
        
        return result
    
    def _extract_run_from_item(self, item: Any) -> Optional[Dict[str, Any]]:
        """Extracts run information from item (for formatting)."""
        if not hasattr(item, 'data') or not isinstance(item.data, dict):
            return None
        
        data = item.data
        text = data.get('text', '')
        if not text:
            return None
        
        run = {
            "text": text
        }
        
        # Extract formatting from data
        if 'style' in data:
            style = data['style']
            if isinstance(style, dict):
                # Run-level formatting
                if style.get('bold'):
                    run['bold'] = True
                if style.get('italic'):
                    run['italic'] = True
                if style.get('underline'):
                    run['underline'] = style.get('underline')
                if style.get('font_name'):
                    run['font_name'] = style.get('font_name')
                if style.get('font_size'):
                    run['font_size'] = style.get('font_size')
                if style.get('color'):
                    run['color'] = style.get('color')
                if style.get('highlight'):
                    run['highlight'] = style.get('highlight')
                if style.get('superscript'):
                    run['superscript'] = True
                if style.get('subscript'):
                    run['subscript'] = True
                if style.get('strike_through') or style.get('strikethrough'):
                    run['strike_through'] = True
        
        # Also check directly in data
        for key in ['bold', 'italic', 'underline', 'font_name', 'font_size', 'color', 'highlight']:
            if key in data:
                run[key] = data[key]
        
        return run if len(run) > 1 else None  # Return only if has formatting
    
    def _serialize_table_layout(self, table: Any, depth: int) -> Dict[str, Any]:
        """Serializes TableLayout - extracts full table structure with borders, columns..."""
        result = {
            "type": "table",
            "rows": []
        }
        
        # IMPORTANT: Search entire table for images
        self._find_and_register_media(table, "table", context="table")
        
        # Extract table properties
        table_props = self._extract_table_properties(table)
        if table_props:
            result.update(table_props)
        style_dict = None
        if isinstance(table, dict):
            style_dict = table.get("style")
        elif hasattr(table, "style") and isinstance(table.style, dict):
            style_dict = table.style
        
        # Check various possible TableLayout structures
        rows_data = []
        row_props: List[Dict[str, Any]] = []
        
        # Opcja 1: table.rows (TableLayout z rows: List[List[TableCellLayout]])
        if hasattr(table, 'rows'):
            rows = table.rows
            # TableLayout.rows to List[List[TableCellLayout]]
            if rows:
                for row in rows:
                    # Przeszukaj wiersz
                    self._find_and_register_media(row, "table_row")
                    
                    row_data = []
                    # Row to lista TableCellLayout
                    if isinstance(row, (list, tuple)):
                        for cell in row:
                            # cell to TableCellLayout - serializuj go
                            cell_content = self._serialize_table_cell_layout(cell)
                            if cell_content:
                                row_data.append(cell_content)
                    # Alternatively, row may be TableRow with cells
                    elif hasattr(row, 'cells'):
                        for cell in row.cells:
                            cell_content = self._serialize_cell_content(cell)
                            cell_merge_info = self._extract_cell_merge_info(cell)
                            if cell_merge_info:
                                cell_content.update(cell_merge_info)
                            row_data.append(cell_content)
                    elif hasattr(row, '__iter__') and not isinstance(row, (str, bytes)):
                        # Row is iterable (list of cells)
                        for cell in row:
                            cell_content = self._serialize_cell_content(cell)
                            cell_merge_info = self._extract_cell_merge_info(cell)
                            if cell_merge_info:
                                cell_content.update(cell_merge_info)
                            row_data.append(cell_content)
                    
                    if row_data:
                        rows_data.append(row_data)
                        props = self._extract_row_properties(row)
                        row_props.append(props)
        
        # Option 2: Check if payload/data has table
        if not rows_data and hasattr(table, 'payload'):
            payload = table.payload
            if hasattr(payload, 'rows'):
                return self._serialize_table_layout(payload, depth)
        
        # Option 3: Check if raw has table (from BlockContent)
        if not rows_data and hasattr(table, 'raw'):
            raw = table.raw
            if raw and (hasattr(raw, 'rows') or (isinstance(raw, dict) and 'rows' in raw)):
                return self._serialize_table_from_raw(raw, depth)
        
        # If still no rows, but this is TableLayout, check if may be in content...
        if not rows_data and hasattr(table, 'content'):
            content = table.content
            if hasattr(content, 'rows'):
                return self._serialize_table_layout(content, depth)
        
        result["rows"] = rows_data
        if row_props and any(row_props):
            # Ensure length matches number of rows
            while len(row_props) < len(rows_data):
                row_props.append({})
            result["row_properties"] = row_props
        table_properties = self._build_table_properties_dict(result, table_props, style_dict)
        if table_properties:
            result["properties"] = table_properties
        return result
    
    def _serialize_table_cell_layout(self, cell_layout: Any) -> Dict[str, Any]:
        """Serializes TableCellLayout with full content."""
        result = {
            "text": "",
            "blocks": []
        }
        
        # IMPORTANT: Search cell for images
        self._find_and_register_media(cell_layout, "table_cell_layout", context="table_cell_layout")
        
        # Check various possible TableCellLayout structures
        text_parts = []
        blocks_data = []
        
        # Opcja 1: cell_layout.blocks (TableCellLayout z blocks)
        if hasattr(cell_layout, 'blocks'):
            for block in cell_layout.blocks:
                self._find_and_register_media(block, "table_cell_block", context="table_cell_block")
                
                # Extract text
                block_text = self._extract_text_from_block(block)
                if block_text:
                    text_parts.append(block_text)
                
                # Serializuj blok
                block_data = self._serialize_cell_block(block)
                if block_data:
                    blocks_data.append(block_data)
        
        # Opcja 2: cell_layout.content (TableCellLayout z content)
        elif hasattr(cell_layout, 'content'):
            content = cell_layout.content
            if hasattr(content, 'lines'):
                # ParagraphLayout in cell
                para_data = self._serialize_paragraph_layout(content, depth=0)
                if para_data:
                    blocks_data.append(para_data)
                    if 'text' in para_data:
                        text_parts.append(para_data['text'])
        
        # Option 3: Check if cell_layout has text/data directly
        if hasattr(cell_layout, 'text'):
            text = getattr(cell_layout, 'text', '')
            if text:
                text_parts.append(str(text))
        elif hasattr(cell_layout, 'data') and isinstance(cell_layout.data, dict):
            text = cell_layout.data.get('text', '')
            if text:
                text_parts.append(str(text))
        
        if text_parts:
            result["text"] = ' '.join(text_parts)
        
        if blocks_data:
            result["blocks"] = blocks_data
        
        # Extract cell properties
        cell_props = self._extract_cell_properties(cell_layout)
        if cell_props:
            result.update(cell_props)
        
        merge_info = self._extract_cell_merge_info(cell_layout)
        if merge_info:
            result.update(merge_info)
        
        # Remove empty blocks
        if not result["blocks"]:
            del result["blocks"]
        
        return result
    
    def _extract_table_properties(self, table: Any) -> Dict[str, Any]:
        """Extracts table properties (borders, columns, margins, style, etc.)."""
        props = {}
        
        # Check table style
        if hasattr(table, 'style'):
            style = table.style
            if isinstance(style, dict):
                # Borders
                borders = style.get('borders') or style.get('table_borders')
                if borders:
                    props['borders'] = self._serialize_borders(borders)
                
                # Cell margins (default for entire table)
                cell_margins = style.get('cell_margins') or style.get('margins')
                if cell_margins:
                    props['cell_margins'] = self._serialize_margins(cell_margins)
                
                # Cell spacing
                cell_spacing = style.get('cell_spacing') or style.get('spacing_between_cells')
                if cell_spacing:
                    props['cell_spacing'] = cell_spacing
                
                # Table alignment
                alignment = style.get('alignment') or style.get('table_alignment')
                if alignment:
                    props['alignment'] = alignment
                if style.get('table_alignment'):
                    props['table_alignment'] = style.get('table_alignment')
                if style.get('table_vertical_alignment'):
                    props['table_vertical_alignment'] = style.get('table_vertical_alignment')
                
                # Table width
                width = style.get('width') or style.get('table_width')
                if width:
                    props['width'] = width
                    props['width_type'] = style.get('width_type') or style.get('table_width_type') or 'auto'
                
                if style.get('spacing_before') is not None:
                    props['spacing_before'] = style.get('spacing_before')
                if style.get('spacing_after') is not None:
                    props['spacing_after'] = style.get('spacing_after')
                if style.get('spacing_between_rows') is not None:
                    props['spacing_between_rows'] = style.get('spacing_between_rows')
                if style.get('cell_padding') is not None:
                    props['cell_padding'] = style.get('cell_padding')
                if style.get('table_indent') is not None:
                    props.setdefault('indent', {}).update({'value': style.get('table_indent')})
        
        # Check object properties
        if hasattr(table, 'properties'):
            table_props = table.properties
            if hasattr(table_props, 'borders') and table_props.borders:
                props['borders'] = self._serialize_borders(table_props.borders)
            if hasattr(table_props, 'cell_margins') and table_props.cell_margins:
                props['cell_margins'] = self._serialize_margins(table_props.cell_margins)
            if hasattr(table_props, 'cell_spacing') and table_props.cell_spacing:
                props['cell_spacing'] = table_props.cell_spacing
            if hasattr(table_props, 'alignment') and table_props.alignment:
                props['alignment'] = table_props.alignment
            if hasattr(table_props, 'style') and table_props.style:
                props['style'] = table_props.style
            if hasattr(table_props, 'style_id') and table_props.style_id:
                props['style_id'] = table_props.style_id
            if hasattr(table_props, 'grid') and table_props.grid:
                props['columns'] = self._serialize_table_grid(table_props.grid)
                props['grid'] = table_props.grid
            if hasattr(table_props, 'indent') and table_props.indent:
                props['indent'] = table_props.indent
            if hasattr(table_props, 'look') and table_props.look:
                props['look'] = table_props.look
            if hasattr(table_props, 'shading') and table_props.shading:
                shading = self._serialize_shading(table_props.shading)
                if shading:
                    props['shading'] = shading
        
        # Check grid directly
        if hasattr(table, 'grid') and table.grid:
            props['columns'] = self._serialize_table_grid(table.grid)
            props['grid'] = table.grid
        
        # Flagi z Table modelu
        if hasattr(table, 'cant_split'):
            props['cant_split'] = bool(getattr(table, 'cant_split'))
        if hasattr(table, 'header_repeat'):
            props['header_repeat'] = bool(getattr(table, 'header_repeat'))
        
        return props
    
    def _serialize_borders(self, borders: Any) -> Dict[str, Any]:
        """Serializes table/cell borders."""
        if not borders:
            return {}
        
        if isinstance(borders, dict):
            result = {}
            # Standardowe ramki: top, bottom, left, right
            for side in ['top', 'bottom', 'left', 'right', 'insideH', 'insideV']:
                border = borders.get(side) or borders.get(side.lower()) or borders.get(side.upper())
                if border:
                    if isinstance(border, dict):
                        result[side] = {
                            'width': border.get('width') or border.get('sz') or border.get('w'),
                            'color': border.get('color') or border.get('val'),
                            'style': border.get('style') or border.get('val') or 'single'
                        }
                    else:
                        result[side] = {'style': 'single', 'width': 1.0}
            return result
        
        return {}

    def _serialize_shading(self, shading: Any) -> Dict[str, Any]:
        """Converts shading data to simple JSON structure."""
        if not shading:
            return {}
        if isinstance(shading, dict):
            result = {}
            for key, value in shading.items():
                plain_key = key.split('}')[-1]
                result[plain_key] = value
            # Most important fields: fill (background), color (text), val (pattern)
            fill = shading.get('fill')
            if fill:
                result.setdefault('fill', fill)
            color = shading.get('color')
            if color:
                result.setdefault('color', color)
            val = shading.get('val')
            if val:
                result.setdefault('pattern', val)
            return result
        return {"value": shading}
    
    def _serialize_margins(self, margins: Any) -> Dict[str, float]:
        """Serializes margins (cell or table)."""
        if not margins:
            return {}
        
        if isinstance(margins, dict):
            result = {}
            for side in ['top', 'bottom', 'left', 'right']:
                margin = margins.get(side)
                if margin:
                    # Convert from twips to points if needed
                    if isinstance(margin, (int, float)):
                        # If value is large (> 100), probably in twips
                        if margin > 100:
                            result[side] = margin / 20.0  # twips to points
                        else:
                            result[side] = float(margin)
                    elif isinstance(margin, dict):
                        # May be in format {w: 1440, type: "dxa"}
                        width = margin.get('w') or margin.get('width') or margin.get('value')
                        if width:
                            if isinstance(width, (int, float)) and width > 100:
                                result[side] = width / 20.0
                            else:
                                result[side] = float(width)
            return result
        
        return {}

    def _twips_to_points(self, value: Any) -> Optional[float]:
        """Konwertuje twips (lub string) na punkty."""
        if value in (None, "", {}, False):
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            try:
                numeric = float(str(value).strip())
            except (TypeError, ValueError):
                return None
        if abs(numeric) < 0.001:
            return 0.0
        try:
            return twips_to_points(numeric)
        except Exception:
            return numeric / 20.0
    
    def _serialize_table_grid(self, grid: List[Any]) -> List[Dict[str, Any]]:
        """Serializes table grid (columns with widths)."""
        columns = []
        for col in grid:
            if isinstance(col, dict):
                col_info = {
                    'width': col.get('width') or col.get('w'),
                    'width_type': col.get('width_type') or col.get('type') or 'auto'
                }
                # Convert from twips to points if needed
                if col_info['width'] and isinstance(col_info['width'], (int, float)):
                    if col_info['width'] > 100:
                        col_info['width'] = col_info['width'] / 20.0
                columns.append(col_info)
            elif isinstance(col, (int, float)):
                # Width only
                width = col / 20.0 if col > 100 else col
                columns.append({'width': width, 'width_type': 'auto'})
        return columns
    
    def _extract_cell_merge_info(self, cell: Any) -> Dict[str, Any]:
        """Extracts merged cells information (grid_span, vertical_merge)."""
        merge_info = {}
        
        # Grid span (horizontal merge)
        grid_span = None
        if hasattr(cell, 'grid_span'):
            grid_span = cell.grid_span
        elif hasattr(cell, 'colspan'):
            grid_span = cell.colspan
        elif isinstance(cell, dict):
            grid_span = cell.get('grid_span') or cell.get('colspan') or cell.get('gridSpan')
        
        if grid_span:
            merge_info['grid_span'] = grid_span
            if grid_span > 1:
                merge_info['colspan'] = grid_span
        
        # Vertical merge
        vertical_merge = None
        if hasattr(cell, 'vertical_merge'):
            vertical_merge = cell.vertical_merge
        elif hasattr(cell, 'rowspan'):
            vertical_merge = cell.rowspan
        elif isinstance(cell, dict):
            vertical_merge = cell.get('vertical_merge') or cell.get('rowspan') or cell.get('vMerge')
        
        vertical_merge_type = getattr(cell, 'vertical_merge_type', None)
        if isinstance(vertical_merge, dict):
            merge_type = vertical_merge.get('val') or vertical_merge.get('type')
        else:
            merge_type = vertical_merge_type or vertical_merge
        if merge_type:
            merge_info['vertical_merge'] = merge_type
            if merge_type == 'restart':
                merge_info['rowspan'] = 1
            elif merge_type == 'continue':
                merge_info['rowspan'] = 'continue'
        elif isinstance(vertical_merge, int) and vertical_merge > 1:
            merge_info['rowspan'] = vertical_merge
        
        # Cell margins (specific to cell)
        cell_margins = None
        if hasattr(cell, 'cell_margins'):
            cell_margins = cell.cell_margins
        elif hasattr(cell, 'margins'):
            cell_margins = cell.margins
        elif isinstance(cell, dict):
            cell_margins = cell.get('cell_margins') or cell.get('margins')
        
        if cell_margins:
            margins = self._serialize_margins(cell_margins)
            if margins:
                merge_info['margins'] = margins
        
        # Cell borders (specific to cell)
        cell_borders = None
        if hasattr(cell, 'borders'):
            cell_borders = cell.borders
        elif isinstance(cell, dict):
            cell_borders = cell.get('borders')
        
        if cell_borders:
            borders = self._serialize_borders(cell_borders)
            if borders:
                merge_info['borders'] = borders
        
        # Cell shading
        shading = None
        if hasattr(cell, 'shading'):
            shading = cell.shading
        elif isinstance(cell, dict):
            shading = cell.get('shading')
        if shading:
            shading_data = self._serialize_shading(shading)
            if shading_data:
                merge_info['shading'] = shading_data
        
        # Preferred width info
        width_attr = getattr(cell, 'width_spec', None)
        if isinstance(cell, dict) and not width_attr:
            width_attr = cell.get('width_attr') or cell.get('preferred_width')
        if width_attr:
            merge_info['preferred_width'] = width_attr
        width_value = getattr(cell, 'width', None)
        if width_value:
            merge_info['width_twips'] = width_value
            width_points = self._twips_to_points(width_value)
            if width_points is not None:
                merge_info['width_pt'] = width_points
        
        # Horizontal alignment
        horizontal_align = getattr(cell, 'horizontal_align', None)
        if not horizontal_align and isinstance(cell, dict):
            horizontal_align = cell.get('horizontal_align') or cell.get('jc')
        if horizontal_align:
            merge_info['horizontal_align'] = horizontal_align
        
        # Text direction
        text_dir = getattr(cell, 'text_direction', None)
        if not text_dir and isinstance(cell, dict):
            text_dir = cell.get('text_direction')
        if text_dir:
            merge_info['text_direction'] = text_dir
        
        return merge_info

    def _extract_row_properties(self, row: Any) -> Dict[str, Any]:
        """Returns table row properties."""
        props: Dict[str, Any] = {}
        if hasattr(row, 'height') and row.height:
            props['height_twips'] = row.height
            height_pt = self._twips_to_points(row.height)
            if height_pt is not None:
                props['height_pt'] = height_pt
        if hasattr(row, 'is_header_row'):
            props['is_header'] = bool(row.is_header_row)
        if hasattr(row, 'row_cant_split'):
            props['cant_split'] = bool(row.row_cant_split)
        if hasattr(row, 'cant_split'):
            props['cant_split'] = bool(getattr(row, 'cant_split')) or props.get('cant_split', False)
        if hasattr(row, 'grid_after') and row.grid_after:
            props['grid_after'] = row.grid_after
        if hasattr(row, 'grid_before') and row.grid_before:
            props['grid_before'] = row.grid_before
        if hasattr(row, 'shading') and row.shading:
            shading = self._serialize_shading(row.shading)
            if shading:
                props['shading'] = shading
        if hasattr(row, 'style') and isinstance(row.style, dict) and row.style:
            props.setdefault('raw_style', row.style)
        # Remove empty entries
        return {k: v for k, v in props.items() if v not in (None, {}, [])}
    
    def _serialize_cell_content(self, cell: Any) -> Dict[str, Any]:
        """Serializes table cell content with full information."""
        result = {
            "text": "",
            "blocks": []
        }
        
        # IMPORTANT: Search cell for images before serialization
        self._find_and_register_media(cell, "table_cell", context="table_cell")
        
        # Check various possible cell structures
        text_parts = []
        blocks_data = []
        
        # Opcja 1: cell.blocks (TableLayout cell)
        if hasattr(cell, 'blocks'):
            for block in cell.blocks:
                # IMPORTANT: Search each block in cell for images
                self._find_and_register_media(block, "table_cell_block", context="table_cell_block")
                
                # Extract text
                block_text = self._extract_text_from_block(block)
                if block_text:
                    text_parts.append(block_text)
                
                # Serialize block (may contain images, nested tables, etc.)
                block_data = self._serialize_cell_block(block)
                if block_data:
                    blocks_data.append(block_data)
        
        # Opcja 2: cell.children (TableCell model)
        elif hasattr(cell, 'children'):
            for child in cell.children:
                self._find_and_register_media(child, "table_cell_child", context="table_cell_child")
                
                # Extract text
                if hasattr(child, 'get_text'):
                    child_text = child.get_text() or ''
                    if child_text:
                        text_parts.append(child_text)
                
                # Serializuj element
                element_data = self._serialize_cell_element(child)
                if element_data:
                    blocks_data.append(element_data)
        
        # Opcja 3: cell.paragraphs (TableCell model)
        elif hasattr(cell, 'paragraphs'):
            for para in cell.paragraphs:
                self._find_and_register_media(para, "table_cell_paragraph", context="table_cell_paragraph")
                
                if hasattr(para, 'get_text'):
                    para_text = para.get_text() or ''
                    if para_text:
                        text_parts.append(para_text)
                
                element_data = self._serialize_cell_element(para)
                if element_data:
                    blocks_data.append(element_data)
        
        # Option 4: cell.get_text() (simple cell)
        elif hasattr(cell, 'get_text'):
            text = cell.get_text() or ''
            if text:
                text_parts.append(text)
        
        # Opcja 5: dict z text
        elif isinstance(cell, dict):
            text = cell.get('text', '')
            if text:
                text_parts.append(text)
        
        if text_parts:
            result["text"] = ' '.join(text_parts)
        
        if blocks_data:
            result["blocks"] = blocks_data
        
        # Extract cell properties (margins, borders, vertical alignment, colspan...
        cell_merge_info = self._extract_cell_merge_info(cell)
        if cell_merge_info:
            result.update(cell_merge_info)
        
        # Remove empty blocks
        if not result["blocks"]:
            del result["blocks"]
        
        return result
    
    def _extract_cell_properties(self, cell: Any) -> Dict[str, Any]:
        """Extracts cell properties (margins, borders, vertical alignment)."""
        props = {}
        
        # Cell margins
        cell_margins = None
        if hasattr(cell, 'cell_margins'):
            cell_margins = cell.cell_margins
        elif hasattr(cell, 'margins'):
            cell_margins = cell.margins
        elif isinstance(cell, dict):
            cell_margins = cell.get('cell_margins') or cell.get('margins')
        
        if cell_margins:
            margins = self._serialize_margins(cell_margins)
            if margins:
                props['margins'] = margins
        
        # Cell borders
        cell_borders = None
        if hasattr(cell, 'borders'):
            cell_borders = cell.borders
        elif isinstance(cell, dict):
            cell_borders = cell.get('borders')
        
        if cell_borders:
            borders = self._serialize_borders(cell_borders)
            if borders:
                props['borders'] = borders
        
        # Vertical alignment
        vertical_align = None
        if hasattr(cell, 'vertical_align'):
            vertical_align = cell.vertical_align
        elif hasattr(cell, 'v_align'):
            vertical_align = cell.v_align
        elif isinstance(cell, dict):
            vertical_align = cell.get('vertical_align') or cell.get('v_align')
        
        if vertical_align:
            props['vertical_align'] = vertical_align
        
        return props
    
    def _serialize_cell_block(self, block: Any) -> Optional[Dict[str, Any]]:
        """Serializes block in table cell."""
        if block is None:
            return None
        
        result = {}
        
        # Check block type
        if hasattr(block, 'payload'):
            payload = block.payload
            if hasattr(payload, 'lines'):
                # ParagraphLayout
                result["type"] = "paragraph"
                text_parts = []
                for line in payload.lines:
                    if hasattr(line, 'items'):
                        for item in line.items:
                            if hasattr(item, 'data') and isinstance(item.data, dict):
                                text = item.data.get('text', '')
                                if text:
                                    text_parts.append(text)
                if text_parts:
                    result["text"] = ' '.join(text_parts)
            elif hasattr(payload, 'path') or hasattr(payload, 'image_path'):
                # ImageLayout
                result["type"] = "image"
                media_id = self._find_and_register_media(payload, block_type="image", context="cell_image")
                if media_id is not None:
                    result["media_id"] = media_id
            elif hasattr(payload, 'rows'):
                # TableLayout (nested table)
                result["type"] = "table"
                result["rows"] = self._serialize_table_layout(payload, depth=0)["rows"]
        
        return result if result else None
    
    def _serialize_generic_layout(self, layout: Any, depth: int) -> Dict[str, Any]:
        """Serializuje GenericLayout."""
        result = {
            "type": "generic"
        }
        
        if hasattr(layout, 'data') and isinstance(layout.data, dict):
            # Extract text if available
            if 'text' in layout.data:
                result["text"] = layout.data['text']
            else:
                # Minimalne dane
                result["data"] = {k: v for k, v in layout.data.items() 
                                if isinstance(v, (str, int, float, bool))}
        
        return result
    
    def _serialize_object(self, obj: Any, depth: int) -> Dict[str, Any]:
        """Serializes object - does NOT use repr(), always returns clean JSON."""
        # Check if this is dict - if so, use it directly
        if isinstance(obj, dict):
            result = {}
            # Move all fields as normal JSON values
            for key, value in obj.items():
                if value is not None:
                    # Serialize recursively instead of using repr()
                    if isinstance(value, (str, int, float, bool, type(None))):
                        result[key] = value
                    elif isinstance(value, (list, tuple)):
                        result[key] = [self._serialize_content(item, depth + 1) if not isinstance(item, (str, int, float, bool)) else item for item in value]
                    else:
                        serialized = self._serialize_content(value, depth + 1)
                        if serialized:
                            result[key] = serialized
            return result if result else {"type": "dict", "empty": True}
        
        result = {
            "type": type(obj).__name__
        }
        
        # Check if this is dict-like object
        if hasattr(obj, '__dict__'):
            obj_dict = obj.__dict__
            # Extract important fields as normal JSON values
            important_fields = ['text', 'data', 'content', 'value', 'style', 'blocks', 'payload', 'raw', 'type', 'blocks', 'runs', 'lines', 'items']
            for field in important_fields:
                if field in obj_dict:
                    value = obj_dict[field]
                    if value is not None:
                        # Serialize recursively instead of using repr()
                        if isinstance(value, (str, int, float, bool, type(None))):
                            result[field] = value
                        elif isinstance(value, (list, tuple)):
                            result[field] = [self._serialize_content(item, depth + 1) if not isinstance(item, (str, int, float, bool)) else item for item in value]
                        else:
                            serialized = self._serialize_content(value, depth + 1)
                            if serialized:
                                result[field] = serialized
        
        # Check if has attributes directly (not in __dict__)
        for attr in ['text', 'data', 'content', 'style', 'blocks', 'payload', 'raw', 'runs', 'lines', 'items']:
            if hasattr(obj, attr) and attr not in result:
                value = getattr(obj, attr, None)
                if value is not None:
                    if isinstance(value, (str, int, float, bool, type(None))):
                        result[attr] = value
                    elif isinstance(value, (list, tuple)):
                        result[attr] = [self._serialize_content(item, depth + 1) if not isinstance(item, (str, int, float, bool)) else item for item in value]
                    else:
                        serialized = self._serialize_content(value, depth + 1)
                        if serialized:
                            result[attr] = serialized
        
        # Check if this is SimpleNamespace or similar object
        if hasattr(obj, '__class__') and hasattr(obj, '__dict__'):
            # Przeszukaj wszystkie atrybuty
            for key in dir(obj):
                if not key.startswith('_') and key not in result:
                    try:
                        value = getattr(obj, key, None)
                        if value is not None and not callable(value):
                            if isinstance(value, (str, int, float, bool, type(None))):
                                result[key] = value
                            elif isinstance(value, (list, tuple)) and len(value) < 100:  # Limit long lists
                                result[key] = [self._serialize_content(item, depth + 1) if not isinstance(item, (str, int, float, bool)) else item for item in value[:10]]  # Limit to 10 elements
                    except:
                        pass
        
        # If no data, return minimal object
        if len(result) == 1:  # Tylko 'type'
            # Try to extract text as last resort
            if hasattr(obj, '__str__'):
                try:
                    str_repr = str(obj)
                    if str_repr and len(str_repr) < 200:  # Only short strings
                        result['value'] = str_repr
                except:
                    pass
        
        return result
    
    def _extract_text_from_block(self, block: Any) -> str:
        """Extracts text from block."""
        if hasattr(block, 'payload') and hasattr(block.payload, 'lines'):
            text_parts = []
            for line in block.payload.lines:
                if hasattr(line, 'items'):
                    for item in line.items:
                        if hasattr(item, 'data') and isinstance(item.data, dict):
                            text = item.data.get('text', '')
                            if text:
                                text_parts.append(text)
            return ' '.join(text_parts)
        
        if hasattr(block, 'text'):
            return str(block.text)
        
        if hasattr(block, 'data') and isinstance(block.data, dict):
            return block.data.get('text', '')
        
        return ''
    
    def _extract_sections(self) -> List[Dict[str, Any]]:
        """Extracts document section information."""
        sections = []
        
        if not self.xml_parser:
            return sections
        
        try:
            # Check if parser has parse_sections method
            if hasattr(self.xml_parser, 'parse_sections'):
                parsed_sections = self.xml_parser.parse_sections()
                for i, section in enumerate(parsed_sections):
                    section_info = {
                        "number": i + 1,
                        "page_size": section.get("page_size", {}),
                        "margins": section.get("margins", {}),
                        "orientation": section.get("page_size", {}).get("orient", "portrait"),
                        "columns": section.get("columns", {}),
                        "headers": section.get("headers", {}),
                        "footers": section.get("footers", {}),
                        # Dodatkowe informacje o sekcji
                        "title_page": section.get("title_page", False),
                        "different_first_page": section.get("different_first_page", False),
                        "different_odd_even": section.get("different_odd_even", False)
                    }
                    sections.append(section_info)
            # Alternatively, check if document has sections
            elif self.document and hasattr(self.document, '_sections'):
                for i, section in enumerate(self.document._sections or []):
                    if isinstance(section, dict):
                        section_info = {
                            "number": i + 1,
                            "page_size": section.get("page_size", {}),
                            "margins": section.get("margins", {}),
                            "orientation": section.get("page_size", {}).get("orient", "portrait"),
                            "columns": section.get("columns", {}),
                            "headers": section.get("headers", {}),
                            "footers": section.get("footers", {}),
                            # Dodatkowe informacje o sekcji
                            "title_page": section.get("title_page", False),
                            "different_first_page": section.get("different_first_page", False),
                            "different_odd_even": section.get("different_odd_even", False)
                        }
                        sections.append(section_info)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Failed to extract sections: {e}")
        
        return sections
    
    def _extract_notes(self) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Extracts footnotes and endnotes from document."""
        footnotes = {}
        endnotes = {}
        
        try:
            # Check if parser has notes parser
            if self.xml_parser and hasattr(self.xml_parser, 'notes_parser'):
                notes_parser = self.xml_parser.notes_parser
                if notes_parser:
                    # Footnotes
                    parsed_footnotes = notes_parser.parse_footnotes()
                    for note_id, note_data in parsed_footnotes.items():
                        footnotes[note_id] = {
                            "id": note_id,
                            "type": note_data.get("type", "normal"),
                            "content": self._serialize_note_content(note_data),
                            "paragraphs": note_data.get("paragraphs", [])
                        }
                    
                    # Endnotes
                    parsed_endnotes = notes_parser.parse_endnotes()
                    for note_id, note_data in parsed_endnotes.items():
                        endnotes[note_id] = {
                            "id": note_id,
                            "content": self._serialize_note_content(note_data),
                            "paragraphs": note_data.get("paragraphs", [])
                        }
            # Alternatively, use NotesParser directly
            elif self.package_reader:
                try:
                    from ..parser.notes_parser import NotesParser
                    notes_parser = NotesParser(self.package_reader)
                    parsed_footnotes = notes_parser.parse_footnotes()
                    parsed_endnotes = notes_parser.parse_endnotes()
                    
                    for note_id, note_data in parsed_footnotes.items():
                        footnotes[note_id] = {
                            "id": note_id,
                            "type": note_data.get("type", "normal"),
                            "content": self._serialize_note_content(note_data),
                            "paragraphs": note_data.get("paragraphs", [])
                        }
                    
                    for note_id, note_data in parsed_endnotes.items():
                        endnotes[note_id] = {
                            "id": note_id,
                            "content": self._serialize_note_content(note_data),
                            "paragraphs": note_data.get("paragraphs", [])
                        }
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug(f"Failed to parse notes: {e}")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Failed to extract notes: {e}")
        
        return footnotes, endnotes
    
    def _serialize_note_content(self, note_data: Dict[str, Any]) -> str:
        """Serializes footnote content to text."""
        if isinstance(note_data, dict):
            # Check various possible content locations
            content = note_data.get("content") or note_data.get("text") or note_data.get("value")
            if content:
                return str(content)
            
            # Check paragraphs
            paragraphs = note_data.get("paragraphs", [])
            if paragraphs:
                text_parts = []
                for para in paragraphs:
                    if isinstance(para, dict):
                        para_text = para.get("text") or para.get("content")
                        if para_text:
                            text_parts.append(str(para_text))
                    elif hasattr(para, 'get_text'):
                        text_parts.append(para.get_text() or "")
                return ' '.join(text_parts)
        
        return ""

