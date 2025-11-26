"""
Drawing parser for DOCX documents.

Implements DrawingML parsing functionality including shape parsing,
image parsing, chart parsing, connector parsing, and group shape parsing.
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Any, Tuple
import logging

logger = logging.getLogger(__name__)

class DrawingParser:
    """
    Parser for drawings and graphics.
    
    Provides functionality for:
    - Drawing element parsing
    - Shape parsing and properties
    - Image parsing and relationships
    - Chart parsing
    - Connector parsing
    - Group shape parsing
    """
    
    def __init__(self, package_reader, xml_mapper):
        """
        Initialize drawing parser.
        
        Args:
            package_reader: Package reader instance
            xml_mapper: XML mapper instance
        """
        self.package_reader = package_reader
        self.xml_mapper = xml_mapper
        self.ns = {
            'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
            'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
            'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
            'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture',
            'c': 'http://schemas.openxmlformats.org/drawingml/2006/chart',
            'wps': 'http://schemas.microsoft.com/office/word/2010/wordprocessingShape',
            'v': 'urn:schemas-microsoft-com:vml'
        }
    
    def parse_drawing(self, drawing_element) -> Dict[str, Any]:
        """
        Parse drawing element.
        
        Args:
            drawing_element: XML element containing drawing
            
        Returns:
            Dictionary with drawing data
        """
        try:
            drawing_data = {
                'type': 'drawing',
                'shapes': [],
                'images': [],
                'charts': [],
                'connectors': [],
                'groups': []
            }
            
            # Parse inline drawings
            inline_elements = drawing_element.findall('.//wp:inline', self.ns)
            for inline_element in inline_elements:
                inline_data = self._parse_inline_drawing(inline_element)
                if inline_data:
                    drawing_data['shapes'].append(inline_data)
            
            # Parse anchor drawings
            anchor_elements = drawing_element.findall('.//wp:anchor', self.ns)
            for anchor_element in anchor_elements:
                anchor_data = self._parse_anchor_drawing(anchor_element)
                if anchor_data:
                    drawing_data['shapes'].append(anchor_data)
            
            # Parse VML shapes (legacy)
            vml_elements = drawing_element.findall('.//v:shape', self.ns)
            for vml_element in vml_elements:
                vml_data = self._parse_vml_shape(vml_element)
                if vml_data:
                    drawing_data['shapes'].append(vml_data)
            
            return drawing_data
            
        except Exception as e:
            logger.error(f"Failed to parse drawing: {e}")
            return {'type': 'drawing', 'error': str(e)}
    
    def parse_shape(self, shape_element) -> Optional[Dict[str, Any]]:
        """
        Parse individual shape.
        
        Args:
            shape_element: XML element containing shape
            
        Returns:
            Dictionary with shape data or None if parsing failed
        """
        try:
            shape_data = {
                'type': 'shape',
                'shape_type': 'unknown',
                'properties': {},
                'text_content': '',
                'position': {},
                'size': {}
            }
            
            # Get shape type
            shape_type = self._get_shape_type(shape_element)
            shape_data['shape_type'] = shape_type
            
            # Parse shape properties
            properties = self._parse_shape_properties(shape_element)
            shape_data['properties'] = properties
            
            # Parse text content
            text_content = self._extract_shape_text(shape_element)
            shape_data['text_content'] = text_content
            
            # Parse position and size
            position = self._parse_shape_position(shape_element)
            shape_data['position'] = position
            
            size = self._parse_shape_size(shape_element)
            shape_data['size'] = size
            
            return shape_data
            
        except Exception as e:
            logger.error(f"Failed to parse shape: {e}")
            return None
    
    def parse_image(self, image_element) -> Optional[Dict[str, Any]]:
        """
        Parse image element.
        
        Args:
            image_element: XML element containing image
            
        Returns:
            Dictionary with image data or None if parsing failed
        """
        try:
            image_data = {
                'type': 'image',
                'relationship_id': '',
                'filename': '',
                'width': 0,
                'height': 0,
                'position': {},
                'properties': {}
            }
            
            # Get relationship ID
            blip_element = image_element.find('.//a:blip', self.ns)
            if blip_element is not None:
                rel_id = blip_element.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                if not rel_id:
                    rel_id = blip_element.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}link')
                image_data['relationship_id'] = rel_id or ''
            
            # Get image dimensions
            ext_elements = image_element.findall('.//a:ext', self.ns)
            if ext_elements:
                ext_element = ext_elements[0]
                width = ext_element.get('cx', '0')
                height = ext_element.get('cy', '0')
                image_data['width'] = int(width) if width.isdigit() else 0
                image_data['height'] = int(height) if height.isdigit() else 0
            
            # Get filename from relationship
            if image_data['relationship_id']:
                relationship = self.package_reader.get_relationship(image_data['relationship_id'])
                if relationship:
                    image_data['filename'] = relationship.get('target', '')
            
            return image_data
            
        except Exception as e:
            logger.error(f"Failed to parse image: {e}")
            return None
    
    def _parse_inline_drawing(self, inline_element) -> Optional[Dict[str, Any]]:
        """Parse inline drawing element."""
        try:
            inline_data = {
                'type': 'inline',
                'position': 'inline',
                'shapes': []
            }
            
            # Parse shapes within inline
            shape_elements = inline_element.findall('.//a:sp', self.ns)
            for shape_element in shape_elements:
                shape_data = self.parse_shape(shape_element)
                if shape_data:
                    inline_data['shapes'].append(shape_data)
            
            # Parse images within inline
            pic_elements = inline_element.findall('.//pic:pic', self.ns)
            for pic_element in pic_elements:
                image_data = self.parse_image(pic_element)
                if image_data:
                    inline_data['shapes'].append(image_data)
            
            return inline_data
            
        except Exception as e:
            logger.error(f"Failed to parse inline drawing: {e}")
            return None
    
    def _parse_anchor_drawing(self, anchor_element) -> Optional[Dict[str, Any]]:
        """Parse anchor drawing element."""
        try:
            anchor_data = {
                'type': 'anchor',
                'position': 'absolute',
                'shapes': [],
                'anchor_properties': {}
            }
            
            # Parse anchor properties
            anchor_props = self._parse_anchor_properties(anchor_element)
            anchor_data['anchor_properties'] = anchor_props
            
            # Parse shapes within anchor
            shape_elements = anchor_element.findall('.//a:sp', self.ns)
            for shape_element in shape_elements:
                shape_data = self.parse_shape(shape_element)
                if shape_data:
                    anchor_data['shapes'].append(shape_data)
            
            # Parse images within anchor
            pic_elements = anchor_element.findall('.//pic:pic', self.ns)
            for pic_element in pic_elements:
                image_data = self.parse_image(pic_element)
                if image_data:
                    anchor_data['shapes'].append(image_data)
            
            return anchor_data
            
        except Exception as e:
            logger.error(f"Failed to parse anchor drawing: {e}")
            return None
    
    def _parse_vml_shape(self, vml_element) -> Optional[Dict[str, Any]]:
        """Parse VML shape element (legacy)."""
        try:
            vml_data = {
                'type': 'vml_shape',
                'shape_type': 'vml',
                'properties': {},
                'text_content': '',
                'position': {},
                'size': {}
            }
            
            # Get VML properties
            style = vml_element.get('style', '')
            vml_data['properties']['style'] = style
            
            # Parse VML text content
            text_elements = vml_element.findall('.//v:textpath', self.ns)
            text_content = []
            for text_element in text_elements:
                if text_element.text:
                    text_content.append(text_element.text)
            vml_data['text_content'] = ' '.join(text_content)
            
            return vml_data
            
        except Exception as e:
            logger.error(f"Failed to parse VML shape: {e}")
            return None
    
    def _get_shape_type(self, shape_element) -> str:
        """Get shape type from element."""
        # Check for predefined shape
        prst_element = shape_element.find('.//a:prstGeom', self.ns)
        if prst_element is not None:
            return prst_element.get('prst', 'unknown')
        
        # Check for custom geometry
        cust_element = shape_element.find('.//a:custGeom', self.ns)
        if cust_element is not None:
            return 'custom'
        
        # Check for text box
        txbx_element = shape_element.find('.//a:txbx', self.ns)
        if txbx_element is not None:
            return 'textbox'
        
        return 'unknown'
    
    def _parse_shape_properties(self, shape_element) -> Dict[str, Any]:
        """Parse shape properties."""
        properties = {}
        
        # Get fill properties
        fill_element = shape_element.find('.//a:fill', self.ns)
        if fill_element is not None:
            properties['fill'] = self._parse_fill_properties(fill_element)
        
        # Get line properties
        ln_element = shape_element.find('.//a:ln', self.ns)
        if ln_element is not None:
            properties['line'] = self._parse_line_properties(ln_element)
        
        # Get text properties
        tx_body_element = shape_element.find('.//a:txBody', self.ns)
        if tx_body_element is not None:
            properties['text'] = self._parse_text_properties(tx_body_element)
        
        return properties
    
    def _parse_fill_properties(self, fill_element) -> Dict[str, Any]:
        """Parse fill properties."""
        fill_props = {}
        
        # Check for solid fill
        solid_fill = fill_element.find('.//a:solidFill', self.ns)
        if solid_fill is not None:
            fill_props['type'] = 'solid'
            color_element = solid_fill.find('.//a:srgbClr', self.ns)
            if color_element is not None:
                fill_props['color'] = color_element.get('val', '')
        
        # Check for gradient fill
        grad_fill = fill_element.find('.//a:gradFill', self.ns)
        if grad_fill is not None:
            fill_props['type'] = 'gradient'
        
        return fill_props
    
    def _parse_line_properties(self, ln_element) -> Dict[str, Any]:
        """Parse line properties."""
        line_props = {}
        
        # Get line width
        width = ln_element.get('w', '0')
        line_props['width'] = int(width) if width.isdigit() else 0
        
        # Get line color
        solid_fill = ln_element.find('.//a:solidFill', self.ns)
        if solid_fill is not None:
            color_element = solid_fill.find('.//a:srgbClr', self.ns)
            if color_element is not None:
                line_props['color'] = color_element.get('val', '')
        
        return line_props
    
    def _parse_text_properties(self, tx_body_element) -> Dict[str, Any]:
        """Parse text properties."""
        text_props = {}
        
        # Get text content
        text_content = self._extract_shape_text(tx_body_element)
        text_props['content'] = text_content
        
        return text_props
    
    def _extract_shape_text(self, element) -> str:
        """Extract text content from shape element."""
        try:
            text_parts = []
            
            # Find all text elements
            text_elements = element.findall('.//a:t', self.ns)
            for text_element in text_elements:
                if text_element.text:
                    text_parts.append(text_element.text)
            
            return ''.join(text_parts)
            
        except Exception as e:
            logger.error(f"Failed to extract shape text: {e}")
            return ''
    
    def _parse_shape_position(self, shape_element) -> Dict[str, Any]:
        """Parse shape position."""
        position = {}
        
        # Get position from parent anchor or inline
        parent = shape_element.getparent()
        if parent is not None:
            if parent.tag.endswith('}anchor'):
                # Parse anchor position
                pos_h = parent.find('.//wp:posH', self.ns)
                pos_v = parent.find('.//wp:posV', self.ns)
                
                if pos_h is not None:
                    position['horizontal'] = pos_h.get('relativeFrom', '')
                if pos_v is not None:
                    position['vertical'] = pos_v.get('relativeFrom', '')
        
        return position
    
    def _parse_shape_size(self, shape_element) -> Dict[str, Any]:
        """Parse shape size."""
        size = {}
        
        # Get size from parent anchor or inline
        parent = shape_element.getparent()
        if parent is not None:
            if parent.tag.endswith('}anchor'):
                # Parse anchor size
                ext_element = parent.find('.//wp:extent', self.ns)
                if ext_element is not None:
                    size['width'] = ext_element.get('cx', '0')
                    size['height'] = ext_element.get('cy', '0')
        
        return size
    
    def _parse_anchor_properties(self, anchor_element) -> Dict[str, Any]:
        """Parse anchor properties."""
        anchor_props = {}
        
        # Get positioning
        pos_h = anchor_element.find('.//wp:posH', self.ns)
        if pos_h is not None:
            anchor_props['horizontal_position'] = pos_h.get('relativeFrom', '')
        
        pos_v = anchor_element.find('.//wp:posV', self.ns)
        if pos_v is not None:
            anchor_props['vertical_position'] = pos_v.get('relativeFrom', '')
        
        # Get size
        extent = anchor_element.find('.//wp:extent', self.ns)
        if extent is not None:
            anchor_props['width'] = extent.get('cx', '0')
            anchor_props['height'] = extent.get('cy', '0')
        
        return anchor_props
