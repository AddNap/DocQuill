"""
Relationship Merger - zarządzanie relacjami OPC podczas scalania dokumentów DOCX.

Obsługuje:
- Kopiowanie części (parts) z zachowaniem relacji
- Aktualizację plików .rels
- Aktualizację [Content_Types].xml
- Aktualizację rel_id w elementach (obrazy, headers, footers)
- Kopiowanie media z aktualizacją ścieżek
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Set, Tuple, Any
from pathlib import Path
import logging
import re
import copy

logger = logging.getLogger(__name__)

# OPC namespaces
OPC_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"


class RelationshipMerger:
    """
    Zarządza relacjami OPC podczas scalania dokumentów DOCX.
    
    Obsługuje kopiowanie części, aktualizację relacji i zachowanie wszystkich zależności.
    """
    
    def __init__(
        self,
        target_package_reader: Any,
        source_package_reader: Any
    ) -> None:
        """
        Inicjalizuje relationship merger.
        
        Args:
            target_package_reader: PackageReader dla dokumentu docelowego
            source_package_reader: PackageReader dla dokumentu źródłowego
        """
        self.target_reader = target_package_reader
        self.source_reader = source_package_reader
        
        # Mappingi relacji (stary_id -> nowy_id)
        self.relationship_id_mapping: Dict[str, Dict[str, str]] = {}
        # Mappingi części (stara_ścieżka -> nowa_ścieżka)
        self.part_path_mapping: Dict[str, str] = {}
        # Zestaw skopiowanych części
        self.copied_parts: Set[str] = set()
        # Licznik relacji dla generowania nowych ID
        self.relationship_counter: Dict[str, int] = {}
        
        # Wewnętrzne struktury do zapisu
        self._copied_parts_data: Dict[str, bytes] = {}
        self._relationships_to_write: Dict[str, List[Dict[str, str]]] = {}
        self._content_types_to_write: Dict[str, str] = {}
        
        logger.debug("RelationshipMerger initialized")
    
    def copy_part_with_relationships(
        self,
        source_part_path: str,
        target_part_path: Optional[str] = None,
        update_content: bool = True
    ) -> Tuple[str, Dict[str, str]]:
        """
        Kopiuje część z dokumentu źródłowego do docelowego wraz z relacjami.
        
        Args:
            source_part_path: Ścieżka części w dokumencie źródłowym (np. "word/media/image1.png")
            target_part_path: Opcjonalna ścieżka docelowa (None = użyj tej samej)
            update_content: Czy aktualizować zawartość (np. XML z rel_id)
            
        Returns:
            Tuple (nowa_ścieżka, mapping_relacji)
        """
        if target_part_path is None:
            target_part_path = source_part_path
        
        # Sprawdź czy część już została skopiowana
        if source_part_path in self.part_path_mapping:
            return self.part_path_mapping[source_part_path], self.relationship_id_mapping.get(source_part_path, {})
        
        # Pobierz zawartość części
        content = self._get_part_content(source_part_path)
        if content is None:
            logger.warning(f"Part not found: {source_part_path}")
            return target_part_path, {}
        
        # Pobierz relacje dla tej części
        source_rels = self._get_part_relationships(source_part_path)
        
        # Skopiuj część
        self._copy_part_content(source_part_path, target_part_path, content)
        self.part_path_mapping[source_part_path] = target_part_path
        self.copied_parts.add(target_part_path)
        
        # Skopiuj relacje i zależne części
        rel_mapping = {}
        if source_rels:
            rel_mapping = self._copy_relationships(
                source_part_path,
                target_part_path,
                source_rels,
                update_content
            )
            self.relationship_id_mapping[source_part_path] = rel_mapping
        
        return target_part_path, rel_mapping
    
    def copy_media_with_relationships(
        self,
        source_rel_id: str,
        source_part: str = "document"
    ) -> Optional[str]:
        """
        Kopiuje media (obraz) wraz z relacjami i zwraca nowy rel_id.
        
        Args:
            source_rel_id: ID relacji w dokumencie źródłowym
            source_part: Część źródłowa (np. "document", "header1")
            
        Returns:
            Nowy rel_id w dokumencie docelowym lub None
        """
        # Pobierz relację źródłową
        source_rels = self._get_part_relationships_for_source(source_part)
        source_rel = None
        for rel in source_rels:
            if rel.get('Id') == source_rel_id:
                source_rel = rel
                break
        
        if not source_rel:
            logger.warning(f"Relationship not found: {source_rel_id} in {source_part}")
            return None
        
        # Pobierz ścieżkę docelową relacji
        target_path = source_rel.get('Target', '')
        if not target_path:
            return None
        
        # Skopiuj część media wraz z relacjami
        new_path, rel_mapping = self.copy_part_with_relationships(
            target_path,
            update_content=False  # Media są binarne
        )
        
        # Dodaj relację w docelowym dokumencie
        target_rel_id = self._add_relationship(
            source_part,
            source_rel.get('Type', ''),
            new_path,
            source_rel.get('TargetMode', 'Internal')
        )
        
        return target_rel_id
    
    def update_content_types(self) -> None:
        """
        Aktualizuje [Content_Types].xml w dokumencie docelowym.
        
        Dodaje typy zawartości dla wszystkich skopiowanych części.
        """
        # Pobierz content types z obu dokumentów
        target_content_types = self._get_content_types(self.target_reader)
        source_content_types = self._get_content_types(self.source_reader)
        
        # Dodaj brakujące typy zawartości
        for part_path in self.copied_parts:
            # Określ typ zawartości na podstawie rozszerzenia lub source
            content_type = self._determine_content_type(part_path, source_content_types)
            if content_type:
                target_content_types[part_path] = content_type
        
        # Zaktualizuj [Content_Types].xml w docelowym dokumencie
        self._write_content_types(target_content_types)
    
    def update_relationship_ids_in_xml(
        self,
        xml_content: str,
        source_part: str,
        relationship_mapping: Dict[str, str]
    ) -> str:
        """
        Aktualizuje rel_id w zawartości XML.
        
        Args:
            xml_content: Zawartość XML do aktualizacji
            source_part: Część źródłowa (dla kontekstu)
            relationship_mapping: Mapping relacji (stary_id -> nowy_id)
            
        Returns:
            Zaktualizowana zawartość XML
        """
        if not relationship_mapping:
            return xml_content
        
        updated_content = xml_content
        
        # Aktualizuj rel_id w różnych miejscach XML
        for old_id, new_id in relationship_mapping.items():
            # Aktualizuj w atrybutach r:embed, r:link, etc.
            patterns = [
                (rf'r:embed="{re.escape(old_id)}"', f'r:embed="{new_id}"'),
                (rf'r:link="{re.escape(old_id)}"', f'r:link="{new_id}"'),
                (rf'r:id="{re.escape(old_id)}"', f'r:id="{new_id}"'),
                (rf'w:anchor="{re.escape(old_id)}"', f'w:anchor="{new_id}"'),
            ]
            
            for pattern, replacement in patterns:
                updated_content = re.sub(pattern, replacement, updated_content)
        
        return updated_content
    
    def _copy_relationships(
        self,
        source_part_path: str,
        target_part_path: str,
        source_rels: List[Dict[str, str]],
        update_content: bool
    ) -> Dict[str, str]:
        """
        Kopiuje relacje dla części i zwraca mapping (stary_id -> nowy_id).
        
        Args:
            source_part_path: Ścieżka części źródłowej
            target_part_path: Ścieżka części docelowej
            source_rels: Lista relacji źródłowych
            update_content: Czy aktualizować zawartość XML
            
        Returns:
            Mapping relacji (stary_id -> nowy_id)
        """
        rel_mapping: Dict[str, str] = {}
        
        # Określ źródło relacji (np. "document", "header1")
        source_name = self._get_relationship_source_name(source_part_path)
        target_name = self._get_relationship_source_name(target_part_path)
        
        for source_rel in source_rels:
            old_rel_id = source_rel.get('Id', '')
            rel_type = source_rel.get('Type', '')
            target_rel_path = source_rel.get('Target', '')
            target_mode = source_rel.get('TargetMode', 'Internal')
            
            if not old_rel_id or not target_rel_path:
                continue
            
            # Skopiuj docelową część relacji (jeśli jest wewnętrzna)
            if target_mode == 'Internal':
                new_target_path, _ = self.copy_part_with_relationships(
                    target_rel_path,
                    update_content=update_content
                )
            else:
                new_target_path = target_rel_path
            
            # Dodaj relację w docelowym dokumencie
            new_rel_id = self._add_relationship(
                target_name,
                rel_type,
                new_target_path,
                target_mode
            )
            
            rel_mapping[old_rel_id] = new_rel_id
        
        return rel_mapping
    
    def _add_relationship(
        self,
        source_name: str,
        rel_type: str,
        target_path: str,
        target_mode: str = 'Internal'
    ) -> str:
        """
        Dodaje relację w docelowym dokumencie.
        
        Args:
            source_name: Nazwa źródła relacji (np. "document")
            rel_type: Typ relacji
            target_path: Ścieżka docelowa
            target_mode: Tryb docelowy (Internal/External)
            
        Returns:
            Nowy ID relacji
        """
        # Generuj nowy ID relacji
        if source_name not in self.relationship_counter:
            self.relationship_counter[source_name] = 1
        
        new_rel_id = f"rId{self.relationship_counter[source_name]}"
        self.relationship_counter[source_name] += 1
        
        # Zapisz relację do wewnętrznej struktury
        rels_path = self._get_relationship_file_path_for_source(source_name)
        if rels_path:
            if rels_path not in self._relationships_to_write:
                self._relationships_to_write[rels_path] = []
            
            self._relationships_to_write[rels_path].append({
                'Id': new_rel_id,
                'Type': rel_type,
                'Target': target_path,
                'TargetMode': target_mode
            })
        
        logger.debug(f"Added relationship: {new_rel_id} ({rel_type}) -> {target_path}")
        
        return new_rel_id
    
    def _get_part_content(self, part_path: str) -> Optional[bytes]:
        """Pobiera zawartość części z dokumentu źródłowego."""
        try:
            return self.source_reader.get_binary_content(part_path)
        except Exception as e:
            logger.warning(f"Failed to get content for {part_path}: {e}")
            return None
    
    def _get_part_relationships(self, part_path: str) -> List[Dict[str, str]]:
        """Pobiera relacje dla części."""
        rels_path = self._get_relationship_file_path(part_path)
        if not rels_path:
            return []
        
        try:
            rels_xml = self.source_reader.get_xml_content(rels_path)
            if rels_xml:
                return self._parse_relationship_xml(rels_xml)
        except Exception:
            pass
        
        return []
    
    def _get_part_relationships_for_source(self, source_name: str) -> List[Dict[str, str]]:
        """Pobiera relacje dla źródła (np. "document", "header1")."""
        rels_path = self._get_relationship_file_path_for_source(source_name)
        if not rels_path:
            return []
        
        try:
            rels_xml = self.source_reader.get_xml_content(rels_path)
            if rels_xml:
                return self._parse_relationship_xml(rels_xml)
        except Exception:
            pass
        
        return []
    
    def _get_relationship_file_path(self, part_path: str) -> Optional[str]:
        """Określa ścieżkę pliku relacji dla części."""
        # Przykład: word/document.xml -> word/_rels/document.xml.rels
        if part_path.startswith('word/'):
            part_name = Path(part_path).name
            return f"word/_rels/{part_name}.rels"
        return None
    
    def _get_relationship_file_path_for_source(self, source_name: str) -> Optional[str]:
        """Określa ścieżkę pliku relacji dla źródła."""
        mapping = {
            'document': 'word/_rels/document.xml.rels',
            'styles': 'word/_rels/styles.xml.rels',
            'theme': 'word/_rels/theme/theme1.xml.rels',
        }
        
        if source_name in mapping:
            return mapping[source_name]
        
        # Dla headers/footers
        if 'header' in source_name.lower():
            return f"word/_rels/{source_name}.xml.rels"
        if 'footer' in source_name.lower():
            return f"word/_rels/{source_name}.xml.rels"
        
        return None
    
    def _get_relationship_source_name(self, part_path: str) -> str:
        """Określa nazwę źródła relacji na podstawie ścieżki części."""
        if part_path == 'word/document.xml':
            return 'document'
        elif part_path == 'word/styles.xml':
            return 'styles'
        elif 'header' in part_path.lower():
            return Path(part_path).stem
        elif 'footer' in part_path.lower():
            return Path(part_path).stem
        return 'document'
    
    def _copy_part_content(
        self,
        source_path: str,
        target_path: str,
        content: bytes
    ) -> None:
        """
        Kopiuje zawartość części do docelowego pakietu.
        
        Zapisuje część do wewnętrznej struktury, która może być później użyta
        przez DOCXExporter do zapisu do pakietu.
        """
        # Zapisujemy do wewnętrznej struktury
        self._copied_parts_data[target_path] = content
        logger.debug(f"Copied part: {source_path} -> {target_path} ({len(content)} bytes)")
    
    def get_copied_parts(self) -> Dict[str, bytes]:
        """
        Zwraca wszystkie skopiowane części do zapisu.
        
        Returns:
            Słownik {part_path: content_bytes}
        """
        return getattr(self, '_copied_parts_data', {}).copy()
    
    def get_relationships_to_write(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Zwraca wszystkie relacje do zapisu.
        
        Returns:
            Słownik {rels_path: [rel_dict, ...]}
            gdzie rel_dict = {'Id': ..., 'Type': ..., 'Target': ..., 'TargetMode': ...}
        """
        relationships_to_write: Dict[str, List[Dict[str, str]]] = {}
        
        # Zbierz wszystkie relacje z relationship_id_mapping
        for source_part, rel_mapping in self.relationship_id_mapping.items():
            # Pobierz relacje źródłowe
            source_rels = self._get_part_relationships(source_part)
            target_rels_path = self._get_relationship_file_path_for_source(
                self._get_relationship_source_name(source_part)
            )
            
            if not target_rels_path:
                continue
            
            if target_rels_path not in relationships_to_write:
                relationships_to_write[target_rels_path] = []
            
            # Mapuj relacje używając rel_mapping
            for source_rel in source_rels:
                old_id = source_rel.get('Id', '')
                if old_id in rel_mapping:
                    new_rel = {
                        'Id': rel_mapping[old_id],
                        'Type': source_rel.get('Type', ''),
                        'Target': source_rel.get('Target', ''),
                        'TargetMode': source_rel.get('TargetMode', 'Internal')
                    }
                    relationships_to_write[target_rels_path].append(new_rel)
        
        return relationships_to_write
    
    def _parse_relationship_xml(self, rels_xml: str) -> List[Dict[str, str]]:
        """Parsuje XML relacji."""
        relationships = []
        try:
            root = ET.fromstring(rels_xml)
            for rel in root.findall(f'.//{{{OPC_NS}}}Relationship'):
                rel_data = {
                    'Id': rel.get('Id', ''),
                    'Type': rel.get('Type', ''),
                    'Target': rel.get('Target', ''),
                    'TargetMode': rel.get('TargetMode', 'Internal')
                }
                relationships.append(rel_data)
        except Exception as e:
            logger.error(f"Failed to parse relationship XML: {e}")
        
        return relationships
    
    def _get_content_types(self, package_reader: Any) -> Dict[str, str]:
        """Pobiera typy zawartości z pakietu."""
        content_types = {}
        try:
            content_types_xml = package_reader.get_xml_content("[Content_Types].xml")
            if content_types_xml:
                root = ET.fromstring(content_types_xml)
                
                # Parse Override elements
                for override in root.findall(f'.//{{{CONTENT_TYPES_NS}}}Override'):
                    part_name = override.get("PartName", "")
                    content_type = override.get("ContentType", "")
                    if part_name and content_type:
                        content_types[part_name] = content_type
                
                # Parse Default elements
                for default in root.findall(f'.//{{{CONTENT_TYPES_NS}}}Default'):
                    extension = default.get("Extension", "")
                    content_type = default.get("ContentType", "")
                    if extension and content_type:
                        content_types[f"*.{extension}"] = content_type
        except Exception as e:
            logger.warning(f"Failed to get content types: {e}")
        
        return content_types
    
    def _determine_content_type(
        self,
        part_path: str,
        source_content_types: Dict[str, str]
    ) -> Optional[str]:
        """Określa typ zawartości dla części."""
        # Sprawdź w źródłowych content types
        if part_path in source_content_types:
            return source_content_types[part_path]
        
        # Określ na podstawie rozszerzenia
        ext = Path(part_path).suffix.lower()
        ext_key = f"*.{ext[1:]}" if ext else None
        
        if ext_key and ext_key in source_content_types:
            return source_content_types[ext_key]
        
        # Domyślne typy zawartości
        default_types = {
            '.xml': 'application/xml',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.rels': 'application/vnd.openxmlformats-package.relationships+xml'
        }
        
        return default_types.get(ext)
    
    def _write_content_types(self, content_types: Dict[str, str]) -> None:
        """
        Zapisuje [Content_Types].xml do wewnętrznej struktury.
        
        Args:
            content_types: Słownik {part_path: content_type}
        """
        self._content_types_to_write.update(content_types)
        logger.debug(f"Prepared {len(content_types)} content types for writing")
    
    def get_content_types_to_write(self) -> Dict[str, str]:
        """
        Zwraca typy zawartości do zapisu.
        
        Returns:
            Słownik {part_path: content_type}
        """
        return getattr(self, '_content_types_to_write', {}).copy()

