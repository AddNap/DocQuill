"""
Validator for DOCX documents.

Handles document integrity validation, structure validation, relationship validation, and content validation.
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class DocumentValidator:
    """
    Validates DOCX document integrity and structure.
    
    Handles document validation, structure validation, relationship validation, and content validation.
    """
    
    def __init__(self, package_reader):
        """
        Initialize validator.
        
        Args:
            package_reader: PackageReader instance for accessing document files
        """
        self.package_reader = package_reader
        self.validation_results = {}
        self.validation_rules = self._get_default_validation_rules()
        
        logger.debug("Document validator initialized")
    
    def validate_document(self) -> Dict[str, Any]:
        """
        Validate entire document.
        
        Returns:
            Dictionary of validation results
        """
        validation_results = {
            'structure': self.validate_structure(),
            'relationships': self.validate_relationships(),
            'content': self.validate_content(),
            'overall': True
        }
        
        # Overall validation result
        validation_results['overall'] = all(
            result.get('valid', False) for result in validation_results.values()
            if isinstance(result, dict) and 'valid' in result
        )
        
        self.validation_results = validation_results
        return validation_results
    
    def validate_structure(self) -> Dict[str, Any]:
        """
        Validate document structure.
        
        Returns:
            Dictionary of structure validation results
        """
        structure_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'checks': []
        }
        
        try:
            # Check document.xml exists
            document_xml = self.package_reader.get_xml_content('word/document.xml')
            if not document_xml:
                structure_results['errors'].append("Missing document.xml")
                structure_results['valid'] = False
            else:
                structure_results['checks'].append("document.xml exists")
            
            # Check styles.xml exists
            styles_xml = self.package_reader.get_xml_content('word/styles.xml')
            if not styles_xml:
                structure_results['warnings'].append("Missing styles.xml")
            else:
                structure_results['checks'].append("styles.xml exists")
            
            # Check relationships
            relationships = self.package_reader.get_relationships('document')
            if not relationships:
                structure_results['warnings'].append("No document relationships found")
            else:
                structure_results['checks'].append(f"Found {len(relationships)} relationships")
            
            # Check content types
            content_types = self.package_reader.get_content_types()
            if not content_types:
                structure_results['errors'].append("Missing content types")
                structure_results['valid'] = False
            else:
                structure_results['checks'].append("Content types found")
            
        except Exception as e:
            structure_results['errors'].append(f"Structure validation failed: {e}")
            structure_results['valid'] = False
        
        return structure_results
    
    def validate_relationships(self) -> Dict[str, Any]:
        """
        Validate document relationships.
        
        Returns:
            Dictionary of relationship validation results
        """
        relationship_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'checks': []
        }
        
        try:
            # Check main relationships
            main_rels = self.package_reader.get_relationships('document')
            if not main_rels:
                relationship_results['errors'].append("No main relationships found")
                relationship_results['valid'] = False
            else:
                relationship_results['checks'].append(f"Found {len(main_rels)} main relationships")
            
            # Check document relationships
            doc_rels = self.package_reader.get_relationships('document')
            if doc_rels:
                relationship_results['checks'].append(f"Found {len(doc_rels)} document relationships")
            
            # Check for broken relationships
            broken_rels = []
            for rel in main_rels:
                target = rel.get('Target', '')
                if target:
                    try:
                        # Try to access the target
                        if target.startswith('word/'):
                            content = self.package_reader.get_xml_content(target)
                            if not content:
                                broken_rels.append(target)
                    except Exception:
                        broken_rels.append(target)
            
            if broken_rels:
                relationship_results['warnings'].append(f"Broken relationships: {broken_rels}")
            else:
                relationship_results['checks'].append("All relationships are valid")
            
        except Exception as e:
            relationship_results['errors'].append(f"Relationship validation failed: {e}")
            relationship_results['valid'] = False
        
        return relationship_results
    
    def validate_content(self) -> Dict[str, Any]:
        """
        Validate document content.
        
        Returns:
            Dictionary of content validation results
        """
        content_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'checks': []
        }
        
        try:
            # Check document content
            document_xml = self.package_reader.get_xml_content('word/document.xml')
            if document_xml:
                # Parse document content
                import xml.etree.ElementTree as ET
                root = ET.fromstring(document_xml)
                
                # Check for body element
                body = root.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}body')
                if body is None:
                    content_results['errors'].append("Missing document body")
                    content_results['valid'] = False
                else:
                    content_results['checks'].append("Document body found")
                
                # Check for paragraphs
                paragraphs = root.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p')
                if not paragraphs:
                    content_results['warnings'].append("No paragraphs found")
                else:
                    content_results['checks'].append(f"Found {len(paragraphs)} paragraphs")
                
                # Check for tables
                tables = root.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tbl')
                if tables:
                    content_results['checks'].append(f"Found {len(tables)} tables")
                
                # Check for images
                images = root.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}drawing')
                if images:
                    content_results['checks'].append(f"Found {len(images)} drawings")
                
                # Check for hyperlinks
                hyperlinks = root.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}hyperlink')
                if hyperlinks:
                    content_results['checks'].append(f"Found {len(hyperlinks)} hyperlinks")
            
        except Exception as e:
            content_results['errors'].append(f"Content validation failed: {e}")
            content_results['valid'] = False
        
        return content_results
    
    def get_validation_errors(self) -> List[str]:
        """
        Get validation errors.
        
        Returns:
            List of validation errors
        """
        errors = []
        for result in self.validation_results.values():
            if isinstance(result, dict) and 'errors' in result:
                errors.extend(result['errors'])
        return errors
    
    def get_validation_warnings(self) -> List[str]:
        """
        Get validation warnings.
        
        Returns:
            List of validation warnings
        """
        warnings = []
        for result in self.validation_results.values():
            if isinstance(result, dict) and 'warnings' in result:
                warnings.extend(result['warnings'])
        return warnings
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """
        Get validation summary.
        
        Returns:
            Dictionary with validation summary
        """
        if not self.validation_results:
            return {'status': 'not_validated', 'message': 'Document not validated yet'}
        
        total_errors = len(self.get_validation_errors())
        total_warnings = len(self.get_validation_warnings())
        
        return {
            'status': 'valid' if self.validation_results.get('overall', False) else 'invalid',
            'total_errors': total_errors,
            'total_warnings': total_warnings,
            'validated_sections': list(self.validation_results.keys())
        }
    
    def _get_default_validation_rules(self) -> Dict[str, Any]:
        """Get default validation rules."""
        return {
            'structure': {
                'require_document_xml': True,
                'require_styles_xml': False,
                'require_relationships': True,
                'require_content_types': True
            },
            'content': {
                'require_body': True,
                'require_paragraphs': False,
                'allow_empty_document': False
            },
            'relationships': {
                'require_main_relationships': True,
                'check_broken_relationships': True,
                'validate_targets': True
            }
        }
    
    def set_validation_rules(self, rules: Dict[str, Any]) -> None:
        """
        Set validation rules.
        
        Args:
            rules: Dictionary of validation rules
        """
        self.validation_rules.update(rules)
        logger.debug("Validation rules updated")
    
    def clear_validation_results(self) -> None:
        """Clear validation results."""
        self.validation_results.clear()
        logger.debug("Validation results cleared")
