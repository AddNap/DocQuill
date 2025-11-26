"""
Enhanced JSON exporter for DOCX documents.

Exports document content to JSON format with various options including flat mode.
"""

import json
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import logging
from .base_exporter import BaseExporter

logger = logging.getLogger(__name__)


class JSONExporterEnhanced(BaseExporter):
    """
    Exports DOCX documents to JSON format with enhanced options.
    """
    
    def __init__(self, document, output_path: Optional[str] = None, 
                 export_options: Optional[Dict[str, Any]] = None):
        """
        Initialize enhanced JSON exporter.
        
        Args:
            document: Document to export
            output_path: Output path for JSON file
            export_options: Export options
        """
        super().__init__(document, output_path, export_options)
        
        # JSON-specific options
        self.indent = self.get_export_option('indent', 2)
        self.ensure_ascii = self.get_export_option('ensure_ascii', False)
        self.flat_mode = self.get_export_option('flat_mode', False)
        self.include_metadata = self.get_export_option('include_metadata', True)
        self.include_styles = self.get_export_option('include_styles', True)
        self.include_formatting = self.get_export_option('include_formatting', True)
        self.include_position_info = self.get_export_option('include_position_info', False)
        self.export_tables_as_arrays = self.get_export_option('export_tables_as_arrays', True)
        self.export_images_as_base64 = self.get_export_option('export_images_as_base64', False)
        
        # Ensure options are in export_options for validation
        self.export_options.setdefault('indent', self.indent)
        self.export_options.setdefault('ensure_ascii', self.ensure_ascii)
        self.export_options.setdefault('flat_mode', self.flat_mode)
        self.export_options.setdefault('include_metadata', self.include_metadata)
        self.export_options.setdefault('include_styles', self.include_styles)
        self.export_options.setdefault('include_formatting', self.include_formatting)
        self.export_options.setdefault('include_position_info', self.include_position_info)
        self.export_options.setdefault('export_tables_as_arrays', self.export_tables_as_arrays)
        self.export_options.setdefault('export_images_as_base64', self.export_images_as_base64)
    
    def export_to_string(self) -> str:
        """
        Export document to JSON string.
        
        Returns:
            JSON content as string
        """
        try:
            if self.flat_mode:
                data = self._export_flat_mode()
            else:
                data = self._export_hierarchical_mode()
            
            return json.dumps(data, indent=self.indent, ensure_ascii=self.ensure_ascii)
            
        except Exception as e:
            logger.error(f"Failed to export to JSON string: {e}")
            raise
    
    def export_to_file(self, file_path: Optional[str] = None) -> bool:
        """
        Export document to JSON file.
        
        Args:
            file_path: Output file path (uses output_path if not provided)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if file_path is None:
                file_path = self.output_path
            
            if file_path is None:
                raise ValueError("No output path specified")
            
            # Convert to Path if needed
            if isinstance(file_path, str):
                file_path = Path(file_path)
            
            # Create directory if it doesn't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Export to string first
            json_content = self.export_to_string()
            
            # Write to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(json_content)
            
            logger.info(f"JSON exported to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export to JSON file: {e}")
            raise
    
    def _export_flat_mode(self) -> Dict[str, Any]:
        """Export document in flat mode (no hierarchy)."""
        data = {
            'document_type': 'flat',
            'elements': []
        }
        
        # Add metadata if requested
        if self.include_metadata and hasattr(self.document, 'get_metadata'):
            metadata = self.document.get_metadata()
            if metadata:
                data['metadata'] = metadata
        
        # Export body content
        if hasattr(self.document, 'get_body'):
            body = self.document.get_body()
            if body:
                self._export_body_flat(data['elements'], body)
        
        return data
    
    def _export_hierarchical_mode(self) -> Dict[str, Any]:
        """Export document in hierarchical mode."""
        data = {
            'document_type': 'hierarchical',
            'document': {}
        }
        
        # Add metadata if requested
        if self.include_metadata and hasattr(self.document, 'get_metadata'):
            metadata = self.document.get_metadata()
            if metadata:
                data['document']['metadata'] = metadata
        
        # Export body content
        if hasattr(self.document, 'get_body'):
            body = self.document.get_body()
            if body:
                data['document']['body'] = self._export_body_hierarchical(body)
        
        return data
    
    def _export_body_flat(self, elements: List[Dict[str, Any]], body):
        """Export body content in flat mode."""
        for child in body.children:
            element_data = self._export_element_flat(child)
            if element_data:
                elements.append(element_data)
    
    def _export_body_hierarchical(self, body) -> Dict[str, Any]:
        """Export body content in hierarchical mode."""
        body_data = {
            'type': 'body',
            'elements': []
        }
        
        for child in body.children:
            element_data = self._export_element_hierarchical(child)
            if element_data:
                body_data['elements'].append(element_data)
        
        return body_data
    
    def _export_element_flat(self, element) -> Dict[str, Any]:
        """Export element in flat mode."""
        element_data = {
            'type': type(element).__name__,
            'id': getattr(element, 'id', None)
        }
        
        # Add text content
        if hasattr(element, 'get_text'):
            text = element.get_text()
            if text:
                element_data['text'] = text
        
        # Add style information
        if self.include_styles and hasattr(element, 'style'):
            element_data['style'] = element.style
        
        # Add formatting information
        if self.include_formatting and hasattr(element, 'get_formatting'):
            element_data['formatting'] = element.get_formatting()
        
        # Add position information
        if self.include_position_info and hasattr(element, 'get_position'):
            element_data['position'] = element.get_position()
        
        # Handle special element types
        if hasattr(element, 'get_rows'):  # Table
            element_data['table_data'] = self._export_table_flat(element)
        elif hasattr(element, 'get_src'):  # Image
            element_data['image_data'] = self._export_image_flat(element)
        
        return element_data
    
    def _export_element_hierarchical(self, element) -> Dict[str, Any]:
        """Export element in hierarchical mode."""
        element_data = {
            'type': type(element).__name__,
            'id': getattr(element, 'id', None)
        }
        
        # Add text content
        if hasattr(element, 'get_text'):
            text = element.get_text()
            if text:
                element_data['text'] = text
        
        # Add style information
        if self.include_styles and hasattr(element, 'style'):
            element_data['style'] = element.style
        
        # Add formatting information
        if self.include_formatting and hasattr(element, 'get_formatting'):
            element_data['formatting'] = element.get_formatting()
        
        # Add position information
        if self.include_position_info and hasattr(element, 'get_position'):
            element_data['position'] = element.get_position()
        
        # Handle special element types
        if hasattr(element, 'get_rows'):  # Table
            element_data['table'] = self._export_table_hierarchical(element)
        elif hasattr(element, 'get_src'):  # Image
            element_data['image'] = self._export_image_hierarchical(element)
        
        # Add children if any
        if hasattr(element, 'children') and element.children:
            element_data['children'] = []
            for child in element.children:
                child_data = self._export_element_hierarchical(child)
                if child_data:
                    element_data['children'].append(child_data)
        
        return element_data
    
    def _export_table_flat(self, table) -> Dict[str, Any]:
        """Export table in flat mode."""
        table_data = {
            'rows': [],
            'columns': 0,
            'total_cells': 0
        }
        
        if hasattr(table, 'get_rows'):
            rows = table.get_rows()
            table_data['columns'] = len(rows[0].cells) if rows else 0
            
            for row in rows:
                row_data = {
                    'cells': []
                }
                
                for cell in row.cells:
                    cell_data = {
                        'text': self._get_cell_text(cell)
                    }
                    
                    if self.include_formatting:
                        cell_data['formatting'] = self._get_cell_formatting(cell)
                    
                    row_data['cells'].append(cell_data)
                    table_data['total_cells'] += 1
                
                table_data['rows'].append(row_data)
        
        return table_data
    
    def _export_table_hierarchical(self, table) -> Dict[str, Any]:
        """Export table in hierarchical mode."""
        table_data = {
            'type': 'table',
            'rows': []
        }
        
        if hasattr(table, 'get_rows'):
            rows = table.get_rows()
            
            for row in rows:
                row_data = {
                    'type': 'table_row',
                    'cells': []
                }
                
                for cell in row.cells:
                    cell_data = {
                        'type': 'table_cell',
                        'text': self._get_cell_text(cell)
                    }
                    
                    if self.include_formatting:
                        cell_data['formatting'] = self._get_cell_formatting(cell)
                    
                    row_data['cells'].append(cell_data)
                
                table_data['rows'].append(row_data)
        
        return table_data
    
    def _export_image_flat(self, image) -> Dict[str, Any]:
        """Export image in flat mode."""
        image_data = {
            'src': getattr(image, 'src', None),
            'alt': getattr(image, 'alt', None),
            'width': getattr(image, 'width', None),
            'height': getattr(image, 'height', None)
        }
        
        if self.export_images_as_base64 and hasattr(image, 'get_base64'):
            image_data['base64'] = image.get_base64()
        
        return image_data
    
    def _export_image_hierarchical(self, image) -> Dict[str, Any]:
        """Export image in hierarchical mode."""
        image_data = {
            'type': 'image',
            'src': getattr(image, 'src', None),
            'alt': getattr(image, 'alt', None),
            'width': getattr(image, 'width', None),
            'height': getattr(image, 'height', None)
        }
        
        if self.export_images_as_base64 and hasattr(image, 'get_base64'):
            image_data['base64'] = image.get_base64()
        
        return image_data
    
    def _get_cell_text(self, cell) -> str:
        """Get text content from cell."""
        if hasattr(cell, 'get_text'):
            return cell.get_text()
        elif hasattr(cell, 'text'):
            return cell.text
        else:
            return str(cell)
    
    def _get_cell_formatting(self, cell) -> Dict[str, Any]:
        """Get formatting information from cell."""
        formatting = {}
        
        if hasattr(cell, 'style'):
            formatting['style'] = cell.style
        
        if hasattr(cell, 'shading'):
            formatting['shading'] = cell.shading
        
        if hasattr(cell, 'vertical_align'):
            formatting['vertical_align'] = cell.vertical_align
        
        return formatting
    
    def get_supported_formats(self) -> List[str]:
        """Get supported export formats."""
        return ['json', 'jsonl']
    
    def get_export_info(self) -> Dict[str, Any]:
        """Get export information."""
        return {
            'format': 'JSON',
            'indent': self.indent,
            'ensure_ascii': self.ensure_ascii,
            'flat_mode': self.flat_mode,
            'include_metadata': self.include_metadata,
            'include_styles': self.include_styles,
            'include_formatting': self.include_formatting,
            'include_position_info': self.include_position_info,
            'export_tables_as_arrays': self.export_tables_as_arrays,
            'export_images_as_base64': self.export_images_as_base64
        }
