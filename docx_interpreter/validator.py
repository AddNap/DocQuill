"""
Document validator for DOCX documents.

Comprehensive validation and diagnostics for document structure,
references, styles, and consistency.
"""

from typing import List, Dict, Any, Optional, Union
import logging
import json
from enum import Enum

logger = logging.getLogger(__name__)

class ValidationLevel(Enum):
    """Validation levels."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

class ValidationIssue:
    """Represents a validation issue."""
    
    def __init__(self, level: ValidationLevel, message: str, 
                 element_id: Optional[str] = None, 
                 element_type: Optional[str] = None,
                 details: Optional[Dict[str, Any]] = None):
        self.level = level
        self.message = message
        self.element_id = element_id
        self.element_type = element_type
        self.details = details or {}
        self.timestamp = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'level': self.level.value,
            'message': self.message,
            'element_id': self.element_id,
            'element_type': self.element_type,
            'details': self.details,
            'timestamp': self.timestamp
        }
    
    def __str__(self) -> str:
        return f"[{self.level.value.upper()}] {self.message}"

class DocumentValidator:
    """
    Comprehensive document validator.
    
    Validates document structure, references, styles, and consistency.
    """
    
    def __init__(self, document=None):
        """
        Initialize validator.
        
        Args:
            document: Document instance to validate
        """
        self.document = document
        self.issues: List[ValidationIssue] = []
        
        logger.debug("Document validator initialized")
    
    def validate(self, document=None) -> List[ValidationIssue]:
        """
        Validate document and return issues.
        
        Args:
            document: Document instance to validate (optional)
            
        Returns:
            List of validation issues
        """
        if document:
            self.document = document
        
        if not self.document:
            raise ValueError("No document provided for validation")
        
        self.issues.clear()
        
        # Run all validation checks
        self._validate_structure()
        self._validate_references()
        self._validate_styles()
        self._validate_sections()
        self._validate_consistency()
        
        logger.info(f"Validation completed: {len(self.issues)} issues found")
        return self.issues
    
    def _validate_structure(self):
        """Validate document structure."""
        logger.debug("Validating document structure...")
        
        # Check if body exists
        if not self.document._body:
            self.issues.append(ValidationIssue(
                ValidationLevel.ERROR,
                "Document body is missing",
                element_type="body"
            ))
            return
        
        # Validate table structure
        tables = self.document.get_tables()
        for i, table in enumerate(tables):
            if not hasattr(table, 'rows') or not table.rows:
                self.issues.append(ValidationIssue(
                    ValidationLevel.WARNING,
                    f"Table {i} has no rows",
                    element_id=getattr(table, 'id', None),
                    element_type="table"
                ))
                continue
            
            # Validate table rows
            for j, row in enumerate(table.rows):
                if not hasattr(row, 'cells') or not row.cells:
                    self.issues.append(ValidationIssue(
                        ValidationLevel.WARNING,
                        f"Table {i}, row {j} has no cells",
                        element_id=getattr(row, 'id', None),
                        element_type="table_row"
                    ))
                    continue
                
                # Validate table cells
                for k, cell in enumerate(row.cells):
                    if not hasattr(cell, 'content'):
                        self.issues.append(ValidationIssue(
                            ValidationLevel.WARNING,
                            f"Table {i}, row {j}, cell {k} has no content attribute",
                            element_id=getattr(cell, 'id', None),
                            element_type="table_cell"
                        ))
        
        # Validate paragraph structure
        paragraphs = self.document.get_paragraphs()
        for i, paragraph in enumerate(paragraphs):
            if not hasattr(paragraph, 'runs'):
                self.issues.append(ValidationIssue(
                    ValidationLevel.WARNING,
                    f"Paragraph {i} has no runs attribute",
                    element_id=getattr(paragraph, 'id', None),
                    element_type="paragraph"
                ))
    
    def _validate_references(self):
        """Validate document references."""
        logger.debug("Validating document references...")
        
        # Check relationship references
        if hasattr(self.document, '_relationships'):
            relationships = self.document._relationships
            if relationships and isinstance(relationships, dict):
                for rel_id, rel_data in relationships.items():
                    if not isinstance(rel_data, dict):
                        self.issues.append(ValidationIssue(
                            ValidationLevel.ERROR,
                            f"Relationship {rel_id} has invalid format",
                            element_id=rel_id,
                            element_type="relationship"
                        ))
        
        # Check style references
        if hasattr(self.document, '_styles'):
            styles = self.document._styles
            for style_id, style_data in styles.items():
                if not isinstance(style_data, dict):
                    self.issues.append(ValidationIssue(
                        ValidationLevel.ERROR,
                        f"Style {style_id} has invalid format",
                        element_id=style_id,
                        element_type="style"
                    ))
                    continue
                
                # Check basedOn references
                based_on = style_data.get('basedOn')
                if based_on and based_on not in styles:
                    self.issues.append(ValidationIssue(
                        ValidationLevel.WARNING,
                        f"Style {style_id} references non-existent base style: {based_on}",
                        element_id=style_id,
                        element_type="style"
                    ))
        
        # Check numbering references
        if hasattr(self.document, '_numbering'):
            numbering = self.document._numbering
            abstract_numberings = numbering.get('abstract_numberings', {})
            numbering_instances = numbering.get('numbering_instances', {})
            
            for num_id, num_data in numbering_instances.items():
                abstract_num_id = num_data.get('abstractNumId')
                if abstract_num_id and abstract_num_id not in abstract_numberings:
                    self.issues.append(ValidationIssue(
                        ValidationLevel.WARNING,
                        f"Numbering instance {num_id} references non-existent abstract numbering: {abstract_num_id}",
                        element_id=num_id,
                        element_type="numbering_instance"
                    ))
    
    def _validate_styles(self):
        """Validate document styles."""
        logger.debug("Validating document styles...")
        
        if not hasattr(self.document, '_styles'):
            self.issues.append(ValidationIssue(
                ValidationLevel.WARNING,
                "Document has no styles",
                element_type="styles"
            ))
            return
        
        styles = self.document._styles
        
        # Check for duplicate style IDs
        style_ids = list(styles.keys())
        if len(style_ids) != len(set(style_ids)):
            self.issues.append(ValidationIssue(
                ValidationLevel.ERROR,
                "Duplicate style IDs found",
                element_type="styles"
            ))
        
        # Check for missing style definitions
        for style_id, style_data in styles.items():
            if not style_data.get('name'):
                self.issues.append(ValidationIssue(
                    ValidationLevel.WARNING,
                    f"Style {style_id} has no name",
                    element_id=style_id,
                    element_type="style"
                ))
            
            if not style_data.get('type'):
                self.issues.append(ValidationIssue(
                    ValidationLevel.WARNING,
                    f"Style {style_id} has no type",
                    element_id=style_id,
                    element_type="style"
                ))
    
    def _validate_sections(self):
        """Validate document sections."""
        logger.debug("Validating document sections...")
        
        sections = self.document._sections
        if not sections:
            self.issues.append(ValidationIssue(
                ValidationLevel.WARNING,
                "Document has no sections",
                element_type="sections"
            ))
            return
        
        for i, section in enumerate(sections):
            if not isinstance(section, dict):
                self.issues.append(ValidationIssue(
                    ValidationLevel.ERROR,
                    f"Section {i} has invalid format",
                    element_type="section"
                ))
                continue
            
            # Check section properties
            if not section.get('margins'):
                self.issues.append(ValidationIssue(
                    ValidationLevel.WARNING,
                    f"Section {i} has no margins",
                    element_type="section"
                ))
    
    def _validate_consistency(self):
        """Validate document consistency."""
        logger.debug("Validating document consistency...")
        
        # Check if document has content
        text = self.document.get_text()
        if not text or not text.strip():
            self.issues.append(ValidationIssue(
                ValidationLevel.WARNING,
                "Document has no text content",
                element_type="document"
            ))
        
        # Check for empty tables
        tables = self.document.get_tables()
        for i, table in enumerate(tables):
            if hasattr(table, 'get_text'):
                table_text = table.get_text()
                if not table_text or not table_text.strip():
                    self.issues.append(ValidationIssue(
                        ValidationLevel.WARNING,
                        f"Table {i} is empty",
                        element_id=getattr(table, 'id', None),
                        element_type="table"
                    ))
    
    def get_issues_by_level(self, level: ValidationLevel) -> List[ValidationIssue]:
        """Get issues by validation level."""
        return [issue for issue in self.issues if issue.level == level]
    
    def get_errors(self) -> List[ValidationIssue]:
        """Get all error issues."""
        return self.get_issues_by_level(ValidationLevel.ERROR)
    
    def get_warnings(self) -> List[ValidationIssue]:
        """Get all warning issues."""
        return self.get_issues_by_level(ValidationLevel.WARNING)
    
    def get_info(self) -> List[ValidationIssue]:
        """Get all info issues."""
        return self.get_issues_by_level(ValidationLevel.INFO)
    
    def has_errors(self) -> bool:
        """Check if document has errors."""
        return len(self.get_errors()) > 0
    
    def has_warnings(self) -> bool:
        """Check if document has warnings."""
        return len(self.get_warnings()) > 0
    
    def generate_report(self, format: str = "json") -> Union[str, Dict[str, Any]]:
        """
        Generate validation report.
        
        Args:
            format: Report format ("json", "text")
            
        Returns:
            Validation report
        """
        report = {
            'summary': {
                'total_issues': len(self.issues),
                'errors': len(self.get_errors()),
                'warnings': len(self.get_warnings()),
                'info': len(self.get_info())
            },
            'issues': [issue.to_dict() for issue in self.issues]
        }
        
        if format == "json":
            return json.dumps(report, indent=2)
        elif format == "text":
            text_parts = []
            text_parts.append(f"Validation Report")
            text_parts.append(f"Total Issues: {report['summary']['total_issues']}")
            text_parts.append(f"Errors: {report['summary']['errors']}")
            text_parts.append(f"Warnings: {report['summary']['warnings']}")
            text_parts.append(f"Info: {report['summary']['info']}")
            text_parts.append("")
            
            for issue in self.issues:
                text_parts.append(str(issue))
            
            return "\n".join(text_parts)
        else:
            return report
