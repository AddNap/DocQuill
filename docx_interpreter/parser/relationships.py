"""
Relationship manager for DOCX documents.

Handles relationship file parsing, management, and target resolution.
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Set, Any
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class RelationshipManager:
    """
    Manages relationships between document parts.
    
    Handles relationship parsing, caching, target resolution, and type-based filtering.
    """
    
    def __init__(self, package_reader):
        """
        Initialize relationship manager.
        
        Args:
            package_reader: PackageReader instance for accessing relationship files
        """
        self.package_reader = package_reader
        self.relationships = {}
        self.relationship_index = {}
        self.target_cache = {}
        
        # Load all relationship files
        self._load_relationships()
        
        logger.debug("Relationship manager initialized")
    
    def get_relationships(self, source: str) -> List[Dict[str, str]]:
        """
        Get relationships for a specific source.
        
        Args:
            source: Source part name (e.g., 'document', 'styles', 'theme')
            
        Returns:
            List of relationship dictionaries
        """
        if source in self.relationships:
            return self.relationships[source].copy()
        return []
    
    def get_relationships_by_type(self, relationship_type: str, source: str = "document") -> List[Dict[str, str]]:
        """
        Get relationships of a specific type.
        
        Args:
            relationship_type: Type of relationship to filter by
            source: Source part name
            
        Returns:
            List of filtered relationships
        """
        relationships = self.get_relationships(source)
        return [rel for rel in relationships if rel.get('Type') == relationship_type]
    
    def get_image_relationships(self) -> List[Dict[str, str]]:
        """
        Get all image relationships.
        
        Returns:
            List of image relationships
        """
        image_relationships = []
        
        # Check document relationships
        doc_images = self.get_relationships_by_type(
            'http://schemas.openxmlformats.org/officeDocument/2006/relationships/image',
            'document'
        )
        image_relationships.extend(doc_images)
        
        # Check header/footer relationships
        for part_name in self.relationships:
            if 'header' in part_name or 'footer' in part_name:
                part_images = self.get_relationships_by_type(
                    'http://schemas.openxmlformats.org/officeDocument/2006/relationships/image',
                    part_name
                )
                image_relationships.extend(part_images)
        
        return image_relationships
    
    def get_target_path(self, relationship_id: str, source: str = "document") -> Optional[str]:
        """
        Get target path for a relationship ID.
        
        Args:
            relationship_id: Relationship ID
            source: Source part name
            
        Returns:
            Target path or None if not found
        """
        cache_key = f"{source}:{relationship_id}"
        if cache_key in self.target_cache:
            return self.target_cache[cache_key]
        
        relationships = self.get_relationships(source)
        for rel in relationships:
            if rel.get('Id') == relationship_id:
                target = rel.get('Target', '')
                self.target_cache[cache_key] = target
                return target
        
        return None
    
    def get_relationship_by_target(self, target: str, source: str = "document") -> Optional[Dict[str, str]]:
        """
        Get relationship by target path.
        
        Args:
            target: Target path
            source: Source part name
            
        Returns:
            Relationship dictionary or None if not found
        """
        relationships = self.get_relationships(source)
        for rel in relationships:
            if rel.get('Target') == target:
                return rel
        return None
    
    def get_all_relationship_types(self) -> Set[str]:
        """
        Get all relationship types in the document.
        
        Returns:
            Set of relationship types
        """
        types = set()
        for source_rels in self.relationships.values():
            for rel in source_rels:
                rel_type = rel.get('Type', '')
                if rel_type:
                    types.add(rel_type)
        return types
    
    def get_relationship_sources(self) -> List[str]:
        """
        Get all relationship sources.
        
        Returns:
            List of source part names
        """
        return list(self.relationships.keys())
    
    def _load_relationships(self) -> None:
        """Load all relationship files from the package."""
        try:
            # Load main document relationships
            self._load_relationship_file('_rels/.rels', 'document')
            
            # Load document relationships
            self._load_relationship_file('word/_rels/document.xml.rels', 'document')
            
            # Load styles relationships
            self._load_relationship_file('word/_rels/styles.xml.rels', 'styles')
            
            # Load theme relationships
            self._load_relationship_file('word/_rels/theme/theme1.xml.rels', 'theme')
            
            # Load header/footer relationships
            self._load_header_footer_relationships()
            
            logger.info(f"Loaded relationships for {len(self.relationships)} sources")
            
        except Exception as e:
            logger.error(f"Failed to load relationships: {e}")
    
    def _load_relationship_file(self, rels_path: str, source: str) -> None:
        """Load a specific relationship file."""
        try:
            rels_xml = self.package_reader.get_xml_content(rels_path)
            if rels_xml:
                relationships = self._parse_relationship_xml(rels_xml)
                self.relationships[source] = relationships
                logger.debug(f"Loaded {len(relationships)} relationships for {source}")
        except Exception as e:
            logger.warning(f"Failed to load relationships from {rels_path}: {e}")
    
    def _load_header_footer_relationships(self) -> None:
        """Load header and footer relationships."""
        # Find all header/footer files
        try:
            # This would need to be implemented based on the actual package structure
            # For now, we'll try common patterns
            header_footer_patterns = [
                'word/_rels/header1.xml.rels',
                'word/_rels/footer1.xml.rels',
                'word/_rels/header2.xml.rels',
                'word/_rels/footer2.xml.rels'
            ]
            
            for pattern in header_footer_patterns:
                try:
                    rels_xml = self.package_reader.get_xml_content(pattern)
                    if rels_xml:
                        source_name = Path(pattern).stem.replace('.xml', '')
                        relationships = self._parse_relationship_xml(rels_xml)
                        self.relationships[source_name] = relationships
                        logger.debug(f"Loaded {len(relationships)} relationships for {source_name}")
                except Exception:
                    # File doesn't exist, continue
                    continue
                    
        except Exception as e:
            logger.warning(f"Failed to load header/footer relationships: {e}")
    
    def _parse_relationship_xml(self, rels_xml: str) -> List[Dict[str, str]]:
        """Parse relationship XML content."""
        relationships = []
        
        try:
            root = ET.fromstring(rels_xml)
            
            for rel in root.findall('.//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'):
                rel_data = {
                    'Id': rel.get('Id', ''),
                    'Type': rel.get('Type', ''),
                    'Target': rel.get('Target', ''),
                    'TargetMode': rel.get('TargetMode', 'Internal')
                }
                relationships.append(rel_data)
                
        except ET.ParseError as e:
            logger.error(f"Failed to parse relationship XML: {e}")
        
        return relationships
    
    def get_relationship_info(self) -> Dict[str, Any]:
        """Get complete relationship information."""
        return {
            'sources': self.get_relationship_sources(),
            'total_relationships': sum(len(rels) for rels in self.relationships.values()),
            'relationship_types': list(self.get_all_relationship_types()),
            'image_relationships': len(self.get_image_relationships())
        }
    
    def clear_cache(self) -> None:
        """Clear relationship cache."""
        self.target_cache.clear()
        logger.debug("Relationship cache cleared")
