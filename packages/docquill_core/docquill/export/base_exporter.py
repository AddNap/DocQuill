"""
Base exporter for DOCX documents.

Provides common functionality for all exporters.
"""

from typing import Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class BaseExporter:
    """
    Base class for all exporters.
    """
    
    def __init__(self, document, output_path: Optional[str] = None, 
                 export_options: Optional[Dict[str, Any]] = None):
        """
        Initialize base exporter.
        
        Args:
            document: Document to export
            output_path: Output path for export file
            export_options: Export options
        """
        self.document = document
        self.output_path = output_path
        self.export_options = export_options or {}
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def get_export_option(self, key: str, default: Any = None) -> Any:
        """
        Get export option value.
        
        Args:
            key: Option key
            default: Default value if key not found
            
        Returns:
            Option value
        """
        return self.export_options.get(key, default)
    
    def set_export_option(self, key: str, value: Any):
        """
        Set export option value.
        
        Args:
            key: Option key
            value: Option value
        """
        self.export_options[key] = value
    
    def update_export_options(self, options: Dict[str, Any]):
        """
        Update export options.
        
        Args:
            options: Options to update
        """
        self.export_options.update(options)
    
    def get_supported_formats(self) -> list:
        """
        Get supported export formats.
        
        Returns:
            List of supported formats
        """
        raise NotImplementedError("Subclasses must implement get_supported_formats")
    
    def get_export_info(self) -> Dict[str, Any]:
        """
        Get export information.
        
        Returns:
            Export information dictionary
        """
        raise NotImplementedError("Subclasses must implement get_export_info")
    
    def export_to_string(self) -> str:
        """
        Export document to string.
        
        Returns:
            Exported content as string
        """
        raise NotImplementedError("Subclasses must implement export_to_string")
    
    def export_to_file(self, file_path: Optional[str] = None) -> bool:
        """
        Export document to file.
        
        Args:
            file_path: Output file path (uses output_path if not provided)
            
        Returns:
            True if successful, False otherwise
        """
        raise NotImplementedError("Subclasses must implement export_to_file")
