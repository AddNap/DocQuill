"""
Enhanced Style parser for DOCX documents.

Full implementation with styles.xml parsing support.
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)

class StyleParser:
    """
    Enhanced parser for document styles.
    
    Full implementation with styles.xml parsing support.
    """
    
    def __init__(self, package_reader):
        """
        Initialize style parser.
        
        Args:
            package_reader: PackageReader instance for accessing styles.xml
        """
        self.package_reader = package_reader
        self.ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        self.styles = {}
        self.style_cache = {}
        self.doc_defaults = {"paragraph": {}, "run": {}}
        
        logger.debug("Style parser initialized")
    
    def parse_styles(self) -> Dict[str, Any]:
        """
        Parse styles from styles.xml.
        
        Returns:
            Dictionary of parsed styles
        """
        try:
            styles_xml = self.package_reader.get_xml_content('word/styles.xml')
            if not styles_xml:
                logger.warning("No styles.xml found")
                return {}
            
            root = ET.fromstring(styles_xml)
            
            # Parse document defaults first
            self.doc_defaults = self._parse_doc_defaults(root)

            # Parse all styles
            for style_element in root.findall('.//w:style', self.ns):
                style_data = self.parse_style_element(style_element)
                if style_data:
                    self.styles[style_data['styleId']] = style_data
            
            logger.info(f"Parsed {len(self.styles)} styles")
            return self.styles
            
        except Exception as e:
            logger.error(f"Failed to parse styles: {e}")
            return {}
    
    def parse_style_element(self, style_element: ET.Element) -> Optional[Dict[str, Any]]:
        """
        Parse individual style element.
        
        Args:
            style_element: Style XML element
            
        Returns:
            Dictionary of style data
        """
        try:
            style_id = style_element.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}styleId', 
                                       style_element.get('styleId', ''))
            style_type = style_element.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type', 
                                         style_element.get('type', ''))
            
            style_data = {
                'styleId': style_id,
                'type': style_type,
                'name': '',
                'basedOn': '',
                'next': '',
                'properties': {}
            }
            
            # Parse style name
            name_element = style_element.find('.//w:name', self.ns)
            if name_element is not None:
                style_data['name'] = name_element.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', 
                                                    name_element.get('val', ''))
            
            # Parse based on
            based_on_element = style_element.find('.//w:basedOn', self.ns)
            if based_on_element is not None:
                style_data['basedOn'] = based_on_element.get('val', '')
            
            # Parse next style
            next_element = style_element.find('.//w:next', self.ns)
            if next_element is not None:
                style_data['next'] = next_element.get('val', '')
            
            # Parse style properties based on type
            if style_type == 'paragraph':
                style_data['properties'] = self.parse_paragraph_style_properties(style_element)
            elif style_type == 'character':
                style_data['properties'] = self.parse_character_style_properties(style_element)
            elif style_type == 'table':
                style_data['properties'] = self.parse_table_style_properties(style_element)
            
            return style_data
            
        except Exception as e:
            logger.error(f"Failed to parse style element: {e}")
            return None
    
    def parse_paragraph_style_properties(self, style_element: ET.Element) -> Dict[str, Any]:
        """
        Parse paragraph style properties.
        
        Args:
            style_element: Style XML element
            
        Returns:
            Dictionary of paragraph properties
        """
        properties = {}
        
        # Parse paragraph properties
        p_pr = style_element.find('.//w:pPr', self.ns)
        if p_pr is not None:
            properties.update(self._parse_paragraph_properties_element(p_pr))

        # Parse run properties associated with paragraph style (default run formatting)
        r_pr = style_element.find('.//w:rPr', self.ns)
        if r_pr is not None:
            run_props = self._parse_run_properties_element(r_pr)
            if run_props:
                properties["run"] = run_props
        
        return properties
    
    def parse_character_style_properties(self, style_element: ET.Element) -> Dict[str, Any]:
        """
        Parse character style properties.
        
        Args:
            style_element: Style XML element
            
        Returns:
            Dictionary of character properties
        """
        properties = {}
        
        # Parse run properties
        r_pr = style_element.find('.//w:rPr', self.ns)
        if r_pr is not None:
            properties.update(self._parse_run_properties_element(r_pr))
        
        return properties

    def _parse_paragraph_properties_element(self, p_pr: ET.Element) -> Dict[str, Any]:
        properties: Dict[str, Any] = {}

        jc = p_pr.find('.//w:jc', self.ns)
        if jc is not None:
            properties['alignment'] = self._get_attr(jc, 'val') or 'left'

        spacing = p_pr.find('.//w:spacing', self.ns)
        if spacing is not None:
            properties['spacing_before'] = self._get_attr(spacing, 'before') or '0'
            properties['spacing_after'] = self._get_attr(spacing, 'after') or '0'
            properties['line_spacing'] = self._get_attr(spacing, 'line') or '240'
            properties['line_rule'] = self._get_attr(spacing, 'lineRule') or 'auto'

        ind = p_pr.find('.//w:ind', self.ns)
        if ind is not None:
            properties['indent_left'] = self._get_attr(ind, 'left') or '0'
            properties['indent_right'] = self._get_attr(ind, 'right') or '0'
            properties['indent_first_line'] = self._get_attr(ind, 'firstLine') or '0'
            properties['indent_hanging'] = self._get_attr(ind, 'hanging') or '0'

        num_pr = p_pr.find('.//w:numPr', self.ns)
        if num_pr is not None:
            properties['numbering'] = self.parse_numbering_properties(num_pr)

        return properties

    def _parse_run_properties_element(self, r_pr: ET.Element) -> Dict[str, Any]:
        properties: Dict[str, Any] = {}

        font = r_pr.find('.//w:rFonts', self.ns)
        if font is not None:
            ascii_font = (
                self._get_attr(font, 'ascii')
                or self._get_attr(font, 'hAnsi')
                or self._get_attr(font, 'cs')
            )
            if ascii_font:
                properties['font_name'] = ascii_font
            for attr in ('ascii', 'hAnsi', 'cs', 'eastAsia'):
                value = self._get_attr(font, attr)
                if value:
                    properties[f'font_{attr}'] = value

        sz = r_pr.find('.//w:sz', self.ns)
        if sz is not None:
            properties['font_size'] = self._get_attr(sz, 'val') or '22'

        sz_cs = r_pr.find('.//w:szCs', self.ns)
        if sz_cs is not None:
            properties['font_size_cs'] = self._get_attr(sz_cs, 'val') or '22'

        b = r_pr.find('.//w:b', self.ns)
        if b is not None:
            properties['bold'] = True

        i = r_pr.find('.//w:i', self.ns)
        if i is not None:
            properties['italic'] = True

        u = r_pr.find('.//w:u', self.ns)
        if u is not None:
            properties['underline'] = self._get_attr(u, 'val') or 'single'

        color = r_pr.find('.//w:color', self.ns)
        if color is not None:
            properties['color'] = self._get_attr(color, 'val') or '000000'

        highlight = r_pr.find('.//w:highlight', self.ns)
        if highlight is not None:
            properties['highlight'] = self._get_attr(highlight, 'val') or 'yellow'

        lang = r_pr.find('.//w:lang', self.ns)
        if lang is not None:
            properties['language'] = self._get_attr(lang, 'val')
            properties['east_asia_lang'] = self._get_attr(lang, 'eastAsia')

        return properties
    
    def parse_table_style_properties(self, style_element: ET.Element) -> Dict[str, Any]:
        """
        Parse table style properties.
        
        Args:
            style_element: Style XML element
            
        Returns:
            Dictionary of table properties
        """
        properties = {}
        
        # Parse table properties
        tbl_pr = style_element.find('.//w:tblPr', self.ns)
        if tbl_pr is not None:
            # Table style
            tbl_style = tbl_pr.find('.//w:tblStyle', self.ns)
            if tbl_style is not None:
                properties['table_style'] = tbl_style.get('val', '')
                properties['table_style_attrs'] = {k.split('}')[-1]: v for k, v in tbl_style.attrib.items()}
            
            # Table width
            tbl_width = tbl_pr.find('.//w:tblW', self.ns)
            if tbl_width is not None:
                properties['table_width'] = tbl_width.get('w', '0')
                properties['table_width_type'] = tbl_width.get('type', 'auto')
            
            # Table alignment
            jc = tbl_pr.find('.//w:jc', self.ns)
            if jc is not None:
                properties['table_alignment'] = jc.get('val', 'left')

            # Table borders
            tbl_borders = tbl_pr.find('.//w:tblBorders', self.ns)
            if tbl_borders is not None:
                borders = {}
                for border in tbl_borders:
                    border_tag = border.tag.split('}')[-1]
                    borders[border_tag] = {k.split('}')[-1]: v for k, v in border.attrib.items()}
                if borders:
                    properties['borders'] = borders

            # Table shading
            tbl_shading = tbl_pr.find('.//w:shd', self.ns)
            if tbl_shading is not None:
                properties['shading'] = {k.split('}')[-1]: v for k, v in tbl_shading.attrib.items()}

            # Table cell spacing
            tbl_spacing = tbl_pr.find('.//w:tblCellSpacing', self.ns)
            if tbl_spacing is not None:
                properties['cell_spacing'] = {k.split('}')[-1]: v for k, v in tbl_spacing.attrib.items()}

            # Table cell margins
            tbl_cell_mar = tbl_pr.find('.//w:tblCellMar', self.ns)
            if tbl_cell_mar is not None:
                cell_margins = {}
                for margin in tbl_cell_mar:
                    margin_tag = margin.tag.split('}')[-1]
                    cell_margins[margin_tag] = {k.split('}')[-1]: v for k, v in margin.attrib.items()}
                if cell_margins:
                    properties['cell_margins'] = cell_margins
 
        return properties
    
    def _parse_doc_defaults(self, root: ET.Element) -> Dict[str, Dict[str, Any]]:
        defaults = {"paragraph": {}, "run": {}}

        doc_defaults = root.find('.//w:docDefaults', self.ns)
        if doc_defaults is None:
            return defaults

        p_pr_default = doc_defaults.find('.//w:pPrDefault/w:pPr', self.ns)
        if p_pr_default is not None:
            defaults["paragraph"] = self._parse_paragraph_properties_element(p_pr_default)

        r_pr_default = doc_defaults.find('.//w:rPrDefault/w:rPr', self.ns)
        if r_pr_default is not None:
            defaults["run"] = self._parse_run_properties_element(r_pr_default)

        return defaults

    def _get_attr(self, element: Optional[ET.Element], local: str) -> Optional[str]:
        if element is None:
            return None
        namespaced = element.get(f"{{{self.ns['w']}}}{local}")
        if namespaced not in (None, ""):
            return namespaced
        value = element.get(local)
        if value not in (None, ""):
            return value
        return None

    def parse_numbering_properties(self, num_pr: ET.Element) -> Dict[str, Any]:
        """
        Parse numbering properties.
        
        Args:
            num_pr: Numbering properties XML element
            
        Returns:
            Dictionary of numbering properties
        """
        properties = {}
        
        # Numbering ID
        num_id = num_pr.find('.//w:numId', self.ns)
        if num_id is not None:
            properties['num_id'] = num_id.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', 
                                            num_id.get('val', '0'))
        
        # Numbering level
        level = num_pr.find('.//w:ilvl', self.ns)
        if level is not None:
            properties['level'] = level.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', 
                                          level.get('val', '0'))
        
        return properties
    
    def get_style(self, style_id: str) -> Optional[Dict[str, Any]]:
        """
        Get style by ID.
        
        Args:
            style_id: Style identifier
            
        Returns:
            Style data or None if not found
        """
        return self.styles.get(style_id)

    def get_doc_defaults(self) -> Dict[str, Dict[str, Any]]:
        """Return parsed document defaults for paragraph and run properties."""
        return self.doc_defaults
    
    def get_style_by_name(self, style_name: str) -> Optional[Dict[str, Any]]:
        """
        Get style by name.
        
        Args:
            style_name: Style name
            
        Returns:
            Style data or None if not found
        """
        for style in self.styles.values():
            if style.get('name') == style_name:
                return style
        return None
    
    def get_styles_by_type(self, style_type: str) -> List[Dict[str, Any]]:
        """
        Get styles by type.
        
        Args:
            style_type: Style type (paragraph, character, table)
            
        Returns:
            List of styles of specified type
        """
        return [style for style in self.styles.values() if style.get('type') == style_type]
    
    def resolve_style_inheritance(self, style_id: str) -> Dict[str, Any]:
        """
        Resolve style inheritance chain.
        
        Args:
            style_id: Style identifier
            
        Returns:
            Resolved style with inherited properties
        """
        if style_id not in self.style_cache:
            style = self.get_style(style_id)
            if not style:
                return {}
            
            resolved_style = style.copy()
            
            # Resolve basedOn inheritance
            if style.get('basedOn'):
                base_style = self.resolve_style_inheritance(style['basedOn'])
                # Merge properties (current style overrides base style)
                resolved_style['properties'] = {**base_style.get('properties', {}), **style.get('properties', {})}
            
            self.style_cache[style_id] = resolved_style
        
        return self.style_cache[style_id]
