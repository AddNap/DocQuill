"""
XML exporter for DOCX documents.

Handles WordML regeneration, roundtrip testing, and XML formatting.
"""

import math
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class XMLExporter:
    """
    Re-generates WordML (roundtrip test).
    
    Handles WordML regeneration, roundtrip testing, and XML formatting.
    """
    
    def __init__(self, document: Any, namespace: str = 'w', xml_namespace: str = None,
                 indent: int = 2, encoding: str = 'utf-8'):
        """
        Initialize XML exporter.
        
        Args:
            document: Document to export
            namespace: XML namespace prefix
            indent: XML indentation level
            encoding: XML encoding
        """
        # Validate document
        if document is None:
            raise ValueError("Document cannot be None")
        
        self.document = document
        self.namespace = namespace
        self.indent = indent
        self.encoding = encoding
        
        # XML namespaces
        self.namespaces = {
            'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
            'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
            'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
            'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
            'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture',
            'mc': 'http://schemas.openxmlformats.org/markup-compatibility/2006'
        }
        
        # Register namespaces to preserve prefixes in ET.tostring
        ET.register_namespace('w', self.namespaces['w'])
        ET.register_namespace('r', self.namespaces['r'])
        ET.register_namespace('wp', self.namespaces['wp'])
        ET.register_namespace('a', self.namespaces['a'])
        ET.register_namespace('pic', self.namespaces['pic'])
        ET.register_namespace('mc', self.namespaces['mc'])
        
        if xml_namespace:
            self.namespaces[namespace] = xml_namespace
        
        self.xml_namespace = self.namespaces.get(namespace, 'http://schemas.openxmlformats.org/wordprocessingml/2006/main')  # Alias for compatibility
        
        logger.debug("XML exporter initialized")
    
    # ------------------------------------------------------------------
    @staticmethod
    def _coerce_attr_value(value: Any) -> Optional[str]:
        """Convert attribute value to a safe string for XML serialization."""
        if value is None:
            return None
        if isinstance(value, bool):
            return "1" if value else "0"
        if isinstance(value, (int,)):
            return str(value)
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                return None
            if value.is_integer():
                return str(int(value))
            return format(value, ".10g")
        return str(value)

    def _set_attr(self, element: ET.Element, key: str, value: Any) -> None:
        """Safely set XML attribute ensuring proper string conversion."""
        coerced = self._coerce_attr_value(value)
        if coerced is None:
            return
        element.set(key, coerced)
    
    def _sanitize_attributes(self, element: ET.Element) -> None:
        """Recursively sanitize attributes to prevent non-string XML values."""
        attrib_items = list(element.attrib.items())
        for attr_key, attr_value in attrib_items:
            coerced = self._coerce_attr_value(attr_value)
            if coerced is None:
                element.attrib.pop(attr_key, None)
            else:
                element.attrib[attr_key] = coerced
        for child in list(element):
            self._sanitize_attributes(child)
    
    def export(self, output_path: Union[str, Path]) -> bool:
        """
        Export document to XML.
        
        Args:
            output_path: Output file path
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Generate XML content
            xml_content = self.regenerate_wordml(self.document)
            
            # Format XML output
            formatted_content = self.format_xml_output(xml_content)
            
            # Write to file
            with open(output_path, 'w', encoding=self.encoding) as f:
                f.write(formatted_content)
            
            logger.info(f"Document exported to XML: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export document to XML: {e}")
            return False
    
    def regenerate_wordml(self, document: Any = None) -> str:
        """
        Regenerate WordML from document model.
        
        Args:
            document: Document to regenerate
            
        Returns:
            WordML XML string
        """
        if document is None:
            document = self.document
        
        # Create root document element
        # Use full namespace URI - ET.tostring will add xmlns declarations based on registered namespaces
        root = ET.Element('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}document')
        # Add mc:Ignorable attribute (mc namespace is registered, so prefix will be preserved)
        root.set('{http://schemas.openxmlformats.org/markup-compatibility/2006}Ignorable', 'w14 wp14 w15')
        
        # Create body element using full namespace URI
        body = ET.SubElement(root, '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}body')
        
        # Export body children directly maintaining order
        # Check both _body (from parser) and body (from JSON importer)
        body_obj = None
        if hasattr(document, '_body') and document._body:
            body_obj = document._body
        elif hasattr(document, 'body') and document.body:
            body_obj = document.body
        
        # Also check elements (from DocumentAdapter)
        children = []
        if body_obj:
            # Get children - check various possible attributes
            if hasattr(body_obj, 'children') and body_obj.children:
                children = body_obj.children if isinstance(body_obj.children, (list, tuple)) else list(body_obj.children)
            elif hasattr(body_obj, 'paragraphs') and body_obj.paragraphs:
                children = body_obj.paragraphs if isinstance(body_obj.paragraphs, (list, tuple)) else list(body_obj.paragraphs)
        
        # If children not found in body_obj, check directly in document...
        if not children:
            if hasattr(document, 'elements') and document.elements:
                children = document.elements if isinstance(document.elements, (list, tuple)) else list(document.elements)
        
        if children:
            
            for child in children:
                # Determine element type
                if hasattr(child, 'get_text') and not hasattr(child, 'get_rows'):
                    # It's a paragraph
                    element_type = 'paragraph'
                elif hasattr(child, 'get_rows'):
                    # It's a table
                    element_type = 'table'
                else:
                    # Unknown type
                    continue
                
                # Export element
                element_xml = self.export_element_xml(child, element_type)
                if element_xml is not None:
                    body.append(element_xml)
        
        # Add section with header/footer references (last section at end of body)
        # Get sections - check multiple possible locations
        sections = None
        if hasattr(document, '_sections') and document._sections:
            sections = document._sections
        elif hasattr(document, '_json_sections') and document._json_sections:
            sections = document._json_sections
        elif hasattr(document, 'sections') and document.sections:
            sections = document.sections
        
        if sections:
            # Use last section's properties for end of body sectPr
            section = sections[-1] if isinstance(sections, list) and len(sections) > 0 else {}
            if section:
                sectPr = ET.SubElement(body, f'{self.namespace}:sectPr')
                self._export_sect_pr(sectPr, section)
        
        # Sanitize attributes before serialization
        self._sanitize_attributes(root)

        # Convert to string with proper formatting
        xml_str = self.format_xml_output(ET.tostring(root, encoding='unicode'))
        
        return xml_str
    
    def _export_sect_pr(self, parent: ET.Element, section: Dict[str, Any]) -> None:
        """
        Export section properties (sectPr) to parent element.
        
        Args:
            parent: Parent element (body or pPr) to add sectPr to
            section: Section properties dictionary
        """
        sectPr = ET.SubElement(parent, f'{self.namespace}:sectPr')
        
        # Add headers
        if 'headers' in section and isinstance(section['headers'], list):
            for hdr in section['headers']:
                headerRef = ET.SubElement(sectPr, f'{self.namespace}:headerReference')
                if 'type' in hdr:
                    headerRef.set(f'{self.namespace}:type', hdr['type'])
                if 'id' in hdr:
                    headerRef.set('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id', hdr['id'])
        
        # Add footers
        if 'footers' in section and isinstance(section['footers'], list):
            for ftr in section['footers']:
                footerRef = ET.SubElement(sectPr, f'{self.namespace}:footerReference')
                if 'type' in ftr:
                    footerRef.set(f'{self.namespace}:type', ftr['type'])
                if 'id' in ftr:
                    footerRef.set('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id', ftr['id'])
        
        # Add page size
        if 'page_size' in section and isinstance(section['page_size'], dict):
            pgSz = ET.SubElement(sectPr, f'{self.namespace}:pgSz')
            pg_size = section['page_size']
            width = pg_size.get('w') or pg_size.get('width')
            height = pg_size.get('h') or pg_size.get('height')
            orient = pg_size.get('orient') or pg_size.get('orientation')
            code = pg_size.get('code')
            
            if width:
                pgSz.set(f'{self.namespace}:w', str(width))
            if height:
                pgSz.set(f'{self.namespace}:h', str(height))
            if orient:
                pgSz.set(f'{self.namespace}:orient', str(orient))
            if code:
                pgSz.set(f'{self.namespace}:code', str(code))
        
        # Add margins
        if 'margins' in section and isinstance(section['margins'], dict):
            pgMar = ET.SubElement(sectPr, f'{self.namespace}:pgMar')
            margins = section['margins']
            for key, value in margins.items():
                pgMar.set(f'{self.namespace}:{key}', str(value))
        
        # Add columns
        if 'columns' in section and isinstance(section['columns'], dict):
            columns = section['columns']
            if columns.get('num') is not None or columns.get('space') is not None:
                cols = ET.SubElement(sectPr, f'{self.namespace}:cols')
                if 'num' in columns and columns['num'] is not None:
                    cols.set(f'{self.namespace}:num', str(columns['num']))
                if 'space' in columns and columns['space'] is not None:
                    cols.set(f'{self.namespace}:space', str(columns['space']))
        
        # Add title page
        if section.get('title_page') or section.get('different_first_page'):
            ET.SubElement(sectPr, f'{self.namespace}:titlePg')
        
        # Add different odd/even headers
        if section.get('different_odd_even'):
            ET.SubElement(sectPr, f'{self.namespace}:evenAndOddHeaders')
        
        # Add docGrid
        if 'doc_grid' in section and isinstance(section['doc_grid'], dict):
            docGrid = ET.SubElement(sectPr, f'{self.namespace}:docGrid')
            grid = section['doc_grid']
            if 'linePitch' in grid:
                docGrid.set(f'{self.namespace}:linePitch', str(grid['linePitch']))
            if 'charSpace' in grid:
                docGrid.set(f'{self.namespace}:charSpace', str(grid['charSpace']))
    
    def _apply_header_footer_fixes(self, document: Any) -> None:
        """Apply automatic positioning fixes to headers and footers."""
        try:
            # Get header/footer parser
            parser = document._header_footer_parser
            
            # Process each header
            for header_id, header_info in parser.headers.items():
                if 'path' in header_info:
                    self._fix_image_positioning_in_file(header_info['path'])
            
            # Process each footer
            for footer_id, footer_info in parser.footers.items():
                if 'path' in footer_info:
                    self._fix_image_positioning_in_file(footer_info['path'])
        
        except Exception as e:
            logger.error(f"Failed to apply header/footer fixes: {e}")
    
    def _fix_image_positioning_in_file(self, file_path: str) -> None:
        """Fix image positioning in a header/footer XML file."""
        try:
            # Read the file
            if not hasattr(self.document, '_package_reader'):
                return
            
            xml_content = self.document._package_reader.get_xml_content(file_path)
            if not xml_content:
                return
            
            # Parse the XML
            root = ET.fromstring(xml_content)
            
            # Apply positioning fix
            wp_ns = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
            modified = False
            
            # Find all drawing elements
            for drawing in root.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing'):
                # Find anchor elements
                for anchor in drawing.findall(f'.//{wp_ns}anchor'):
                    self._fix_anchor_for_header_footer(anchor, wp_ns)
                    modified = True
                    logger.debug(f"Fixed image positioning in {file_path}")
            
            # Write back if modified
            if modified:
                # Note: This would need to be saved to a temporary location
                # since we can't modify the original package reader during export
                # For now, this is a placeholder
                pass
        
        except Exception as e:
            logger.error(f"Failed to fix image positioning in {file_path}: {e}")
    
    def _fix_anchor_for_header_footer(self, anchor_el, wp_ns: str) -> None:
        """
        Fix anchor element for headers/footers to ensure images are visible.
        
        Fixes:
        1. Change relativeFrom from 'column' to 'page' for positionH (page edge, not margin)
        2. Fix negative posOffset (set to 0 for page edge)
        3. Keep positionV at 'page' (correct for headers/footers)
        4. Set layoutInCell to '1' for proper rendering in header tables
        
        Args:
            anchor_el: Anchor element to fix
            wp_ns: WordPress namespace URI
        """
        try:
            # DON'T change positioning - preserve original!
            # The original 'column' with negative offset is correct for positioning
            # We only fix visibility by changing layoutInCell
            
            logger.debug("Preserving original positioning (column/page)")
            
            # Only fix: if layoutInCell prevents visibility
            
            # Fix layoutInCell
            layout_in_cell = anchor_el.get('layoutInCell')
            if layout_in_cell != '1':
                anchor_el.set('layoutInCell', '1')
                logger.debug("Fixed layoutInCell: 0 -> 1")
        
        except Exception as e:
            logger.error(f"Failed to fix anchor for header/footer: {e}")
    
    def export_document_xml(self, document: Any) -> str:
        """
        Export document as XML.
        
        Args:
            document: Document to export
            
        Returns:
            XML string representation
        """
        return self.regenerate_wordml(document)
    
    def export_element_xml(self, element: Union[Dict[str, Any], Any], element_type: str = None) -> ET.Element:
        """
        Export element as XML.
        
        Args:
            element: Element to export
            element_type: Type of element
            
        Returns:
            XML element
        """
        # Auto-detect element type if not provided
        if element_type is None:
            if isinstance(element, dict):
                element_type = element.get('type', 'unknown')
            else:
                # Check class name
                class_name = element.__class__.__name__.lower()
                if 'table' in class_name:
                    element_type = 'table'
                elif 'paragraph' in class_name:
                    element_type = 'paragraph'
                elif 'image' in class_name:
                    element_type = 'image'
                else:
                    element_type = 'unknown'
        
        if element_type == 'paragraph':
            xml_element = self._export_paragraph_xml(element)
        elif element_type == 'table':
            xml_element = self._export_table_xml(element)
        elif element_type == 'image':
            xml_element = self._export_image_xml(element)
        else:
            xml_element = self._export_generic_xml(element)
        
        return xml_element
    
    def export_element_xml_string(self, element: Union[Dict[str, Any], Any], element_type: str = None) -> str:
        """
        Export element as XML string.
        
        Args:
            element: Element to export
            element_type: Type of element
            
        Returns:
            XML string
        """
        xml_element = self.export_element_xml(element, element_type)
        return ET.tostring(xml_element, encoding=self.encoding).decode(self.encoding)
    
    def format_xml_output(self, xml_content: str) -> str:
        """
        Format XML output.
        
        Args:
            xml_content: Raw XML content
            
        Returns:
            Formatted XML content
        """
        try:
            # Parse XML for formatting
            root = ET.fromstring(xml_content)
            
            # For DOCX compatibility, generate compact XML (minimal formatting)
            # This matches the format used by Microsoft Word and avoids SAX parser issues
            # Convert to string without indentation to match original DOCX format
            formatted_xml = ET.tostring(root, encoding='unicode', method='xml')
            
            # Remove all unnecessary whitespace between tags (but preserve text content)
            # This creates compact XML like original DOCX files
            import re
            # Remove whitespace between tags, but preserve text nodes
            formatted_xml = re.sub(r'>\s+<', '><', formatted_xml)
            
            # Remove trailing whitespace/newlines that might cause SAX parser issues
            formatted_xml = formatted_xml.rstrip()
            
            # Add XML declaration with standalone="yes"
            # Use UTF-8 (uppercase) to match original DOCX format
            encoding = 'UTF-8' if self.encoding.lower() == 'utf-8' else self.encoding
            return f'<?xml version="1.0" encoding="{encoding}" standalone="yes"?>\n{formatted_xml}'
            
        except Exception as e:
            logger.error(f"Failed to format XML: {e}")
            return xml_content
    
    def _export_paragraph_xml(self, paragraph: Union[Dict[str, Any], Any]) -> ET.Element:
        """Export paragraph as XML."""
        # Check if we have raw_xml (lossless mode)
        if isinstance(paragraph, dict) and 'raw_xml' in paragraph:
            raw_xml = paragraph['raw_xml']
        else:
            raw_xml = getattr(paragraph, 'raw_xml', None)
        
        # If raw_xml exists, parse and return it directly for lossless export
        # but with automatic positioning fixes for images and style updates
        if raw_xml:
            try:
                para_elem = ET.fromstring(raw_xml)
                
                # Check if this paragraph is from header/footer - if so, don't modify it
                # Headers/footers are in separate XML files and should be preserved as-is
                is_header_footer = False
                raw_lower = raw_xml.lower()
                if 'header' in raw_lower or 'footer' in raw_lower or 'word/header' in raw_lower or 'word/footer' in raw_lower:
                    is_header_footer = True
                
                # Only update styles if not from header/footer
                if not is_header_footer:
                    # Update pStyle if paragraph has a style_name
                    if isinstance(paragraph, dict):
                        style = paragraph.get('style')
                    else:
                        style = getattr(paragraph, 'style', None)
                    
                    if isinstance(style, dict) and style.get('style_name'):
                        style_name = style.get('style_name')
                        w_ns = self.namespaces["w"]
                        p_pr = para_elem.find(f'.//{{{w_ns}}}pPr')
                        if p_pr is not None:
                            p_style = p_pr.find(f'.//{{{w_ns}}}pStyle')
                            if p_style is not None:
                                # Update existing pStyle - use full namespace URI for attribute
                                # Remove old val attribute first
                                for key in list(p_style.attrib.keys()):
                                    if key.endswith('val') or key == 'val':
                                        del p_style.attrib[key]
                                # Set new val with proper namespace
                                p_style.set(f'{{{w_ns}}}val', str(style_name))
                            else:
                                # Add new pStyle
                                p_style = ET.SubElement(p_pr, f'{{{w_ns}}}pStyle')
                                p_style.set(f'{{{w_ns}}}val', str(style_name))
                
                # Apply automatic positioning fix for images in this paragraph
                # (but only if not from header/footer - headers/footers are in separate files)
                if not is_header_footer:
                    wp_ns = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
                    
                    # Find all drawing elements in the paragraph and fix anchors
                    for drawing in para_elem.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing'):
                        # Find anchor elements
                        for anchor in drawing.findall(f'.//{wp_ns}anchor'):
                            self._fix_anchor_for_header_footer(anchor, wp_ns)
                
                return para_elem
            except Exception as e:
                logger.error(f"Failed to parse raw_xml for paragraph: {e}")
                # Fall through to normal export
        
        p = ET.Element(f'{self.namespace}:p')
        
        # Handle both dict and object inputs
        if isinstance(paragraph, dict):
            style = paragraph.get('style')
            text = paragraph.get('text', '')
            runs = paragraph.get('runs', [])
            images = paragraph.get('images', [])
        else:
            style = getattr(paragraph, 'style', None)
            text = paragraph.get_text() if hasattr(paragraph, 'get_text') else ''
            runs = paragraph.runs if hasattr(paragraph, 'runs') else []
            images = getattr(paragraph, 'images', [])
        
        # Add paragraph properties if available
        # Check numbering directly from paragraph (may not be in style)
        paragraph_numbering = None
        if isinstance(paragraph, dict):
            paragraph_numbering = paragraph.get('numbering')
        else:
            paragraph_numbering = getattr(paragraph, 'numbering', None)
        
        # If numbering not in style, add it
        if paragraph_numbering and (not style or not isinstance(style, dict) or 'numbering' not in style):
            if not style:
                style = {}
            if not isinstance(style, dict):
                style = {'style_name': str(style)}
            style['numbering'] = paragraph_numbering if isinstance(paragraph_numbering, dict) else {
                'id': getattr(paragraph_numbering, 'id', None),
                'level': getattr(paragraph_numbering, 'level', None)
            }
        
        # Check if paragraph has section_properties (sectPr in pPr)
        section_props = None
        if isinstance(paragraph, dict):
            section_props = paragraph.get('section_properties')
        else:
            section_props = getattr(paragraph, 'section_properties', None)
        
        if style:
            pPr = ET.SubElement(p, f'{self.namespace}:pPr')
            if isinstance(style, dict):
                self._add_paragraph_properties(pPr, style)
            else:
                # Handle string style
                pStyle = ET.SubElement(pPr, f'{self.namespace}:pStyle')
                pStyle.set(f'{self.namespace}:val', str(style))
            
            # Add sectPr to pPr if paragraph has section_properties
            if section_props:
                self._export_sect_pr(pPr, section_props)
        elif section_props:
            # Create pPr just for sectPr if no style
            pPr = ET.SubElement(p, f'{self.namespace}:pPr')
            self._export_sect_pr(pPr, section_props)
        
        # Add runs - if no runs, create a single run from text
        if runs:
            # Group consecutive SDT runs together
            i = 0
            while i < len(runs):
                run_obj = runs[i]
                from_sdt = getattr(run_obj, 'from_sdt', False)
                
                # If this run is from SDT, collect all consecutive SDT runs
                if from_sdt:
                    sdt_runs = []
                    j = i
                    while j < len(runs) and getattr(runs[j], 'from_sdt', False):
                        sdt_runs.append(runs[j])
                        j += 1
                    
                    # Export as SDT
                    sdt_element = self._export_sdt_xml(sdt_runs)
                    if sdt_element:
                        p.append(sdt_element)
                    
                    i = j  # Skip to next non-SDT run
                    continue
                
                # Regular run (not from SDT)
                r = ET.SubElement(p, f'{self.namespace}:r')
                run_text = run_obj.get_text() if hasattr(run_obj, 'get_text') else (run_obj.get('text', '') if isinstance(run_obj, dict) else '')
                run_style = run_obj.style if hasattr(run_obj, 'style') else (run_obj.get('style') if isinstance(run_obj, dict) else None)
                
                # Add run properties if available
                if run_style:
                    rPr = ET.SubElement(r, f'{self.namespace}:rPr')
                    if isinstance(run_style, dict):
                        self._add_run_properties(rPr, run_style)
                    else:
                        rStyle = ET.SubElement(rPr, f'{self.namespace}:rStyle')
                        rStyle.set(f'{self.namespace}:val', str(run_style))
                
                # Check for breaks, tabs, drawings
                if isinstance(run_obj, dict):
                    has_break = run_obj.get('has_break', False)
                    has_tab = run_obj.get('has_tab', False)
                    has_drawing = run_obj.get('has_drawing', False)
                    break_type = run_obj.get('break_type')
                else:
                    # Handle Run object
                    has_break = getattr(run_obj, 'has_break', False)
                    has_tab = getattr(run_obj, 'has_tab', False)
                    has_drawing = getattr(run_obj, 'has_drawing', False)
                    break_type = getattr(run_obj, 'break_type', None)
                
                # Add break
                if has_break:
                    br_elem = ET.SubElement(r, f'{self.namespace}:br')
                    if break_type and break_type not in (None, "", "textWrapping"):
                        br_elem.set(f'{self.namespace}:type', str(break_type))
                
                # Add tab
                if has_tab:
                    ET.SubElement(r, f'{self.namespace}:tab')
                
                # Add text (only if run has meaningful text, not just whitespace)
                # Empty runs (with just spaces) should not have a text element
                if run_text and run_text.strip():
                    t = ET.SubElement(r, f'{self.namespace}:t')
                    t.text = run_text
                
                i += 1  # Move to next run
        elif text:
            # Fallback: single run with text
            run = ET.SubElement(p, f'{self.namespace}:r')
            
            if style:
                rPr = ET.SubElement(run, f'{self.namespace}:rPr')
                if isinstance(style, dict):
                    self._add_run_properties(rPr, style)
                else:
                    rStyle = ET.SubElement(rPr, f'{self.namespace}:rStyle')
                    rStyle.set(f'{self.namespace}:val', str(style))
            
            t = ET.SubElement(run, f'{self.namespace}:t')
            t.text = text
        
        # Add images (drawings) if any
        if images:
            for image in images:
                if isinstance(image, dict) and 'raw_xml' in image:
                    # Parse raw XML and add directly as child of paragraph
                    try:
                        drawing_elem = ET.fromstring(image['raw_xml'])
                        # Clone the drawing element with all its children
                        drawing = ET.SubElement(p, drawing_elem.tag)
                        
                        # Copy all attributes
                        for attr_name, attr_value in drawing_elem.attrib.items():
                            drawing.set(attr_name, attr_value)
                        
                        # Copy all children with deep copy and fix positioning if needed
                        import copy
                        wp_ns = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
                        
                        for child in drawing_elem:
                            child_copy = copy.deepcopy(child)
                            
                            # Check if this is an anchor element and fix positioning for headers/footers
                            if child.tag.endswith('}anchor'):
                                self._fix_anchor_for_header_footer(child_copy, wp_ns)
                            
                            drawing.append(child_copy)
                    except Exception as e:
                        logger.error(f"Failed to export raw XML image: {e}")
        
        return p
    
    def _export_sdt_xml(self, runs: List[Any]) -> ET.Element:
        """Export SDT (structured document tag) element containing runs."""
        sdt = ET.Element(f'{self.namespace}:sdt')
        
        # Create sdtContent element
        sdt_content = ET.SubElement(sdt, f'{self.namespace}:sdtContent')
        
        # Export each run
        for run_obj in runs:
            r = ET.SubElement(sdt_content, f'{self.namespace}:r')
            run_text = run_obj.get_text() if hasattr(run_obj, 'get_text') else ''
            run_style = run_obj.style if hasattr(run_obj, 'style') else {}
            
            # Add run properties if available
            if run_style:
                rPr = ET.SubElement(r, f'{self.namespace}:rPr')
                if isinstance(run_style, dict):
                    self._add_run_properties(rPr, run_style)
            
            # Check for breaks, tabs, drawings
            has_break = getattr(run_obj, 'has_break', False)
            has_tab = getattr(run_obj, 'has_tab', False)
            has_drawing = getattr(run_obj, 'has_drawing', False)
            break_type = getattr(run_obj, 'break_type', None)
            
            # Add break
            if has_break:
                br_elem = ET.SubElement(r, f'{self.namespace}:br')
                if break_type and break_type not in (None, "", "textWrapping"):
                    br_elem.set(f'{self.namespace}:type', str(break_type))
            
            # Add tab
            if has_tab:
                ET.SubElement(r, f'{self.namespace}:tab')
            
            # Add text (only if meaningful)
            if run_text and run_text.strip():
                t = ET.SubElement(r, f'{self.namespace}:t')
                t.text = run_text
        
        return sdt
    
    def _export_table_xml(self, table: Union[Dict[str, Any], Any]) -> ET.Element:
        """Export table as XML."""
        tbl = ET.Element(f'{self.namespace}:tbl')
        
        # Handle both dict and object inputs
        if isinstance(table, dict):
            style = table.get('style')
            rows = table.get('rows', [])
        else:
            style = getattr(table, 'style', None)
            rows = table.get_rows() if hasattr(table, 'get_rows') else []
        
        # Add table properties if available
        if style:
            tblPr = ET.SubElement(tbl, f'{self.namespace}:tblPr')
            if isinstance(style, dict):
                self._add_table_properties(tblPr, style)
            else:
                # Handle string style
                tblStyle = ET.SubElement(tblPr, f'{self.namespace}:tblStyle')
                tblStyle.set(f'{self.namespace}:val', str(style))
        
        # Determine column count from first row (before adding tblGrid)
        if rows:
            first_row_data = rows[0]
            if isinstance(first_row_data, dict):
                cells = first_row_data.get('cells', [])
            else:
                cells = first_row_data.get_cells() if hasattr(first_row_data, 'get_cells') else []
            cols = len(cells)
        else:
            # Try to get from table object
            if isinstance(table, dict):
                cols = table.get('cols', 1)
            else:
                cols = getattr(table, 'cols', 1)
                if not isinstance(cols, int):
                    cols = 1
        
        # Add table grid FIRST (before rows) with correct column count and widths
        tblGrid = ET.SubElement(tbl, f'{self.namespace}:tblGrid')
        
        # Try to get grid widths from table object
        grid_widths = []
        if isinstance(table, dict):
            grid = table.get('grid', [])
        else:
            grid = getattr(table, 'grid', [])
        
        # Extract widths from grid
        for i, grid_col in enumerate(grid):
            if isinstance(grid_col, dict):
                width = grid_col.get('width', '1000')
                grid_widths.append(str(width))
            else:
                grid_widths.append('1000')
        
        # Create grid columns with widths
        for i in range(cols):
            gridCol = ET.SubElement(tblGrid, f'{self.namespace}:gridCol')
            if i < len(grid_widths):
                gridCol.set(f'{self.namespace}:w', grid_widths[i])
            else:
                gridCol.set(f'{self.namespace}:w', '1000')  # Default width
        
        # Add rows AFTER tblGrid (correct order: tblPr, tblGrid, tr...)
        table_rows = []
        for row_data in rows:
            tr = ET.SubElement(tbl, f'{self.namespace}:tr')
            table_rows.append((tr, row_data))
        
        # Process rows
        for tr, row_data in table_rows:
            
            # Handle row properties (trPr)
            if isinstance(row_data, dict):
                row_style = row_data.get('style')
                cells = row_data.get('cells', [])
            else:
                row_style = getattr(row_data, 'style', None)
                cells = row_data.get_cells() if hasattr(row_data, 'get_cells') else []
            
            if row_style:
                trPr = ET.SubElement(tr, f'{self.namespace}:trPr')
                if isinstance(row_style, dict):
                    # Height
                    if row_style.get('height'):
                        trHeight = ET.SubElement(trPr, f'{self.namespace}:trHeight')
                        height_data = row_style['height']
                        if isinstance(height_data, dict):
                            for key, value in height_data.items():
                                if key.startswith('{'):
                                    trHeight.set(key, value)
                                else:
                                    trHeight.set(f'{self.namespace}:{key}', value)
                    
                    # cantSplit
                    if row_style.get('cant_split'):
                        cantSplit = ET.SubElement(trPr, f'{self.namespace}:cantSplit')
                    
                    # hidden
                    if row_style.get('hidden'):
                        hidden = ET.SubElement(trPr, f'{self.namespace}:hidden')
            
            # Handle cell data
            for cell_data in cells:
                tc = ET.SubElement(tr, f'{self.namespace}:tc')
                
                # Handle both dict and object inputs for cells
                if isinstance(cell_data, dict):
                    cell_style = cell_data.get('style', {})
                    cell_text = cell_data.get('text', '')
                    cell_children = cell_data.get('children', [])
                    # Check colspan/rowspan directly in cell_data
                    if 'colspan' in cell_data:
                        if not isinstance(cell_style, dict):
                            cell_style = {}
                        cell_style['gridSpan'] = cell_data['colspan']
                    if 'rowspan' in cell_data:
                        if not isinstance(cell_style, dict):
                            cell_style = {}
                        cell_style['vMerge'] = cell_data['rowspan']
                    if 'grid_span' in cell_data:
                        if not isinstance(cell_style, dict):
                            cell_style = {}
                        cell_style['gridSpan'] = cell_data['grid_span']
                else:
                    cell_style = getattr(cell_data, 'style', None)
                    cell_text = cell_data.get_text() if hasattr(cell_data, 'get_text') else ''
                    cell_children = cell_data.children if hasattr(cell_data, 'children') else []
                    # Check colspan/rowspan in object
                    if hasattr(cell_data, 'colspan') and cell_data.colspan:
                        if not isinstance(cell_style, dict):
                            cell_style = {}
                        cell_style['gridSpan'] = cell_data.colspan
                    if hasattr(cell_data, 'rowspan') and cell_data.rowspan:
                        if not isinstance(cell_style, dict):
                            cell_style = {}
                        cell_style['vMerge'] = cell_data.rowspan
                    if hasattr(cell_data, 'grid_span') and cell_data.grid_span:
                        if not isinstance(cell_style, dict):
                            cell_style = {}
                        cell_style['gridSpan'] = cell_data.grid_span
                
                # Add cell properties if available
                if cell_style:
                    tcPr = ET.SubElement(tc, f'{self.namespace}:tcPr')
                    if isinstance(cell_style, dict):
                        self._add_cell_properties(tcPr, cell_style)
                    else:
                        tcStyle = ET.SubElement(tcPr, f'{self.namespace}:tcStyle')
                        tcStyle.set(f'{self.namespace}:val', str(cell_style))
                
                # Add cell content - if children exist, export them recursively
                if cell_children:
                    for child in cell_children:
                        if hasattr(child, 'get_text'):
                            # It's a paragraph
                            para_xml = self._export_paragraph_xml(child)
                            tc.append(para_xml)
                        else:
                            # Fallback to simple paragraph
                            p = ET.SubElement(tc, f'{self.namespace}:p')
                            run = ET.SubElement(p, f'{self.namespace}:r')
                            t = ET.SubElement(run, f'{self.namespace}:t')
                            t.text = str(child)
                elif cell_text:
                    # Fallback: single paragraph with text
                    p = ET.SubElement(tc, f'{self.namespace}:p')
                    run = ET.SubElement(p, f'{self.namespace}:r')
                    t = ET.SubElement(run, f'{self.namespace}:t')
                    t.text = cell_text
                else:
                    # Empty cell - still need a paragraph
                    p = ET.SubElement(tc, f'{self.namespace}:p')
        
        return tbl
    
    def _export_image_xml(self, image: Union[Dict[str, Any], Any]) -> ET.Element:
        """Export image as XML."""
        # Check if we have raw_xml (preserved from parsing)
        if isinstance(image, dict) and 'raw_xml' in image:
            # Parse the raw XML and insert it directly
            try:
                # Parse the raw XML string
                drawing_elem = ET.fromstring(image['raw_xml'])
                
                # Wrap in paragraph
                p = ET.Element(f'{self.namespace}:p')
                
                # Clone the drawing element (preserving its namespace)
                drawing = ET.SubElement(p, drawing_elem.tag)
                
                # Copy all attributes from original drawing element
                for attr_name, attr_value in drawing_elem.attrib.items():
                    drawing.set(attr_name, attr_value)
                
                # Copy all children and fix positioning if needed
                wp_ns = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
                
                for child in drawing_elem:
                    # Create a deep copy of the child
                    import copy
                    child_copy = copy.deepcopy(child)
                    
                    # Check if this is an anchor element and fix positioning for headers/footers
                    if child.tag.endswith('}anchor'):
                        self._fix_anchor_for_header_footer(child_copy, wp_ns)
                    
                    drawing.append(child_copy)
                
                return p
            except Exception as e:
                logger.error(f"Failed to export raw XML image: {e}")
                # Fall through to default export
        
        p = ET.Element(f'{self.namespace}:p')
        
        # Handle both dict and object inputs
        if isinstance(image, dict):
            width = image.get('width', 100)
            height = image.get('height', 100)
            src = image.get('src', '')
            alt = image.get('alt', '')
        else:
            width = getattr(image, 'width', 100)
            height = getattr(image, 'height', 100)
            src = image.get_src() if hasattr(image, 'get_src') else ''
            alt = image.get_alt() if hasattr(image, 'get_alt') else ''
        
        # Ensure width and height are integers
        if not isinstance(width, int):
            width = 100
        if not isinstance(height, int):
            height = 100
        
        # Ensure src and alt are strings
        if not isinstance(src, str):
            src = ''
        if not isinstance(alt, str):
            alt = ''
        
        # Add drawing element
        drawing = ET.SubElement(p, f'{self.namespace}:drawing')
        
        # Add anchor
        anchor = ET.SubElement(drawing, f'{self.namespace}:anchor')
        anchor.set('distT', '0')
        anchor.set('distB', '0')
        anchor.set('distL', '0')
        anchor.set('distR', '0')
        anchor.set('simplePos', '0')
        anchor.set('relativeHeight', '251658240')
        anchor.set('behindDoc', '0')
        anchor.set('locked', '0')
        anchor.set('layoutInCell', '1')
        anchor.set('allowOverlap', '1')
        
        # Add simple position
        simplePos = ET.SubElement(anchor, f'{self.namespace}:simplePos')
        simplePos.set('x', '0')
        simplePos.set('y', '0')
        
        # Add extent
        extent = ET.SubElement(anchor, f'{self.namespace}:extent')
        extent.set('cx', str(width * 9525))  # Convert to EMU
        extent.set('cy', str(height * 9525))
        
        # Add effect extent
        effectExtent = ET.SubElement(anchor, f'{self.namespace}:effectExtent')
        effectExtent.set('l', '0')
        effectExtent.set('t', '0')
        effectExtent.set('r', '0')
        effectExtent.set('b', '0')
        
        # Add wrap
        wrap = ET.SubElement(anchor, f'{self.namespace}:wrapSquare')
        wrap.set('wrapText', 'bothSides')
        
        # Add doc properties
        docPr = ET.SubElement(anchor, f'{self.namespace}:docPr')
        docPr.set('id', '1')
        if isinstance(image, dict):
            filename = image.get('filename', 'image')
        else:
            filename = getattr(image, 'filename', 'image')
        if not isinstance(filename, str):
            filename = 'image'
        docPr.set('name', filename)
        
        # Add graphic
        graphic = ET.SubElement(anchor, f'{self.namespace}:graphic')
        graphic.set('xmlns:a', self.namespaces['a'])
        
        # Add graphic data
        graphicData = ET.SubElement(graphic, f'{self.namespace}:graphicData')
        graphicData.set('uri', 'http://schemas.openxmlformats.org/drawingml/2006/picture')
        
        # Add picture
        pic = ET.SubElement(graphicData, f'{self.namespace}:pic')
        pic.set('xmlns:pic', self.namespaces['pic'])
        
        # Add picture properties
        picPr = ET.SubElement(pic, f'{self.namespace}:picPr')
        
        # Add picture fill
        picFill = ET.SubElement(picPr, f'{self.namespace}:picFill')
        blip = ET.SubElement(picFill, f'{self.namespace}:blip')
        if isinstance(image, dict):
            rel_id = image.get('rel_id', 'rId1')
        else:
            rel_id = getattr(image, 'rel_id', 'rId1')
        if not isinstance(rel_id, str):
            rel_id = 'rId1'
        blip.set('r:embed', rel_id)
        
        return p
    
    def _export_generic_xml(self, element: Union[Dict[str, Any], Any]) -> ET.Element:
        """Export generic element as XML."""
        # Handle both dict and object inputs
        if isinstance(element, dict):
            element_type = element.get('type', 'unknown')
            element_name = f'{self.namespace}:{element_type}'
            
            xml_element = ET.Element(element_name)
            
            # Add attributes
            for key, value in element.items():
                if key != 'type' and value is not None:
                    xml_element.set(key, str(value))
        else:
            # Handle object input
            element_type = getattr(element, 'type', 'unknown')
            element_name = f'{self.namespace}:{element_type}'
            
            xml_element = ET.Element(element_name)
            
            # Add text content if available
            if hasattr(element, 'get_text'):
                text = element.get_text()
                if text:
                    text_elem = ET.SubElement(xml_element, f'{self.namespace}:t')
                    text_elem.text = text
        
        return xml_element
    
    def export_paragraph_xml(self, paragraph: Union[Dict[str, Any], Any]) -> str:
        """
        Export paragraph as XML.
        
        Args:
            paragraph: Paragraph to export (dict or object)
            
        Returns:
            XML string
        """
        element = self._export_paragraph_xml(paragraph)
        return ET.tostring(element, encoding=self.encoding).decode(self.encoding)
    
    def export_table_xml(self, table: Union[Dict[str, Any], Any]) -> str:
        """
        Export table as XML.
        
        Args:
            table: Table to export (dict or object)
            
        Returns:
            XML string
        """
        element = self._export_table_xml(table)
        return ET.tostring(element, encoding=self.encoding).decode(self.encoding)
    
    def export_image_xml(self, image: Union[Dict[str, Any], Any]) -> str:
        """
        Export image as XML.
        
        Args:
            image: Image to export (dict or object)
            
        Returns:
            XML string
        """
        element = self._export_image_xml(image)
        return ET.tostring(element, encoding=self.encoding).decode(self.encoding)
    
    def _add_paragraph_properties(self, pPr: ET.Element, style: Dict[str, Any]) -> None:
        """Add paragraph properties to XML element."""
        # Paragraph style name reference
        # Check both style_name and styleId for compatibility
        style_name = style.get('style_name') or style.get('styleId')
        if style_name and style_name not in ('', None):
            # Check if pStyle already exists (shouldn't happen, but be safe)
            existing_pStyle = pPr.find(f'.//{{{self.namespaces["w"]}}}pStyle')
            if existing_pStyle is not None:
                # Update existing pStyle instead of creating new one
                existing_pStyle.set(f'{self.namespace}:val', str(style_name))
            else:
                pStyle = ET.SubElement(pPr, f'{self.namespace}:pStyle')
                pStyle.set(f'{self.namespace}:val', str(style_name))
        
        # Alignment (justification)
        if style.get('justification'):
            jc = ET.SubElement(pPr, f'{self.namespace}:jc')
            jc.set(f'{self.namespace}:val', style['justification'])
        elif style.get('alignment'):
            jc = ET.SubElement(pPr, f'{self.namespace}:jc')
            jc.set(f'{self.namespace}:val', style['alignment'])
        
        # Spacing
        if style.get('spacing'):
            spacing = ET.SubElement(pPr, f'{self.namespace}:spacing')
            spacing_dict = style['spacing']
            if isinstance(spacing_dict, dict):
                if 'before' in spacing_dict:
                    spacing.set(f'{self.namespace}:before', str(spacing_dict['before']))
                if 'after' in spacing_dict:
                    spacing.set(f'{self.namespace}:after', str(spacing_dict['after']))
                if 'line' in spacing_dict:
                    spacing.set(f'{self.namespace}:line', str(spacing_dict['line']))
        
        # Indentation
        # Check if paragraph has numbering - if yes, always export indent (even if 0)
        has_numbering = 'numbering' in style and style['numbering'] and style['numbering'].get('id')
        
        if style.get('indent') or has_numbering:
            indent_dict = style.get('indent', {})
            
            # If we have numbering and no indent, set empty dict to force export
            if has_numbering and not indent_dict:
                indent_dict = {'left': '0', 'hanging': '0'}
            
            if indent_dict:
                ind = ET.SubElement(pPr, f'{self.namespace}:ind')
                if isinstance(indent_dict, dict):
                    # For numbering paragraphs, always add left and hanging (even if 0)
                    # For non-numbering paragraphs, only add if non-zero
                    if 'left' in indent_dict:
                        left_val = indent_dict['left']
                        if has_numbering or (left_val != '0' and left_val != 0):
                            ind.set(f'{self.namespace}:left', str(left_val))
                    if 'right' in indent_dict and indent_dict['right'] != '0' and indent_dict['right'] != 0:
                        ind.set(f'{self.namespace}:right', str(indent_dict['right']))
                    if 'hanging' in indent_dict:
                        hanging_val = indent_dict['hanging']
                        if has_numbering or (hanging_val != '0' and hanging_val != 0):
                            ind.set(f'{self.namespace}:hanging', str(hanging_val))
                    if 'first_line' in indent_dict and indent_dict['first_line'] != '0' and indent_dict['first_line'] != 0:
                        ind.set(f'{self.namespace}:firstLine', str(indent_dict['first_line']))
        
        # Numbering
        if style.get('numbering'):
            numPr = ET.SubElement(pPr, f'{self.namespace}:numPr')
            num_dict = style['numbering']
            if isinstance(num_dict, dict):
                if 'id' in num_dict:
                    numId = ET.SubElement(numPr, f'{self.namespace}:numId')
                    numId.set(f'{self.namespace}:val', str(num_dict['id']))
                if 'level' in num_dict:
                    ilvl = ET.SubElement(numPr, f'{self.namespace}:ilvl')
                    ilvl.set(f'{self.namespace}:val', str(num_dict['level']))
        
        # Borders
        if style.get('borders'):
            pBdr = ET.SubElement(pPr, f'{self.namespace}:pBdr')
            borders = style['borders']
            if isinstance(borders, dict):
                for border_name in ['top', 'left', 'bottom', 'right']:
                    if border_name in borders:
                        border = ET.SubElement(pBdr, f'{self.namespace}:{border_name}')
                        border_data = borders[border_name]
                        if isinstance(border_data, dict):
                            # Copy all attributes from border_data
                            for key, value in border_data.items():
                                # Handle namespaced attributes
                                if key.startswith('{'):
                                    border.set(key, value)
                                else:
                                    # Try with namespace
                                    try:
                                        border.set(f'{self.namespace}:{key}', value)
                                    except:
                                        pass
        
        # Tab stops
        if style.get('tabs'):
            tabs = ET.SubElement(pPr, f'{self.namespace}:tabs')
            for tab_data in style['tabs']:
                if isinstance(tab_data, dict):
                    tab = ET.SubElement(tabs, f'{self.namespace}:tab')
                    # Copy all attributes
                    for key, value in tab_data.items():
                        if key.startswith('{'):
                            tab.set(key, value)
                        else:
                            try:
                                tab.set(f'{self.namespace}:{key}', value)
                            except:
                                pass
        
        # Shading
        if style.get('shading'):
            shading = ET.SubElement(pPr, f'{self.namespace}:shd')
            shade = style['shading']
            if isinstance(shade, dict):
                # Copy all attributes
                for key, value in shade.items():
                    if key.startswith('{'):
                        shading.set(key, value)
                    else:
                        try:
                            shading.set(f'{self.namespace}:{key}', value)
                        except:
                            pass
        
        # Contextual spacing
        if style.get('contextual_spacing'):
            contextualSpacing = ET.SubElement(pPr, f'{self.namespace}:contextualSpacing')
            contextualSpacing.set(f'{self.namespace}:val', str(style['contextual_spacing']))
    
    def _add_run_properties(self, rPr: ET.Element, style: Dict[str, Any]) -> None:
        """Add run properties to XML element."""
        # Bold
        if style.get('bold'):
            ET.SubElement(rPr, f'{self.namespace}:b')
        
        # Bold complex script
        if style.get('bold_cs'):
            ET.SubElement(rPr, f'{self.namespace}:bCs')
        
        # Italic
        if style.get('italic'):
            ET.SubElement(rPr, f'{self.namespace}:i')
        
        # Italic complex script
        if style.get('italic_cs'):
            ET.SubElement(rPr, f'{self.namespace}:iCs')
        
        # Underline
        if style.get('underline'):
            u = ET.SubElement(rPr, f'{self.namespace}:u')
            u.set(f'{self.namespace}:val', style.get('underline_val', 'single'))
        
        # Strikethrough
        if style.get('strikethrough'):
            ET.SubElement(rPr, f'{self.namespace}:strike')
        
        # Font size (already in half-points in WordML)
        if style.get('font_size'):
            sz = ET.SubElement(rPr, f'{self.namespace}:sz')
            sz.set(f'{self.namespace}:val', str(style['font_size']))
        
        # Font size complex script (already in half-points in WordML)
        if style.get('font_size_cs'):
            szCs = ET.SubElement(rPr, f'{self.namespace}:szCs')
            szCs.set(f'{self.namespace}:val', str(style['font_size_cs']))
        
        # Color
        if style.get('color'):
            color = ET.SubElement(rPr, f'{self.namespace}:color')
            color.set(f'{self.namespace}:val', style['color'])
            if style.get('color_theme'):
                color.set(f'{self.namespace}:themeColor', style['color_theme'])
            if style.get('color_shade'):
                color.set(f'{self.namespace}:shade', style['color_shade'])
        
        # Font family
        if style.get('font_ascii') or style.get('font_hAnsi') or style.get('font_cs') or style.get('font_eastAsia'):
            rFonts = ET.SubElement(rPr, f'{self.namespace}:rFonts')
            if style.get('font_ascii'):
                rFonts.set(f'{self.namespace}:ascii', style['font_ascii'])
            if style.get('font_hAnsi'):
                rFonts.set(f'{self.namespace}:hAnsi', style['font_hAnsi'])
            if style.get('font_cs'):
                rFonts.set(f'{self.namespace}:cs', style['font_cs'])
            if style.get('font_eastAsia'):
                rFonts.set(f'{self.namespace}:eastAsia', style['font_eastAsia'])
        
        # Character spacing
        if style.get('character_spacing'):
            spacing = ET.SubElement(rPr, f'{self.namespace}:spacing')
            spacing.set(f'{self.namespace}:val', str(style['character_spacing']))
        
        # Character scaling
        if style.get('character_scaling'):
            w = ET.SubElement(rPr, f'{self.namespace}:w')
            w.set(f'{self.namespace}:val', str(style['character_scaling']))
        
        # Kerning
        if style.get('kerning'):
            kern = ET.SubElement(rPr, f'{self.namespace}:kern')
            kern.set(f'{self.namespace}:val', str(style['kerning']))
        
        # Language
        if style.get('lang') or style.get('lang_eastAsia') or style.get('lang_bidi'):
            lang = ET.SubElement(rPr, f'{self.namespace}:lang')
            if style.get('lang'):
                lang.set(f'{self.namespace}:val', style['lang'])
            if style.get('lang_eastAsia'):
                lang.set(f'{self.namespace}:eastAsia', style['lang_eastAsia'])
            if style.get('lang_bidi'):
                lang.set(f'{self.namespace}:bidi', style['lang_bidi'])
        
        # Shadow
        if style.get('shading'):
            shd = ET.SubElement(rPr, f'{self.namespace}:shd')
            shading = style['shading']
            if shading.get('fill'):
                shd.set(f'{self.namespace}:fill', shading['fill'])
            if shading.get('color'):
                shd.set(f'{self.namespace}:color', shading['color'])
            if shading.get('themeFill'):
                shd.set(f'{self.namespace}:themeFill', shading['themeFill'])
            if shading.get('themeFillShade'):
                shd.set(f'{self.namespace}:themeFillShade', shading['themeFillShade'])
        
        # Highlighting
        if style.get('highlight'):
            highlight = ET.SubElement(rPr, f'{self.namespace}:highlight')
            highlight.set(f'{self.namespace}:val', style['highlight'])
        
        # Run style reference
        if style.get('run_style'):
            rStyle = ET.SubElement(rPr, f'{self.namespace}:rStyle')
            rStyle.set(f'{self.namespace}:val', style['run_style'])
        
        # Emphasize mark
        if style.get('emphasis_mark'):
            em = ET.SubElement(rPr, f'{self.namespace}:em')
            em.set(f'{self.namespace}:val', style['emphasis_mark'])
        
        # Vertically align
        if style.get('vertical_align'):
            vertAlign = ET.SubElement(rPr, f'{self.namespace}:vertAlign')
            vertAlign.set(f'{self.namespace}:val', style['vertical_align'])
        
        # Position
        if style.get('position'):
            position = ET.SubElement(rPr, f'{self.namespace}:position')
            position.set(f'{self.namespace}:val', str(style['position']))
        
        # Complex script ligatures
        if style.get('ligatures'):
            ligatures = ET.SubElement(rPr, f'{self.namespace}:ligatures')
            ligatures.set(f'{self.namespace}:val', str(style['ligatures']))
        
        # Number form
        if style.get('number_form'):
            numForm = ET.SubElement(rPr, f'{self.namespace}:numForm')
            numForm.set(f'{self.namespace}:val', str(style['number_form']))
        
        # Number spacing
        if style.get('number_spacing'):
            numSpacing = ET.SubElement(rPr, f'{self.namespace}:numSpacing')
            numSpacing.set(f'{self.namespace}:val', str(style['number_spacing']))
        
        # Stylistic sets
        if style.get('stylistic_sets'):
            stylisticSets = ET.SubElement(rPr, f'{self.namespace}:stylisticSets')
            stylisticSets.set(f'{self.namespace}:val', str(style['stylistic_sets']))
        
        # Snap to grid
        if style.get('snap_to_grid'):
            ET.SubElement(rPr, f'{self.namespace}:snapToGrid')
        
        # Suppress auto hyphens
        if style.get('suppress_auto_hyphens'):
            ET.SubElement(rPr, f'{self.namespace}:suppressAutoHyphens')
        
        # Suppress line breaking
        if style.get('suppress_line_breaks'):
            ET.SubElement(rPr, f'{self.namespace}:suppressLineBreaks')
    
    def _add_table_properties(self, tblPr: ET.Element, style: Dict[str, Any]) -> None:
        """Add table properties to XML element."""
        # Table style
        if style.get('table_style'):
            tblStyle = ET.SubElement(tblPr, f'{self.namespace}:tblStyle')
            style_data = style['table_style']
            if isinstance(style_data, dict):
                for key, value in style_data.items():
                    if key.startswith('{'):
                        tblStyle.set(key, value)
                    else:
                        tblStyle.set(f'{self.namespace}:{key}', value)
        
        # Width
        if style.get('width'):
            tblW = ET.SubElement(tblPr, f'{self.namespace}:tblW')
            width_data = style['width']
            if isinstance(width_data, dict):
                for key, value in width_data.items():
                    if key.startswith('{'):
                        tblW.set(key, value)
                    else:
                        tblW.set(f'{self.namespace}:{key}', value)
            else:
                tblW.set(f'{self.namespace}:w', str(width_data))
                tblW.set(f'{self.namespace}:type', 'dxa')
        
        # Alignment
        if style.get('alignment'):
            jc = ET.SubElement(tblPr, f'{self.namespace}:jc')
            jc.set(f'{self.namespace}:val', style['alignment'])
        
        # Indentation
        if style.get('indentation'):
            tblInd = ET.SubElement(tblPr, f'{self.namespace}:tblInd')
            indent_data = style['indentation']
            if isinstance(indent_data, dict):
                for key, value in indent_data.items():
                    if key.startswith('{'):
                        tblInd.set(key, value)
                    else:
                        tblInd.set(f'{self.namespace}:{key}', value)
        
        # Layout
        if style.get('layout'):
            tblLayout = ET.SubElement(tblPr, f'{self.namespace}:tblLayout')
            layout_data = style['layout']
            if isinstance(layout_data, dict):
                for key, value in layout_data.items():
                    if key.startswith('{'):
                        tblLayout.set(key, value)
                    else:
                        tblLayout.set(f'{self.namespace}:{key}', value)
        
        # Cell margins
        if style.get('cell_margins'):
            tblCellMar = ET.SubElement(tblPr, f'{self.namespace}:tblCellMar')
            margins = style['cell_margins']
            if isinstance(margins, dict):
                for margin_name, margin_data in margins.items():
                    if isinstance(margin_data, dict):
                        margin_elem = ET.SubElement(tblCellMar, f'{self.namespace}:{margin_name}')
                        for key, value in margin_data.items():
                            if key.startswith('{'):
                                margin_elem.set(key, value)
                            else:
                                margin_elem.set(f'{self.namespace}:{key}', value)
        
        # Look
        if style.get('look'):
            tblLook = ET.SubElement(tblPr, f'{self.namespace}:tblLook')
            look_data = style['look']
            if isinstance(look_data, dict):
                for key, value in look_data.items():
                    if key.startswith('{'):
                        tblLook.set(key, value)
                    else:
                        tblLook.set(f'{self.namespace}:{key}', value)
    
    def _add_cell_properties(self, tcPr: ET.Element, style: Dict[str, Any]) -> None:
        """Add cell properties to XML element."""
        # Cell width
        if style.get('width'):
            tcW = ET.SubElement(tcPr, f'{self.namespace}:tcW')
            width_data = style['width']
            if isinstance(width_data, dict):
                # Copy all attributes
                for key, value in width_data.items():
                    if key.startswith('{'):
                        tcW.set(key, value)
                    else:
                        try:
                            tcW.set(f'{self.namespace}:{key}', value)
                        except:
                            pass
            else:
                tcW.set(f'{self.namespace}:w', str(width_data))
                tcW.set(f'{self.namespace}:type', 'dxa')
        
        # Vertical alignment
        if style.get('vAlign'):
            vAlign = ET.SubElement(tcPr, f'{self.namespace}:vAlign')
            valign_data = style['vAlign']
            if isinstance(valign_data, dict):
                # Copy all attributes
                for key, value in valign_data.items():
                    if key.startswith('{'):
                        vAlign.set(key, value)
                    else:
                        try:
                            vAlign.set(f'{self.namespace}:{key}', value)
                        except:
                            pass
            elif isinstance(style.get('vertical_align'), str):
                vAlign.set(f'{self.namespace}:val', style['vertical_align'])
        
        # Cell borders
        if style.get('borders'):
            tcBorders = ET.SubElement(tcPr, f'{self.namespace}:tcBorders')
            borders = style['borders']
            if isinstance(borders, dict):
                for border_name in ['top', 'left', 'bottom', 'right']:
                    if border_name in borders:
                        border = ET.SubElement(tcBorders, f'{self.namespace}:{border_name}')
                        border_data = borders[border_name]
                        if isinstance(border_data, dict):
                            # Copy all attributes
                            for key, value in border_data.items():
                                if key.startswith('{'):
                                    border.set(key, value)
                                else:
                                    try:
                                        border.set(f'{self.namespace}:{key}', value)
                                    except:
                                        pass
        
        # Grid span (colspan)
        if style.get('gridSpan') or style.get('grid_span') or style.get('colspan'):
            gridSpan = ET.SubElement(tcPr, f'{self.namespace}:gridSpan')
            colspan_value = style.get('gridSpan') or style.get('grid_span') or style.get('colspan')
            if isinstance(colspan_value, (int, str)):
                gridSpan.set(f'{self.namespace}:val', str(colspan_value))
            elif isinstance(colspan_value, dict):
                # Copy all attributes
                for key, value in colspan_value.items():
                    if key.startswith('{'):
                        gridSpan.set(key, value)
                    else:
                        try:
                            gridSpan.set(f'{self.namespace}:{key}', value)
                        except:
                            pass
        
        # Vertical merge
        if style.get('vMerge') or style.get('v_merge') or style.get('rowspan'):
            vMerge = ET.SubElement(tcPr, f'{self.namespace}:vMerge')
            rowspan_value = style.get('vMerge') or style.get('v_merge') or style.get('rowspan')
            if isinstance(rowspan_value, dict):
                # Copy all attributes
                for key, value in rowspan_value.items():
                    if key.startswith('{'):
                        vMerge.set(key, value)
                    else:
                        try:
                            vMerge.set(f'{self.namespace}:{key}', value)
                        except:
                            pass
            elif isinstance(rowspan_value, (int, str)) and str(rowspan_value) != '1':
                # If rowspan > 1, set val="restart" for first cell
                # and val="continue" for subsequent (this is handled by Word)
                vMerge.set(f'{self.namespace}:val', 'restart')
        
        # Shading
        if style.get('shading'):
            shading = ET.SubElement(tcPr, f'{self.namespace}:shd')
            shade = style['shading']
            if isinstance(shade, dict):
                # Copy all attributes
                for key, value in shade.items():
                    if key.startswith('{'):
                        shading.set(key, value)
                    else:
                        try:
                            shading.set(f'{self.namespace}:{key}', value)
                        except:
                            pass
    
    def _indent_xml(self, elem: ET.Element, level: int = 0) -> None:
        """Add indentation to XML element."""
        indent = '\n' + ' ' * (level * self.indent)
        
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = indent + ' '
            
            for child in elem:
                self._indent_xml(child, level + 1)
                if not child.tail or not child.tail.strip():
                    child.tail = indent + ' '
            
            if not elem.tail or not elem.tail.strip():
                elem.tail = indent
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = indent
    
    def export_to_string(self) -> str:
        """
        Export document to XML string.
        
        Returns:
            XML string representation
        """
        return self.regenerate_wordml(self.document)
    
    def validate_xml(self, xml_content: str) -> bool:
        """
        Validate XML content.
        
        Args:
            xml_content: XML content to validate
            
        Returns:
            True if valid XML, False otherwise
        """
        try:
            ET.fromstring(xml_content)
            return True
        except ET.ParseError:
            return False
    
    def get_export_info(self) -> Dict[str, Any]:
        """Get export information."""
        return {
            'exporter_type': 'XML',
            'namespace': self.namespace,
            'xml_namespace': self.xml_namespace,
            'indent': self.indent,
            'encoding': self.encoding,
            'document_type': type(self.document).__name__ if self.document else None
        }
