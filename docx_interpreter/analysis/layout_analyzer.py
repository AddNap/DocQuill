"""
Layout analyzer for DOCX documents.

Provides analysis of document layout, reading order, and content structure.
"""

from typing import List, Dict, Any, Tuple, Optional
import logging
from ..models.body import Body
from ..models.paragraph import Paragraph
from ..models.table import Table

logger = logging.getLogger(__name__)


class LayoutAnalyzer:
    """
    Analyzes document layout and structure.
    """
    
    def __init__(self, body: Body):
        """
        Initialize layout analyzer.
        
        Args:
            body: Document body to analyze
        """
        self.body = body
        self.logger = logging.getLogger(__name__)
    
    def analyze_reading_order(self) -> List[Dict[str, Any]]:
        """
        Analyze reading order of document elements.
        
        Returns:
            List of elements in reading order with position information
        """
        reading_order = []
        
        for i, child in enumerate(self.body.children):
            element_info = {
                'index': i,
                'type': type(child).__name__,
                'element': child,
                'position': self._get_element_position(child),
                'reading_priority': self._get_reading_priority(child)
            }
            
            # Add content information
            if hasattr(child, 'get_text'):
                element_info['text_length'] = len(child.get_text())
                element_info['has_text'] = bool(child.get_text().strip())
            
            reading_order.append(element_info)
        
        # Sort by reading priority and position
        reading_order.sort(key=lambda x: (x['reading_priority'], x['position']['y'], x['position']['x']))
        
        return reading_order
    
    def detect_tables(self) -> List[Dict[str, Any]]:
        """
        Detect and analyze tables in the document.
        
        Returns:
            List of table analysis results
        """
        tables = []
        
        for i, child in enumerate(self.body.children):
            if isinstance(child, Table):
                table_info = {
                    'index': i,
                    'table': child,
                    'position': self._get_element_position(child),
                    'dimensions': self._analyze_table_dimensions(child),
                    'content_analysis': self._analyze_table_content(child),
                    'structure_analysis': self._analyze_table_structure(child)
                }
                tables.append(table_info)
        
        return tables
    
    def analyze_content_structure(self) -> Dict[str, Any]:
        """
        Analyze overall content structure of the document.
        
        Returns:
            Dictionary with structure analysis results
        """
        structure = {
            'total_elements': len(self.body.children),
            'paragraph_count': 0,
            'table_count': 0,
            'image_count': 0,
            'textbox_count': 0,
            'element_types': {},
            'content_distribution': {},
            'reading_flow': self.analyze_reading_order()
        }
        
        # Count element types
        for child in self.body.children:
            element_type = type(child).__name__
            structure['element_types'][element_type] = structure['element_types'].get(element_type, 0) + 1
            
            if isinstance(child, Paragraph):
                structure['paragraph_count'] += 1
            elif isinstance(child, Table):
                structure['table_count'] += 1
            elif hasattr(child, 'get_src'):  # Image-like
                structure['image_count'] += 1
            elif hasattr(child, 'get_text') and hasattr(child, 'get_position'):  # TextBox-like
                structure['textbox_count'] += 1
        
        # Analyze content distribution
        structure['content_distribution'] = self._analyze_content_distribution()
        
        return structure
    
    def _get_element_position(self, element) -> Dict[str, float]:
        """
        Get element position information.
        
        Args:
            element: Element to analyze
            
        Returns:
            Position dictionary with x, y coordinates
        """
        position = {'x': 0.0, 'y': 0.0}
        
        # Try to get position from element
        if hasattr(element, 'position'):
            position = element.position
        elif hasattr(element, 'get_position'):
            position = element.get_position()
        
        return position
    
    def _get_reading_priority(self, element) -> int:
        """
        Get reading priority for element.
        
        Args:
            element: Element to analyze
            
        Returns:
            Priority value (lower = higher priority)
        """
        # Define reading priorities
        if isinstance(element, Paragraph):
            return 1  # Highest priority
        elif isinstance(element, Table):
            return 2
        elif hasattr(element, 'get_src'):  # Image
            return 3
        elif hasattr(element, 'get_text') and hasattr(element, 'get_position'):  # TextBox
            return 4
        else:
            return 5  # Lowest priority
    
    def _analyze_table_dimensions(self, table: Table) -> Dict[str, Any]:
        """
        Analyze table dimensions and structure.
        
        Args:
            table: Table to analyze
            
        Returns:
            Dimension analysis results
        """
        dimensions = {
            'row_count': len(table.rows),
            'column_count': 0,
            'total_cells': 0,
            'max_cells_per_row': 0,
            'min_cells_per_row': float('inf'),
            'average_cells_per_row': 0
        }
        
        if table.rows:
            cell_counts = []
            for row in table.rows:
                cell_count = len(row.cells)
                cell_counts.append(cell_count)
                dimensions['total_cells'] += cell_count
                dimensions['max_cells_per_row'] = max(dimensions['max_cells_per_row'], cell_count)
                dimensions['min_cells_per_row'] = min(dimensions['min_cells_per_row'], cell_count)
            
            dimensions['column_count'] = dimensions['max_cells_per_row']
            dimensions['average_cells_per_row'] = sum(cell_counts) / len(cell_counts)
            
            if dimensions['min_cells_per_row'] == float('inf'):
                dimensions['min_cells_per_row'] = 0
        
        return dimensions
    
    def _analyze_table_content(self, table: Table) -> Dict[str, Any]:
        """
        Analyze table content.
        
        Args:
            table: Table to analyze
            
        Returns:
            Content analysis results
        """
        content_analysis = {
            'has_header_row': False,
            'empty_cells': 0,
            'filled_cells': 0,
            'total_text_length': 0,
            'average_text_length_per_cell': 0,
            'cells_with_images': 0,
            'cells_with_tables': 0
        }
        
        for row_idx, row in enumerate(table.rows):
            for cell in row.cells:
                if hasattr(cell, 'get_text'):
                    text = cell.get_text()
                    if text and text.strip():
                        content_analysis['filled_cells'] += 1
                        content_analysis['total_text_length'] += len(text)
                    else:
                        content_analysis['empty_cells'] += 1
                
                # Check for nested content
                if hasattr(cell, 'get_images') and cell.get_images():
                    content_analysis['cells_with_images'] += 1
                if hasattr(cell, 'get_tables') and cell.get_tables():
                    content_analysis['cells_with_tables'] += 1
        
        # Calculate averages
        total_cells = content_analysis['filled_cells'] + content_analysis['empty_cells']
        if total_cells > 0:
            content_analysis['average_text_length_per_cell'] = content_analysis['total_text_length'] / total_cells
        
        # Check for header row (first row)
        if table.rows and len(table.rows) > 0:
            first_row = table.rows[0]
            if hasattr(first_row, 'is_header_row') and first_row.is_header_row:
                content_analysis['has_header_row'] = True
        
        return content_analysis
    
    def _analyze_table_structure(self, table: Table) -> Dict[str, Any]:
        """
        Analyze table structure.
        
        Args:
            table: Table to analyze
            
        Returns:
            Structure analysis results
        """
        structure_analysis = {
            'is_regular': True,
            'has_merged_cells': False,
            'has_nested_tables': False,
            'has_nested_images': False,
            'complexity_score': 0
        }
        
        # Check for merged cells
        for row in table.rows:
            for cell in row.cells:
                if hasattr(cell, 'grid_span') and cell.grid_span > 1:
                    structure_analysis['has_merged_cells'] = True
                if hasattr(cell, 'vertical_merge') and cell.vertical_merge:
                    structure_analysis['has_merged_cells'] = True
        
        # Check for nested content
        for row in table.rows:
            for cell in row.cells:
                if hasattr(cell, 'get_tables') and cell.get_tables():
                    structure_analysis['has_nested_tables'] = True
                if hasattr(cell, 'get_images') and cell.get_images():
                    structure_analysis['has_nested_images'] = True
        
        # Calculate complexity score
        complexity_score = 0
        if structure_analysis['has_merged_cells']:
            complexity_score += 2
        if structure_analysis['has_nested_tables']:
            complexity_score += 3
        if structure_analysis['has_nested_images']:
            complexity_score += 1
        
        structure_analysis['complexity_score'] = complexity_score
        structure_analysis['is_regular'] = complexity_score == 0
        
        return structure_analysis
    
    def _analyze_content_distribution(self) -> Dict[str, Any]:
        """
        Analyze content distribution in the document.
        
        Returns:
            Content distribution analysis
        """
        distribution = {
            'text_density': 0.0,
            'table_density': 0.0,
            'image_density': 0.0,
            'textbox_density': 0.0,
            'content_balance': 'text_heavy'  # text_heavy, table_heavy, image_heavy, balanced
        }
        
        total_elements = len(self.body.children)
        if total_elements == 0:
            return distribution
        
        # Count element types
        text_elements = 0
        table_elements = 0
        image_elements = 0
        textbox_elements = 0
        
        for child in self.body.children:
            if isinstance(child, Paragraph):
                text_elements += 1
            elif isinstance(child, Table):
                table_elements += 1
            elif hasattr(child, 'get_src'):  # Image
                image_elements += 1
            elif hasattr(child, 'get_text') and hasattr(child, 'get_position'):  # TextBox
                textbox_elements += 1
        
        # Calculate densities
        distribution['text_density'] = text_elements / total_elements
        distribution['table_density'] = table_elements / total_elements
        distribution['image_density'] = image_elements / total_elements
        distribution['textbox_density'] = textbox_elements / total_elements
        
        # Determine content balance
        max_density = max(distribution['text_density'], distribution['table_density'], 
                         distribution['image_density'], distribution['textbox_density'])
        
        if max_density == distribution['text_density']:
            distribution['content_balance'] = 'text_heavy'
        elif max_density == distribution['table_density']:
            distribution['content_balance'] = 'table_heavy'
        elif max_density == distribution['image_density']:
            distribution['content_balance'] = 'image_heavy'
        else:
            distribution['content_balance'] = 'balanced'
        
        return distribution
    
    def get_layout_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the document layout analysis.
        
        Returns:
            Layout summary dictionary
        """
        structure = self.analyze_content_structure()
        tables = self.detect_tables()
        
        summary = {
            'document_type': self._determine_document_type(structure, tables),
            'complexity_level': self._calculate_complexity_level(structure, tables),
            'reading_difficulty': self._assess_reading_difficulty(structure, tables),
            'recommendations': self._generate_recommendations(structure, tables),
            'structure': structure,
            'tables': tables
        }
        
        return summary
    
    def _determine_document_type(self, structure: Dict[str, Any], tables: List[Dict[str, Any]]) -> str:
        """
        Determine the type of document based on content analysis.
        
        Args:
            structure: Content structure analysis
            tables: Table analysis results
            
        Returns:
            Document type string
        """
        if structure['table_count'] > structure['paragraph_count']:
            return 'table_heavy'
        elif structure['image_count'] > structure['paragraph_count']:
            return 'image_heavy'
        elif structure['textbox_count'] > 0:
            return 'mixed_layout'
        elif structure['paragraph_count'] > 10:
            return 'text_heavy'
        else:
            return 'simple'
    
    def _calculate_complexity_level(self, structure: Dict[str, Any], tables: List[Dict[str, Any]]) -> str:
        """
        Calculate the complexity level of the document.
        
        Args:
            structure: Content structure analysis
            tables: Table analysis results
            
        Returns:
            Complexity level string
        """
        complexity_score = 0
        
        # Base complexity from element count
        if structure['total_elements'] > 50:
            complexity_score += 3
        elif structure['total_elements'] > 20:
            complexity_score += 2
        elif structure['total_elements'] > 10:
            complexity_score += 1
        
        # Add complexity from tables
        for table_info in tables:
            table_complexity = table_info['structure_analysis']['complexity_score']
            complexity_score += table_complexity
        
        # Determine level
        if complexity_score >= 10:
            return 'high'
        elif complexity_score >= 5:
            return 'medium'
        else:
            return 'low'
    
    def _assess_reading_difficulty(self, structure: Dict[str, Any], tables: List[Dict[str, Any]]) -> str:
        """
        Assess the reading difficulty of the document.
        
        Args:
            structure: Content structure analysis
            tables: Table analysis results
            
        Returns:
            Reading difficulty level
        """
        difficulty_score = 0
        
        # Base difficulty from content balance
        if structure['content_distribution']['content_balance'] == 'table_heavy':
            difficulty_score += 3
        elif structure['content_distribution']['content_balance'] == 'image_heavy':
            difficulty_score += 2
        elif structure['content_distribution']['content_balance'] == 'mixed_layout':
            difficulty_score += 4
        
        # Add difficulty from table complexity
        for table_info in tables:
            if table_info['structure_analysis']['complexity_score'] > 2:
                difficulty_score += 2
            elif table_info['structure_analysis']['complexity_score'] > 0:
                difficulty_score += 1
        
        # Determine difficulty level
        if difficulty_score >= 8:
            return 'high'
        elif difficulty_score >= 4:
            return 'medium'
        else:
            return 'low'
    
    def _generate_recommendations(self, structure: Dict[str, Any], tables: List[Dict[str, Any]]) -> List[str]:
        """
        Generate recommendations for improving document layout.
        
        Args:
            structure: Content structure analysis
            tables: Table analysis results
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # Content balance recommendations
        if structure['content_distribution']['content_balance'] == 'table_heavy':
            recommendations.append("Consider breaking up large tables into smaller sections")
            recommendations.append("Add explanatory text between tables")
        
        if structure['content_distribution']['content_balance'] == 'image_heavy':
            recommendations.append("Add captions or descriptions for images")
            recommendations.append("Consider adding text content to balance the layout")
        
        # Table-specific recommendations
        for table_info in tables:
            if table_info['structure_analysis']['has_merged_cells']:
                recommendations.append("Consider simplifying table structure by reducing merged cells")
            
            if table_info['structure_analysis']['has_nested_tables']:
                recommendations.append("Nested tables can be difficult to read - consider flattening structure")
            
            if table_info['content_analysis']['empty_cells'] > table_info['content_analysis']['filled_cells']:
                recommendations.append("Table has many empty cells - consider restructuring")
        
        # General recommendations
        if structure['total_elements'] > 100:
            recommendations.append("Document is quite long - consider adding section breaks or headings")
        
        if not recommendations:
            recommendations.append("Document layout looks good - no specific recommendations")
        
        return recommendations
