"""
CSV exporter for DOCX documents.

Exports document content to CSV format, focusing on tabular data.
"""

import csv
import io
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import logging
from .base_exporter import BaseExporter

logger = logging.getLogger(__name__)


class CSVExporter(BaseExporter):
    """
    Exports DOCX documents to CSV format.
    """
    
    def __init__(self, document, output_path: Optional[str] = None, 
                 export_options: Optional[Dict[str, Any]] = None):
        """
        Initialize CSV exporter.
        
        Args:
            document: Document to export
            output_path: Output path for CSV file
            export_options: Export options
        """
        super().__init__(document, output_path, export_options)
        
        # CSV-specific options
        self.delimiter = self.get_export_option('delimiter', ',')
        self.quotechar = self.get_export_option('quotechar', '"')
        self.quoting = self.get_export_option('quoting', csv.QUOTE_MINIMAL)
        self.include_headers = self.get_export_option('include_headers', True)
        self.export_tables_only = self.get_export_option('export_tables_only', False)
        self.export_paragraphs_as_rows = self.get_export_option('export_paragraphs_as_rows', True)
        self.include_metadata = self.get_export_option('include_metadata', False)
        
        # Ensure options are in export_options for validation
        self.export_options.setdefault('delimiter', self.delimiter)
        self.export_options.setdefault('quotechar', self.quotechar)
        self.export_options.setdefault('quoting', self.quoting)
        self.export_options.setdefault('include_headers', self.include_headers)
        self.export_options.setdefault('export_tables_only', self.export_tables_only)
        self.export_options.setdefault('export_paragraphs_as_rows', self.export_paragraphs_as_rows)
        self.export_options.setdefault('include_metadata', self.include_metadata)
    
    def export_to_string(self) -> str:
        """
        Export document to CSV string.
        
        Returns:
            CSV content as string
        """
        try:
            output = io.StringIO()
            writer = csv.writer(output, delimiter=self.delimiter, quotechar=self.quotechar, 
                              quoting=self.quoting)
            
            # Export metadata if requested
            if self.include_metadata:
                self._export_metadata(writer)
            
            # Export content
            if self.export_tables_only:
                self._export_tables_only(writer)
            else:
                self._export_full_content(writer)
            
            return output.getvalue()
            
        except Exception as e:
            logger.error(f"Failed to export to CSV string: {e}")
            raise
    
    def export_to_file(self, file_path: Optional[str] = None) -> bool:
        """
        Export document to CSV file.
        
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
            csv_content = self.export_to_string()
            
            # Write to file
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                f.write(csv_content)
            
            logger.info(f"CSV exported to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export to CSV file: {e}")
            raise
    
    def _export_metadata(self, writer: csv.writer):
        """Export document metadata."""
        if hasattr(self.document, 'get_metadata'):
            metadata = self.document.get_metadata()
            if metadata:
                writer.writerow(['Metadata'])
                for key, value in metadata.items():
                    writer.writerow([key, str(value)])
                writer.writerow([])  # Empty row
    
    def _export_tables_only(self, writer: csv.writer):
        """Export only tables from the document."""
        if hasattr(self.document, 'get_tables'):
            tables = self.document.get_tables()
            
            for i, table in enumerate(tables):
                # Add table header
                writer.writerow([f'Table {i + 1}'])
                
                # Export table content
                self._export_table(writer, table)
                
                # Add empty row between tables
                if i < len(tables) - 1:
                    writer.writerow([])
    
    def _export_full_content(self, writer: csv.writer):
        """Export full document content."""
        if hasattr(self.document, 'get_body'):
            body = self.document.get_body()
            if body:
                self._export_body(writer, body)
    
    def _export_body(self, writer: csv.writer, body):
        """Export body content."""
        for child in body.children:
            if hasattr(child, 'get_rows'):  # Table
                self._export_table(writer, child)
            elif self.export_paragraphs_as_rows and hasattr(child, 'get_text'):  # Paragraph
                text = child.get_text()
                if text.strip():
                    writer.writerow(['Paragraph', text])
            elif hasattr(child, 'get_text'):  # Other text elements
                text = child.get_text()
                if text.strip():
                    writer.writerow([type(child).__name__, text])
    
    def _export_table(self, writer: csv.writer, table):
        """Export table to CSV."""
        if not hasattr(table, 'get_rows'):
            return
        
        rows = table.get_rows()
        if not rows:
            return
        
        # Export header row if it exists
        if self.include_headers and rows:
            first_row = rows[0]
            if hasattr(first_row, 'is_header_row') and first_row.is_header_row:
                header_cells = []
                for cell in first_row.cells:
                    header_cells.append(self._get_cell_text(cell))
                writer.writerow(header_cells)
        
        # Export data rows
        for row in rows:
            if hasattr(row, 'is_header_row') and row.is_header_row:
                continue  # Skip header row if already exported
            
            row_cells = []
            for cell in row.cells:
                row_cells.append(self._get_cell_text(cell))
            writer.writerow(row_cells)
    
    def _get_cell_text(self, cell) -> str:
        """Get text content from cell."""
        if hasattr(cell, 'get_text'):
            return cell.get_text()
        elif hasattr(cell, 'text'):
            return cell.text
        else:
            return str(cell)
    
    def get_supported_formats(self) -> List[str]:
        """Get supported export formats."""
        return ['csv', 'tsv']
    
    def get_export_info(self) -> Dict[str, Any]:
        """Get export information."""
        return {
            'format': 'CSV',
            'delimiter': self.delimiter,
            'quotechar': self.quotechar,
            'quoting': self.quoting,
            'include_headers': self.include_headers,
            'export_tables_only': self.export_tables_only,
            'export_paragraphs_as_rows': self.export_paragraphs_as_rows,
            'include_metadata': self.include_metadata
        }
