"""
JSON exporter for DOCX documents.

Handles JSON export with full model serialization and formatting.
"""

import json
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class JSONExporter:
    """
    Exports document as JSON (full model).
    
    Handles JSON export with full model serialization and formatting.
    """
    
    def __init__(self, document: Any, indent: int = 2, ensure_ascii: bool = False):
        """
        Initialize JSON exporter.
        
        Args:
            document: Document to export
            indent: JSON indentation level
            ensure_ascii: Whether to ensure ASCII encoding
        """
        self.document = document
        self.indent = indent
        self.ensure_ascii = ensure_ascii
        
        logger.debug("JSON exporter initialized")
    
    def export(self, output_path: Union[str, Path]) -> bool:
        """
        Export document to JSON.
        
        Args:
            output_path: Output file path
            
        Returns:
            True if export successful, False otherwise
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Export document model
            document_data = self.export_document_model(self.document)
            
            # Format JSON output
            json_output = self.format_json_output(document_data)
            
            # Write to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(json_output)
            
            logger.info(f"Document exported to JSON: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export document to JSON: {e}")
            return False
    
    def export_document_model(self, document: Any = None) -> Dict[str, Any]:
        """
        Export full document model.
        
        Args:
            document: Document to export (uses self.document if not provided)
            
        Returns:
            Document model as dictionary
        """
        if document is None:
            document = self.document
        
        document_data = {
            'metadata': {
                'export_timestamp': datetime.now().isoformat(),
                'exporter_version': '1.0.0',
                'document_type': 'DOCX'
            },
            'content': self._extract_document_content(document),
            'styles': self._extract_document_styles(document),
            'layout': self._extract_document_layout(document),
            'document': {
                'properties': self._extract_document_properties(document),
                'content': self._extract_document_content(document),
                'styles': self._extract_document_styles(document),
                'layout': self._extract_document_layout(document)
            }
        }
        
        logger.debug("Document model exported")
        return document_data
    
    def export_element(self, element: Any) -> Dict[str, Any]:
        """
        Export individual element.
        
        Args:
            element: Element to export
            
        Returns:
            Element as dictionary
        """
        if hasattr(element, 'to_dict'):
            return element.to_dict()
        elif hasattr(element, '__dict__'):
            return self._serialize_object(element)
        else:
            return {'type': type(element).__name__, 'value': str(element)}
    
    def format_json_output(self, data: Dict[str, Any]) -> str:
        """
        Format JSON output.
        
        Args:
            data: Data to format
            
        Returns:
            Formatted JSON string
        """
        try:
            json_output = json.dumps(
                data,
                indent=self.indent,
                ensure_ascii=self.ensure_ascii,
                default=self._json_serializer
            )
            return json_output
        except Exception as e:
            logger.error(f"Failed to format JSON: {e}")
            return json.dumps({'error': str(e)})
    
    def _extract_document_properties(self, document: Any) -> Dict[str, Any]:
        """Extract document properties."""
        properties = {}
        
        if hasattr(document, 'metadata'):
            properties['metadata'] = self._serialize_object(document.metadata)
        
        if hasattr(document, 'title'):
            properties['title'] = document.title
        
        if hasattr(document, 'author'):
            properties['author'] = document.author
        
        if hasattr(document, 'created'):
            properties['created'] = document.created
        
        if hasattr(document, 'modified'):
            properties['modified'] = document.modified
        
        return properties
    
    def _extract_document_content(self, document: Any) -> Dict[str, Any]:
        """Extract document content."""
        content = {
            'paragraphs': [],
            'tables': [],
            'images': [],
            'other_elements': []
        }
        
        # Extract paragraphs
        if hasattr(document, 'get_paragraphs'):
            paragraphs = document.get_paragraphs()
            for para in paragraphs:
                content['paragraphs'].append(self.export_element(para))
        
        # Extract tables
        if hasattr(document, 'get_tables'):
            tables = document.get_tables()
            for table in tables:
                content['tables'].append(self.export_element(table))
        
        # Extract images
        if hasattr(document, 'get_images'):
            images = document.get_images()
            for image in images:
                content['images'].append(self.export_element(image))
        
        return content
    
    def _extract_document_styles(self, document: Any) -> Dict[str, Any]:
        """Extract document styles."""
        styles = {}
        
        if hasattr(document, 'styles'):
            styles['document_styles'] = self._serialize_object(document.styles)
        
        if hasattr(document, 'themes'):
            styles['themes'] = self._serialize_object(document.themes)
        
        return styles
    
    def _extract_document_layout(self, document: Any) -> Dict[str, Any]:
        """Extract document layout."""
        layout = {}
        
        if hasattr(document, 'pages'):
            layout['pages'] = []
            for page in document.pages:
                layout['pages'].append(self.export_element(page))
        
        if hasattr(document, 'sections'):
            layout['sections'] = []
            for section in document.sections:
                layout['sections'].append(self.export_element(section))
        
        return layout
    
    def _serialize_object(self, obj: Any) -> Dict[str, Any]:
        """Serialize object to dictionary."""
        if obj is None:
            return None
        
        if isinstance(obj, (str, int, float, bool)):
            return obj
        
        if isinstance(obj, (list, tuple)):
            return [self._serialize_object(item) for item in obj]
        
        if isinstance(obj, dict):
            return {key: self._serialize_object(value) for key, value in obj.items()}
        
        if hasattr(obj, '__dict__'):
            result = {}
            for key, value in obj.__dict__.items():
                if not key.startswith('_'):
                    result[key] = self._serialize_object(value)
            return result
        
        return str(obj)
    
    def _json_serializer(self, obj: Any) -> Any:
        """JSON serializer for non-standard types."""
        if hasattr(obj, 'isoformat'):  # datetime objects
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):  # custom objects
            return self._serialize_object(obj)
        else:
            return str(obj)
    
    def export_to_string(self) -> str:
        """
        Export document to JSON string.
        
        Returns:
            JSON string representation
        """
        document_data = self.export_document_model(self.document)
        return self.format_json_output(document_data)
    
    def validate_json(self, json_string: str) -> bool:
        """
        Validate JSON string.
        
        Args:
            json_string: JSON string to validate
            
        Returns:
            True if valid JSON, False otherwise
        """
        try:
            json.loads(json_string)
            return True
        except json.JSONDecodeError:
            return False
    
    def get_export_info(self) -> Dict[str, Any]:
        """Get export information."""
        return {
            'exporter_type': 'JSON',
            'indent': self.indent,
            'ensure_ascii': self.ensure_ascii,
            'document_type': type(self.document).__name__ if self.document else None
        }
