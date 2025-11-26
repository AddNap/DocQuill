"""

LayoutEngine - converts document model to logical layout structure
(without coordinate calculations, kerning and pagination).

"""

import re
import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from types import SimpleNamespace

from .styles_bridge import StyleBridge
from .placeholder_resolver import PlaceholderResolver
from .numbering_formatter import NumberingFormatter
from .geometry import twips_to_points
from .list_tree import (
    IndentSpec as _IndentSpec,
    ListTreeBuilder,
    ParagraphEntry as _ParagraphEntry,
)
from ..styles.style_manager import StyleManager

_LIST_MARKER_REGEX = re.compile(
    r"^\s*(?:[0-9]+[.)]|[A-Za-z][.)]|[IVXLCMivxlcm]+[.)]|[\u2022\u25CF\u25E6\u25AA\u25A0\u25B8\u00B7\-•])\s+"
)


@dataclass
class LayoutStructure:
    """Result of LayoutEngine operation - logical groups of document elements."""
    body: List[Any] = field(default_factory=list)
    headers: Dict[str, List[Any]] = field(default_factory=lambda: {"default": []})
    footers: Dict[str, List[Any]] = field(default_factory=lambda: {"default": []})
    sections: Dict[str, List[Any]] = field(default_factory=dict)


class LayoutEngine:
    """

    Main document model interpretation engine (without positioning).
    Responsible for: assigning styles, placeholders, block structures.

    """

    def __init__(self, numbering_data: Optional[Dict[str, Any]] = None, resolve_placeholders: bool = True):
        self.style_bridge = StyleBridge()
        self.placeholder_resolver = PlaceholderResolver()
        self.resolve_placeholders = resolve_placeholders
        self.numbering_formatter = NumberingFormatter(numbering_data)
        self.style_manager: Optional[StyleManager] = None
        self._numbering_data: Dict[str, Any] = numbering_data or {}

    # ----------------------------------------------------------------------
    # Main method building layout structure
    # ----------------------------------------------------------------------
    def build(self, model: Any) -> LayoutStructure:
        """
        Przetwarza model dokumentu (np. DocumentModel z JSON lub parsera DOCX)
        i zwraca strukturalny layout z blokami gotowymi do dalszego przetwarzania.
        """
        parser = getattr(model, "parser", None)
        numbering_data = getattr(parser, "numbering_data", None)
        if numbering_data is not None:
            self.numbering_formatter = NumberingFormatter(numbering_data)
            self._numbering_data = numbering_data or {}
        else:
            # Ensure formatter exists even if numbering data unavailable
            self.numbering_formatter = NumberingFormatter()
            self._numbering_data = {}
        # Reset counters for new document build
        self.numbering_formatter.reset()

        layout = LayoutStructure()
        
        # Parse headers and footers if available in model
        # Check if model has parser with parse_header/parse_footer methods
        import logging
        logger = logging.getLogger(__name__)
        
        if hasattr(model, "parser"):
            parser = model.parser
            if hasattr(parser, "package_reader"):
                try:
                    style_manager = getattr(parser, "_style_manager_cache", None)
                    if style_manager is None:
                        style_manager = StyleManager(parser.package_reader)
                        style_manager.load_styles()
                        setattr(parser, "_style_manager_cache", style_manager)
                    self.style_manager = style_manager
                except Exception as exc:
                    logger.debug(f"Failed to initialize style manager: {exc}")
                    self.style_manager = None
            # Parsuj headers
            if hasattr(parser, "parse_header"):
                header_body = parser.parse_header()
                logger.info(f"parse_header() returned: {header_body is not None}, "
                          f"has children: {hasattr(header_body, 'children') if header_body else False}, "
                          f"children count: {len(header_body.children) if header_body and hasattr(header_body, 'children') else 0}")
                if header_body and hasattr(header_body, "children"):
                    for i, header_element in enumerate(header_body.children):
                        # Recognize element type and process through appropriate method
                        header_block = self._build_header_footer_element(header_element, "header")
                        if header_block:
                            layout.headers["default"].append(header_block)
                            logger.info(f"  Added header element {i+1} to layout.headers['default']")
                else:
                    logger.warning(f"header_body is None or has no children attribute")
            
            # Parsuj footers
            if hasattr(parser, "parse_footer"):
                footer_body = parser.parse_footer()
                logger.info(f"parse_footer() returned: {footer_body is not None}, "
                          f"has children: {hasattr(footer_body, 'children') if footer_body else False}, "
                          f"children count: {len(footer_body.children) if footer_body and hasattr(footer_body, 'children') else 0}")
                if footer_body and hasattr(footer_body, "children"):
                    for i, footer_element in enumerate(footer_body.children):
                        # Recognize element type and process through appropriate method
                        footer_block = self._build_header_footer_element(footer_element, "footer")
                        if footer_block:
                            layout.footers["default"].append(footer_block)
                            logger.info(f"  Added footer element {i+1} to layout.footers['default']: "
                                      f"type={footer_block.get('type', 'unknown')}, "
                                      f"images={len(footer_block.get('images', []))}")
                else:
                    logger.warning(f"footer_body is None or has no children attribute")

        # Get elements - check various possible attributes
        elements = []
        if hasattr(model, "elements"):
            elements = model.elements if isinstance(model.elements, (list, tuple)) else list(model.elements) if model.elements else []
        elif hasattr(model, "body") and hasattr(model.body, "children"):
            elements = model.body.children if isinstance(model.body.children, (list, tuple)) else list(model.body.children) if model.body.children else []
        elif hasattr(model, "body") and hasattr(model.body, "paragraphs"):
            # If body has paragraphs, use them
            elements = model.body.paragraphs if isinstance(model.body.paragraphs, (list, tuple)) else list(model.body.paragraphs) if model.body.paragraphs else []
            # Also add tables and images if present
            if hasattr(model.body, "tables"):
                tables = model.body.tables if isinstance(model.body.tables, (list, tuple)) else list(model.body.tables) if model.body.tables else []
                elements.extend(tables)
            if hasattr(model.body, "images"):
                images = model.body.images if isinstance(model.body.images, (list, tuple)) else list(model.body.images) if model.body.images else []
                elements.extend(images)
        
        for element in elements:
            # Recognize element type - first check type attribute, then class name
            element_type = None
            if isinstance(element, dict):
                element_type = element.get("type")
            else:
                element_type = getattr(element, "type", None)
            
            if element_type is None:
                # Check class name
                class_name = type(element).__name__.lower()
                if "paragraph" in class_name:
                    element_type = "paragraph"
                elif "table" in class_name:
                    element_type = "table"
                elif "image" in class_name:
                    element_type = "image"
                elif "textbox" in class_name:
                    element_type = "textbox"
                elif "header" in class_name:
                    element_type = "header"
                elif "footer" in class_name:
                    element_type = "footer"
            
            element_type_str = str(element_type).lower() if element_type else ""
            
            match element_type_str:
                case "paragraph":
                    layout.body.append(self._build_paragraph(element))
                case "table":
                    layout.body.append(self._build_table(element))
                case "image":
                    layout.body.append(self._build_image(element))
                case "textbox":
                    layout.body.append(self._build_textbox(element))
                case "header":
                    layout.headers["default"].append(self._build_header(element))
                case "footer":
                    layout.footers["default"].append(self._build_footer(element))
                case _:
                    layout.body.append(self._build_generic(element))

        self._postprocess_paragraphs(layout.body)
        for header_list in layout.headers.values():
            self._postprocess_paragraphs(header_list)
        for footer_list in layout.footers.values():
            self._postprocess_paragraphs(footer_list)

        return layout

    # ----------------------------------------------------------------------
    # Mini-engines for individual types
    # ----------------------------------------------------------------------
    def _build_header_footer_element(self, element: Any, context: str) -> Dict[str, Any]:
        """

        Builds block for element in header/footer.
        Recognizes element type (table, paragraph, image, textbox) and uses appropriate method.

        Args:
        element: Element from header/footer
        context: "header" or "footer"

        Returns:
        Dict with block data with appropriate type

        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Recognize element type - check various sources
        element_type = None
        
        # 1. Check type attribute
        if hasattr(element, "type") and element.type:
            element_type = element.type
        
        # 2. Check class name
        if element_type is None:
            class_name = type(element).__name__.lower()
            if "paragraph" in class_name:
                element_type = "paragraph"
            elif "table" in class_name:
                element_type = "table"
            elif "image" in class_name or "drawing" in class_name:
                element_type = "image"
            elif "textbox" in class_name or "txbxcontent" in class_name:
                element_type = "textbox"
            elif "hyperlink" in class_name:
                # Hyperlinks are handled in runs, but if directly in footer, treat as paragraph
                element_type = "paragraph"
            elif "field" in class_name:
                # Fields are handled in runs, but if directly in footer, treat as paragraph
                element_type = "paragraph"
        
        # 3. Check object attributes to recognize type
        if element_type is None:
            if hasattr(element, "rows") or hasattr(element, "cells"):
                element_type = "table"
            elif hasattr(element, "runs") or hasattr(element, "children") and any(
                hasattr(c, "text") or hasattr(c, "get_text") for c in (element.children if hasattr(element, "children") else [])
            ):
                element_type = "paragraph"
            elif hasattr(element, "path") or hasattr(element, "image_path") or hasattr(element, "relationship_id"):
                element_type = "image"
            elif hasattr(element, "content") and isinstance(getattr(element, "content", None), str):
                # May be textbox or paragraph
                if hasattr(element, "textbox") or "textbox" in class_name:
                    element_type = "textbox"
                else:
                    element_type = "paragraph"
        
        element_type_str = str(element_type).lower() if element_type else ""
        
        logger.debug(f"_build_header_footer_element: element type={element_type_str}, class={type(element).__name__}, context={context}")
        
        # Process element through appropriate method
        if element_type_str == "table":
            block = self._build_table(element)
            block["header_footer_context"] = context
            return block
        elif element_type_str == "paragraph":
            block = self._build_paragraph(element)
            block["header_footer_context"] = context
            return block
        elif element_type_str == "image":
            block = self._build_image(element)
            block["header_footer_context"] = context
            return block
        elif element_type_str == "textbox":
            block = self._build_textbox(element)
            block["header_footer_context"] = context
            return block
        else:
            # For unknown types, try to recognize based on content
            logger.warning(f"_build_header_footer_element: unknown element type, trying fallback. class={type(element).__name__}, context={context}")
            
            # Try to use _build_paragraph as fallback (may contain text)
            try:
                block = self._build_paragraph(element)
                block["header_footer_context"] = context
                logger.debug(f"_build_header_footer_element: fallback to paragraph succeeded")
                return block
            except Exception as e:
                logger.debug(f"_build_header_footer_element: fallback to paragraph failed: {e}")
            
            # Final fallback - use _build_header/_build_footer method
            if context == "header":
                return self._build_header(element)
            else:
                return self._build_footer(element)
    
    def _build_paragraph(self, element: Any) -> Dict[str, Any]:
        style = dict(self.style_bridge.resolve(element, "paragraph") or {})
        
        # Resolve font from document style if not present
        if not style.get("font_name") and not style.get("font_ascii"):
            style_id = getattr(element, "style_id", None) or getattr(element, "style_name", None) or "Normal"
            if self.style_manager:
                doc_style = self.style_manager.get_style(style_id)
                if doc_style and isinstance(doc_style, dict):
                    props = doc_style.get("properties", {})
                    run_props = props.get("run", {}) if isinstance(props, dict) else {}
                    font_name = (
                        run_props.get("font_ascii") or 
                        run_props.get("font_hAnsi") or 
                        run_props.get("font_name") or
                        run_props.get("font_eastAsia")
                    )
                    if font_name:
                        style["font_name"] = font_name
                        style["font_ascii"] = font_name
                        # Also store in nested 'run' for consistency
                        if "run" not in style:
                            style["run"] = {}
                        style["run"]["font_name"] = font_name
                        style["run"]["font_ascii"] = font_name
        
        meta: Dict[str, Any] = {}

        indent_dict = style.get("indent") or {}
        if not isinstance(indent_dict, dict):
            indent_dict = {}
        else:
            indent_dict = dict(indent_dict)

        line_spacing_attr = getattr(element, "line_spacing", None)
        if line_spacing_attr not in (None, ""):
            try:
                style["line_spacing"] = float(line_spacing_attr)
            except (TypeError, ValueError):
                style["line_spacing"] = line_spacing_attr

        line_spacing_rule_attr = getattr(element, "line_spacing_rule", None)
        if line_spacing_rule_attr not in (None, ""):
            style["line_spacing_rule"] = str(line_spacing_rule_attr)

        spacing_dict = style.get("spacing")
        if not isinstance(spacing_dict, dict):
            spacing_dict = dict(spacing_dict) if isinstance(spacing_dict, dict) else {}

        # Merge spacing information from paragraph attributes if available
        spacing_before = getattr(element, "spacing_before", None)
        spacing_after = getattr(element, "spacing_after", None)
        if spacing_before not in (None, ""):
            try:
                spacing_dict["before_pt"] = float(spacing_before)
            except (TypeError, ValueError):
                spacing_dict["before_pt"] = spacing_before
        if spacing_after not in (None, ""):
            try:
                spacing_dict["after_pt"] = float(spacing_after)
            except (TypeError, ValueError):
                spacing_dict["after_pt"] = spacing_after

        # Preserve raw DOCX spacing definition (e.g. w:line) if available
        element_style = getattr(element, "style", {}) or {}
        if isinstance(element_style, dict):
            raw_spacing = element_style.get("spacing")
            if isinstance(raw_spacing, dict):
                for key, value in raw_spacing.items():
                    spacing_dict.setdefault(key, value)

        spacing_before_lines_attr = getattr(element, "spacing_before_lines", None)
        spacing_after_lines_attr = getattr(element, "spacing_after_lines", None)
        spacing_before_auto_attr = getattr(element, "spacing_before_auto", None)
        spacing_after_auto_attr = getattr(element, "spacing_after_auto", None)

        if spacing_before_lines_attr not in (None, ""):
            spacing_dict["before_lines"] = spacing_before_lines_attr
        if spacing_after_lines_attr not in (None, ""):
            spacing_dict["after_lines"] = spacing_after_lines_attr
        if spacing_before_auto_attr not in (None, "", False):
            spacing_dict["before_autospacing"] = spacing_before_auto_attr
        if spacing_after_auto_attr not in (None, "", False):
            spacing_dict["after_autospacing"] = spacing_after_auto_attr

        if spacing_dict:
            style["spacing"] = spacing_dict

        def _coerce_inline_indent(value: Any) -> Optional[float]:
            if value is None or value == "":
                return None
            if isinstance(value, (int, float)):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                return None
            # Reuse _to_points for twips conversion where needed
            return self._to_points(numeric)

        inline_left_pt = _coerce_inline_indent(getattr(element, "left_indent", None))
        inline_right_pt = _coerce_inline_indent(getattr(element, "right_indent", None))
        inline_first_line_pt = _coerce_inline_indent(getattr(element, "first_line_indent", None))
        inline_hanging_pt = _coerce_inline_indent(getattr(element, "hanging_indent", None))

        inline_indent_dict = {
            "left_pt": inline_left_pt,
            "right_pt": inline_right_pt,
            "first_line_pt": inline_first_line_pt,
            "hanging_pt": inline_hanging_pt,
        }
        inline_indent_dict = {
            key: value for key, value in inline_indent_dict.items() if value is not None
        }

        spacing_metrics = self._resolve_spacing_metrics(style)

        indent_left_pt = self._to_points(indent_dict.get("left"))
        indent_right_pt = self._to_points(indent_dict.get("right"))
        indent_first_line_pt = self._to_points(indent_dict.get("first_line"))
        indent_hanging_pt = self._to_points(indent_dict.get("hanging"))

        indent_dict["left_pt"] = indent_left_pt
        indent_dict["right_pt"] = indent_right_pt
        indent_dict["first_line_pt"] = indent_first_line_pt
        indent_dict["hanging_pt"] = indent_hanging_pt

        if indent_first_line_pt == 0.0 and indent_hanging_pt:
            indent_dict["first_line_pt"] = indent_left_pt - indent_hanging_pt

        indent_dict.setdefault("text_position_pt", indent_dict.get("first_line_pt", indent_left_pt))
        indent_dict.setdefault("number_position_pt", indent_left_pt - indent_hanging_pt)

        if inline_indent_dict:
            style["inline_indent"] = dict(inline_indent_dict)
            block_data_inline_indent = dict(inline_indent_dict)
            meta["explicit_indent"] = True
        else:
            block_data_inline_indent = {}
        style["indent"] = indent_dict
        
        # Pobierz tekst
        text = ""
        if hasattr(element, "get_text"):
            text = element.get_text()
        elif hasattr(element, "text"):
            text = str(element.text) if element.text else ""
        else:
            text = getattr(element, "text", "") or getattr(element, "get_text", lambda: "")()
        
        # Resolve placeholders
        if self.resolve_placeholders:
            text = self.placeholder_resolver.resolve_text(text)
        
        # Pobierz obrazy z paragrafu
        images = []
        if hasattr(element, "images"):
            images_list = element.images if isinstance(element.images, list) else [element.images] if element.images else []
            images.extend(images_list)
        
        # Pobierz VML shapes z paragrafu (watermarks)
        vml_shapes = []
        if hasattr(element, "vml_shapes"):
            vml_shapes_list = element.vml_shapes if isinstance(element.vml_shapes, list) else [element.vml_shapes] if element.vml_shapes else []
            vml_shapes.extend(vml_shapes_list)
        
        # Get images, textboxes and fields also from runs (for images, textboxes and fields in runs)
        textboxes = []
        fields = []
        run_objects = []
        if hasattr(element, "children") or hasattr(element, "runs"):
            runs = getattr(element, "children", []) or getattr(element, "runs", [])
            for run in runs:
                run_objects.append(run)
                if hasattr(run, "images"):
                    run_images = run.images if isinstance(run.images, list) else [run.images] if run.images else []
                    if run_images:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.info(f"Found {len(run_images)} images in run of paragraph")
                    images.extend(run_images)
                
                # Check if run has fields (PAGE, NUMPAGES, etc.)
                if hasattr(run, "children"):
                    # Pobierz style runu dla field codes
                    run_style = self.style_bridge.resolve(run, "run")
                    for child in run.children:
                        if isinstance(child, dict) and child.get("type") == "Field":
                            field_instr = child.get("instr", "")
                            if field_instr:
                                fields.append({
                                    "type": "field",
                                    "instr": field_instr,
                                    "field_type": self._detect_field_type(field_instr),
                                    "style": run_style  # Pass run formatting
                                })
                        elif hasattr(child, "type") and getattr(child, "type", None) == "Field":
                            field_instr = getattr(child, "instr", "")
                            if field_instr:
                                fields.append({
                                    "type": "field",
                                    "instr": field_instr,
                                    "field_type": self._detect_field_type(field_instr),
                                    "style": run_style  # Pass run formatting
                                })
                
                # Check if run has textbox
                if hasattr(run, "textbox") and run.textbox:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f"Found textbox in run of paragraph: hasattr={hasattr(run, 'textbox')}, textbox={run.textbox is not None}")

                    def _build_textbox_dict(tb_source):
                        anchor_info = None
                        textbox_text_parts = []

                        if isinstance(tb_source, list):
                            for tb_run in tb_source:
                                if hasattr(tb_run, 'textbox_anchor_info') and tb_run.textbox_anchor_info:
                                    anchor_info = tb_run.textbox_anchor_info
                                    break
                            for tb_run in tb_source:
                                if hasattr(tb_run, "get_text"):
                                    run_text = tb_run.get_text()
                                elif hasattr(tb_run, "text"):
                                    run_text = str(tb_run.text) if tb_run.text else ""
                                else:
                                    run_text = ""
                                if run_text:
                                    textbox_text_parts.append(run_text)
                        else:
                            if hasattr(tb_source, 'textbox_anchor_info') and tb_source.textbox_anchor_info:
                                anchor_info = tb_source.textbox_anchor_info
                            if hasattr(tb_source, "get_text"):
                                run_text = tb_source.get_text()
                                if run_text:
                                    textbox_text_parts.append(run_text)
                            elif hasattr(tb_source, "text") and tb_source.text:
                                textbox_text_parts.append(str(tb_source.text))

                        textbox_dict = {
                            "type": "textbox",
                            "anchor_type": (anchor_info or {}).get('anchor_type', 'inline'),
                            "position": (anchor_info or {}).get('position', {}),
                            "width": (anchor_info or {}).get('width', 0),
                            "height": (anchor_info or {}).get('height', 0),
                            "content": tb_source,
                            "text": " ".join(textbox_text_parts).strip()
                        }
                        return textbox_dict

                    if isinstance(run.textbox, list):
                        logger.info(f"  Textbox is a list with {len(run.textbox)} items")
                        textboxes.append(_build_textbox_dict(run.textbox))
                    else:
                        logger.info(f"  Textbox is a single item: {type(run.textbox).__name__}")
                        textboxes.append(_build_textbox_dict(run.textbox))
        
        # Extract pagination and formatting properties
        block_data = {
            "type": "paragraph",
            "text": text,
            "style": style,
            "page_break_before": self._get_page_break_before(element),
            "page_break_after": self._get_page_break_after(element),
            "keep_with_next": getattr(element, "keep_with_next", False) or style.get("keep_with_next", False),
            "keep_together": getattr(element, "keep_together", False) or style.get("keep_together", False),
        }
        if style.get("line_spacing") is not None:
            block_data["line_spacing"] = style.get("line_spacing")
        if style.get("line_spacing_rule"):
            block_data["line_spacing_rule"] = style.get("line_spacing_rule")
        if style.get("spacing"):
            block_data["spacing"] = style.get("spacing")
        if spacing_metrics:
            block_data["spacing_metrics"] = spacing_metrics
        if block_data_inline_indent:
            block_data["inline_indent"] = block_data_inline_indent
        block_data["indent"] = indent_dict
        
        # Add images if present
        if images:
            block_data["images"] = images
        
        # Add textboxes if present
        if textboxes:
            block_data["textboxes"] = textboxes
        
        # Add VML shapes if present (watermarks)
        if vml_shapes:
            block_data["vml_shapes"] = vml_shapes
        
        # Add fields if present
        if fields:
            block_data["fields"] = fields
        
        bookmarks = getattr(element, "bookmarks", None)
        if bookmarks:
            try:
                block_data["bookmarks"] = copy.deepcopy(bookmarks)
            except Exception:
                block_data["bookmarks"] = bookmarks
        
        if run_objects:
            runs_payload: List[Dict[str, Any]] = []
            for run in run_objects:
                # Check if run has field codes BEFORE parsing text
                run_fields = []
                if hasattr(run, "children"):
                    # Pobierz style runu dla field codes
                    run_style_for_fields = self.style_bridge.resolve(run, "run")
                    for child in run.children:
                        if isinstance(child, dict) and child.get("type") == "Field":
                            field_instr = child.get("instr", "")
                            if field_instr:
                                run_fields.append({
                                    "type": "field",
                                    "instr": field_instr,
                                    "field_type": self._detect_field_type(field_instr),
                                    "style": run_style_for_fields
                                })
                        elif hasattr(child, "type") and getattr(child, "type", None) == "Field":
                            field_instr = getattr(child, "instr", "")
                            if field_instr:
                                run_fields.append({
                                    "type": "field",
                                    "instr": field_instr,
                                    "field_type": self._detect_field_type(field_instr),
                                    "style": run_style_for_fields
                                })
                
                run_text = ""
                if hasattr(run, "get_text"):
                    run_text = run.get_text() or ""
                elif hasattr(run, "text"):
                    run_text = run.text or ""

                run_style: Dict[str, Any] = {}
                raw_style = getattr(run, "style", {}) or {}
                if isinstance(raw_style, dict):
                    run_style.update(raw_style)

                def _merge_flag(style_key: str, attr_name: str) -> None:
                    value = getattr(run, attr_name, None)
                    if isinstance(value, bool):
                        if value:
                            run_style[style_key] = True
                    elif value not in (None, "", False):
                        run_style[style_key] = value

                _merge_flag("bold", "bold")
                _merge_flag("italic", "italic")
                _merge_flag("underline", "underline")
                _merge_flag("strike_through", "strike_through")
                _merge_flag("strikethrough", "strikethrough")
                _merge_flag("double_strikethrough", "double_strikethrough")
                _merge_flag("superscript", "superscript")
                _merge_flag("subscript", "subscript")

                font_name = getattr(run, "font_name", None)
                # Try to get font from run.style if not directly on run
                if not font_name and isinstance(raw_style, dict):
                    font_name = (
                        raw_style.get("font_ascii") or 
                        raw_style.get("font_hAnsi") or 
                        raw_style.get("font_name") or
                        raw_style.get("font_eastAsia") or
                        raw_style.get("font_cs")
                    )
                # Fallback to paragraph style font
                if not font_name and isinstance(style, dict):
                    para_run_style = style.get("run", {})
                    if isinstance(para_run_style, dict):
                        font_name = (
                            para_run_style.get("font_ascii") or 
                            para_run_style.get("font_hAnsi") or 
                            para_run_style.get("font_name") or
                            para_run_style.get("font_eastAsia")
                        )
                    # Also check direct paragraph style
                    if not font_name:
                        font_name = (
                            style.get("font_ascii") or 
                            style.get("font_hAnsi") or 
                            style.get("font_name") or
                            style.get("font_eastAsia")
                        )
                if font_name:
                    run_style.setdefault("font_name", font_name)
                    run_style.setdefault("font_ascii", font_name)
                font_size = getattr(run, "font_size", None)
                if font_size:
                    run_style.setdefault("font_size", font_size)
                color = getattr(run, "color", None)
                if color:
                    if isinstance(color, str) and color and not color.startswith("#"):
                        color = f"#{color}"
                    run_style.setdefault("color", color)
                highlight = getattr(run, "highlight", None)
                if highlight:
                    run_style.setdefault("highlight", highlight)
                
                # Check if run has footnote/endnote references (in second loop)
                footnote_refs = []
                endnote_refs = []
                if hasattr(run, "footnote_refs") and run.footnote_refs:
                    footnote_refs = run.footnote_refs if isinstance(run.footnote_refs, list) else [run.footnote_refs]
                elif hasattr(run, "footnote_ref"):
                    footnote_refs = [run.footnote_ref]
                
                if hasattr(run, "endnote_refs") and run.endnote_refs:
                    endnote_refs = run.endnote_refs if isinstance(run.endnote_refs, list) else [run.endnote_refs]
                elif hasattr(run, "endnote_ref"):
                    endnote_refs = [run.endnote_ref]
                
                # Add footnote/endnote references to run_style and directly to run dict
                if footnote_refs:
                    run_style["footnote_refs"] = footnote_refs
                if endnote_refs:
                    run_style["endnote_refs"] = endnote_refs

                run_dict = {
                    "text": run_text,
                    "style": run_style,
                    "has_break": getattr(run, "has_break", False),
                    "has_tab": getattr(run, "has_tab", False),
                    "has_drawing": getattr(run, "has_drawing", False),
                }
                # Also add directly to run dict for easier access
                if footnote_refs:
                    run_dict["footnote_refs"] = footnote_refs
                if endnote_refs:
                    run_dict["endnote_refs"] = endnote_refs
                if run_fields:
                    run_dict["fields"] = run_fields  # Dodaj field codes do run dict
                
                # Add run to runs_payload even if no text, but has footnote/endnote references or field codes
                # This ensures footnote indices and field codes will be rendered
                if run_text or footnote_refs or endnote_refs or run_fields or getattr(run, "has_break", False) or getattr(run, "has_tab", False) or getattr(run, "has_drawing", False):
                    runs_payload.append(run_dict)

            if runs_payload:
                block_data["runs_payload"] = runs_payload
        
        # Add numbering information if exists
        has_numbering = bool(getattr(element, "numbering", None))
        hidden_marker = False
        if has_numbering:
            raw_numbering_info = getattr(element, "numbering", {})
            if isinstance(raw_numbering_info, dict):
                numbering_info = dict(raw_numbering_info)
            else:
                numbering_info = {
                    "id": getattr(raw_numbering_info, "id", None),
                    "level": getattr(raw_numbering_info, "level", None),
                }
            block_data["numbering"] = numbering_info
            if self._numbering_level_overridden(numbering_info.get("id"), numbering_info.get("level")):
                meta["numbering_override"] = True

            marker = self.numbering_formatter.format(
                numbering_info.get("id"), numbering_info.get("level")
            )

            if not self._has_visible_number_marker(element, marker):
                numbering_info["hidden_marker"] = True
                marker = None
                hidden_marker = True
                self.numbering_formatter.rewind(
                    numbering_info.get("id"), numbering_info.get("level")
                )
            elif marker:
                block_data["marker"] = marker

            metrics = self.numbering_formatter.get_level_metrics(
                numbering_info.get("id"), numbering_info.get("level")
            )
            if metrics:
                def _maybe_override(field_pt_key: str, metric_key: str) -> None:
                    metric_val = metrics.get(metric_key)
                    if metric_val is None:
                        return
                    current_val = indent_dict.get(field_pt_key)
                    if not current_val:
                        indent_dict[field_pt_key] = metric_val

                _maybe_override("left_pt", "indent_left")
                _maybe_override("right_pt", "indent_right")
                _maybe_override("first_line_pt", "indent_first_line")
                _maybe_override("hanging_pt", "indent_hanging")

                if metrics.get("text_position") is not None:
                    indent_dict["text_position_pt"] = metrics["text_position"]
                if metrics.get("tab_position") is not None:
                    indent_dict["tab_position_pt"] = metrics["tab_position"]
                if metrics.get("number_position") is not None:
                    indent_dict["number_position_pt"] = metrics["number_position"]
                if metrics.get("suffix") is not None:
                    indent_dict["suffix"] = metrics["suffix"]
                if metrics.get("alignment") is not None:
                    indent_dict["number_alignment"] = metrics["alignment"]

                if marker:
                    marker.setdefault("indent_left", indent_dict.get("left_pt", 0.0))
                    marker.setdefault("indent_right", indent_dict.get("right_pt", 0.0))
                    marker.setdefault("indent_hanging", indent_dict.get("hanging_pt", 0.0))
                    marker.setdefault("indent_first_line", indent_dict.get("first_line_pt", 0.0))
                    marker.setdefault("number_position", indent_dict.get("number_position_pt"))
                    marker.setdefault("text_position", indent_dict.get("text_position_pt"))
                    if indent_dict.get("suffix") is not None:
                        marker.setdefault("suffix", indent_dict.get("suffix"))
                    if indent_dict.get("number_alignment") is not None:
                        marker.setdefault("alignment", indent_dict.get("number_alignment"))
                    if indent_dict.get("tab_position_pt") is not None:
                        marker.setdefault("tab_position", indent_dict.get("tab_position_pt"))

                if not indent_dict.get("number_position_pt"):
                    indent_dict["number_position_pt"] = indent_dict.get("left_pt", 0.0) - indent_dict.get("hanging_pt", 0.0)

        if inline_indent_dict:
            def _apply_inline(key: str, value: Optional[float], sum_when_numbered: bool = True) -> None:
                if value is None:
                    return
                base = indent_dict.get(key)
                if base is None:
                    base = 0.0
                if has_numbering and sum_when_numbered:
                    indent_dict[key] = base + value
                else:
                    indent_dict[key] = value

            _apply_inline("left_pt", inline_indent_dict.get("left_pt"))
            _apply_inline("right_pt", inline_indent_dict.get("right_pt"))
            _apply_inline("first_line_pt", inline_indent_dict.get("first_line_pt"))
            _apply_inline("hanging_pt", inline_indent_dict.get("hanging_pt"))

            indent_dict["text_position_pt"] = indent_dict.get("first_line_pt", indent_dict.get("left_pt", 0.0))
            indent_dict["number_position_pt"] = indent_dict.get("left_pt", 0.0) - indent_dict.get("hanging_pt", 0.0)

            if "tab_position_pt" in indent_dict and indent_dict.get("tab_position_pt") is None:
                indent_dict.pop("tab_position_pt")

        if has_numbering and inline_indent_dict and not hidden_marker:
            marker = block_data.get("marker")
            if marker:
                marker["indent_left"] = indent_dict.get("left_pt", 0.0)
                marker["indent_right"] = indent_dict.get("right_pt", 0.0)
                marker["indent_first_line"] = indent_dict.get("first_line_pt", 0.0)
                marker["indent_hanging"] = indent_dict.get("hanging_pt", 0.0)
                marker["number_position"] = indent_dict.get("number_position_pt")
                marker["text_position"] = indent_dict.get("text_position_pt")
        
        # Section properties (sectPr) attached to this paragraph (signals section break)
        section_props = getattr(element, "section_properties", None)
        if section_props:
            try:
                block_data["section_properties"] = copy.deepcopy(section_props)
            except Exception:
                block_data["section_properties"] = section_props
        
        block_data["meta"] = dict(meta)
        return block_data

    @staticmethod
    def _to_points(value: Any) -> float:
        if value is None or value == "":
            return 0.0
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0.0
        if numeric > 144:
            return twips_to_points(numeric)
        return numeric

    def _resolve_spacing_metrics(self, style: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(style, dict):
            return {}

        spacing_raw = style.get("spacing")
        if isinstance(spacing_raw, dict):
            spacing_dict = dict(spacing_raw)
        else:
            spacing_dict = {}

        def _parse_float(value: Any) -> Optional[float]:
            if value in (None, ""):
                return None
            if isinstance(value, (int, float)):
                return float(value)
            try:
                return float(str(value).strip())
            except (ValueError, TypeError):
                return None

        def _parse_lines_value(value: Any) -> Optional[float]:
            numeric = _parse_float(value)
            if numeric is None:
                return None
            if abs(numeric) > 24:
                numeric = numeric / 240.0
            return numeric

        def _parse_bool_token(value: Any) -> bool:
            if isinstance(value, bool):
                return value
            if value in (None, "", {}):
                return False
            token = str(value).strip().lower()
            return token in {"1", "true", "yes", "on"}

        font_size = _parse_float(style.get("font_size")) or 11.0
        base_line_height = font_size * 1.2

        before_pt = _parse_float(spacing_dict.get("before_pt"))
        if before_pt is None:
            before_val = _parse_float(spacing_dict.get("before"))
            if before_val is not None:
                before_pt = twips_to_points(before_val)
        if before_pt is None:
            before_pt = _parse_float(style.get("spacing_before"))
        if before_pt is None:
            before_pt = 0.0

        after_pt = _parse_float(spacing_dict.get("after_pt"))
        if after_pt is None:
            after_val = _parse_float(spacing_dict.get("after"))
            if after_val is not None:
                after_pt = twips_to_points(after_val)
        if after_pt is None:
            after_pt = _parse_float(style.get("spacing_after"))
        if after_pt is None:
            after_pt = 0.0

        line_rule_raw = spacing_dict.get("lineRule") or spacing_dict.get("line_rule") or style.get("line_spacing_rule")
        if isinstance(line_rule_raw, str):
            line_rule = line_rule_raw.strip().lower() or None
        else:
            line_rule = None

        line_raw_value = _parse_float(spacing_dict.get("line"))
        style_line_spacing = _parse_float(style.get("line_spacing"))
        line_multiplier = None
        line_pt_value = None

        if line_rule == "auto":
            if line_raw_value is not None:
                line_multiplier = line_raw_value / 240.0
        else:
            if line_raw_value is not None:
                line_pt_value = twips_to_points(line_raw_value)

        line_height_pt = base_line_height

        if line_rule == "auto":
            if line_multiplier is None and style_line_spacing is not None:
                if style_line_spacing > 0 and style_line_spacing <= 8:
                    line_multiplier = style_line_spacing
                elif style_line_spacing > 8:
                    # Treat as absolute points converted to multiplier
                    tentative = style_line_spacing / base_line_height if base_line_height else 1.0
                    if tentative > 0:
                        line_multiplier = tentative
            if line_multiplier is None or line_multiplier <= 0:
                line_multiplier = 1.0
            line_height_pt = base_line_height * line_multiplier
        elif line_rule == "exact":
            effective_line = line_pt_value
            if effective_line is None and style_line_spacing is not None:
                effective_line = style_line_spacing if style_line_spacing > 0 else None
            if effective_line is not None and effective_line > 0:
                line_height_pt = effective_line
        elif line_rule == "atleast":
            threshold = line_pt_value
            if threshold is None and style_line_spacing is not None:
                threshold = style_line_spacing if style_line_spacing > 0 else None
            if threshold is not None and threshold > 0:
                line_height_pt = threshold if threshold > base_line_height else base_line_height
        else:
            if style_line_spacing is not None and style_line_spacing > 0:
                if style_line_spacing <= 8:
                    line_height_pt = base_line_height * style_line_spacing
                else:
                    line_height_pt = style_line_spacing

        before_lines_val = (
            spacing_dict.get("before_lines")
            if "before_lines" in spacing_dict
            else spacing_dict.get("beforeLines")
        )
        after_lines_val = (
            spacing_dict.get("after_lines")
            if "after_lines" in spacing_dict
            else spacing_dict.get("afterLines")
        )
        before_lines = _parse_lines_value(before_lines_val)
        after_lines = _parse_lines_value(after_lines_val)
        if before_lines is None:
            before_lines = _parse_lines_value(style.get("spacing_before_lines"))
        if after_lines is None:
            after_lines = _parse_lines_value(style.get("spacing_after_lines"))

        before_auto_flag = spacing_dict.get("before_autospacing") or spacing_dict.get("beforeAutospacing")
        if before_auto_flag is None:
            before_auto_flag = style.get("spacing_before_auto")
        after_auto_flag = spacing_dict.get("after_autospacing") or spacing_dict.get("afterAutospacing")
        if after_auto_flag is None:
            after_auto_flag = style.get("spacing_after_auto")
        before_auto = _parse_bool_token(before_auto_flag)
        after_auto = _parse_bool_token(after_auto_flag)

        line_reference_height = line_height_pt if line_height_pt > 0 else base_line_height
        if line_reference_height <= 0:
            line_reference_height = base_line_height if base_line_height > 0 else font_size * 1.2

        if before_lines is not None:
            before_pt = before_lines * line_reference_height
            spacing_dict["before_lines"] = before_lines
        if after_lines is not None:
            after_pt = after_lines * line_reference_height
            spacing_dict["after_lines"] = after_lines

        if before_auto and before_pt == 0.0:
            before_pt = line_reference_height
        if after_auto and after_pt == 0.0:
            after_pt = line_reference_height

        spacing_dict["before_pt"] = before_pt
        spacing_dict["after_pt"] = after_pt
        spacing_dict["line_rule_resolved"] = line_rule
        spacing_dict["line_height_pt"] = line_height_pt
        spacing_dict["base_line_height_pt"] = base_line_height
        if line_multiplier is not None:
            spacing_dict["line_multiplier"] = line_multiplier
        if line_pt_value is not None:
            spacing_dict["line_point"] = line_pt_value

        style["spacing"] = spacing_dict
        style["spacing_before"] = before_pt
        style["spacing_after"] = after_pt
        if before_lines is not None:
            style["spacing_before_lines"] = before_lines
        if after_lines is not None:
            style["spacing_after_lines"] = after_lines
        if before_auto:
            style["spacing_before_auto"] = True
        if after_auto:
            style["spacing_after_auto"] = True
        if line_rule:
            style["line_spacing_rule"] = line_rule
        style["line_spacing_effective"] = line_height_pt

        return {
            "before_pt": before_pt,
            "after_pt": after_pt,
            "line_rule": line_rule,
            "line_height_pt": line_height_pt,
            "line_multiplier": line_multiplier if line_rule == "auto" else None,
            "base_line_height_pt": base_line_height,
            "style_line_spacing": style_line_spacing,
        }

    @staticmethod
    def _collect_leading_run_text(element: Any, limit: int = 48) -> str:
        """Extract the concatenated text from runs/children up to a character limit."""
        text_parts: List[str] = []
        remaining = limit

        def _consume_text(candidate: Any) -> None:
            nonlocal remaining
            if remaining <= 0:
                return
            run_text = getattr(candidate, "text", None)
            if not run_text and hasattr(candidate, "get_text") and callable(candidate.get_text):
                try:
                    run_text = candidate.get_text()
                except Exception:
                    run_text = None
            if isinstance(run_text, str) and run_text:
                slice_text = run_text[:remaining]
                text_parts.append(slice_text)
                remaining -= len(slice_text)

        runs = getattr(element, "runs", None)
        if runs:
            for run in runs:
                _consume_text(run)
                if remaining <= 0:
                    break
        elif hasattr(element, "children"):
            for child in getattr(element, "children", []):
                _consume_text(child)
                if remaining <= 0:
                    break

        return "".join(text_parts).strip()

    def _has_visible_number_marker(self, element: Any, marker: Optional[Dict[str, Any]]) -> bool:
        """Determine whether a numbering marker should be considered visible."""
        if marker:
            marker_text = str(marker.get("text", ""))
            if marker_text.strip():
                return True

        leading_text = self._collect_leading_run_text(element)
        if not leading_text:
            return False

        return bool(_LIST_MARKER_REGEX.match(leading_text))

    def _postprocess_paragraphs(self, blocks: List[Dict[str, Any]]) -> None:
        """Resolve indents by building a logical list tree."""
        builder = ListTreeBuilder(self._numbering_data)
        builder.reset()

        for block in blocks:
            if not self._is_paragraph_block(block):
                continue

            entry = self._make_paragraph_entry(block)
            indent_spec, text_start, number_start, effective_num_id, effective_level, meta = builder.process_paragraph(entry)
            self._apply_indent_values(block, indent_spec, text_start, number_start)
            self._update_marker_geometry_from_values(block, indent_spec, text_start, number_start)
            marker_override = meta.get("marker_override_text")
            if marker_override is not None:
                marker_dict = block.get("marker")
                if not isinstance(marker_dict, dict):
                    marker_dict = {}
                    block["marker"] = marker_dict
                marker_dict["text"] = marker_override
                if "marker_override_counter" in meta:
                    marker_dict["counter"] = meta["marker_override_counter"]
            self._apply_meta_updates(block, meta)
        
        # Print list tree structure for debugging
        builder.print_tree_structure()

    # ------------------------------------------------------------------
    # Helper methods related to indentation
    # ------------------------------------------------------------------

    @staticmethod
    def _is_paragraph_block(block: Dict[str, Any]) -> bool:
        return isinstance(block, dict) and block.get("type") == "paragraph"

    def _make_paragraph_entry(self, block: Dict[str, Any]) -> _ParagraphEntry:
        style_dict = block.get("style") or {}
        meta_dict = block.get("meta") or {}
        indent_dict = block.get("indent") or {}

        style_name = str(style_dict.get("style_name") or style_dict.get("style") or "")
        style_is_list = self._style_is_list_style(style_name, style_dict)
        has_border_style = self._style_has_border(style_dict)

        paragraph_indent = self._indent_spec_from_dict(indent_dict)
        style_indent = self._indent_spec_from_dict(style_dict.get("indent"))
        inline_indent_spec = self._inline_indent_spec(block.get("inline_indent"))

        numbering = block.get("numbering") or {}
        num_id_raw = numbering.get("id") or numbering.get("num_id")
        num_id = str(num_id_raw) if num_id_raw is not None else None
        level = self._safe_int(numbering.get("level"))

        marker_dict = block.get("marker") or {}
        marker_text = str(marker_dict.get("text") or "")
        marker_visible = bool(marker_text.strip())

        text_preview = (block.get("text") or "").lstrip()

        explicit_indent = bool(meta_dict.get("explicit_indent"))
        if explicit_indent and numbering.get("id") and not block.get("inline_indent"):
            explicit_indent = False
        number_override = bool(meta_dict.get("numbering_override"))
        auto_correction = self._is_auto_correctable(meta_dict, style_is_list, num_id)

        return _ParagraphEntry(
            block_ref=block,
            style_name=style_name,
            paragraph_indent=paragraph_indent,
            style_indent=style_indent,
            num_id=num_id,
            level=level,
            marker_text=marker_text,
            marker_visible=marker_visible,
            style_is_list=style_is_list,
            has_border=has_border_style,
            number_override=number_override,
            auto_correction=auto_correction,
            explicit_indent=explicit_indent,
            inline_indent=inline_indent_spec,
        )

    def _apply_indent_values(self, block: Dict[str, Any], indent_spec: _IndentSpec, text_start: float, number_start: float) -> None:
        indent = block.get("indent")
        if not isinstance(indent, dict):
            indent = {}
            block["indent"] = indent

        indent["left_pt"] = indent_spec.left
        indent["left"] = indent_spec.left
        indent["right_pt"] = indent_spec.right
        indent["right"] = indent_spec.right
        indent["first_line_pt"] = indent_spec.first_line
        indent["first_line"] = indent_spec.first_line
        indent["hanging_pt"] = indent_spec.hanging
        indent["hanging"] = indent_spec.hanging
        indent["text_position_pt"] = text_start
        indent["text_position"] = text_start
        indent["number_position_pt"] = number_start
        indent["number_position"] = number_start
        indent["tab_position_pt"] = text_start
        indent["tab_position"] = text_start

    def _update_marker_geometry_from_values(self, block: Dict[str, Any], indent_spec: _IndentSpec, text_start: float, number_start: float) -> None:
        marker = block.get("marker")
        if not isinstance(marker, dict):
            return

        marker["indent_left"] = indent_spec.left
        marker["indent_hanging"] = indent_spec.hanging
        marker["indent_first_line"] = indent_spec.left if indent_spec.hanging == 0 else number_start
        marker["number_position"] = number_start
        marker["text_position"] = text_start
        marker["tab_position"] = text_start

    def _apply_meta_updates(self, block: Dict[str, Any], meta_updates: Dict[str, Any]) -> None:
        meta = block.setdefault("meta", {})
        if meta_updates:
            meta.update(meta_updates)

    def _is_auto_correctable(
        self,
        meta: Dict[str, Any],
        style_is_list: bool,
        num_id: Optional[str],
    ) -> bool:
        if meta.get("explicit_indent"):
            return False
        if meta.get("numbering_override"):
            return False
        if num_id and not style_is_list:
            return False
        if meta.get("explicit_numbering"):
            return False
        return True

    def _numbering_level_overridden(self, num_id: Optional[str], level: Optional[Any]) -> bool:
        if num_id in (None, "", False) or level in (None, "", False):
            return False
        data = self._numbering_data or {}
        instances = data.get("numbering_instances") or {}
        instance = instances.get(str(num_id))
        if not instance:
            return False
        overrides = instance.get("levels") or {}
        return str(level) in overrides

    def _indent_spec_from_dict(self, indent_dict: Optional[Dict[str, Any]]) -> _IndentSpec:
        if not isinstance(indent_dict, dict):
            return _IndentSpec()

        return _IndentSpec(
            left=self._safe_float(indent_dict.get("left_pt") or indent_dict.get("left")),
            right=self._safe_float(indent_dict.get("right_pt") or indent_dict.get("right")),
            first_line=self._safe_float(indent_dict.get("first_line_pt") or indent_dict.get("first_line")),
            hanging=self._safe_float(indent_dict.get("hanging_pt") or indent_dict.get("hanging")),
        )

    def _inline_indent_spec(self, inline_dict: Optional[Dict[str, Any]]) -> Optional[_IndentSpec]:
        if not isinstance(inline_dict, dict):
            return None
        left = self._safe_float(inline_dict.get("left_pt"))
        right = self._safe_float(inline_dict.get("right_pt"))
        first_line = self._safe_float(inline_dict.get("first_line_pt"))
        hanging = self._safe_float(inline_dict.get("hanging_pt"))
        if not any((left, right, first_line, hanging)):
            return None
        return _IndentSpec(left=left, right=right, first_line=first_line, hanging=hanging)

    @staticmethod
    def _style_is_list_style(style_name: str, style_dict: Dict[str, Any]) -> bool:
        name = style_name.lower()
        if any(token in name for token in ("list", "bullet", "number")):
            return True
        numbering = style_dict.get("numbering")
        if numbering:
            return True
        return False

    @staticmethod
    def _style_has_border(style_dict: Dict[str, Any]) -> bool:
        if not style_dict:
            return False
        if style_dict.get("_border_group_id"):
            return True
        if style_dict.get("borders"):
            return True
        if style_dict.get("background") or style_dict.get("background_color"):
            return True
        if style_dict.get("shading"):
            return True
        return False

    @staticmethod
    def _safe_float(value: Any) -> float:
        if value in (None, "", False):
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).strip())
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        if value in (None, "", False):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return None

    def _build_table(self, element: Any) -> Dict[str, Any]:
        style = self.style_bridge.resolve(element, "table")
        rows = getattr(element, "rows", [])
        
        # Get grid (column widths) from element
        grid = None
        if hasattr(element, "grid"):
            grid = element.grid
        elif hasattr(element, "properties") and hasattr(element.properties, "grid"):
            grid = element.properties.grid
        
        return {
            "type": "table",
            "rows": rows,
            "grid": grid,  # Add grid (column widths) to structure
            "style": style,
            "page_break_before": self._get_page_break_before(element),
            "page_break_after": self._get_page_break_after(element),
            "keep_with_next": getattr(element, "keep_with_next", False) or style.get("keep_with_next", False),
        }

    def _build_image(self, element: Any) -> Dict[str, Any]:
        style = self.style_bridge.resolve(element, "image")
        
        # Get image path - handle both objects and dict
        path = None
        if isinstance(element, dict):
            path = element.get("path") or element.get("image_path") or element.get("src")
        else:
            path = getattr(element, "path", "") or getattr(element, "image_path", "")
        
        # Pobierz wymiary obrazu
        width = None
        height = None
        if isinstance(element, dict):
            width = element.get("width")
            height = element.get("height")
        else:
            width = getattr(element, "width", None)
            height = getattr(element, "height", None)
        
        return {
            "type": "image",
            "path": path or "",
            "image_path": path or "",  # For compatibility
            "style": style,
            "page_break_before": self._get_page_break_before(element),
            "page_break_after": self._get_page_break_after(element),
            "width": width or style.get("width"),
            "height": height or style.get("height"),
            "relationship_id": element.get("relationship_id") if isinstance(element, dict) else getattr(element, "relationship_id", None),
        }

    def _build_textbox(self, element: Any) -> Dict[str, Any]:
        style = self.style_bridge.resolve(element, "textbox")
        content = getattr(element, "content", "") or getattr(element, "get_text", lambda: "")()
        
        # Get anchor_info if element has textbox_anchor_info
        anchor_info = None
        if hasattr(element, 'textbox_anchor_info') and element.textbox_anchor_info:
            anchor_info = element.textbox_anchor_info
        elif hasattr(element, 'anchor_info') and element.anchor_info:
            anchor_info = element.anchor_info
        
        # If content is dict, add anchor_info
        if isinstance(content, dict):
            if anchor_info:
                content["anchor_info"] = anchor_info
        elif anchor_info:
            # If content is string, convert to dict with anchor_info
            content = {
                "content": content,
                "text": str(content) if content else "",
                "anchor_info": anchor_info
            }
        
        # Set anchor_type directly in dict (as in _build_textbox_dict)
        anchor_type = (anchor_info or {}).get('anchor_type', 'inline') if anchor_info else 'inline'
        
        return {
            "type": "textbox",
            "content": content,
            "style": style,
            "anchor_type": anchor_type,
            "anchor_info": anchor_info,
            "page_break_before": self._get_page_break_before(element),
            "page_break_after": self._get_page_break_after(element),
        }

    def _build_header(self, element: Any) -> Dict[str, Any]:
        style = self.style_bridge.resolve(element, "header")
        
        # Get text from element - handle various types
        text = ""
        images = []
        
        # Check if paragraph has images at paragraph level (not just in runs)
        if hasattr(element, "images"):
            for img in element.images:
                images.append(img)
        
        if hasattr(element, "get_text"):
            text = element.get_text()
        elif hasattr(element, "text"):
            text = str(element.text) if element.text else ""
        elif hasattr(element, "runs"):
            # If element has runs, collect text and images from all runs
            text_parts = []
            for run in element.runs:
                # Tekst z run
                if hasattr(run, "get_text"):
                    run_text = run.get_text()
                    if run_text:
                        text_parts.append(run_text)
                elif hasattr(run, "text"):
                    run_text = str(run.text) if run.text else ""
                    if run_text:
                        text_parts.append(run_text)
                
                # Obrazy z run
                if hasattr(run, "images"):
                    for img in run.images:
                        images.append(img)
                elif hasattr(run, "children"):
                    for child in run.children:
                        if hasattr(child, "path") or hasattr(child, "image_path") or type(child).__name__.lower() == "image":
                            images.append(child)
            
            text = " ".join(text_parts)
        
        # Resolve placeholders
        if self.resolve_placeholders:
            text = self.placeholder_resolver.resolve_text(text)
        
        # If element is table, try to extract text from table
        if hasattr(element, "rows") or type(element).__name__.lower() == "table":
            # For table, collect text from all cells
            text_parts = []
            if hasattr(element, "rows"):
                for row in element.rows:
                    if hasattr(row, "cells"):
                        for cell in row.cells:
                            if hasattr(cell, "get_text"):
                                cell_text = cell.get_text()
                                if cell_text:
                                    text_parts.append(cell_text)
                            elif hasattr(cell, "text"):
                                cell_text = str(cell.text) if cell.text else ""
                                if cell_text:
                                    text_parts.append(cell_text)
            text = " ".join(text_parts) if text_parts else text
        
        # Build content - may contain text and images
        content = {
            "text": text,
            "images": images,
            "content": text  # For compatibility
        }
        
        return {
            "type": "header",
            "text": text,
            "content": content,
            "images": images,
            "style": style,
            "header_type": getattr(element, "header_type", "default"),  # first, even, default
        }

    def _build_footer(self, element: Any) -> Dict[str, Any]:
        """

        Builds footer block with support for various element types.

        Supports:
        - Paragraphs with text and images
        - Tables
        - Images
        - Textboxes
        - Other special elements

        """
        style = self.style_bridge.resolve(element, "footer")
        
        # Get text from element - handle various types
        text = ""
        images = []
        textboxes = []

        def _build_textbox_dict(tb_source):
            anchor_info = None
            textbox_text_parts = []
            paragraph_style_id = None
            paragraph_spacing = None

            if isinstance(tb_source, list):
                for tb_run in tb_source:
                    if hasattr(tb_run, 'textbox_anchor_info') and tb_run.textbox_anchor_info:
                        anchor_info = tb_run.textbox_anchor_info
                        break
                for tb_run in tb_source:
                    if paragraph_style_id is None:
                        paragraph_style_id = getattr(tb_run, "paragraph_style_id", None) or getattr(tb_run, "paragraph_style", None)
                    if paragraph_spacing is None:
                        spacing = getattr(tb_run, "paragraph_spacing", None)
                        if spacing:
                            paragraph_spacing = dict(spacing)
                    if hasattr(tb_run, "get_text"):
                        run_text = tb_run.get_text()
                    elif hasattr(tb_run, "text"):
                        run_text = str(tb_run.text) if tb_run.text else ""
                    else:
                        run_text = ""
                    if run_text:
                        textbox_text_parts.append(run_text)
            else:
                if hasattr(tb_source, 'textbox_anchor_info') and tb_source.textbox_anchor_info:
                    anchor_info = tb_source.textbox_anchor_info
                if paragraph_style_id is None:
                    paragraph_style_id = getattr(tb_source, "paragraph_style_id", None) or getattr(tb_source, "paragraph_style", None)
                if paragraph_spacing is None:
                    spacing = getattr(tb_source, "paragraph_spacing", None)
                    if spacing:
                        paragraph_spacing = dict(spacing)
                if hasattr(tb_source, "get_text"):
                    run_text = tb_source.get_text()
                    if run_text:
                        textbox_text_parts.append(run_text)
                elif hasattr(tb_source, "text") and tb_source.text:
                    textbox_text_parts.append(str(tb_source.text))

            textbox_style: Dict[str, Any] = {}
            if paragraph_style_id:
                proxy = SimpleNamespace(style_id=paragraph_style_id)
                resolved_style = self.style_bridge.resolve(proxy, "paragraph")
                if isinstance(resolved_style, dict):
                    textbox_style.update(resolved_style)
                textbox_style.setdefault("style_id", paragraph_style_id)
                textbox_style.setdefault("style_name", resolved_style.get("style_name") if isinstance(resolved_style, dict) else paragraph_style_id)
                if self.style_manager:
                    resolved = self.style_manager.resolve_style(paragraph_style_id)
                    if resolved:
                        props = resolved.get("properties") or {}
                        spacing_before = props.get("spacing_before")
                        spacing_after = props.get("spacing_after")
                        line_spacing_raw = props.get("line_spacing")
                        line_rule = props.get("line_rule")
                        if spacing_before not in (None, "", "0"):
                            try:
                                textbox_style["spacing_before"] = twips_to_points(float(spacing_before))
                            except (TypeError, ValueError):
                                pass
                        if spacing_after not in (None, "", "0"):
                            try:
                                textbox_style["spacing_after"] = twips_to_points(float(spacing_after))
                            except (TypeError, ValueError):
                                pass
                        if line_spacing_raw not in (None, "", "0"):
                            try:
                                textbox_style["line_spacing"] = twips_to_points(float(line_spacing_raw))
                                textbox_style["line_spacing_rule"] = line_rule or "auto"
                            except (TypeError, ValueError):
                                pass
                        run_props = props.get("run") or {}
                        font_size_raw = run_props.get("font_size") or run_props.get("sz")
                        if font_size_raw not in (None, "", "0"):
                            try:
                                textbox_style["font_size"] = max(float(font_size_raw) / 2.0, 0.1)
                            except (TypeError, ValueError):
                                pass
                        font_size_cs = run_props.get("font_size_cs")
                        if "font_size" not in textbox_style and font_size_cs not in (None, "", "0"):
                            try:
                                textbox_style["font_size"] = max(float(font_size_cs) / 2.0, 0.1)
                            except (TypeError, ValueError):
                                pass
                        font_name = run_props.get("font_name")
                        if font_name:
                            textbox_style["font_name"] = font_name
                        color = run_props.get("color")
                        if color:
                            textbox_style["color"] = color
            if paragraph_spacing:
                spacing_existing = textbox_style.get("spacing")
                if isinstance(spacing_existing, dict):
                    spacing_existing.update(paragraph_spacing)
                else:
                    textbox_style["spacing"] = dict(paragraph_spacing)

            textbox_dict = {
                "type": "textbox",
                "anchor_type": (anchor_info or {}).get('anchor_type', 'inline'),
                "position": (anchor_info or {}).get('position', {}),
                "width": (anchor_info or {}).get('width', 0),
                "height": (anchor_info or {}).get('height', 0),
                "content": tb_source,
                "text": " ".join(textbox_text_parts).strip(),
            }
            textbox_dict["style"] = dict(textbox_style)
            if paragraph_style_id:
                textbox_dict["style_ref"] = paragraph_style_id
                textbox_dict["style_id"] = paragraph_style_id
            return textbox_dict

        def _append_textbox(tb_source):
            if not tb_source:
                return
            if isinstance(tb_source, list) and len(tb_source) == 1:
                textboxes.append(_build_textbox_dict(tb_source[0]))
            else:
                textboxes.append(_build_textbox_dict(tb_source))

        # Check if element has images at element level (not just in runs)
        if hasattr(element, "images"):
            images_list = element.images if isinstance(element.images, list) else [element.images] if element.images else []
            images.extend(images_list)
        
        # Check if element has textboxes
        if hasattr(element, "textbox") and element.textbox:
            textboxes_list = element.textbox if isinstance(element.textbox, list) else [element.textbox] if element.textbox else []
            for tb_item in textboxes_list:
                _append_textbox(tb_item)
        
        # Pobierz tekst z elementu
        fields = []
        if hasattr(element, "get_text"):
            text = element.get_text()
        elif hasattr(element, "text"):
            text = str(element.text) if element.text else ""
        elif hasattr(element, "runs"):
            # If element has runs, collect text, images, fields and textboxes from all runs
            text_parts = []
            for run in element.runs:
                # Tekst z run
                if hasattr(run, "get_text"):
                    run_text = run.get_text()
                    if run_text:
                        text_parts.append(run_text)
                elif hasattr(run, "text"):
                    run_text = str(run.text) if run.text else ""
                    if run_text:
                        text_parts.append(run_text)
                
                # Obrazy z run
                if hasattr(run, "images"):
                    run_images = run.images if isinstance(run.images, list) else [run.images] if run.images else []
                    images.extend(run_images)
                elif hasattr(run, "children"):
                    for child in run.children:
                        if hasattr(child, "path") or hasattr(child, "image_path") or type(child).__name__.lower() == "image":
                            images.append(child)
                        elif hasattr(child, "textbox") or type(child).__name__.lower() == "textbox":
                            _append_textbox(child)
                        elif isinstance(child, dict) and child.get("type") == "Field":
                            field_instr = child.get("instr", "")
                            if field_instr:
                                fields.append({
                                    "type": "field",
                                    "instr": field_instr,
                                    "field_type": self._detect_field_type(field_instr)
                                })
                        elif hasattr(child, "type") and getattr(child, "type", None) == "Field":
                            field_instr = getattr(child, "instr", "")
                            if field_instr:
                                fields.append({
                                    "type": "field",
                                    "instr": field_instr,
                                    "field_type": self._detect_field_type(field_instr)
                                })
            
                # Textboxes assigned directly to run
                if hasattr(run, "textbox") and run.textbox:
                    _append_textbox(run.textbox)

            text = " ".join(text_parts)
        elif hasattr(element, "children"):
            # If element has children, collect text and images from all children
            text_parts = []
            for child in element.children:
                if hasattr(child, "get_text"):
                    child_text = child.get_text()
                    if child_text:
                        text_parts.append(child_text)
                elif hasattr(child, "text"):
                    child_text = str(child.text) if child.text else ""
                    if child_text:
                        text_parts.append(child_text)
                
                # Obrazy z child
                if hasattr(child, "images"):
                    child_images = child.images if isinstance(child.images, list) else [child.images] if child.images else []
                    images.extend(child_images)
                elif hasattr(child, "path") or hasattr(child, "image_path") or type(child).__name__.lower() == "image":
                    images.append(child)
                
                # Textboxy z child
                if hasattr(child, "textbox") or type(child).__name__.lower() == "textbox":
                    _append_textbox(child)
            
            text = " ".join(text_parts)
        
        # Resolve placeholders
        if self.resolve_placeholders:
            text = self.placeholder_resolver.resolve_text(text)
        
        # If element is table, try to extract text from table
        if hasattr(element, "rows") or type(element).__name__.lower() == "table":
            # For table, collect text from all cells
            text_parts = []
            if hasattr(element, "rows"):
                for row in element.rows:
                    if hasattr(row, "cells"):
                        for cell in row.cells:
                            if hasattr(cell, "get_text"):
                                cell_text = cell.get_text()
                                if cell_text:
                                    text_parts.append(cell_text)
                            elif hasattr(cell, "text"):
                                cell_text = str(cell.text) if cell.text else ""
                                if cell_text:
                                    text_parts.append(cell_text)
                            
                            # Images from cells
                            if hasattr(cell, "images"):
                                cell_images = cell.images if isinstance(cell.images, list) else [cell.images] if cell.images else []
                                images.extend(cell_images)
            text = " ".join(text_parts) if text_parts else text
        
        # Build content - may contain text, images, textboxes and fields
        content = {
            "text": text,
            "images": images,
            "textboxes": textboxes,
            "fields": fields,
            "content": text  # For compatibility
        }
        
        return {
            "type": "footer",
            "text": text,
            "content": content,
            "images": images,
            "textboxes": textboxes,
            "fields": fields,
            "style": style,
            "footer_type": getattr(element, "footer_type", "default"),  # first, even, default
        }

    def _build_generic(self, element: Any) -> Dict[str, Any]:
        style = self.style_bridge.resolve(element, "paragraph")
        text = getattr(element, "text", "") or getattr(element, "get_text", lambda: "")()
        
        return {
            "type": "generic",
            "content": text,
            "style": style,
            "page_break_before": self._get_page_break_before(element),
            "page_break_after": self._get_page_break_after(element),
        }
    
    # ----------------------------------------------------------------------
    # Helper methods for pagination properties
    # ----------------------------------------------------------------------
    def _get_page_break_before(self, element: Any) -> bool:
        """Sprawdza czy element wymaga page-break-before."""
        # Check element attribute
        if hasattr(element, "page_break_before") and element.page_break_before:
            return True
        if hasattr(element, "break_before") and element.break_before == "page":
            return True
        
        # Check in style
        style = getattr(element, "style", {})
        if isinstance(style, dict):
            if style.get("page_break_before") or style.get("break_before") == "page":
                return True
        
        return False
    
    def _detect_field_type(self, instruction: str) -> str:
        """
        Wykrywa typ pola na podstawie instrukcji.
        
        Args:
            instruction: Instrukcja pola (np. "PAGE", "NUMPAGES", "DATE")
            
        Returns:
            Typ pola (PAGE, NUMPAGES, DATE, etc.)
        """
        instruction = instruction.strip().upper()
        
        if instruction.startswith('PAGE'):
            return 'PAGE'
        elif instruction.startswith('NUMPAGES'):
            return 'NUMPAGES'
        elif instruction.startswith('DATE'):
            return 'DATE'
        elif instruction.startswith('TIME'):
            return 'TIME'
        elif instruction.startswith('REF'):
            return 'REF'
        elif instruction.startswith('TOC'):
            return 'TOC'
        else:
            return 'unknown'
    
    def _get_page_break_after(self, element: Any) -> bool:
        """Sprawdza czy element wymaga page-break-after."""
        # Check element attribute
        if hasattr(element, "page_break_after") and element.page_break_after:
            return True
        if hasattr(element, "break_after") and element.break_after == "page":
            return True
        
        # Check in style
        style = getattr(element, "style", {})
        if isinstance(style, dict):
            if style.get("page_break_after") or style.get("break_after") == "page":
                return True
        
        return False
