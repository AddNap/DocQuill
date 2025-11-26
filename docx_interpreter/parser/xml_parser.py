"""
Main XML parser for DOCX documents.

Central XML parsing coordination with factory pattern.
"""

import xml.etree.ElementTree as ET
from lxml import etree as lxml_etree
from typing import List, Optional, Dict, Any, Union
import logging

from ..styles.style_manager import StyleManager

logger = logging.getLogger(__name__)

class XMLParser:
    """
    Main XML parser for DOCX documents with factory pattern.
    
    Coordinates parsing of all XML components with factory pattern.
    """
    
    # Factory pattern - tag mapping registry
    TAG_MAP = {
        "p": "Paragraph",
        "r": "Run", 
        "tbl": "Table",
        "tr": "TableRow",
        "tc": "TableCell",
        "drawing": "Image",
        "fldSimple": "Field",
        "hyperlink": "Hyperlink",
        "txbxContent": "TextBox",
    }
    
    def __init__(self, package_reader):
        """
        Initialize XML parser with factory registry.
        
        Args:
            package_reader: PackageReader instance for accessing DOCX content
        """
        self.package_reader = package_reader
        self.ns = {
            "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
            "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
            "a": "http://schemas.openxmlformats.org/drawingml/2006/main"
        }
        self.ns_wps = {"wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"}
        self.ns_v = {"v": "urn:schemas-microsoft-com:vml"}
        self.parser_registry = self._build_parser_registry()
        
        # Cache for parsed elements
        self._element_cache: Dict[str, Any] = {}
        self._current_part_path: Optional[str] = None
        self._current_relationship_file: Optional[str] = None
        
        # Image conversion cache (set externally)
        self.image_cache = None
        
        # Initialize numbering parser
        from .numbering_parser import NumberingParser
        self.numbering_parser = NumberingParser(package_reader)
        self.numbering_data = self.numbering_parser.parse_numbering()
        try:
            self.style_manager = StyleManager(package_reader)
            self.style_manager.load_styles()
        except Exception as exc:
            logger.debug(f"Failed to initialize StyleManager: {exc}")
            self.style_manager = None
        
        logger.info("XML parser initialized")
    
    def _sanitize_attrib(self, attrib: Dict[str, Any]) -> Dict[str, Any]:
        """Strip namespaces and prefixes from attribute keys for easier downstream use."""
        clean: Dict[str, Any] = {}
        for key, value in attrib.items():
            if '}' in key:
                clean_key = key.split('}')[-1]
            elif ':' in key:
                clean_key = key.split(':')[-1]
            else:
                clean_key = key
            clean[clean_key] = value
        return clean

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        if value in (None, "", {}):
            return None
        if isinstance(value, (int, float)):
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
        try:
            return float(str(value).strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalize_color_value(value: Any) -> Optional[str]:
        if value in (None, "", {}, "auto", "Auto", "AUTO", "none", "None", "NONE"):
            return None
        token = str(value).strip()
        if not token or token.lower() in {"auto", "none", "transparent"}:
            return None
        if token.startswith("#"):
            token = token[1:]
        if len(token) == 3 and all(ch in "0123456789abcdefABCDEF" for ch in token):
            token = "".join(ch * 2 for ch in token)
        if len(token) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in token):
            return f"#{token.upper()}"
        return None

    def _parse_border_spec(self, border_elem) -> Optional[Dict[str, Any]]:
        if border_elem is None:
            return None

        attrs = self._sanitize_attrib(border_elem.attrib)
        if not attrs:
            return None

        spec: Dict[str, Any] = dict(attrs)

        style_token = attrs.get("val") or attrs.get("style")
        if style_token:
            spec["style"] = style_token
            style_lower = str(style_token).strip().lower()
            if style_lower in {"none", "nil"}:
                # Explicitly mark as non-visible border. Keep raw attributes for downstream logic.
                return spec

        size_raw = attrs.get("width")
        width_pt = None
        if size_raw is not None:
            width_pt = self._safe_float(size_raw)
        elif attrs.get("sz") is not None:
            size_value = self._safe_float(attrs.get("sz"))
            if size_value is not None:
                width_pt = size_value / 8.0
        if width_pt is not None:
            spec["width"] = width_pt

        space_raw = attrs.get("space")
        space_value = self._safe_float(space_raw)
        if space_value is not None:
            spec["space"] = space_value

        color_raw = attrs.get("color") or attrs.get("colour")
        if color_raw is not None:
            spec["color_raw"] = color_raw
            normalized_color = self._normalize_color_value(color_raw)
            if normalized_color:
                spec["color"] = normalized_color

        theme_color = attrs.get("themeColor") or attrs.get("theme_colour")
        if theme_color:
            spec["theme_color"] = theme_color
        theme_tint = attrs.get("themeTint")
        if theme_tint:
            spec["theme_tint"] = theme_tint

        shadow = attrs.get("shadow")
        if shadow not in (None, "", "0", "false", "False"):
            spec["shadow"] = True

        return spec
    
    def _build_parser_registry(self) -> Dict[str, callable]:
        """Build registry of parser functions."""
        return {
            "Paragraph": self._parse_paragraph,
            "Run": self._parse_run,
            "Table": self._parse_table,
            "TableRow": self._parse_table_row,
            "TableCell": self._parse_table_cell,
            "Image": self._parse_image,
            "Field": self._parse_field,
            "Hyperlink": self._parse_hyperlink,
            "TextBox": self._parse_textbox,
        }
    
    def parse_metadata(self) -> Dict[str, Any]:
        """
        Parse document metadata from core.xml, app.xml, and custom.xml.
        
        Returns:
            Dictionary of metadata
        """
        try:
            metadata = {}
            
            # Parse core properties
            try:
                core_props_xml = self.package_reader.get_xml_content("docProps/core.xml")
                if core_props_xml:
                    metadata['core_properties'] = self._parse_core_properties(core_props_xml)
            except KeyError:
                pass
            
            # Parse app properties
            try:
                app_props_xml = self.package_reader.get_xml_content("docProps/app.xml")
                if app_props_xml:
                    metadata['app_properties'] = self._parse_app_properties(app_props_xml)
            except KeyError:
                pass
            
            # Parse custom properties
            try:
                custom_props_xml = self.package_reader.get_xml_content("docProps/custom.xml")
                if custom_props_xml:
                    metadata['custom_properties'] = self._parse_custom_properties(custom_props_xml)
            except KeyError:
                pass
            
            logger.info(f"Parsed metadata: {len(metadata)} properties")
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to parse metadata: {e}")
            return {}
    
    def parse_body(self) -> 'Body':
        """
        Parse document body content.
        
        Returns:
            Body object containing parsed elements
        """
        try:
            # Import Body class
            from ..models.body import Body
            
            # Get document XML
            document_xml = self.package_reader.get_xml_content("word/document.xml")
            if not document_xml:
                logger.warning("No document.xml found")
                return Body()
            
            # Parse document root
            root = ET.fromstring(document_xml)
            body_element = root.find("w:body", self.ns)
            if body_element is None:
                logger.warning("No body element found in document")
                return Body()
            
            previous_part = self._current_part_path
            previous_rel = self._current_relationship_file
            self._current_part_path = "word/document.xml"
            self._current_relationship_file = "word/_rels/document.xml.rels"
            try:
                # Create Body object
                body = Body()
                
                # Parse body elements in order (like old renderer)
                # Iterate through all direct children of body, preserving order
                for child in list(body_element):
                    tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    
                    # Skip sectPr (section properties) - handled separately
                    if tag == 'sectPr':
                        # Parse section properties but don't add to body content
                        sect_props = self._parse_section_properties(child)
                        if sect_props:
                            body.section_properties = sect_props
                        continue
                    
                    # Parse element and add to body (preserving order)
                    element = self.parse_element(child, body)
                    if element:
                        body.add_child(element)
                
                logger.info(f"Parsed {len(body.children)} body elements")
                return body
            finally:
                self._current_part_path = previous_part
                self._current_relationship_file = previous_rel
            
        except Exception as e:
            logger.error(f"Failed to parse body: {e}")
            # Re-raise exception for error handling tests
            raise e
    
    def parse_element(self, node, parent) -> Optional[Any]:
        """
        Parse single XML element using factory pattern.
        
        Args:
            node: XML element to parse
            parent: Parent element (if any)
            
        Returns:
            Parsed element or None
        """
        try:
            # Extract tag name (remove namespace)
            tag = node.tag.split("}")[-1] if "}" in node.tag else node.tag
            cls_name = self.TAG_MAP.get(tag)
            
            if cls_name and cls_name in self.parser_registry:
                # Use factory pattern to create element
                parser_func = self.parser_registry[cls_name]
                element = parser_func(node, parent)
                
                if element and parent:
                    parent.add_child(element)
                
                return element
            else:
                logger.debug(f"Unknown element tag: {tag}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to parse element {node.tag}: {e}")
            return None
    
    def parse_container(self, node, parent) -> List[Any]:
        """
        Recursively parse container elements (TableCell, TextBox).
        
        Args:
            node: Container XML element
            parent: Parent element
            
        Returns:
            List of parsed child elements
        """
        try:
            elements = []
            for child in node:
                # Sprawdź czy child to sdt (Structured Document Tag)
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag == "sdt":
                    # Parsuj zawartość sdt (sdtContent)
                    sdt_content = child.find(".//w:sdtContent", self.ns)
                    if sdt_content is not None:
                        # Parsuj wszystkie elementy wewnątrz sdtContent
                        for sdt_child in sdt_content:
                            element = self.parse_element(sdt_child, parent)
                            if element:
                                elements.append(element)
                    continue
                
                element = self.parse_element(child, parent)
                if element:
                    elements.append(element)
            return elements
            
        except Exception as e:
            logger.error(f"Failed to parse container: {e}")
            return []
    
    def parse_run(self, r_node, parent) -> Optional[Any]:
        """
        Parse run-level elements with style and field support.
        
        Args:
            r_node: Run XML element
            parent: Parent element
            
        Returns:
            Parsed run element
        """
        try:
            text_parts = []
            # Get space attribute from run element first
            space_attr = r_node.get("{http://www.w3.org/XML/1998/namespace}space", "default")
            style = None
            
            # Parse style (rPr)
            rpr = r_node.find("w:rPr", self.ns)
            if rpr is not None:
                style = self._parse_run_style(rpr)
            
            # Parse text and space handling
            has_break = False
            has_tab = False
            has_drawing = False
            break_type = None
            footnote_refs = []
            endnote_refs = []
            
            for child in r_node:
                tag = child.tag.split("}")[-1]
                if tag == "t":
                    # Handle xml:space attribute from text element if not set on run
                    if space_attr == "default":
                        space_attr = child.get("{http://www.w3.org/XML/1998/namespace}space", "default")
                    text_parts.append(child.text or "")
                elif tag == "br":
                    # Line break
                    has_break = True
                    br_type = child.get(f"{{{self.ns['w']}}}type") if "w" in self.ns else None
                    break_type = br_type or "textWrapping"
                    if break_type.lower() in ("textwrapping", "line"):
                        text_parts.append("\n")  # Add newline for soft breaks
                elif tag == "tab":
                    # Tab character
                    has_tab = True
                    text_parts.append("\t")  # Add tab character
                elif tag == "drawing":
                    # Drawing/image
                    has_drawing = True
                elif tag == "pict":
                    # VML pict element (watermarks)
                    if parent:
                        if not hasattr(parent, 'vml_shapes'):
                            parent.vml_shapes = []
                        vml_shape = self._parse_vml_pict(child, parent)
                        if vml_shape:
                            parent.vml_shapes.append(vml_shape)
                elif tag == "cr":
                    has_break = True
                    break_type = "line"
                    text_parts.append("\n")
                elif tag == "fldSimple":
                    # Handle fields
                    field = self._parse_field(child)
                    if field and parent:
                        parent.add_child(field)
                elif tag == "footnoteReference":
                    # Handle footnote references
                    ns_w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                    footnote_id = child.get(f"{{{ns_w}}}id", "") or child.get("id", "")
                    if footnote_id:
                        footnote_refs.append(footnote_id)
                elif tag == "endnoteReference":
                    # Handle endnote references
                    ns_w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                    endnote_id = child.get(f"{{{ns_w}}}id", "") or child.get("id", "")
                    if endnote_id:
                        endnote_refs.append(endnote_id)
            
            # Create run with proper space handling
            run_dict = None
            if text_parts or has_break or has_tab or has_drawing or footnote_refs or endnote_refs:
                # For now, return a simple dict representation
                # In full implementation, this would create a Run object
                run_dict = {
                    "type": "Run",
                    "text": "".join(text_parts),
                    "style": style,
                    "space": space_attr,
                    "has_break": has_break,
                    "has_tab": has_tab,
                    "has_drawing": has_drawing,
                    "break_type": break_type,
                }
                # Add footnote/endnote references to run dict
                if footnote_refs:
                    run_dict["footnote_refs"] = footnote_refs
                if endnote_refs:
                    run_dict["endnote_refs"] = endnote_refs
                return run_dict
            
            # Even if no text, return run if it has footnote/endnote references
            if footnote_refs or endnote_refs:
                run_dict = {
                    "type": "Run",
                    "text": "",
                    "style": style,
                    "space": space_attr,
                    "has_break": False,
                    "has_tab": False,
                    "has_drawing": False,
                    "break_type": None,
                }
                if footnote_refs:
                    run_dict["footnote_refs"] = footnote_refs
                if endnote_refs:
                    run_dict["endnote_refs"] = endnote_refs
                return run_dict
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to parse run: {e}")
            return None
    
    def parse_sections(self) -> List[Dict[str, Any]]:
        """
        Parse document sections.
        
        Returns:
            List of parsed sections
        """
        try:
            sections = []
            
            # Get document XML
            document_xml = self.package_reader.get_xml_content("word/document.xml")
            if not document_xml:
                return sections
            
            root = ET.fromstring(document_xml)
            body = root.find("w:body", self.ns)
            if body is None:
                return sections
            
            # Find all section properties in the document
            # sectPr can be:
            # 1. At the end of body (last section)
            # 2. In pPr of paragraphs (marks start of new section)
            
            # First, check sectPr at end of body
            sect_pr = body.find("w:sectPr", self.ns)
            if sect_pr is not None:
                section = self._parse_section_properties(sect_pr)
                if section:
                    sections.append(section)
            
            # Then, find all sectPr in paragraph properties
            # These mark the start of new sections
            for para in body.iterfind("w:p", self.ns):
                p_pr = para.find("w:pPr", self.ns)
                if p_pr is not None:
                    sect_pr = p_pr.find("w:sectPr", self.ns)
                    if sect_pr is not None:
                        section = self._parse_section_properties(sect_pr)
                        if section:
                            sections.append(section)
            
            logger.info(f"Parsed {len(sections)} sections")
            return sections
            
        except Exception as e:
            logger.error(f"Failed to parse sections: {e}")
            return []
    
    def _parse_section_properties(self, sect_pr_element) -> Optional[Dict[str, Any]]:
        """
        Parse section properties from sectPr element.
        
        Args:
            sect_pr_element: XML element with section properties
            
        Returns:
            Dictionary with section properties or None
        """
        try:
            if sect_pr_element is None:
                return None
            
            section_props = {}
            
            # Parse page margins
            pg_mar = sect_pr_element.find("w:pgMar", self.ns)
            if pg_mar is not None:
                margins = {}
                for attr in ['top', 'right', 'bottom', 'left', 'header', 'footer', 'gutter']:
                    val = pg_mar.get(f"{{{self.ns['w']}}}{attr}")
                    if val:
                        try:
                            margins[attr] = int(val)
                        except (ValueError, TypeError):
                            # Jeśli nie można przekonwertować, spróbuj jako string
                            margins[attr] = val
                if margins:
                    section_props['margins'] = margins
            
            # Parse page size
            pg_sz = sect_pr_element.find("w:pgSz", self.ns)
            if pg_sz is not None:
                page_size = {}
                for attr in ['w', 'h', 'orient', 'code']:
                    val = pg_sz.get(f"{{{self.ns['w']}}}{attr}")
                    if val:
                        if attr == 'orient':
                            page_size[attr] = val
                        elif attr == 'code':
                            page_size[attr] = val  # Keep as string
                        else:
                            page_size[attr] = int(val)
                if page_size:
                    section_props['page_size'] = page_size
            
            # Parse columns
            cols = sect_pr_element.find("w:cols", self.ns)
            if cols is not None:
                columns = {}
                # Parse num attribute
                val = cols.get(f"{{{self.ns['w']}}}num")
                if val:
                    columns['num'] = int(val)
                # Parse space attribute - zawsze sprawdź, nawet jeśli None w dict
                val = cols.get(f"{{{self.ns['w']}}}space")
                if val:
                    columns['space'] = int(val)
                # Jeśli element cols istnieje, zawsze dodaj columns (nawet jeśli puste)
                # To pozwala na eksport pustego cols jeśli był w oryginalnym XML
                section_props['columns'] = columns
            
            # Parse section break type (w:type)
            sect_type = sect_pr_element.find("w:type", self.ns)
            if sect_type is not None:
                type_val = sect_type.get(f"{{{self.ns['w']}}}val") or sect_type.get("val")
                if type_val:
                    section_props['type'] = type_val
            
            # Parse header references (first, even, odd, default)
            header_refs = sect_pr_element.findall("w:headerReference", self.ns)
            if header_refs:
                headers = []
                # Namespace for relationships
                rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
                for hdr_ref in header_refs:
                    hdr_type = hdr_ref.get(f"{{{self.ns['w']}}}type") or hdr_ref.get("type", "default")
                    # ID uses relationships namespace, not wordprocessingml namespace
                    hdr_id = hdr_ref.get(f"{{{rel_ns}}}id") or hdr_ref.get("r:id") or hdr_ref.get("id")
                    if hdr_id:
                        headers.append({
                            "type": hdr_type,
                            "id": hdr_id
                        })
                if headers:
                    section_props['headers'] = headers
            
            # Parse footer references (first, even, odd, default)
            footer_refs = sect_pr_element.findall("w:footerReference", self.ns)
            if footer_refs:
                footers = []
                # Namespace for relationships
                rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
                for ftr_ref in footer_refs:
                    ftr_type = ftr_ref.get(f"{{{self.ns['w']}}}type") or ftr_ref.get("type", "default")
                    # ID uses relationships namespace, not wordprocessingml namespace
                    ftr_id = ftr_ref.get(f"{{{rel_ns}}}id") or ftr_ref.get("r:id") or ftr_ref.get("id")
                    if ftr_id:
                        footers.append({
                            "type": ftr_type,
                            "id": ftr_id
                        })
                if footers:
                    section_props['footers'] = footers
            
            # Parse title page and different first/odd/even page settings
            title_page = sect_pr_element.find("w:titlePg", self.ns)
            if title_page is not None:
                section_props['title_page'] = True
                section_props['different_first_page'] = True
            
            # Check for differentOddEven (different headers/footers for odd/even pages)
            different_odd_even = sect_pr_element.find("w:evenAndOddHeaders", self.ns)
            if different_odd_even is not None:
                section_props['different_odd_even'] = True
            
            # Parse docGrid
            doc_grid = sect_pr_element.find("w:docGrid", self.ns)
            if doc_grid is not None:
                grid_props = {}
                line_pitch = doc_grid.get(f"{{{self.ns['w']}}}linePitch")
                if line_pitch:
                    grid_props['linePitch'] = int(line_pitch)
                char_space = doc_grid.get(f"{{{self.ns['w']}}}charSpace")
                if char_space:
                    grid_props['charSpace'] = int(char_space)
                if grid_props:
                    section_props['doc_grid'] = grid_props
            
            return section_props if section_props else None
            
        except Exception as e:
            logger.error(f"Failed to parse section properties: {e}")
            return None
    
    # Helper methods for parsing specific elements
    def _parse_paragraph(self, p_node, parent) -> 'Paragraph':
        """Parse paragraph element with raw XML preservation."""
        try:
            from ..models.paragraph import Paragraph
            
            # Create Paragraph object
            paragraph = Paragraph()
            
            # Preserve raw XML for lossless export
            raw_xml = ET.tostring(p_node, encoding='unicode', method='xml')
            paragraph.raw_xml = raw_xml
            
            # Parse complex field codes (fldChar) first - they span multiple runs
            # This needs to be done before parsing individual runs
            self._parse_complex_fields_in_paragraph(p_node, paragraph)
            
            # Get list of all run elements (for field code matching)
            all_runs = list(p_node.findall("w:r", self.ns))
            
            bookmarks: List[Dict[str, Any]] = []
            
            # Parse runs, drawings, hyperlinks, structured document tags (sdt), bookmarks
            run_index = 0  # Index in all_runs list
            for child in p_node:
                if child.tag.endswith("}r"):
                    # Find index of this run in all_runs list
                    try:
                        run_xml_index = all_runs.index(child)
                    except ValueError:
                        # Run not found in all_runs (shouldn't happen)
                        run_xml_index = run_index
                    
                    # Skip runs that are part of field codes (already processed)
                    if child.get("_field_code_processed") == "true":
                        # Check if this run should have a field code added
                        if hasattr(paragraph, "_field_codes"):
                            field_added = False
                            for field_info in paragraph._field_codes:
                                if run_xml_index in field_info["run_indices"]:
                                    # Check if this is the first run of the field
                                    if run_xml_index == field_info["run_indices"][0]:
                                        # This is the first run of a field - add field to it
                                        run_result = self._parse_run(child, paragraph)
                                        if run_result:
                                            if isinstance(run_result, list):
                                                for run in run_result:
                                                    if run:
                                                        # Add field code to first run
                                                        if not hasattr(run, "children"):
                                                            run.children = []
                                                        field_dict = field_info["field"]
                                                        run.children.append(field_dict)
                                                        paragraph.add_run(run)
                                            else:
                                                # Add field code to run
                                                if not hasattr(run_result, "children"):
                                                    run_result.children = []
                                                field_dict = field_info["field"]
                                                run_result.children.append(field_dict)
                                                paragraph.add_run(run_result)
                                        field_added = True
                                        break
                            if not field_added:
                                # Skip this run (it's part of field code but not the first)
                                pass
                        run_index += 1
                        continue
                    
                    # Skip runs inside textboxes to avoid duplication
                    if self._is_run_inside_textbox(child):
                        run_index += 1
                        continue
                    
                    run_result = self._parse_run(child, paragraph)
                    if run_result:
                        # Handle both single run and list of runs (for footnote references)
                        if isinstance(run_result, list):
                            for run in run_result:
                                if run:
                                    paragraph.add_run(run)
                        else:
                            paragraph.add_run(run_result)
                    run_index += 1
                elif child.tag.endswith("}bookmarkStart"):
                    bookmark_attrs = self._sanitize_attrib(child.attrib)
                    bookmark_name = bookmark_attrs.get('name') or bookmark_attrs.get('w:name')
                    bookmark_id = bookmark_attrs.get('id') or bookmark_attrs.get('w:id')
                    bookmark = {
                        "type": "start",
                        "name": bookmark_name,
                        "id": bookmark_id,
                        "raw": bookmark_attrs
                    }
                    bookmarks.append(bookmark)
                elif child.tag.endswith("}bookmarkEnd"):
                    bookmark_attrs = self._sanitize_attrib(child.attrib)
                    bookmark_id = bookmark_attrs.get('id') or bookmark_attrs.get('w:id')
                    bookmark = {
                        "type": "end",
                        "id": bookmark_id,
                        "raw": bookmark_attrs
                    }
                    bookmarks.append(bookmark)
                elif child.tag.endswith("}hyperlink"):
                    # Parse hyperlink - extract runs from hyperlink element
                    hyperlink_runs = self._parse_hyperlink_content(child, paragraph)
                    for run in hyperlink_runs:
                        if run:
                            paragraph.add_run(run)
                elif child.tag.endswith("}sdt"):
                    # Parse structured document tag - extract runs from sdtContent
                    sdt_runs = self._parse_sdt(child)
                    for run in sdt_runs:
                        if run:
                            paragraph.add_run(run)
                elif child.tag.endswith("}drawing"):
                    # Parse drawing element as image with raw XML
                    image = self._parse_image(child, paragraph)
                    if image:
                        # Add as a special "content" to the paragraph
                        if not hasattr(paragraph, 'images'):
                            paragraph.images = []
                        paragraph.images.append(image)
                elif child.tag.endswith("}pict"):
                    # Parse VML pict element (legacy format, often used for watermarks)
                    vml_shape = self._parse_vml_pict(child, paragraph)
                    if vml_shape:
                        # Add as a special "content" to the paragraph (similar to images)
                        if not hasattr(paragraph, 'vml_shapes'):
                            paragraph.vml_shapes = []
                        paragraph.vml_shapes.append(vml_shape)
                elif child.tag.endswith("}AlternateContent"):
                    # Parse AlternateContent - handle Choice and Fallback
                    self._parse_alternate_content(child, paragraph)
            
            # Clean up temporary field codes attribute
            if hasattr(paragraph, "_field_codes"):
                delattr(paragraph, "_field_codes")
            
            if bookmarks:
                paragraph.bookmarks = bookmarks
            
            # Check if paragraph has sectPr in pPr (marks start of new section)
            p_pr = p_node.find("w:pPr", self.ns)
            if p_pr is not None:
                sect_pr = p_pr.find("w:sectPr", self.ns)
                if sect_pr is not None:
                    # Parse section properties and store in paragraph
                    section_props = self._parse_section_properties(sect_pr)
                    if section_props:
                        paragraph.section_properties = section_props
            
            # Set style
            style = self._parse_paragraph_style(p_node)
            if style:
                paragraph.set_style(style)
                # Map selected style properties onto paragraph fields used by dumps/rendering
                try:
                    # Alignment
                    justification = style.get("justification")
                    if justification:
                        paragraph.alignment = justification

                    # Spacing
                    spacing = style.get("spacing", {})
                    if isinstance(spacing, dict):
                        def _parse_lines_value(raw):
                            if raw in (None, "", {}):
                                return None
                            try:
                                numeric = float(raw)
                            except (TypeError, ValueError):
                                return None
                            if abs(numeric) > 24:
                                numeric = numeric / 240.0
                            return numeric

                        def _parse_bool_token(raw):
                            if isinstance(raw, bool):
                                return raw
                            if raw in (None, "", {}):
                                return False
                            token = str(raw).strip().lower()
                            return token in {"1", "true", "yes", "on"}

                        before_val = spacing.get("before")
                        after_val = spacing.get("after")
                        line_val = spacing.get("line")
                        if before_val:
                            try:
                                paragraph.spacing_before = int(before_val) / 20.0
                            except Exception:
                                paragraph.spacing_before = before_val
                        if after_val:
                            try:
                                paragraph.spacing_after = int(after_val) / 20.0
                            except Exception:
                                paragraph.spacing_after = after_val
                        if line_val:
                            line_rule = spacing.get("lineRule", "auto")
                            paragraph.line_spacing_rule = line_rule
                            try:
                                if line_rule == "auto":
                                    # Auto spacing: line is a multiplier (240 = 1.0, 276 = 1.15)
                                    paragraph.line_spacing = int(line_val) / 240.0
                                else:
                                    # Exact spacing: line is in twips, convert to points
                                    paragraph.line_spacing = int(line_val) / 20.0
                            except Exception:
                                paragraph.line_spacing = line_val

                        before_lines_val = spacing.get("beforeLines") or spacing.get("before_lines")
                        after_lines_val = spacing.get("afterLines") or spacing.get("after_lines")
                        before_lines = _parse_lines_value(before_lines_val)
                        after_lines = _parse_lines_value(after_lines_val)
                        if before_lines is not None:
                            paragraph.spacing_before_lines = before_lines
                        if after_lines is not None:
                            paragraph.spacing_after_lines = after_lines

                        before_auto_val = spacing.get("beforeAutospacing") or spacing.get("before_autospacing")
                        after_auto_val = spacing.get("afterAutospacing") or spacing.get("after_autospacing")
                        if before_auto_val is not None:
                            paragraph.spacing_before_auto = _parse_bool_token(before_auto_val)
                        if after_auto_val is not None:
                            paragraph.spacing_after_auto = _parse_bool_token(after_auto_val)

                    # Indentation
                    indent = style.get("indent", {})
                    if isinstance(indent, dict):
                        left = indent.get("left")
                        right = indent.get("right")
                        hanging = indent.get("hanging")
                        first_line = indent.get("first_line")
                        if left:
                            try:
                                paragraph.left_indent = int(left) / 20.0
                            except Exception:
                                paragraph.left_indent = left
                        if right:
                            try:
                                paragraph.right_indent = int(right) / 20.0
                            except Exception:
                                paragraph.right_indent = right
                        if hanging:
                            try:
                                paragraph.hanging_indent = int(hanging) / 20.0
                            except Exception:
                                paragraph.hanging_indent = hanging
                        if first_line:
                            try:
                                paragraph.first_line_indent = int(first_line) / 20.0
                            except Exception:
                                paragraph.first_line_indent = first_line
                        # If hanging_indent is set, calculate first_line_indent
                        if hasattr(paragraph, 'hanging_indent') and paragraph.hanging_indent and not paragraph.first_line_indent:
                            paragraph.first_line_indent = -paragraph.hanging_indent

                    # Numbering - najpierw z style, potem bezpośrednio z pPr
                    if "numbering" in style:
                        paragraph.numbering = style["numbering"]
                    else:
                        # Sprawdź bezpośrednio w pPr (paragraph properties)
                        p_pr = p_node.find("w:pPr", self.ns)
                        if p_pr is not None:
                            num_pr = p_pr.find("w:numPr", self.ns)
                            if num_pr is not None:
                                numbering_info = {}
                                ilvl = num_pr.find("w:ilvl", self.ns)
                                num_id = num_pr.find("w:numId", self.ns)
                                if ilvl is not None:
                                    numbering_info["level"] = ilvl.get(f"{{{self.ns['w']}}}val", "0")
                                if num_id is not None:
                                    numbering_info["id"] = num_id.get(f"{{{self.ns['w']}}}val", "0")
                                if numbering_info:
                                    paragraph.numbering = numbering_info

                    # Borders and shading
                    if "borders" in style:
                        paragraph.borders = style["borders"]
                    if "shading" in style:
                        paragraph.background = style["shading"]
                except Exception as e:
                    logger.error(f"Failed to map paragraph style to properties: {e}")
            
            return paragraph
        except Exception as e:
            logger.error(f"Failed to parse paragraph: {e}")
            return None
    
    def _parse_table(self, tbl_node, parent) -> 'Table':
        """Parse table element."""
        try:
            from ..models.table import Table
            
            # Create Table object
            table = Table()
            
            # Parse grid (column widths)
            tbl_grid = tbl_node.find("w:tblGrid", self.ns)
            if tbl_grid is not None:
                grid = []
                for grid_col in tbl_grid.findall("w:gridCol", self.ns):
                    # Get width attribute - try both with and without namespace
                    grid_col_width = grid_col.get("w:w", "0")
                    if grid_col_width == "0":
                        # Try getting from properties with namespace
                        for key, value in grid_col.attrib.items():
                            if key.endswith('}w'):
                                grid_col_width = value
                                break
                    grid.append({
                        'width': grid_col_width,
                        'properties': dict(grid_col.attrib)
                    })
                table.set_grid(grid)
            
            # Parse rows
            for child in tbl_node:
                if child.tag.endswith("}tr"):
                    row = self._parse_table_row(child, table)
                    if row:
                        table.add_row(row)
            
            # Set table properties (width, alignment) from tblPr
            style = self._parse_table_style(tbl_node)
            if style:
                try:
                    from ..models.table import TableProperties
                    props = TableProperties()
                    # width
                    width = style.get('width') or {}
                    wval = width.get('w') or width.get('val')
                    if wval:
                        try:
                            props.width = int(wval)
                        except (TypeError, ValueError):
                            props.width = wval
                    width_type = width.get('type') or width.get('w:type')
                    if width_type:
                        props.width_type = width_type
                    # alignment
                    if 'alignment' in style:
                        props.alignment = style['alignment']
                    # indentation
                    indentation = style.get('indentation') or {}
                    indent_value = indentation.get('w') or indentation.get('val')
                    indent_type = indentation.get('type') or indentation.get('w:type')
                    if indent_value is not None or indent_type:
                        try:
                            indent_numeric = int(indent_value)
                        except (TypeError, ValueError):
                            indent_numeric = indent_value
                        props.indent = {
                            'value': indent_numeric,
                            'type': indent_type
                        }
                    # borders
                    borders = style.get('borders')
                    if borders:
                        props.borders = borders
                    # shading
                    if style.get('shading'):
                        props.shading = style.get('shading')
                    # cell spacing (convert from twips to points if possible)
                    cell_spacing = style.get('cell_spacing') or {}
                    spacing_val = cell_spacing.get('w') or cell_spacing.get('val')
                    if spacing_val is not None:
                        try:
                            props.cell_spacing = int(spacing_val) / 20.0
                        except (TypeError, ValueError):
                            props.cell_spacing = spacing_val
                    # cell margins
                    if style.get('cell_margins'):
                        props.cell_margins = style.get('cell_margins')
                    # style identifiers / name
                    style_id = style.get('style_id')
                    if not style_id and isinstance(style.get('table_style'), dict):
                        style_id = style['table_style'].get('val')
                    if style_id:
                        props.style_id = style_id
                        if not props.style:
                            props.style = style_id
                    # grid already set above
                    props.grid = getattr(table, 'grid', [])
                    table.set_properties(props)
                    if props.borders:
                        table.borders = props.borders
                    if props.shading:
                        table.shading = props.shading
                    if props.cell_margins:
                        table.cell_margins = props.cell_margins
                    if props.cell_spacing is not None:
                        table.properties.cell_spacing = props.cell_spacing
                    if props.style_id:
                        table.style_id = props.style_id
                except Exception:
                    # Fallback: keep style dict for reference
                    table.style = style
            
            return table
        except Exception as e:
            logger.error(f"Failed to parse table: {e}")
            return None
    
    def _parse_table_row(self, tr_node, parent) -> 'TableRow':
        """Parse table row element."""
        try:
            from ..models.table import TableRow
            
            # Create TableRow object
            row = TableRow()
            
            # Parse row properties (trPr)
            tr_pr = tr_node.find("w:trPr", self.ns)
            if tr_pr is not None:
                row_props = {}
                for child in tr_pr:
                    tag = child.tag.split("}")[-1]
                    if tag == "trHeight":
                        row_props["height"] = {}
                        for key, value in child.attrib.items():
                            attr_name = key.split('}')[-1]
                            row_props["height"][attr_name] = value
                    elif tag == "cantSplit":
                        row_props["cant_split"] = True
                    elif tag == "hidden":
                        row_props["hidden"] = True
                    elif tag == "tblHeader":
                        row_props["tblHeader"] = True
                    elif tag == "shd":
                        row_props["shading"] = self._sanitize_attrib(child.attrib)
                    elif tag in {"tblBorders", "trBorders"}:
                        borders = {}
                        for border_child in child:
                            border_tag = border_child.tag.split("}")[-1]
                            border_spec = self._parse_border_spec(border_child)
                            if border_spec:
                                borders[border_tag] = border_spec
                        if borders:
                            row_props["borders"] = borders
                
                if row_props:
                    # Apply height if present
                    h = row_props.get('height', {})
                    hval = h.get('val') or h.get('w')
                    if hval:
                        try:
                            row.set_height(int(hval))
                        except (TypeError, ValueError):
                            row.set_height(None)
                    if row_props.get('cant_split'):
                        row.set_cant_split(True)
                        row.cant_split = True
                    if row_props.get('tblHeader'):
                        row.set_header_row(True)
                        row.header = True
                    if row_props.get('shading'):
                        row.set_shading(row_props['shading'])
                    # Store full props as style as well
                    row.style = row_props
            
            # Parse cells
            current_col_index = 0
            # parent is Table; try to get its grid widths for fallback sizing
            parent_grid = getattr(parent, 'grid', []) if parent is not None else []
            grid_widths = []
            for g in parent_grid:
                try:
                    grid_widths.append(int(g.get('width') or 0))
                except (TypeError, ValueError):
                    grid_widths.append(0)

            for child in tr_node:
                if child.tag.endswith("}tc"):
                    cell = self._parse_table_cell(child, row)
                    if cell:
                        # Fallback width from tblGrid if tcW missing
                        if getattr(cell, 'width', None) is None and grid_widths:
                            span = getattr(cell, 'grid_span', 1) or 1
                            w = sum(grid_widths[current_col_index:current_col_index+span])
                            if w:
                                try:
                                    cell.set_width(int(w))
                                except (TypeError, ValueError):
                                    pass
                            current_col_index += span
                        row.add_cell(cell)
            
            return row
        except Exception as e:
            logger.error(f"Failed to parse table row: {e}")
            return None
    
    def _parse_table_cell(self, tc_node, parent) -> 'TableCell':
        """Parse table cell element."""
        try:
            from ..models.table import TableCell
            
            # Create TableCell object
            cell = TableCell()
            
            # Parse cell properties (tcPr)
            tc_pr = tc_node.find("w:tcPr", self.ns)
            if tc_pr is not None:
                cell_props = {}
                for child in tc_pr:
                    tag = child.tag.split("}")[-1]
                    if tag == "tcBorders":
                        # Parse cell borders
                        borders_raw: Dict[str, Any] = {}
                        borders_normalized: Dict[str, Any] = {}
                        for border_child in child:
                            border_tag = border_child.tag.split("}")[-1]
                            attrs = self._sanitize_attrib(border_child.attrib)
                            if attrs:
                                borders_raw[border_tag] = attrs
                            border_spec = self._parse_border_spec(border_child)
                            if border_spec:
                                borders_normalized[border_tag] = border_spec
                        if borders_raw and "borders_raw" not in cell_props:
                            cell_props["borders_raw"] = borders_raw
                        if borders_normalized:
                            cell_props["borders"] = borders_normalized
                            cell.set_borders(borders_normalized)
                        elif borders_raw:
                            cell_props["borders"] = borders_raw
                    elif tag == "tcW":
                        # Parse cell width
                        width_attrs = self._sanitize_attrib(child.attrib)
                        cell_props["width"] = width_attrs
                        if width_attrs:
                            cell.set_width_spec(width_attrs)
                    elif tag == "gridSpan":
                        # Parse horizontal merge (gridSpan → colspan)
                        span_attrs = self._sanitize_attrib(child.attrib)
                        cell_props["gridSpan"] = span_attrs
                        sval = span_attrs.get('val')
                        if sval:
                            try:
                                cell.set_grid_span(int(sval))
                            except (TypeError, ValueError):
                                pass
                    elif tag == "vMerge":
                        # Parse vertical merge
                        merge_attrs = self._sanitize_attrib(child.attrib)
                        cell_props["vMerge"] = merge_attrs
                        merge_val = merge_attrs.get('val')
                        if merge_val is None:
                            merge_val = 'continue'
                        cell.set_vertical_merge(merge_val)
                    elif tag == "vAlign":
                        # Parse vertical alignment
                        align_attrs = self._sanitize_attrib(child.attrib)
                        cell_props["vAlign"] = align_attrs
                        v_align_val = align_attrs.get('val')
                        if v_align_val:
                            cell.set_vertical_align(v_align_val)
                    elif tag == "jc":
                        # Parse horizontal text alignment (justification)
                        jc_attrs = self._sanitize_attrib(child.attrib)
                        cell_props["jc"] = jc_attrs
                        if jc_attrs:
                            jc_val = jc_attrs.get('val') or jc_attrs.get('w:val')
                            if jc_val:
                                cell.set_horizontal_align(jc_val)
                    elif tag == "shd":
                        # Parse shading
                        shading_attrs = self._sanitize_attrib(child.attrib)
                        cell_props["shading"] = shading_attrs
                        cell.set_shading(shading_attrs)
                        cell.background = shading_attrs
                    elif tag == "tcMar":
                        margins: Dict[str, Any] = {}
                        for margin_child in child:
                            margin_tag = margin_child.tag.split('}')[-1]
                            margins[margin_tag] = self._sanitize_attrib(margin_child.attrib)
                        cell_props['margins'] = margins
                        cell.set_margins(margins)
                    elif tag == "textDirection":
                        direction_attrs = self._sanitize_attrib(child.attrib)
                        cell_props['textDirection'] = direction_attrs
                        direction_val = direction_attrs.get('val')
                        if direction_val:
                            cell.set_text_direction(direction_val)
 
                # Store properties in cell style
                if cell_props:
                    cell.style = cell_props
            
            # Parse content
            content = self.parse_container(tc_node, cell)
            if content:
                for item in content:
                    cell.add_content(item)
            
            return cell
        except Exception as e:
            logger.error(f"Failed to parse table cell: {e}")
            return None
    
    def _parse_image(self, drawing_node, parent) -> Dict[str, Any]:
        """Parse image element with original XML blob."""
        try:
            import xml.etree.ElementTree as ET
            
            # Preserve the original XML as a string to maintain exact structure
            # This is critical for maintaining wp:anchor positioning and attributes
            raw_xml = ET.tostring(drawing_node, encoding='unicode', method='xml')

            # Determine anchor type and obtain anchor/inline element
            anchor_type = 'inline'
            anchor_element = None
            for child in drawing_node:
                local_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if local_tag == 'anchor':
                    anchor_type = 'anchor'
                    anchor_element = child
                    break
                if local_tag == 'inline':
                    anchor_type = 'inline'
                    anchor_element = child
                    break

            # Extract extent (width/height) in EMUs
            width = 0
            height = 0
            if anchor_element is not None:
                extent = anchor_element.find('wp:extent', self.ns)
                if extent is not None:
                    width_attr = extent.get('cx')
                    height_attr = extent.get('cy')
                    try:
                        width = int(width_attr) if width_attr is not None else 0
                    except (TypeError, ValueError):
                        width = 0
                    try:
                        height = int(height_attr) if height_attr is not None else 0
                    except (TypeError, ValueError):
                        height = 0

            # Extract relationship id from blip
            rel_id = None
            blip = drawing_node.find('.//a:blip', self.ns)
            if blip is not None:
                rel_id = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                if not rel_id:
                    rel_id = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}link')

            # Extract positioning offsets if available (for anchors)
            position = {}
            if anchor_element is not None and anchor_type == 'anchor':
                pos_h = anchor_element.find('wp:positionH', self.ns)
                if pos_h is not None:
                    rel = pos_h.get('relativeFrom') or pos_h.get('{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}relativeFrom')
                    if rel:
                        position['x_rel'] = rel
                    pos_offset = pos_h.find('wp:posOffset', self.ns)
                    if pos_offset is not None and pos_offset.text:
                        try:
                            position['x'] = int(pos_offset.text)
                        except ValueError:
                            position['x'] = 0
                pos_v = anchor_element.find('wp:positionV', self.ns)
                if pos_v is not None:
                    rel = pos_v.get('relativeFrom') or pos_v.get('{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}relativeFrom')
                    if rel:
                        position['y_rel'] = rel
                    pos_offset = pos_v.find('wp:posOffset', self.ns)
                    if pos_offset is not None and pos_offset.text:
                        try:
                            position['y'] = int(pos_offset.text)
                        except ValueError:
                            position['y'] = 0

            # Preserve anchor properties (useful for layout comparisons)
            properties = dict(anchor_element.attrib) if anchor_element is not None else {}
            
            # Pobierz ścieżkę obrazu z relationship jeśli jest rel_id
            image_path = None
            if rel_id:
                try:
                    # Pobierz relationship target - użyj tego samego podejścia co header_footer_parser
                    relationship_source = self._current_relationship_file or "word/_rels/document.xml.rels"
                    logger.info(f"Parsing image with relationship_id={rel_id}, relationship_source={relationship_source}, part_path={self._current_part_path}")
                    # Jeśli relationship_source nie kończy się na .rels, dodaj _rels/ i .rels
                    if not relationship_source.endswith('.rels'):
                        # Dla document.xml, relationship_source to "word/_rels/document.xml.rels"
                        # Dla header1.xml, relationship_source to "word/_rels/header1.xml.rels"
                        if relationship_source.startswith("word/"):
                            part_name = relationship_source.replace("word/", "")
                            relationship_source = f"word/_rels/{part_name}.rels"
                        else:
                            relationship_source = f"word/_rels/{relationship_source}.rels"
                    
                    relationships = self.package_reader.get_relationships(relationship_source)
                    if relationships and rel_id in relationships:
                        rel_data = relationships[rel_id]
                        rel_target = rel_data.get("target", "")
                        if rel_target:
                            # Pobierz pełną ścieżkę do obrazu
                            # rel_target to ścieżka względna w DOCX, np. "media/image2.jpeg"
                            # Musimy zbudować pełną ścieżkę w wyekstraktowanym katalogu
                            from pathlib import Path
                            extract_to = self.package_reader.extract_to
                            # rel_target może być już z "word/" lub bez
                            if rel_target.startswith("word/"):
                                image_path = Path(extract_to) / rel_target
                            else:
                                image_path = Path(extract_to) / "word" / rel_target
                            if image_path.exists():
                                image_path = str(image_path)
                                logger.debug(f"Pobrano ścieżkę obrazu z relationship: {image_path}")
                            else:
                                logger.debug(f"Obraz nie istnieje: {image_path}")
                                image_path = None
                except Exception as e:
                    logger.debug(f"Nie udało się pobrać ścieżki obrazu z rel_id {rel_id}: {e}")
            
            return {
                "type": "Image",
                "raw_xml": raw_xml,
                "anchor_type": anchor_type,
                "relationship_id": rel_id,
                "width": width,
                "height": height,
                "position": position,
                "properties": properties,
                "parent": parent,
                "relationship_source": self._current_relationship_file,
                "part_path": self._current_part_path,
                "path": image_path,  # Dodaj ścieżkę obrazu
                "image_path": image_path  # Dla kompatybilności
            }
        except Exception as e:
            logger.error(f"Failed to parse image: {e}")
            return None
    
    def _parse_field(self, field_node, parent) -> Dict[str, Any]:
        """Parse field element (fldSimple)."""
        try:
            # fldSimple ma atrybut w:instr z instrukcją pola
            instr = field_node.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}instr", "")
            if not instr:
                # Spróbuj bez namespace
                instr = field_node.get("instr", "")
            
            # Sprawdź czy jest tekst wynikowy (w:t w fldSimple)
            result_text = ""
            t_elem = field_node.find("w:t", self.ns)
            if t_elem is not None and t_elem.text:
                result_text = t_elem.text
            
            field_dict = {
                "type": "Field",
                "instr": instr,
                "result": result_text
            }
            
            # Dodaj pole do run.children jeśli parent to run
            if parent and hasattr(parent, "add_child"):
                parent.add_child(field_dict)
            
            return field_dict
        except Exception as e:
            logger.error(f"Failed to parse field: {e}")
            return None
    
    def _parse_complex_fields_in_paragraph(self, p_node, paragraph) -> None:
        """
        Parse complex field codes (fldChar) that span multiple runs.
        This method processes all runs in a paragraph and extracts field codes.
        
        Args:
            p_node: Paragraph XML element
            paragraph: Paragraph object to add field codes to
        """
        try:
            ns_w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            runs = list(p_node.findall("w:r", self.ns))
            
            if not runs:
                return
            
            # Track field state across runs
            current_field = None
            field_runs = []  # Runs that are part of the current field
            
            for i, run in enumerate(runs):
                # Check for fldChar elements
                fld_chars = run.findall("w:fldChar", self.ns)
                instr_texts = run.findall("w:instrText", self.ns)
                
                # Check for field begin
                for fld_char in fld_chars:
                    fld_char_type = fld_char.get(f"{{{ns_w}}}fldCharType", "")
                    if fld_char_type == "begin":
                        # Start new field
                        current_field = {
                            "type": "Field",
                            "instr": "",
                            "result": "",
                            "runs": []
                        }
                        field_runs = [i]
                    elif fld_char_type == "separate":
                        # Field instruction ends, result begins
                        if current_field is not None:
                            field_runs.append(i)
                    elif fld_char_type == "end":
                        # Field ends - create Field object and add to paragraph
                        if current_field is not None:
                            field_runs.append(i)
                            # Create Field object
                            # NIE używaj result z XML - to jest tylko wynik z dokumentu źródłowego
                            # Zamiast tego użyjemy dynamicznego rozwiązania podczas renderowania
                            field_dict = {
                                "type": "Field",
                                "instr": current_field["instr"].strip(),
                                "result": ""  # Nie używaj result z XML - będzie rozwiązane dynamicznie
                            }
                            # Mark runs as processed (we'll skip them during normal parsing)
                            # To obejmuje wszystkie runy: begin, instrText, separate, result text, end
                            for run_idx in field_runs:
                                if run_idx < len(runs):
                                    # Mark run as containing field code
                                    runs[run_idx].set("_field_code_processed", "true")
                            # Add field to paragraph (as a child of the first run)
                            # We'll need to add it to the first run when we parse it
                            if not hasattr(paragraph, "_field_codes"):
                                paragraph._field_codes = []
                            paragraph._field_codes.append({
                                "field": field_dict,
                                "run_indices": field_runs
                            })
                            current_field = None
                            field_runs = []
                
                # Collect instruction text
                if current_field is not None:
                    for instr_text in instr_texts:
                        if instr_text.text:
                            current_field["instr"] += instr_text.text
                    if instr_texts:
                        field_runs.append(i)
                
                # Collect result text (between separate and end)
                # UWAGA: Nie zbieramy result text - to jest tylko wynik z dokumentu źródłowego
                # Zamiast tego oznaczymy runy z tekstem między separate a end jako część field code
                if current_field is not None:
                    # Check if we're past the separate marker
                    has_separate = any(
                        fld_char.get(f"{{{ns_w}}}fldCharType", "") == "separate"
                        for fld_char in fld_chars
                    )
                    if has_separate:
                        # Jesteśmy w części result - oznaczymy ten run jako część field code
                        # (tekst między separate a end nie powinien być parsowany jako zwykły tekst)
                        field_runs.append(i)
                    elif len(field_runs) > 1:
                        # Sprawdź czy już przeszliśmy przez separate (czyli jesteśmy w części result)
                        # Sprawdź poprzednie runy czy mają separate
                        for prev_idx in range(i):
                            if prev_idx < len(runs):
                                prev_run = runs[prev_idx]
                                prev_fld_chars = prev_run.findall("w:fldChar", self.ns)
                                for prev_fld_char in prev_fld_chars:
                                    if prev_fld_char.get(f"{{{ns_w}}}fldCharType", "") == "separate":
                                        # Jesteśmy w części result - oznaczymy ten run jako część field code
                                        field_runs.append(i)
                                        break
        except Exception as e:
            logger.error(f"Failed to parse complex fields in paragraph: {e}")
    
    def _parse_hyperlink(self, hyperlink_node, parent) -> Dict[str, Any]:
        """Parse hyperlink element."""
        try:
            target = hyperlink_node.get("w:anchor", "")
            return {
                "type": "Hyperlink",
                "target": target
            }
        except Exception as e:
            logger.error(f"Failed to parse hyperlink: {e}")
            return None
    
    def _parse_hyperlink_content(self, hyperlink_node, paragraph) -> List['Run']:
        """Parse hyperlink element and return list of runs with hyperlink info."""
        try:
            from ..models.run import Run
            
            runs = []
            
            # Get hyperlink attributes - try both with and without namespace prefix
            relationship_id = hyperlink_node.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id", "")
            if not relationship_id:
                # Try without namespace
                relationship_id = hyperlink_node.get("id", "")
            
            anchor = hyperlink_node.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}anchor", "")
            if not anchor:
                anchor = hyperlink_node.get("anchor", "")
            
            tooltip = hyperlink_node.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tooltip", "")
            if not tooltip:
                tooltip = hyperlink_node.get("tooltip", "")

            relationship_target = None
            relationship_type = None
            target_mode = None
            resolved_url = None

            if relationship_id:
                relationship_sources: List[str] = []

                def _add_source(candidate: Optional[str]) -> None:
                    if candidate and candidate not in relationship_sources:
                        relationship_sources.append(candidate)

                _add_source(self._current_relationship_file)
                _add_source(self._current_part_path)
                if self._current_part_path and self._current_part_path.endswith(".xml"):
                    part_name = self._current_part_path.split("/")[-1]
                    _add_source(f"word/_rels/{part_name}.rels")
                _add_source("document")
                _add_source("word/_rels/document.xml.rels")

                for rel_source in relationship_sources:
                    relationships = self.package_reader.get_relationships(rel_source)
                    if relationships and relationship_id in relationships:
                        rel_data = relationships[relationship_id]
                        relationship_target = rel_data.get("target")
                        relationship_type = rel_data.get("type")
                        target_mode = rel_data.get("target_mode") or rel_data.get("TargetMode")
                        break

                if relationship_target:
                    normalized_target = str(relationship_target).strip()
                    mode_token = str(target_mode or "").strip().lower()
                    if mode_token == "external":
                        resolved_url = normalized_target
                    else:
                        lowered = normalized_target.lower()
                        if lowered.startswith(("http://", "https://", "mailto:", "ftp://", "ftps://", "news:", "tel:", "sms:", "file://")):
                            resolved_url = normalized_target

            if not resolved_url and anchor:
                # Internal anchor links are not converted to URL here,
                # but we still record the anchor for downstream processing.
                resolved_url = None
            
            # Parse all runs within hyperlink
            for child in hyperlink_node:
                if child.tag.endswith("}r"):
                    run = self._parse_run(child, paragraph)
                    if run:
                        # Store hyperlink information in run style
                        if not hasattr(run, 'style') or not run.style:
                            run.style = {}
                        
                        hyperlink_info = dict(run.style.get('hyperlink', {}))
                        if relationship_id:
                            hyperlink_info['relationship_id'] = relationship_id
                        if relationship_target:
                            hyperlink_info['relationship_target'] = relationship_target
                        if relationship_type:
                            hyperlink_info['relationship_type'] = relationship_type
                        if target_mode:
                            hyperlink_info['target_mode'] = target_mode
                        if anchor:
                            hyperlink_info['anchor'] = anchor
                        if tooltip:
                            hyperlink_info['tooltip'] = tooltip
                        if resolved_url and not hyperlink_info.get('url'):
                            hyperlink_info['url'] = resolved_url
                        hyperlink_info.setdefault('relationship_source', self._current_relationship_file)
                        run.style['hyperlink'] = hyperlink_info
                        
                        runs.append(run)
            
            return runs
        except Exception as e:
            logger.error(f"Failed to parse hyperlink content: {e}")
            return []
    
    def _parse_textbox(self, textbox_node, parent) -> Dict[str, Any]:
        """Parse textbox element."""
        try:
            content = self.parse_container(textbox_node, None)
            return {
                "type": "TextBox",
                "content": content
            }
        except Exception as e:
            logger.error(f"Failed to parse textbox: {e}")
            return None
    
    def _parse_textbox_content(self, textbox_node) -> List['Run']:
        """Parse textbox content and return list of Run objects."""
        try:
            from ..models.run import Run
            logger.debug(f"Parsing textbox content from {textbox_node.tag}")
            runs = []
            
            # Find txbxContent element
            txbx_content = textbox_node.find("w:txbxContent", self.ns)
            if txbx_content is None:
                logger.debug("No txbxContent found in textbox")
                return runs
            
            logger.debug(f"Found txbxContent, parsing paragraphs...")
            w_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            # Parse paragraphs in txbxContent and extract runs
            for p_elem in txbx_content.findall("w:p", self.ns):
                logger.debug(f"Parsing paragraph in textbox, runs before: {len(runs)}")

                paragraph_style_id = None
                paragraph_spacing = {}
                paragraph_run_props: Dict[str, Any] = {}

                p_pr = p_elem.find("w:pPr", self.ns)
                if p_pr is not None:
                    p_style = p_pr.find("w:pStyle", self.ns)
                    if p_style is not None:
                        paragraph_style_id = p_style.get(f"{{{w_ns}}}val") or p_style.get("val")

                    spacing_elem = p_pr.find("w:spacing", self.ns)
                    if spacing_elem is not None:
                        for attr_key, output_key in (
                            ("before", "before"),
                            ("after", "after"),
                            ("line", "line"),
                            ("lineRule", "line_rule"),
                            ("beforeLines", "before_lines"),
                            ("afterLines", "after_lines"),
                            ("beforeAutospacing", "before_autospacing"),
                            ("afterAutospacing", "after_autospacing"),
                        ):
                            raw_value = spacing_elem.get(f"{{{w_ns}}}{attr_key}") or spacing_elem.get(attr_key)
                            if raw_value not in (None, "", "0"):
                                paragraph_spacing[output_key] = raw_value

                if paragraph_style_id and getattr(self, "style_manager", None):
                    try:
                        resolved_style = self.style_manager.resolve_style(paragraph_style_id)
                    except Exception:
                        resolved_style = None
                    if resolved_style:
                        props = resolved_style.get("properties") or {}
                        run_props = props.get("run") or {}
                        font_size_raw = run_props.get("font_size") or run_props.get("sz")
                        if font_size_raw not in (None, "", "0"):
                            try:
                                paragraph_run_props["font_size"] = max(float(font_size_raw) / 2.0, 0.1)
                            except (TypeError, ValueError):
                                pass
                        font_size_cs = run_props.get("font_size_cs")
                        if "font_size" not in paragraph_run_props and font_size_cs not in (None, "", "0"):
                            try:
                                paragraph_run_props["font_size"] = max(float(font_size_cs) / 2.0, 0.1)
                            except (TypeError, ValueError):
                                pass
                        font_name = run_props.get("font_name")
                        if font_name:
                            paragraph_run_props["font_name"] = font_name
                        color = run_props.get("color")
                        if color:
                            paragraph_run_props["color"] = color

                # Parse runs in this paragraph
                for r_elem in p_elem.findall("w:r", self.ns):
                    run = self._parse_run(r_elem, None)
                    if run:
                        if paragraph_style_id and not getattr(run, "paragraph_style_id", None):
                            setattr(run, "paragraph_style_id", paragraph_style_id)
                            setattr(run, "paragraph_style", paragraph_style_id)
                        if paragraph_spacing and not getattr(run, "paragraph_spacing", None):
                            setattr(run, "paragraph_spacing", dict(paragraph_spacing))
                        if paragraph_run_props:
                            if "font_size" in paragraph_run_props and not getattr(run, "paragraph_font_size", None):
                                setattr(run, "paragraph_font_size", paragraph_run_props["font_size"])
                            if "font_name" in paragraph_run_props and not getattr(run, "paragraph_font_name", None):
                                setattr(run, "paragraph_font_name", paragraph_run_props["font_name"])
                            if "color" in paragraph_run_props and not getattr(run, "paragraph_font_color", None):
                                setattr(run, "paragraph_font_color", paragraph_run_props["color"])
                        runs.append(run)
                        logger.debug(f"Added run to textbox: text='{run.text[:20] if run.text else ''}'")
                logger.debug(f"Parsed paragraph in textbox, runs after: {len(runs)}")
            
            logger.debug(f"Textbox content parsing complete: {len(runs)} runs")
            return runs
        except Exception as e:
            logger.error(f"Failed to parse textbox content: {e}")
            return []
    
    def _extract_textbox_anchor_info(self, container, textbox_node=None):
        """Extract anchor positioning info for textbox content from given XML container."""
        if container is None:
            return None

        anchor_type = 'inline'
        anchor_element = None

        for candidate in container.findall('.//wp:anchor', self.ns):
            if textbox_node is None or candidate.find('.//wps:txbx', self.ns_wps) is not None:
                anchor_element = candidate
                anchor_type = 'anchor'
                break

        if anchor_element is None:
            for candidate in container.findall('.//wp:inline', self.ns):
                if textbox_node is None or candidate.find('.//wps:txbx', self.ns_wps) is not None:
                    anchor_element = candidate
                    anchor_type = 'inline'
                    break

        if anchor_element is None:
            return None

        width = 0
        height = 0
        extent = anchor_element.find('wp:extent', self.ns)
        if extent is not None:
            width_attr = extent.get('cx')
            height_attr = extent.get('cy')
            try:
                width = int(width_attr) if width_attr is not None else 0
            except (TypeError, ValueError):
                width = 0
            try:
                height = int(height_attr) if height_attr is not None else 0
            except (TypeError, ValueError):
                height = 0

        position = {}
        pos_h = anchor_element.find('wp:positionH', self.ns)
        if pos_h is not None:
            rel = pos_h.get('relativeFrom') or pos_h.get('{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}relativeFrom')
            if rel:
                position['x_rel'] = rel
            pos_offset = pos_h.find('wp:posOffset', self.ns)
            if pos_offset is not None and pos_offset.text:
                try:
                    position['x'] = int(pos_offset.text)
                except ValueError:
                    position['x'] = 0

        pos_v = anchor_element.find('wp:positionV', self.ns)
        if pos_v is not None:
            rel = pos_v.get('relativeFrom') or pos_v.get('{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}relativeFrom')
            if rel:
                position['y_rel'] = rel
            pos_offset = pos_v.find('wp:posOffset', self.ns)
            if pos_offset is not None and pos_offset.text:
                try:
                    position['y'] = int(pos_offset.text)
                except ValueError:
                    position['y'] = 0

        return {
            'anchor_type': anchor_type,
            'position': position,
            'width': width,
            'height': height,
        }

    def _apply_textbox_anchor_info(self, run, textbox_content, anchor_info):
        """Attach anchor info dict to run and its textbox content."""
        if not anchor_info:
            return

        setattr(run, 'textbox_anchor_info', dict(anchor_info))

        if isinstance(textbox_content, list):
            for tb_run in textbox_content:
                setattr(tb_run, 'textbox_anchor_info', dict(anchor_info))
        else:
            setattr(textbox_content, 'textbox_anchor_info', dict(anchor_info))

    def _is_run_inside_textbox(self, run_element) -> bool:
        """
        Check if run is inside a textbox to avoid duplication.
        
        Args:
            run_element: Run XML element
            
        Returns:
            True if run is inside textbox, False otherwise
        """
        # Check if run is inside txbxContent by checking parent tags
        parent = run_element
        while parent is not None:
            tag = parent.tag
            if any(x in tag for x in ('txbxContent', 'wps:txbx', 'v:textbox')):
                return True
            # Try to get parent - use getparent if available (lxml), otherwise None
            parent = getattr(parent, 'getparent', lambda: None)() or None
        return False
    
    def _parse_vml_pict(self, pict_node, paragraph) -> Optional[Dict[str, Any]]:
        """
        Parse VML pict element (legacy format, often used for watermarks).
        
        Args:
            pict_node: w:pict XML element
            paragraph: Parent paragraph
            
        Returns:
            Dictionary with VML shape data or None
        """
        try:
            # Find v:shape element
            vml_shape = pict_node.find(".//v:shape", self.ns_v)
            if vml_shape is None:
                return None
            
            vml_data = {
                "type": "vml_shape",
                "shape_type": "vml",
                "properties": {},
                "text_content": "",
                "position": {},
                "size": {},
                "is_watermark": False,
            }
            
            # Get VML properties
            shape_id = vml_shape.get("id", "")
            style = vml_shape.get("style", "")
            rotation = vml_shape.get("rotation", "")
            fillcolor = vml_shape.get("fillcolor", "")
            
            # Check if this is a watermark (PowerPlusWaterMarkObject or similar)
            if "PowerPlusWaterMarkObject" in shape_id or "WaterMark" in shape_id:
                vml_data["is_watermark"] = True
            
            # Parse style for positioning and size
            if style:
                vml_data["properties"]["style"] = style
                # Extract position and size from style (e.g., "position:absolute; margin-left:0; margin-top:0; width:468pt; height:117pt")
                style_parts = style.split(";")
                for part in style_parts:
                    part = part.strip()
                    if ":" in part:
                        key, value = part.split(":", 1)
                        key = key.strip().lower()
                        value = value.strip()
                        if key == "width":
                            # Convert pt to points (already in points)
                            try:
                                width_pt = float(value.replace("pt", "").strip())
                                vml_data["size"]["width"] = width_pt
                                vml_data["properties"]["shape_width"] = width_pt  # Zapisz również w properties dla łatwego dostępu
                            except (ValueError, TypeError):
                                pass
                        elif key == "height":
                            try:
                                height_pt = float(value.replace("pt", "").strip())
                                vml_data["size"]["height"] = height_pt
                                vml_data["properties"]["shape_height"] = height_pt  # Zapisz również w properties dla łatwego dostępu
                            except (ValueError, TypeError):
                                pass
                        elif key == "position" and value == "absolute":
                            vml_data["position"]["absolute"] = True
                            vml_data["is_watermark"] = True  # Absolute positioning often indicates watermark
                        elif key == "rotation":
                            # Rotacja może być w stylu (np. "rotation:315")
                            try:
                                rotation_from_style = float(value)
                                # Konwertuj do zakresu -180 do 180 (315° = -45°)
                                if rotation_from_style > 180:
                                    rotation_from_style = rotation_from_style - 360
                                vml_data["properties"]["rotation"] = rotation_from_style
                                # Jeśli nie ma rotacji z atrybutu, użyj tej ze stylu
                                if not rotation:
                                    rotation = str(rotation_from_style)
                            except (ValueError, TypeError):
                                pass
            
            # Parse VML text content (v:textpath)
            textpath = vml_shape.find(".//v:textpath", self.ns_v)
            if textpath is not None:
                text_string = textpath.get("string", "")
                if text_string:
                    vml_data["text_content"] = text_string
                elif textpath.text:
                    vml_data["text_content"] = textpath.text
            
            # Parse font properties from textpath
            if textpath is not None:
                textpath_style = textpath.get("style", "")
                if textpath_style:
                    vml_data["properties"]["textpath_style"] = textpath_style
                    # Extract font-family and font-size
                    style_parts = textpath_style.split(";")
                    for part in style_parts:
                        part = part.strip()
                        if ":" in part:
                            key, value = part.split(":", 1)
                            key = key.strip().lower()
                            value = value.strip()
                            if key == "font-family":
                                vml_data["properties"]["font_name"] = value.strip("'\"")
                            elif key == "font-size":
                                try:
                                    # Convert to points (e.g., "1in" = 72pt)
                                    if value.endswith("in"):
                                        vml_data["properties"]["font_size"] = float(value.replace("in", "").strip()) * 72.0
                                    elif value.endswith("pt"):
                                        vml_data["properties"]["font_size"] = float(value.replace("pt", "").strip())
                                    else:
                                        vml_data["properties"]["font_size"] = float(value)
                                except (ValueError, TypeError):
                                    pass
            
            # Store rotation and fillcolor
            if rotation:
                try:
                    vml_data["properties"]["rotation"] = float(rotation)
                except (ValueError, TypeError):
                    pass
            if fillcolor:
                vml_data["properties"]["fillcolor"] = fillcolor
            
            # Store raw XML
            try:
                vml_data["raw_xml"] = ET.tostring(pict_node, encoding='unicode', method='xml')
            except Exception:
                vml_data["raw_xml"] = None
            
            return vml_data
            
        except Exception as e:
            logger.error(f"Failed to parse VML pict: {e}")
            return None
    
    def _parse_alternate_content(self, alt_content_node, paragraph):
        """
        Parse AlternateContent element - handle Choice and Fallback.
        
        Args:
            alt_content_node: AlternateContent XML element
            paragraph: Paragraph object to add runs to
        """
        try:
            # First check for Choice
            choice = alt_content_node.find(".//mc:Choice", {"mc": "http://schemas.openxmlformats.org/markup-compatibility/2006"})
            if choice is not None:
                # Parse Choice content
                self._parse_choice_content(choice, paragraph)
            else:
                # No Choice, try Fallback
                fallback = alt_content_node.find(".//mc:Fallback", {"mc": "http://schemas.openxmlformats.org/markup-compatibility/2006"})
                if fallback is not None:
                    # Parse Fallback content
                    self._parse_fallback_content(fallback, paragraph)
        except Exception as e:
            logger.error(f"Failed to parse AlternateContent: {e}")
    
    def _parse_choice_content(self, choice_node, paragraph):
        """
        Parse Choice content - handle wps:txbx.
        
        Args:
            choice_node: Choice XML element
            paragraph: Paragraph object to add runs to
        """
        try:
            # Look for textbox in Choice
            textbox_node = choice_node.find(".//wps:txbx", self.ns_wps)
            if textbox_node is not None:
                textbox_content = self._parse_textbox_content(textbox_node)
                if textbox_content:
                    # Create a run with textbox content
                    from ..models.run import Run
                    run = Run()
                    run.textbox = textbox_content
                    paragraph.add_run(run)
        except Exception as e:
            logger.error(f"Failed to parse Choice content: {e}")
    
    def _parse_fallback_content(self, fallback_node, paragraph):
        """
        Parse Fallback content - handle v:textbox.
        
        Args:
            fallback_node: Fallback XML element
            paragraph: Paragraph object to add runs to
        """
        # According to recent requirements we ignore mc:Fallback so that only Choice content is materialised.
        logger.debug("Skipping mc:Fallback content for textbox to avoid duplicate runs")
    
    def _parse_run(self, r_node, parent) -> 'Run':
        """Parse run element with raw XML preservation."""
        try:
            from ..models.run import Run
            import xml.etree.ElementTree as ET
            
            logger.debug(f"Parsing run element: {r_node.tag}")
            
            # Check for breaks, tabs, drawings
            br_node = r_node.find("w:br", self.ns)
            cr_node = None
            if br_node is None:
                cr_node = r_node.find("w:cr", self.ns)
            break_type = None
            if br_node is not None:
                br_type_attr = br_node.get(f"{{{self.ns['w']}}}type") if "w" in self.ns else None
                break_type = br_type_attr or "textWrapping"
            elif cr_node is not None:
                break_type = "line"
            normalized_break = (break_type or "").lower()
            has_break = br_node is not None or cr_node is not None
            has_tab = r_node.find("w:tab", self.ns) is not None
            has_drawing = r_node.find("w:drawing", self.ns) is not None
            
            logger.debug(f"Run has_break={has_break}, has_tab={has_tab}, has_drawing={has_drawing}")
            
            # Get run properties first (needed for footnote reference styles)
            rpr = r_node.find("w:rPr", self.ns)
            style = self._parse_run_style(rpr) if rpr is not None else {}
            
            # Parse footnote and endnote references - create separate runs for each
            footnote_refs = []
            endnote_refs = []
            for child in r_node:
                tag = child.tag.split("}")[-1]
                if tag == "footnoteReference":
                    ns_w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                    footnote_id = child.get(f"{{{ns_w}}}id", "") or child.get("id", "")
                    if footnote_id:
                        footnote_refs.append(footnote_id)
                elif tag == "endnoteReference":
                    ns_w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                    endnote_id = child.get(f"{{{ns_w}}}id", "") or child.get("id", "")
                    if endnote_id:
                        endnote_refs.append(endnote_id)
            
            # If there are footnote/endnote references, create separate runs for each
            if footnote_refs or endnote_refs:
                runs = []
                
                # Create a run for each footnote reference
                for footnote_id in footnote_refs:
                    footnote_run = Run()
                    footnote_run.footnote_refs.append(footnote_id)
                    # Apply style from rPr to footnote run
                    if style:
                        footnote_run.set_style(style)
                        self._apply_style_to_run(footnote_run, style)
                    runs.append(footnote_run)
                
                # Create a run for each endnote reference
                for endnote_id in endnote_refs:
                    endnote_run = Run()
                    endnote_run.endnote_refs.append(endnote_id)
                    # Apply style from rPr to endnote run
                    if style:
                        endnote_run.set_style(style)
                        self._apply_style_to_run(endnote_run, style)
                    runs.append(endnote_run)
                
                # If there's also text content, create a regular run for it
                text_content = ""
                for t_node in r_node.findall("w:t", self.ns):
                    if t_node.text:
                        text_content += t_node.text
                
                if text_content or has_break or has_tab or has_drawing:
                    regular_run = Run(has_break=has_break, has_tab=has_tab, has_drawing=has_drawing, break_type=break_type)
                    if style:
                        regular_run.set_style(style)
                        self._apply_style_to_run(regular_run, style)
                    if text_content:
                        regular_run.add_text(text_content)
                    elif has_break and normalized_break in ("textwrapping", "line", ""):
                        regular_run.add_text("\n")
                    elif has_tab:
                        regular_run.add_text("\t")
                    runs.append(regular_run)
                
                # Return list of runs (footnote/endnote runs + regular run if any)
                return runs
            
            # Create Run object with special elements (no footnote/endnote references)
            run = Run(has_break=has_break, has_tab=has_tab, has_drawing=has_drawing, break_type=break_type)
            
            # Parse drawing content if present
            if has_drawing:
                drawing_node = r_node.find("w:drawing", self.ns)
                if drawing_node is not None:
                    # Check for textbox in drawing - handle AlternateContent properly
                    textbox_node = None
                    
                    # First check for AlternateContent
                    alt_content = drawing_node.find(".//mc:AlternateContent", {"mc": "http://schemas.openxmlformats.org/markup-compatibility/2006"})
                    if alt_content is not None:
                        # Use Choice if available, otherwise Fallback
                        choice = alt_content.find(".//mc:Choice", {"mc": "http://schemas.openxmlformats.org/markup-compatibility/2006"})
                        if choice is not None:
                            textbox_node = choice.find(".//wps:txbx", self.ns_wps)
                        else:
                            fallback = alt_content.find(".//mc:Fallback", {"mc": "http://schemas.openxmlformats.org/markup-compatibility/2006"})
                            if fallback is not None:
                                textbox_node = fallback.find(".//v:textbox", self.ns_v)
                    else:
                        # No AlternateContent, try both formats directly
                        textbox_node = drawing_node.find(".//wps:txbx", self.ns_wps) or drawing_node.find(".//v:textbox", self.ns_v)
                    
                    if textbox_node is not None:
                        textbox_content = self._parse_textbox_content(textbox_node)
                        if textbox_content:
                            anchor_info = self._extract_textbox_anchor_info(drawing_node, textbox_node)
                            logger.info(
                                "Textbox parsing from drawing: has_anchor=%s, anchor_type=%s, content_type=%s, is_list=%s",
                                anchor_info is not None,
                                (anchor_info or {}).get('anchor_type'),
                                type(textbox_content).__name__,
                                isinstance(textbox_content, list),
                            )
                            if anchor_info:
                                self._apply_textbox_anchor_info(run, textbox_content, anchor_info)
                            
                            run.textbox = textbox_content
                    else:
                        # No textbox, so this is an image - parse it
                        image = self._parse_image(drawing_node, parent)
                        if image:
                            # Add image to run
                            if not hasattr(run, 'images'):
                                run.images = []
                            run.images.append(image)
                            # Also add to parent paragraph if it's a paragraph
                            # Zawsze ustaw parent.images, nawet jeśli parent nie ma tego atrybutu
                            # To pozwoli _measure_cell_height znaleźć obrazy w paragrafach
                            if parent:
                                parent_type = type(parent).__name__
                                logger.info(f"xml_parser: Adding image to parent, parent_type={parent_type}, hasattr(parent, 'images')={hasattr(parent, 'images')}")
                                if hasattr(parent, 'images'):
                                    if not isinstance(parent.images, list):
                                        parent.images = []
                                    parent.images.append(image)
                                    logger.info(f"xml_parser: Added image to parent.images (existing), parent.images now has {len(parent.images)} images")
                                elif hasattr(parent, 'add_image'):
                                    parent.add_image(image)
                                    logger.info(f"xml_parser: Added image via parent.add_image()")
                                else:
                                    # Jeśli parent nie ma atrybutu images, utwórz go
                                    parent.images = [image]
                                    parent_id = getattr(parent, 'id', None)
                                    logger.info(f"xml_parser: Created parent.images and added image, parent.images now has 1 image, parent.id={parent_id}, parent type={type(parent).__name__}")
            
            # Check for w:pict elements (VML shapes, watermarks)
            pict_node = r_node.find("w:pict", self.ns)
            if pict_node is not None:
                vml_shape = self._parse_vml_pict(pict_node, parent)
                if vml_shape and parent:
                    if not hasattr(parent, 'vml_shapes'):
                        parent.vml_shapes = []
                    parent.vml_shapes.append(vml_shape)
            
            # Check for AlternateContent in run (not in drawing)
            alt_content = r_node.find(".//mc:AlternateContent", {"mc": "http://schemas.openxmlformats.org/markup-compatibility/2006"})
            if alt_content is not None:
                # If we already attached textbox content from the w:drawing branch, skip fallback parsing
                if getattr(run, "textbox", None):
                    logger.debug("Run already has textbox content from drawing; skipping AlternateContent fallback")
                else:
                    logger.debug(f"Found AlternateContent in run, parsing textbox...")
                    # Use Choice if available, otherwise Fallback
                    choice = alt_content.find(".//mc:Choice", {"mc": "http://schemas.openxmlformats.org/markup-compatibility/2006"})
                    fallback = None if choice is not None else alt_content.find(".//mc:Fallback", {"mc": "http://schemas.openxmlformats.org/markup-compatibility/2006"})

                    textbox_node = None
                    if choice is not None:
                        textbox_node = choice.find(".//wps:txbx", self.ns_wps)
                        logger.debug(f"Found Choice with wps:txbx: {textbox_node is not None}")
                    elif fallback is not None:
                        textbox_node = fallback.find(".//v:textbox", self.ns_v)
                        logger.debug(f"Found Fallback with v:textbox: {textbox_node is not None}")

                    if textbox_node is not None:
                        textbox_content = self._parse_textbox_content(textbox_node)
                        if textbox_content:
                            run.textbox = textbox_content
                            logger.debug(f"Added textbox content to run: {len(textbox_content)} runs")
                            anchor_container = choice if choice is not None else fallback
                            anchor_info = self._extract_textbox_anchor_info(anchor_container, textbox_node)
                            if anchor_info:
                                logger.debug("Applying anchor info from AlternateContent to textbox run")
                                self._apply_textbox_anchor_info(run, textbox_content, anchor_info)
                        else:
                            logger.debug(f"No textbox content parsed from textbox_node")
                    else:
                        logger.debug(f"No textbox node found in AlternateContent")
            
            # Preserve raw XML for lossless export
            raw_xml = ET.tostring(r_node, encoding='unicode', method='xml')
            run.raw_xml = raw_xml
            
            # Apply style to run (style was already parsed above)
            if style:
                run.set_style(style)
                self._apply_style_to_run(run, style)
            
            # Get text content - but skip if run has textbox to avoid duplication
            text_content = ""
            if not hasattr(run, 'textbox') or not run.textbox:
                for t_node in r_node.findall("w:t", self.ns):
                    if t_node.text:
                        text_content += t_node.text
            
            if text_content:
                run.add_text(text_content)
            elif has_break and normalized_break in ("textwrapping", "line", ""):
                # Empty run with break
                run.add_text("\n")
            elif has_tab:
                # Empty run with tab
                run.add_text("\t")
            # Note: Empty runs without any content are intentionally left empty
            # They will be exported as run elements with only rPr (run properties) and no text element
            
            logger.debug(f"Run parsing complete: text='{run.text[:20] if run.text else ''}', has_textbox={hasattr(run, 'textbox') and run.textbox is not None}")
            
            return run
        except Exception as e:
            logger.error(f"Failed to parse run: {e}")
            return None
    
    def _apply_style_to_run(self, run: 'Run', style: Dict[str, Any]) -> None:
        """
        Apply parsed style properties to run attributes.
        Also resolves run_style references from styles.xml.
        
        Args:
            run: Run object to apply style to
            style: Style dictionary from _parse_run_style
        """
        # Apply parsed style properties to run attributes
        if style.get('bold') or style.get('bold_cs'):
            run.set_bold(True)
        if style.get('italic') or style.get('italic_cs'):
            run.set_italic(True)
        if style.get('underline'):
            run.set_underline(True)
        if style.get('strike'):
            run.set_strike_through(True)
        # Font size (convert half-points to points)
        sz = style.get('font_size') or style.get('font_size_cs')
        if sz:
            try:
                run.set_font_size(int(sz) // 2)
            except (TypeError, ValueError):
                pass
        # Font name
        font_ascii = style.get('font_ascii')
        font_hansi = style.get('font_hAnsi')
        font_name = font_ascii or font_hansi
        if font_name:
            run.set_font_name(font_name)
        # Color
        color = style.get('color')
        if color:
            run.set_color(f"#{color}")
        # Vertical alignment
        vert_align = style.get('vertical_align')
        if vert_align == 'superscript':
            run.set_superscript(True)
        elif vert_align == 'subscript':
            run.set_subscript(True)
        
        # Resolve run_style reference if present (odwołanie do stylu z styles.xml)
        run_style_id = style.get('run_style')
        if run_style_id and self.style_manager:
            try:
                resolved_style = self.style_manager.resolve_style(run_style_id)
                if resolved_style:
                    # Merge resolved style properties with inline style
                    resolved_props = resolved_style.get('properties', {}).get('run', {})
                    if resolved_props:
                        # Apply resolved style properties (font, size, color, etc.)
                        if resolved_props.get('font_name'):
                            run.set_font_name(resolved_props['font_name'])
                        if resolved_props.get('font_size'):
                            try:
                                # Font size in styles.xml is in half-points
                                run.set_font_size(int(resolved_props['font_size']) // 2)
                            except (TypeError, ValueError):
                                pass
                        if resolved_props.get('color'):
                            run.set_color(f"#{resolved_props['color']}")
                        if resolved_props.get('bold'):
                            run.set_bold(True)
                        if resolved_props.get('italic'):
                            run.set_italic(True)
                        if resolved_props.get('underline'):
                            run.set_underline(True)
                        # Vertical alignment from resolved style
                        resolved_vert_align = resolved_props.get('vertical_align')
                        if resolved_vert_align == 'superscript':
                            run.set_superscript(True)
                        elif resolved_vert_align == 'subscript':
                            run.set_subscript(True)
            except Exception as e:
                logger.debug(f"Failed to resolve run style {run_style_id}: {e}")
    
    def _parse_sdt(self, sdt_node) -> List['Run']:
        """Parse structured document tag (sdt) and return list of runs from sdtContent."""
        try:
            from ..models.run import Run
            
            runs = []
            
            # Find sdtContent element
            sdt_content = sdt_node.find("w:sdtContent", self.ns)
            if sdt_content is None:
                return runs
            
            # Parse all runs within sdtContent
            for child in sdt_content:
                if child.tag.endswith("}r"):
                    run = self._parse_run(child, None)
                    if run:
                        # Mark run as coming from SDT
                        run.from_sdt = True
                        runs.append(run)
            
            return runs
        except Exception as e:
            logger.error(f"Failed to parse SDT: {e}")
            return []
    
    def _parse_run_style(self, rpr_node) -> Dict[str, Any]:
        """Parse run style properties."""
        style = {}
        try:
            if rpr_node is None:
                return style
            
            # Parse common style properties
            for child in rpr_node:
                tag = child.tag.split("}")[-1]
                
                # Bold
                if tag == "b":
                    style["bold"] = True
                # Bold complex script
                elif tag == "bCs":
                    style["bold_cs"] = True
                # Italic
                elif tag == "i":
                    style["italic"] = True
                # Italic complex script
                elif tag == "iCs":
                    style["italic_cs"] = True
                # Underline
                elif tag == "u":
                    style["underline"] = True
                    style["underline_val"] = child.get(f"{{{self.ns['w']}}}val", "single")
                # Strikethrough
                elif tag == "strike":
                    style["strikethrough"] = True
                # Font size
                elif tag == "sz":
                    style["font_size"] = child.get(f"{{{self.ns['w']}}}val", "")
                # Font size complex script
                elif tag == "szCs":
                    style["font_size_cs"] = child.get(f"{{{self.ns['w']}}}val", "")
                # Color
                elif tag == "color":
                    style["color"] = child.get(f"{{{self.ns['w']}}}val", "")
                    style["color_theme"] = child.get(f"{{{self.ns['w']}}}themeColor", "")
                    style["color_shade"] = child.get(f"{{{self.ns['w']}}}shade", "")
                # Font family
                elif tag == "rFonts":
                    # Try both with and without namespace prefix
                    style["font_ascii"] = child.get(f"{{{self.ns['w']}}}ascii", "") or child.get("ascii", "")
                    style["font_hAnsi"] = child.get(f"{{{self.ns['w']}}}hAnsi", "") or child.get("hAnsi", "")
                    style["font_cs"] = child.get(f"{{{self.ns['w']}}}cs", "") or child.get("cs", "")
                    style["font_eastAsia"] = child.get(f"{{{self.ns['w']}}}eastAsia", "") or child.get("eastAsia", "")
                # Character spacing
                elif tag == "spacing":
                    style["character_spacing"] = child.get(f"{{{self.ns['w']}}}val", "")
                # Character scaling
                elif tag == "w":
                    style["character_scaling"] = child.get(f"{{{self.ns['w']}}}val", "")
                # Kerning
                elif tag == "kern":
                    style["kerning"] = child.get(f"{{{self.ns['w']}}}val", "")
                # Language
                elif tag == "lang":
                    style["lang"] = child.get(f"{{{self.ns['w']}}}val", "")
                    style["lang_eastAsia"] = child.get(f"{{{self.ns['w']}}}eastAsia", "")
                    style["lang_bidi"] = child.get(f"{{{self.ns['w']}}}bidi", "")
                # Shadow
                elif tag == "shd":
                    style["shading"] = {
                        "fill": child.get(f"{{{self.ns['w']}}}fill", ""),
                        "color": child.get(f"{{{self.ns['w']}}}color", ""),
                        "themeFill": child.get(f"{{{self.ns['w']}}}themeFill", ""),
                        "themeFillShade": child.get(f"{{{self.ns['w']}}}themeFillShade", "")
                    }
                # Highlighting
                elif tag == "highlight":
                    style["highlight"] = child.get(f"{{{self.ns['w']}}}val", "")
                # Run style reference
                elif tag == "rStyle":
                    style["run_style"] = child.get(f"{{{self.ns['w']}}}val", "")
                # Emphasize mark
                elif tag == "em":
                    style["emphasis_mark"] = child.get(f"{{{self.ns['w']}}}val", "")
                # Vertically align (superscript/subscript)
                elif tag == "vertAlign":
                    val = child.get(f"{{{self.ns['w']}}}val", "").lower()
                    style["vertical_align"] = val
                    # Map to superscript/subscript flags for easier downstream use
                    if val == "superscript" or val == "sup":
                        style["superscript"] = True
                        style["subscript"] = False
                    elif val == "subscript" or val == "sub":
                        style["subscript"] = True
                        style["superscript"] = False
                # Position
                elif tag == "position":
                    style["position"] = child.get(f"{{{self.ns['w']}}}val", "")
                # Complex script ligatures
                elif tag == "ligatures":
                    style["ligatures"] = child.get(f"{{{self.ns['w']}}}val", "")
                # Number form
                elif tag == "numForm":
                    style["number_form"] = child.get(f"{{{self.ns['w']}}}val", "")
                # Number spacing
                elif tag == "numSpacing":
                    style["number_spacing"] = child.get(f"{{{self.ns['w']}}}val", "")
                # Stylistic sets
                elif tag == "stylisticSets":
                    style["stylistic_sets"] = child.get(f"{{{self.ns['w']}}}val", "")
                # Snap to grid
                elif tag == "snapToGrid":
                    style["snap_to_grid"] = True
                # Suppress auto hyphens
                elif tag == "suppressAutoHyphens":
                    style["suppress_auto_hyphens"] = True
                # Suppress line breaking
                elif tag == "suppressLineBreaks":
                    style["suppress_line_breaks"] = True
        except Exception as e:
            logger.error(f"Failed to parse run style: {e}")
        return style
    
    def _parse_paragraph_style(self, p_node) -> Dict[str, Any]:
        """Parse paragraph style properties."""
        style = {}
        try:
            ppr = p_node.find("w:pPr", self.ns)
            if ppr is not None:
                for child in ppr:
                    tag = child.tag.split("}")[-1]
                    if tag == "pStyle":
                        # Parse style name reference
                        style["style_name"] = child.get(f"{{{self.ns['w']}}}val", "")
                    elif tag == "jc":
                        style["justification"] = child.get(f"{{{self.ns['w']}}}val", "")
                    elif tag == "spacing":
                        spacing_attrs = {
                            "before": child.get(f"{{{self.ns['w']}}}before"),
                            "after": child.get(f"{{{self.ns['w']}}}after"),
                            "line": child.get(f"{{{self.ns['w']}}}line"),
                            "beforeLines": child.get(f"{{{self.ns['w']}}}beforeLines"),
                            "afterLines": child.get(f"{{{self.ns['w']}}}afterLines"),
                            "lineRule": child.get(f"{{{self.ns['w']}}}lineRule"),
                            "beforeAutospacing": child.get(f"{{{self.ns['w']}}}beforeAutospacing"),
                            "afterAutospacing": child.get(f"{{{self.ns['w']}}}afterAutospacing"),
                        }
                        style["spacing"] = {
                            key: value for key, value in spacing_attrs.items() if value not in (None, "")
                        }
                    elif tag == "ind":
                        # Parse indentation
                        style["indent"] = {
                            "left": child.get(f"{{{self.ns['w']}}}left", "0"),
                            "right": child.get(f"{{{self.ns['w']}}}right", "0"),
                            "hanging": child.get(f"{{{self.ns['w']}}}hanging", "0"),
                            "first_line": child.get(f"{{{self.ns['w']}}}firstLine", "0")
                        }
                    elif tag == "numPr":
                        # Parse numbering properties
                        style["numbering"] = {}
                        for num_child in child:
                            num_tag = num_child.tag.split("}")[-1]
                            if num_tag == "ilvl":
                                style["numbering"]["level"] = num_child.get(f"{{{self.ns['w']}}}val", "0")
                            elif num_tag == "numId":
                                style["numbering"]["id"] = num_child.get(f"{{{self.ns['w']}}}val", "0")
                    elif tag == "contextualSpacing":
                        # Parse contextual spacing
                        style["contextual_spacing"] = child.get(f"{{{self.ns['w']}}}val", "")
                    elif tag == "pBdr":
                        # Parse paragraph borders
                        borders = {}
                        for border_child in child:
                            border_tag = border_child.tag.split("}")[-1]
                            border_spec = self._parse_border_spec(border_child)
                            if border_spec:
                                borders[border_tag] = border_spec
                        if borders:
                            style["borders"] = borders
                    elif tag == "tabs":
                        # Parse tab stops
                        tabs = []
                        for tab in child.findall(f"{{{self.ns['w']}}}tab", self.ns):
                            tabs.append(dict(tab.attrib))
                        style["tabs"] = tabs
                    elif tag == "shd":
                        # Parse shading
                        style["shading"] = dict(child.attrib)
        except Exception as e:
            logger.error(f"Failed to parse paragraph style: {e}")
        return style
    
    def _parse_table_style(self, tbl_node) -> Dict[str, Any]:
        """Parse table style properties."""
        style = {}
        try:
            tbl_pr = tbl_node.find("w:tblPr", self.ns)
            if tbl_pr is not None:
                for child in tbl_pr:
                    tag = child.tag.split("}")[-1]
                    if tag == "tblStyle":
                        attrs = self._sanitize_attrib(child.attrib)
                        style["table_style"] = attrs
                        style["style_id"] = attrs.get('val')
                        # Keep legacy key for compatibility
                        if 'style' not in style and attrs.get('val'):
                            style['style'] = attrs.get('val')
                    elif tag == "tblW":
                        style["width"] = self._sanitize_attrib(child.attrib)
                    elif tag == "jc":
                        style["alignment"] = child.get(f"{{{self.ns['w']}}}val", "")
                    elif tag == "tblInd":
                        style["indentation"] = self._sanitize_attrib(child.attrib)
                    elif tag == "tblLayout":
                        style["layout"] = self._sanitize_attrib(child.attrib)
                    elif tag == "tblCellMar":
                        style["cell_margins"] = {}
                        for margin_child in child:
                            margin_tag = margin_child.tag.split('}')[-1]
                            style["cell_margins"][margin_tag] = self._sanitize_attrib(margin_child.attrib)
                    elif tag == "tblLook":
                        style["look"] = self._sanitize_attrib(child.attrib)
                    elif tag == "tblBorders":
                        borders = {}
                        for border_child in child:
                            border_tag = border_child.tag.split('}')[-1]
                            border_spec = self._parse_border_spec(border_child)
                            if border_spec:
                                borders[border_tag] = border_spec
                        if borders:
                            style['borders'] = borders
                    elif tag == "shd":
                        style['shading'] = self._sanitize_attrib(child.attrib)
                    elif tag == "tblCellSpacing":
                        style['cell_spacing'] = self._sanitize_attrib(child.attrib)
        except Exception as e:
            logger.error(f"Failed to parse table style: {e}")
        return style
    
    def _parse_core_properties(self, core_props_xml: str) -> Dict[str, Any]:
        """Parse core properties XML."""
        props = {}
        try:
            root = ET.fromstring(core_props_xml)
            for prop_name in ['title', 'subject', 'creator', 'description', 'keywords']:
                element = root.find(f".//{{http://purl.org/dc/elements/1.1/}}{prop_name}")
                if element is not None and element.text:
                    props[prop_name] = element.text
            
            # Parse created date
            created_element = root.find(".//{http://purl.org/dc/terms/}created")
            if created_element is not None and created_element.text:
                props['created'] = created_element.text
        except Exception as e:
            logger.error(f"Failed to parse core properties: {e}")
        return props
    
    def _parse_paragraph_properties(self, p_pr_element) -> Dict[str, Any]:
        """Parse paragraph properties."""
        props = {}
        try:
            # Parse alignment
            jc = p_pr_element.find("w:jc", self.ns)
            if jc is not None:
                props['alignment'] = jc.get("w:val", "left")
            
            # Parse spacing
            spacing = p_pr_element.find("w:spacing", self.ns)
            if spacing is not None:
                spacing_props = {}
                before_val = spacing.get("w:before")
                if before_val:
                    spacing_props['before'] = before_val
                after_val = spacing.get("w:after")
                if after_val:
                    spacing_props['after'] = after_val
                # Always add spacing if spacing element exists
                props['spacing'] = spacing_props
        except Exception as e:
            logger.error(f"Failed to parse paragraph properties: {e}")
        return props
    
    def _parse_run_properties(self, r_pr_element) -> Dict[str, Any]:
        """Parse run properties."""
        props = {}
        try:
            # Parse bold
            if r_pr_element.find("w:b", self.ns) is not None:
                props['bold'] = True
            
            # Parse italic
            if r_pr_element.find("w:i", self.ns) is not None:
                props['italic'] = True
            
            # Parse size
            sz = r_pr_element.find("w:sz", self.ns)
            if sz is not None:
                props['size'] = sz.get("w:val")
            
            # Parse color
            color = r_pr_element.find("w:color", self.ns)
            if color is not None:
                props['color'] = color.get("w:val")
        except Exception as e:
            logger.error(f"Failed to parse run properties: {e}")
        return props
    
    def _parse_table_properties(self, tbl_pr_element) -> Dict[str, Any]:
        """Parse table properties."""
        props = {}
        try:
            # Parse style
            style = tbl_pr_element.find("w:tblStyle", self.ns)
            if style is not None:
                props['style'] = style.get("w:val")
            
            # Parse width
            width = tbl_pr_element.find("w:tblW", self.ns)
            if width is not None:
                props['width'] = width.get("w:w")
            
            # Parse borders
            borders = tbl_pr_element.find("w:tblBorders", self.ns)
            if borders is not None:
                border_props = {}
                for border in borders:
                    border_name = border.tag.split("}")[-1]
                    border_props[border_name] = {
                        'val': border.get("w:val"),
                        'sz': border.get("w:sz")
                    }
                if border_props:
                    props['borders'] = border_props
        except Exception as e:
            logger.error(f"Failed to parse table properties: {e}")
        return props
    
    def _parse_app_properties(self, app_props_xml: str) -> Dict[str, Any]:
        """Parse app properties XML."""
        props = {}
        try:
            root = ET.fromstring(app_props_xml)
            for prop_name in ['Application', 'AppVersion', 'Company', 'Manager']:
                element = root.find(f".//{{http://schemas.openxmlformats.org/officeDocument/2006/extended-properties}}{prop_name}")
                if element is not None and element.text:
                    props[prop_name] = element.text
        except Exception as e:
            logger.error(f"Failed to parse app properties: {e}")
        return props
    
    def _parse_custom_properties(self, custom_props_xml: str) -> Dict[str, Any]:
        """Parse custom properties XML."""
        props = {}
        try:
            root = ET.fromstring(custom_props_xml)
            for prop in root.findall(".//{http://schemas.openxmlformats.org/officeDocument/2006/custom-properties}property"):
                name = prop.get("name", "")
                if name:
                    # Get property value from lpwstr element
                    value_elem = prop.find(".//{http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes}lpwstr")
                    if value_elem is not None and value_elem.text:
                        props[name] = value_elem.text
        except Exception as e:
            logger.error(f"Failed to parse custom properties: {e}")
        return props
    
    def parse_header(self) -> Optional['Body']:
        """
        Parse document header.
        
        Returns:
            Body object containing header content or None if no header
        """
        try:
            # Get header XML
            header_xml = self.package_reader.get_xml_content("word/header1.xml")
            if not header_xml:
                logger.debug("No header found")
                return None
            
            # Ustaw relationship file dla headerów, żeby obrazy miały poprawne ścieżki
            previous_part = self._current_part_path
            previous_rel = self._current_relationship_file
            self._current_part_path = "word/header1.xml"
            self._current_relationship_file = "word/_rels/header1.xml.rels"
            
            try:
                root = ET.fromstring(header_xml)
                
                # Create header body
                from ..models.body import Body
                header_body = Body()
                
                # Parse header content
                for child in root:
                    if child.tag.endswith("}p"):  # Paragraph
                        paragraph = self.parse_element(child, header_body)
                        if paragraph:
                            header_body.add_child(paragraph)
                    elif child.tag.endswith("}tbl"):  # Table
                        table = self.parse_element(child, header_body)
                        if table:
                            header_body.add_child(table)
                
                logger.info(f"Parsed header with {len(header_body.children)} elements")
                return header_body
            finally:
                # Przywróć poprzednie wartości
                self._current_part_path = previous_part
                self._current_relationship_file = previous_rel
            
        except Exception as e:
            logger.error(f"Failed to parse header: {e}")
            return None
    
    def parse_footer(self) -> Optional['Body']:
        """
        Parse document footer.
        
        Returns:
            Body object containing footer content or None if no footer
        """
        try:
            # Get footer XML
            footer_xml = self.package_reader.get_xml_content("word/footer1.xml")
            if not footer_xml:
                logger.debug("No footer found")
                return None
            
            # Ustaw relationship file dla footerów, żeby obrazy miały poprawne ścieżki
            previous_part = self._current_part_path
            previous_rel = self._current_relationship_file
            self._current_part_path = "word/footer1.xml"
            self._current_relationship_file = "word/_rels/footer1.xml.rels"
            
            try:
                root = ET.fromstring(footer_xml)
                
                # Create footer body
                from ..models.body import Body
                footer_body = Body()
                
                # Parse footer content
                for child in root:
                    if child.tag.endswith("}p"):  # Paragraph
                        paragraph = self.parse_element(child, footer_body)
                        if paragraph:
                            footer_body.add_child(paragraph)
                    elif child.tag.endswith("}tbl"):  # Table
                        table = self.parse_element(child, footer_body)
                        if table:
                            footer_body.add_child(table)
                    elif child.tag.endswith("}sdt"): # Structured Document Tag
                        sdt_content = child.find(f"{self.ns['w']}sdtContent")
                        if sdt_content is not None:
                            for sdt_child in sdt_content:
                                if sdt_child.tag.endswith("}p"):
                                    paragraph = self.parse_element(sdt_child, footer_body)
                                    if paragraph:
                                        footer_body.add_child(paragraph)
                                elif sdt_child.tag.endswith("}tbl"):
                                    table = self.parse_element(sdt_child, footer_body)
                                    if table:
                                        footer_body.add_child(table)
                                elif sdt_child.tag.endswith("}drawing"):
                                    image = self._parse_image(sdt_child, footer_body)
                                    if image:
                                        footer_body.add_child(image)
                                elif sdt_child.tag.endswith("}txbxContent"):
                                    textbox = self._parse_textbox(sdt_child)
                                    footer_body.add_child(textbox)
                    elif child.tag.endswith("}drawing"): # Direct drawing in footer
                        image = self._parse_image(child, footer_body)
                        if image:
                            footer_body.add_child(image)
                    elif child.tag.endswith("}txbxContent"): # Direct textbox in footer
                        textbox = self._parse_textbox(child)
                        footer_body.add_child(textbox)
                
                logger.info(f"Parsed footer with {len(footer_body.children)} elements")
                return footer_body
            finally:
                # Przywróć poprzednie wartości
                self._current_part_path = previous_part
                self._current_relationship_file = previous_rel
            
        except Exception as e:
            logger.error(f"Failed to parse footer: {e}")
            return None