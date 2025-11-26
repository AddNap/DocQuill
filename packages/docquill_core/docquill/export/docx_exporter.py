"""

DOCX exporter - creates DOCX files from document models.

Uses XMLExporter to generate WordML XML and packages everything
into DOCX package (ZIP) with relationships and [Content_Types].xml.

"""

from __future__ import annotations

import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Union, Any, Set
from pathlib import Path
import logging
import tempfile
import shutil

from .xml_exporter import XMLExporter

logger = logging.getLogger(__name__)

# OPC namespaces
OPC_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


class DOCXExporter:
    """

    DOCX Exporter - creates DOCX files from document models.

    Uses XMLExporter to generate WordML XML and packages everything
    into DOCX package (ZIP) with relationships and [Content_Types].xml.

    Uses empty template (new_doc.docx) as base and fills it with content.

    """
    
    # Path to empty document template
    TEMPLATE_PATH = Path(__file__).parent / "new_doc.docx"
    
    def __init__(
        self, 
        document: Any, 
        use_relationship_merger: bool = True, 
        template_path: Optional[Union[str, Path]] = None,
        source_docx_path: Optional[Union[str, Path]] = None
    ):
        """

        Initializes DOCX exporter.

        Args:
        document: Document to export (from PackageReader or model)
        use_relationship_merger: Whether to use RelationshipMerger for relationship management
        template_path: Optional path to DOCX template (overrides source_docx_path)
        source_docx_path: Optional path to source DOCX (used as template if exists)

        """
        self.document = document
        self.xml_exporter = XMLExporter(document)
        self.use_relationship_merger = use_relationship_merger
        
        # Priorytet wyboru szablonu:
        # 1. template_path (if provided - highest priority)
        # 2. source_docx_path (if exists - use original DOCX as template, copy ALL files)
        # 3. TEMPLATE_PATH (default new_doc.docx for new documents)
        if template_path:
            self.template_path = Path(template_path)
        elif source_docx_path and Path(source_docx_path).exists():
            # Use original DOCX as template (for round-trip: JSON → DOCX)
            # Copy ALL files from it (except document.xml, which we generate)
            self.template_path = Path(source_docx_path)
        else:
            # Use default template (for new documents)
            self.template_path = self.TEMPLATE_PATH
        
        # Package parts (part_name -> content)
        self._parts: Dict[str, bytes] = {}
        # Relacje (source -> [(rel_id, rel_type, target, target_mode)])
        self._relationships: Dict[str, List[tuple]] = {}
        # Content types (part_name -> content_type)
        self._content_types: Dict[str, str] = {}
        # Default content types (extension -> content_type)
        self._default_content_types: Dict[str, str] = {}
        # Media files (part_name -> content)
        self._media: Dict[str, bytes] = {}
        
        # Licznik relacji dla generowania ID
        self._rel_id_counters: Dict[str, int] = {}
        
        # Mapowanie starych ID na nowe ID dla headers/footers (old_id -> new_id)
        self._header_footer_id_mapping: Dict[str, str] = {}
        
        # RelationshipMerger for advanced relationship management
        self.relationship_merger = None
        if self.use_relationship_merger and hasattr(document, '_package_reader'):
            try:
                from ..merger.relationship_merger import RelationshipMerger
                # Create mock target_reader (use same document as target)
                # In reality RelationshipMerger will manage relationships during export
                self.relationship_merger = RelationshipMerger(
                    target_package_reader=document._package_reader,
                    source_package_reader=document._package_reader
                )
            except Exception as e:
                logger.warning(f"Failed to initialize RelationshipMerger: {e}")
                self.relationship_merger = None
        
        logger.debug("DOCXExporter initialized")
    
    def _get_package_reader(self):
        """Gets package_reader from various possible locations."""
        if hasattr(self.document, '_package_reader') and self.document._package_reader:
            return self.document._package_reader
        elif hasattr(self.document, 'parser') and hasattr(self.document.parser, 'package_reader'):
            return self.document.parser.package_reader
        # For documents from JSON, check importer's package_reader
        elif hasattr(self.document, '_importer') and hasattr(self.document._importer, '_package_reader'):
            return self.document._importer._package_reader
        # Also check source_docx_path and create package_reader if needed
        elif hasattr(self.document, '_source_docx') and self.document._source_docx:
            from ..parser.package_reader import PackageReader
            try:
                return PackageReader(str(self.document._source_docx))
            except Exception:
                pass
        return None
    
    def export(self, output_path: Union[str, Path]) -> bool:
        """

        Exports document to DOCX file.

        Uses empty template (new_doc.docx) as base and fills it with content.

        Args:
        output_path: Path to output DOCX file

        Returns:
        True if export succeeded

        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 0. Load template (if exists)
            self._load_template()
            
            # 1. Prepare package parts (will override document.xml, add new files)
            self._prepare_parts()
            
            # 2. Przygotuj relacje (zachowa relacje z szablonu, doda nowe)
            self._prepare_relationships()
            
            # 2.5. Zaktualizuj ID w sectPr w document.xml (po wygenerowaniu relacji)
            self._update_sectpr_ids()
            
            # 3. Przygotuj [Content_Types].xml (zachowa typy z szablonu, doda nowe)
            self._prepare_content_types()
            
            # 4. Zapisz do ZIP
            self._write_package(output_path)
            
            logger.info(f"Document exported to DOCX: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export document to DOCX: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _load_template(self) -> None:
        """Loads DOCX template as base for export."""
        if not self.template_path.exists():
            logger.warning(f"Template not found: {self.template_path}, creating DOCX from scratch")
            return
        
        try:
            # Open template as ZIP
            with zipfile.ZipFile(self.template_path, 'r') as template_zip:
                # Skopiuj wszystkie pliki z szablonu
                # IMPORTANT: If using original DOCX as template, copy ALL files
                # (except document.xml, which will be generated)
                for item in template_zip.namelist():
                    # Skip document.xml - will be generated
                    if item == 'word/document.xml':
                        continue
                    
                    # Skopiuj plik z szablonu
                    try:
                        content = template_zip.read(item)
                        self._parts[item] = content
                        
                        # Determine content type based on extension
                        if item.endswith('.xml'):
                            if 'styles' in item:
                                self._content_types[item] = (
                                    'application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml'
                                )
                            elif 'settings' in item:
                                self._content_types[item] = (
                                    'application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml'
                                )
                            elif 'theme' in item:
                                self._content_types[item] = (
                                    'application/vnd.openxmlformats-officedocument.theme+xml'
                                )
                            elif 'fontTable' in item:
                                self._content_types[item] = (
                                    'application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml'
                                )
                            elif 'webSettings' in item:
                                self._content_types[item] = (
                                    'application/vnd.openxmlformats-officedocument.wordprocessingml.webSettings+xml'
                                )
                            elif item == '[Content_Types].xml':
                                # Zostanie nadpisane przez _prepare_content_types
                                pass
                            elif item.startswith('_rels/'):
                                # Relationships - keep from template as base
                                # _prepare_relationships will add new relationships but keep existing
                                if item not in self._relationships:
                                    # Parsuj relacje z XML
                                    try:
                                        rels_xml = ET.fromstring(content)
                                        rels_list = []
                                        for rel in rels_xml.findall('.//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'):
                                            rel_id = rel.get('Id')
                                            rel_type = rel.get('Type')
                                            target = rel.get('Target')
                                            target_mode = rel.get('TargetMode', 'Internal')
                                            if rel_id and rel_type and target:
                                                rels_list.append((rel_id, rel_type, target, target_mode))
                                        if rels_list:
                                            self._relationships[item] = rels_list
                                    except Exception as e:
                                        logger.debug(f"Failed to parse relationships from {item}: {e}")
                        
                        # Also copy content types from [Content_Types].xml
                        if item == '[Content_Types].xml':
                            try:
                                ct_xml = ET.fromstring(content)
                                for override in ct_xml.findall('.//{http://schemas.openxmlformats.org/package/2006/content-types}Override'):
                                    part_name = override.get('PartName')
                                    content_type = override.get('ContentType')
                                    if part_name and content_type:
                                        # Remove leading slash if present
                                        if part_name.startswith('/'):
                                            part_name = part_name[1:]
                                        self._content_types[part_name] = content_type
                                for default in ct_xml.findall('.//{http://schemas.openxmlformats.org/package/2006/content-types}Default'):
                                    extension = default.get('Extension')
                                    content_type = default.get('ContentType')
                                    if extension and content_type:
                                        self._default_content_types[extension] = content_type
                            except Exception as e:
                                logger.debug(f"Failed to parse Content_Types from template: {e}")
                    except Exception as e:
                        logger.warning(f"Failed to copy {item} from template: {e}")
            
            logger.debug(f"Loaded template from {self.template_path}")
        except Exception as e:
            logger.warning(f"Failed to load template {self.template_path}: {e}, creating DOCX from scratch")
    
    def _prepare_parts(self) -> None:
        """Prepares package parts (document.xml, styles.xml, etc.)."""
        # 1. Generate document.xml using XMLExporter
        document_xml = self.xml_exporter.regenerate_wordml(self.document)
        self._parts['word/document.xml'] = document_xml.encode('utf-8')
        self._content_types['word/document.xml'] = (
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'
        )
        
        # 2. Generate styles.xml from models (uses StyleNormalizer from normalize.py)
        styles_xml = self._generate_styles_xml()
        if styles_xml:
            self._parts['word/styles.xml'] = styles_xml.encode('utf-8')
            self._content_types['word/styles.xml'] = (
                'application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml'
            )
        
        # 3. Generate numbering.xml from models (uses NumberingNormalizer from normalize.py)
        # Only if not already loaded from template
        if 'word/numbering.xml' not in self._parts:
            numbering_xml = self._generate_numbering_xml()
            if numbering_xml:
                self._parts['word/numbering.xml'] = numbering_xml.encode('utf-8')
                self._content_types['word/numbering.xml'] = (
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml'
                )
        
        # 4. Copy settings.xml if exists (only if not already loaded from template)
        if 'word/settings.xml' not in self._parts:
            if hasattr(self.document, '_package_reader'):
                package_reader = self.document._package_reader
                settings_xml = package_reader.get_xml_content('word/settings.xml')
                if settings_xml:
                    self._parts['word/settings.xml'] = settings_xml.encode('utf-8')
                    self._content_types['word/settings.xml'] = (
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml'
                    )
        
        # 5. Copy media (images) if exist and find new images in documents
        self._prepare_media()
        
        # 6. Use RelationshipMerger for relationship management if available
        if self.relationship_merger:
            self._use_relationship_merger_for_parts()
        
        # 7. Copy headers and footers if exist
        # First from original document (if exists)
        if hasattr(self.document, '_package_reader'):
            package_reader = self.document._package_reader
            # Check headers/footers relationships in document.xml.rels
            if hasattr(package_reader, 'relationships'):
                doc_rels = package_reader.relationships.get('document', {})
                # doc_rels can be dict (rId -> rel_dict) or list
                if isinstance(doc_rels, dict):
                    rels_iter = doc_rels.values()
                else:
                    rels_iter = doc_rels
                for rel in rels_iter:
                    if isinstance(rel, dict):
                        rel_type = rel.get('Type', '') or rel.get('type', '')
                        target = rel.get('Target', '') or rel.get('target', '')
                    else:
                        # Skip if not a dict
                        continue
                    
                    if 'header' in rel_type.lower() or 'footer' in rel_type.lower():
                        # Get header/footer content
                        # Target can be relative (header1.xml) or full (word/header1.xml)
                        full_target = target if target.startswith('word/') else f'word/{target}'
                        try:
                            hf_xml = package_reader.get_xml_content(full_target)
                            if hf_xml:
                                # Store with relative path for relationships
                                rel_target = target if not target.startswith('word/') else target[5:]
                                self._parts[f'word/{rel_target}'] = hf_xml.encode('utf-8')
                                if 'header' in target.lower():
                                    self._content_types[f'word/{rel_target}'] = (
                                        'application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml'
                                    )
                                else:
                                    self._content_types[f'word/{rel_target}'] = (
                                        'application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml'
                                    )
                        except Exception as e:
                            logger.debug(f"Header/footer {target} not found, may be added later: {e}")
        
        # If document has no _package_reader (e.g. created from JSON), check headers/footers in model
        if not hasattr(self.document, '_package_reader') or not self.document._package_reader:
            # Check if document has headers/footers in model
            # Headers/footers can be in different places depending on model structure
            headers_dict = {}
            footers_dict = {}
            
            # Check various possible locations for headers/footers
            # First check directly in document (may be SimpleNamespace from to_document_model)
            if hasattr(self.document, 'headers'):
                headers_dict = self.document.headers if isinstance(self.document.headers, dict) else {}
            elif hasattr(self.document, '_headers'):
                headers_dict = self.document._headers if isinstance(self.document._headers, dict) else {}
            # Check in _model (if document is Document API)
            elif hasattr(self.document, '_model') and hasattr(self.document._model, 'headers'):
                headers_dict = self.document._model.headers if isinstance(self.document._model.headers, dict) else {}
            # Check directly in document (if document is model from to_document_model)
            elif hasattr(self.document, 'body') and hasattr(self.document, 'headers'):
                headers_dict = self.document.headers if isinstance(self.document.headers, dict) else {}
            
            if hasattr(self.document, 'footers'):
                footers_dict = self.document.footers if isinstance(self.document.footers, dict) else {}
            elif hasattr(self.document, '_footers'):
                footers_dict = self.document._footers if isinstance(self.document._footers, dict) else {}
            elif hasattr(self.document, '_model') and hasattr(self.document._model, 'footers'):
                footers_dict = self.document._model.footers if isinstance(self.document._model.footers, dict) else {}
            elif hasattr(self.document, 'body') and hasattr(self.document, 'footers'):
                footers_dict = self.document.footers if isinstance(self.document.footers, dict) else {}
            
            # Eksportuj headers - headers_dict to dict z kluczami jak 'default', 'first', 'even'
            header_index = 1
            for header_key, header_list in headers_dict.items():
                if header_list and isinstance(header_list, list):
                    # Create simple header model from list of elements
                    from types import SimpleNamespace
                    header_model = SimpleNamespace()
                    header_model.body = SimpleNamespace()
                    header_model.body.children = header_list
                    
                    try:
                        # Eksportuj header jako XML
                        header_xml = self.xml_exporter.regenerate_wordml(header_model)
                        header_path = f'word/header{header_index}.xml'
                        self._parts[header_path] = header_xml.encode('utf-8')
                        self._content_types[header_path] = (
                            'application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml'
                        )
                        header_index += 1
                    except Exception as e:
                        logger.warning(f"Failed to export header {header_key}: {e}")
            
            # Eksportuj footers - footers_dict to dict z kluczami jak 'default', 'first', 'even'
            footer_index = 1
            for footer_key, footer_list in footers_dict.items():
                if footer_list and isinstance(footer_list, list):
                    # Create simple footer model from list of elements
                    from types import SimpleNamespace
                    footer_model = SimpleNamespace()
                    footer_model.body = SimpleNamespace()
                    footer_model.body.children = footer_list
                    
                    try:
                        # Eksportuj footer jako XML
                        footer_xml = self.xml_exporter.regenerate_wordml(footer_model)
                        footer_path = f'word/footer{footer_index}.xml'
                        self._parts[footer_path] = footer_xml.encode('utf-8')
                        self._content_types[footer_path] = (
                            'application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml'
                        )
                        footer_index += 1
                    except Exception as e:
                        logger.warning(f"Failed to export footer {footer_key}: {e}")
    
    def _prepare_relationships(self) -> None:
        """Prepares relationships for all parts."""
        # 1. Main relationships (_rels/.rels) - keep from template if exist
        if '_rels/.rels' not in self._relationships:
            self._relationships['_rels/.rels'] = []
        
        # Add relationship to document.xml
        doc_rel_id = self._get_next_rel_id('_rels/.rels')
        self._relationships['_rels/.rels'].append((
            doc_rel_id,
            'http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument',
            'word/document.xml',
            'Internal'
        ))
        
        # 2. Relacje document.xml (word/_rels/document.xml.rels)
        self._relationships['word/_rels/document.xml.rels'] = []
        
        # Set of targets that already have relationships (to avoid duplicates)
        existing_rel_targets = set()
        # Set of used relationship IDs (to avoid duplicates)
        used_rel_ids = set()
        
        # First copy relationships from original document if exist
        package_reader = self._get_package_reader()
        
        # Collect all relationships from original document
        all_orig_rels = []
        if package_reader and hasattr(package_reader, 'relationships'):
                doc_rels = package_reader.relationships.get('document', [])
                # doc_rels can be list or dictionary
                if isinstance(doc_rels, dict):
                    rels_iter = doc_rels.items()
                else:
                    rels_iter = enumerate(doc_rels) if isinstance(doc_rels, list) else []
                
                for rel_key, rel in rels_iter:
                    old_rel_id_from_key = rel_key if isinstance(rel_key, str) and rel_key.startswith('rId') else None
                    
                    if isinstance(rel, dict):
                        rel_type = rel.get('Type', '') or rel.get('type', '')
                        target = rel.get('Target', '') or rel.get('target', '')
                        target_mode = rel.get('TargetMode', 'Internal') or rel.get('target_mode', 'Internal')
                        rel_id_from_rel = rel.get('Id', '') or rel.get('id', '')
                    else:
                        rel_type = getattr(rel, 'Type', '') or getattr(rel, 'type', '')
                        target = getattr(rel, 'Target', '') or getattr(rel, 'target', '')
                        target_mode = getattr(rel, 'TargetMode', 'Internal') or getattr(rel, 'target_mode', 'Internal')
                        rel_id_from_rel = getattr(rel, 'Id', '') or getattr(rel, 'id', '')
                    
                    old_rel_id = old_rel_id_from_key or rel_id_from_rel
                    if target.startswith('/'):
                        target = target[1:]
                    
                    is_external = target_mode == 'External' or target.startswith('http://') or target.startswith('https://') or target.startswith('mailto:')
                    all_orig_rels.append((old_rel_id, rel_type, target, target_mode, is_external))
        
        # PASS 1: Add all external relationships first with their original IDs
        # External relationships can have duplicate targets (same URL with different IDs)
        for old_rel_id, rel_type, target, target_mode, is_external in all_orig_rels:
            if is_external and old_rel_id:
                # For external rels, don't check for duplicate targets - each hyperlink needs its own ID
                self._relationships['word/_rels/document.xml.rels'].append((
                    old_rel_id, rel_type, target, target_mode
                ))
                used_rel_ids.add(old_rel_id)
                # Update counter
                try:
                    id_num = int(old_rel_id.replace('rId', ''))
                    if 'word/_rels/document.xml.rels' not in self._rel_id_counters:
                        self._rel_id_counters['word/_rels/document.xml.rels'] = id_num + 1
                    else:
                        self._rel_id_counters['word/_rels/document.xml.rels'] = max(
                            self._rel_id_counters['word/_rels/document.xml.rels'], 
                            id_num + 1
                        )
                except ValueError:
                    pass
        
        # PASS 2: Add internal relationships
        for old_rel_id, rel_type, target, target_mode, is_external in all_orig_rels:
            if is_external:
                continue  # Already processed
            
            # Check if part exists
            target_exists = False
            normalized_target = target
            
            if target in self._parts or target in self._media:
                target_exists = True
                normalized_target = target
            elif not target.startswith('word/'):
                full_target = f'word/{target}'
                if full_target in self._parts or full_target in self._media:
                    target_exists = True
                    normalized_target = target
            elif target.startswith('word/'):
                short_target = target[5:]
                if short_target in self._parts or short_target in self._media:
                    target_exists = True
                    normalized_target = short_target
            
            # Headers/footers variants
            if not target_exists and ('header' in rel_type.lower() or 'footer' in rel_type.lower()):
                variants = [target, f'word/{target}', target.replace('word/', '')]
                for variant in variants:
                    if variant in self._parts:
                        target_exists = True
                        normalized_target = Path(target).name
                        break
            
            # Media variants
            if not target_exists and ('media' in target or 'image' in rel_type.lower()):
                variants = [
                    target, f'word/{target}', target.replace('word/', ''),
                    target if target.startswith('media/') else f'media/{Path(target).name}',
                    f'word/media/{Path(target).name}'
                ]
                for variant in variants:
                    if variant in self._media:
                        target_exists = True
                        normalized_target = target
                        break
                if not target_exists:
                    for media_key in self._media.keys():
                        if Path(media_key).name == Path(target).name:
                            target_exists = True
                            normalized_target = target
                            break
            
            if target_exists:
                check_target = normalized_target
                if 'header' in rel_type.lower() or 'footer' in rel_type.lower():
                    check_target = Path(normalized_target).name
                
                if check_target not in existing_rel_targets:
                    rel_id = self._get_next_rel_id('word/_rels/document.xml.rels')
                    while rel_id in used_rel_ids:
                        rel_id = self._get_next_rel_id('word/_rels/document.xml.rels')
                    used_rel_ids.add(rel_id)
                    
                    rel_target = normalized_target
                    if 'header' in rel_type.lower() or 'footer' in rel_type.lower():
                        rel_target = Path(normalized_target).name
                    
                    self._relationships['word/_rels/document.xml.rels'].append((
                        rel_id, rel_type, rel_target, target_mode
                    ))
                    existing_rel_targets.add(check_target)
                    
                    if old_rel_id and ('header' in rel_type.lower() or 'footer' in rel_type.lower()):
                        self._header_footer_id_mapping[old_rel_id] = rel_id
                        logger.debug(f"Mapped {rel_type.split('/')[-1]} ID: {old_rel_id} -> {rel_id} for {rel_target}")
        
        # Add relationships for parts that are in package but don't have relationships
        # (e.g. for documents created from JSON)
        existing_targets = {rel[2] for rel in self._relationships['word/_rels/document.xml.rels']}
        
        # Relationship to styles.xml (only if no relationship exists)
        # Check both full path and relative
        styles_targets = {'word/styles.xml', 'styles.xml'}
        if 'word/styles.xml' in self._parts and not any(t in existing_targets for t in styles_targets):
            rel_id = self._get_next_rel_id('word/_rels/document.xml.rels')
            self._relationships['word/_rels/document.xml.rels'].append((
                rel_id,
                'http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles',
                'styles.xml',  # In document.xml relationships use relative path
                'Internal'
            ))
            existing_targets.add('styles.xml')
        
        # Relacja do numbering.xml
        numbering_targets = {'word/numbering.xml', 'numbering.xml'}
        if 'word/numbering.xml' in self._parts and not any(t in existing_targets for t in numbering_targets):
            rel_id = self._get_next_rel_id('word/_rels/document.xml.rels')
            self._relationships['word/_rels/document.xml.rels'].append((
                rel_id,
                'http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering',
                'numbering.xml',  # In document.xml relationships use relative path
                'Internal'
            ))
            existing_targets.add('numbering.xml')
        
        # Relationships to headers - find old ID from section
        sections = None
        if hasattr(self.document, '_sections') and self.document._sections:
            sections = self.document._sections
        elif hasattr(self.document, '_json_sections') and self.document._json_sections:
            sections = self.document._json_sections
        
        # Mapowanie nazwy pliku -> stare ID z sekcji
        header_file_to_old_id = {}
        footer_file_to_old_id = {}
        if sections:
            section = sections[0] if isinstance(sections, list) and len(sections) > 0 else {}
            if 'headers' in section and isinstance(section['headers'], list):
                for hdr in section['headers']:
                    if 'id' in hdr:
                        # Find header filename based on target in relationships
                        package_reader = self._get_package_reader()
                        if package_reader and hasattr(package_reader, 'relationships'):
                            doc_rels = package_reader.relationships.get('document', [])
                            # doc_rels can be list or dictionary
                            if isinstance(doc_rels, dict):
                                # If dict, check directly by key (ID)
                                if hdr['id'] in doc_rels:
                                    rel = doc_rels[hdr['id']]
                                    if isinstance(rel, dict):
                                        target = rel.get('Target', '') or rel.get('target', '')
                                    else:
                                        target = getattr(rel, 'Target', '') or getattr(rel, 'target', '')
                                    header_file_to_old_id[Path(target).name] = hdr['id']
                                    logger.debug(f"Found header mapping: {hdr['id']} -> {Path(target).name}")
                            else:
                                # If list, iterate through elements
                                for rel in doc_rels:
                                    if isinstance(rel, dict):
                                        rel_id = rel.get('Id') or rel.get('id')
                                        target = rel.get('Target', '') or rel.get('target', '')
                                    else:
                                        rel_id = getattr(rel, 'Id', '') or getattr(rel, 'id', '')
                                        target = getattr(rel, 'Target', '') or getattr(rel, 'target', '')
                                    if rel_id == hdr['id']:
                                        header_file_to_old_id[Path(target).name] = hdr['id']
                                        logger.debug(f"Found header mapping: {hdr['id']} -> {Path(target).name}")
            if 'footers' in section and isinstance(section['footers'], list):
                for ftr in section['footers']:
                    if 'id' in ftr:
                        package_reader = self._get_package_reader()
                        if package_reader and hasattr(package_reader, 'relationships'):
                            doc_rels = package_reader.relationships.get('document', [])
                            # doc_rels can be list or dictionary
                            if isinstance(doc_rels, dict):
                                # If dict, check directly by key (ID)
                                if ftr['id'] in doc_rels:
                                    rel = doc_rels[ftr['id']]
                                    if isinstance(rel, dict):
                                        target = rel.get('Target', '') or rel.get('target', '')
                                    else:
                                        target = getattr(rel, 'Target', '') or getattr(rel, 'target', '')
                                    footer_file_to_old_id[Path(target).name] = ftr['id']
                                    logger.debug(f"Found footer mapping: {ftr['id']} -> {Path(target).name}")
                            else:
                                # If list, iterate through elements
                                for rel in doc_rels:
                                    if isinstance(rel, dict):
                                        rel_id = rel.get('Id') or rel.get('id')
                                        target = rel.get('Target', '') or rel.get('target', '')
                                    else:
                                        rel_id = getattr(rel, 'Id', '') or getattr(rel, 'id', '')
                                        target = getattr(rel, 'Target', '') or getattr(rel, 'target', '')
                                    if rel_id == ftr['id']:
                                        footer_file_to_old_id[Path(target).name] = ftr['id']
                                        logger.debug(f"Found footer mapping: {ftr['id']} -> {Path(target).name}")
        
        logger.debug(f"header_file_to_old_id: {header_file_to_old_id}")
        logger.debug(f"footer_file_to_old_id: {footer_file_to_old_id}")
        
        # Relationships to headers (skip .rels files)
        for part_name in self._parts:
            if 'header' in part_name.lower() and part_name.endswith('.xml') and not part_name.endswith('.rels'):
                header_name = Path(part_name).name
                # Check if relationship already exists (by filename)
                if header_name not in existing_targets:
                    rel_id = self._get_next_rel_id('word/_rels/document.xml.rels')
                    self._relationships['word/_rels/document.xml.rels'].append((
                        rel_id,
                        'http://schemas.openxmlformats.org/officeDocument/2006/relationships/header',
                        header_name,
                        'Internal'
                    ))
                    existing_targets.add(header_name)
                    # Save ID mapping if we found old ID
                    if header_name in header_file_to_old_id:
                        old_id = header_file_to_old_id[header_name]
                        self._header_footer_id_mapping[old_id] = rel_id
                        logger.debug(f"Mapped header ID: {old_id} -> {rel_id} for {header_name}")
                    else:
                        logger.debug(f"No old ID found for header {header_name} in mapping: {header_file_to_old_id}")
                else:
                    logger.debug(f"Header {header_name} already in existing_targets")
        
        # Relationships to footers (skip .rels files)
        for part_name in self._parts:
            if 'footer' in part_name.lower() and part_name.endswith('.xml') and not part_name.endswith('.rels'):
                footer_name = Path(part_name).name
                # Check if relationship already exists (by filename)
                if footer_name not in existing_targets:
                    rel_id = self._get_next_rel_id('word/_rels/document.xml.rels')
                    self._relationships['word/_rels/document.xml.rels'].append((
                        rel_id,
                        'http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer',
                        footer_name,
                        'Internal'
                    ))
                    existing_targets.add(footer_name)
                    # Save ID mapping if we found old ID
                    if footer_name in footer_file_to_old_id:
                        old_id = footer_file_to_old_id[footer_name]
                        self._header_footer_id_mapping[old_id] = rel_id
                        logger.debug(f"Mapped footer ID: {old_id} -> {rel_id} for {footer_name}")
                    else:
                        logger.debug(f"No old ID found for footer {footer_name} in mapping: {footer_file_to_old_id}")
                else:
                    logger.debug(f"Footer {footer_name} already in existing_targets")
        
        logger.debug(f"Final header_footer_id_mapping: {self._header_footer_id_mapping}")
        
        # Relacje do media (obrazy)
        for media_name in self._media:
            if media_name not in existing_targets:
                rel_id = self._get_next_rel_id('word/_rels/document.xml.rels')
                # In document.xml relationships use relative path
                # If media_name is "word/media/image.png", target is "media/image.png"
                if media_name.startswith('word/'):
                    media_target = media_name[5:]  # Remove "word/"
                else:
                    media_target = media_name
                self._relationships['word/_rels/document.xml.rels'].append((
                    rel_id,
                    'http://schemas.openxmlformats.org/officeDocument/2006/relationships/image',
                    media_target,
                    'Internal'
                ))
        
        # 3. Relationships for headers/footers (if exist)
        for part_name in self._parts:
            if 'header' in part_name.lower() or 'footer' in part_name.lower():
                rels_path = self._get_relationship_path(part_name)
                if rels_path not in self._relationships:
                    self._relationships[rels_path] = []
                    
                    # Skopiuj relacje z oryginalnego dokumentu
                    if hasattr(self.document, '_package_reader'):
                        package_reader = self.document._package_reader
                        if hasattr(package_reader, 'relationships'):
                            # Determine source name for header/footer
                            source_name = Path(part_name).stem
                            hf_rels = package_reader.relationships.get(source_name, [])
                            for rel in hf_rels:
                                rel_type = rel.get('Type', '')
                                target = rel.get('Target', '')
                                target_mode = rel.get('TargetMode', 'Internal')
                                
                                if target in self._parts or target in self._media:
                                    rel_id = self._get_next_rel_id(rels_path)
                                    self._relationships[rels_path].append((
                                        rel_id, rel_type, target, target_mode
                                    ))
    
    def _update_sectpr_ids(self) -> None:
        """Aktualizuje ID w sectPr w document.xml na podstawie mapowania ID."""
        if not self._header_footer_id_mapping or 'word/document.xml' not in self._parts:
            logger.debug(f"No mapping to update: mapping={self._header_footer_id_mapping}, has_doc={'word/document.xml' in self._parts}")
            return
        
        try:
            import xml.etree.ElementTree as ET
            
            # Parsuj document.xml
            document_xml = self._parts['word/document.xml'].decode('utf-8')
            root = ET.fromstring(document_xml)
            
            # Find all sectPr in document (can be in different places)
            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            all_sect_prs = root.findall('.//w:sectPr', ns)
            
            if all_sect_prs:
                updated_count = 0
                for sect_pr in all_sect_prs:
                    # Zaktualizuj ID w headerReference
                    for header_ref in sect_pr.findall('w:headerReference', ns):
                        old_id = header_ref.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
                        if old_id and old_id in self._header_footer_id_mapping:
                            new_id = self._header_footer_id_mapping[old_id]
                            header_ref.set('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id', new_id)
                            updated_count += 1
                            logger.debug(f"Updated headerReference ID: {old_id} -> {new_id}")
                        elif old_id:
                            logger.debug(f"HeaderReference ID {old_id} not found in mapping: {self._header_footer_id_mapping}")
                    
                    # Zaktualizuj ID w footerReference
                    for footer_ref in sect_pr.findall('w:footerReference', ns):
                        old_id = footer_ref.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
                        if old_id and old_id in self._header_footer_id_mapping:
                            new_id = self._header_footer_id_mapping[old_id]
                            footer_ref.set('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id', new_id)
                            updated_count += 1
                            logger.debug(f"Updated footerReference ID: {old_id} -> {new_id}")
                        elif old_id:
                            logger.debug(f"FooterReference ID {old_id} not found in mapping: {self._header_footer_id_mapping}")
                
                if updated_count > 0:
                    # Zaktualizuj document.xml
                    self._parts['word/document.xml'] = ET.tostring(root, encoding='utf-8', xml_declaration=True)
                    logger.debug(f"Updated {updated_count} IDs in {len(all_sect_prs)} sectPr elements")
        except Exception as e:
            logger.warning(f"Failed to update sectPr IDs: {e}")
            import traceback
            logger.debug(traceback.format_exc())
    
    def _prepare_content_types(self) -> None:
        """Przygotowuje [Content_Types].xml."""
        # Default content types (only if not loaded from template)
        if not self._default_content_types:
            default_types = {
                'rels': 'application/vnd.openxmlformats-package.relationships+xml',
                'xml': 'application/xml',
                'png': 'image/png',
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg',
                'gif': 'image/gif',
                'bmp': 'image/bmp',
            }
            
            # Add default types for extensions
            for ext, content_type in default_types.items():
                self._default_content_types[ext] = content_type
        
        # Add default types to _content_types with *. prefix for _generate_content_types_xml
        for ext, content_type in self._default_content_types.items():
            self._content_types[f'*.{ext}'] = content_type
    
    def _write_package(self, output_path: Path) -> None:
        """Zapisuje pakiet DOCX do pliku ZIP."""
        # Collect all files to save (without duplicates)
        files_to_write = {}
        
        # 1. [Content_Types].xml (zawsze nadpisujemy)
        content_types_xml = self._generate_content_types_xml()
        files_to_write['[Content_Types].xml'] = content_types_xml
        
        # 2. Main relationships
        if '_rels/.rels' in self._relationships:
            rels_xml = self._generate_relationships_xml(self._relationships['_rels/.rels'])
            files_to_write['_rels/.rels'] = rels_xml
        
        # 3. Parts - override if already exist
        for part_name, content in self._parts.items():
            files_to_write[part_name] = content
        
        # 4. Media
        for media_name, content in self._media.items():
            files_to_write[media_name] = content
        
        # 5. Relationships for parts
        for rels_path, rels in self._relationships.items():
            if rels_path != '_rels/.rels' and rels:  # Main relationships already saved
                rels_xml = self._generate_relationships_xml(rels)
                files_to_write[rels_path] = rels_xml
        
        # Save everything to ZIP (without duplicates)
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_name, content in files_to_write.items():
                zip_file.writestr(file_name, content)
    
    def _generate_content_types_xml(self) -> bytes:
        """Generuje [Content_Types].xml."""
        # Register namespace to avoid ns0: prefixes
        ET.register_namespace('', 'http://schemas.openxmlformats.org/package/2006/content-types')
        
        root = ET.Element('{http://schemas.openxmlformats.org/package/2006/content-types}Types')
        
        # Add default types
        default_extensions: Set[str] = set()
        for part_name, content_type in self._content_types.items():
            if part_name.startswith('*.'):
                ext = part_name[2:]
                default_extensions.add(ext)
                default_elem = ET.SubElement(root, '{http://schemas.openxmlformats.org/package/2006/content-types}Default')
                default_elem.set('Extension', ext)
                default_elem.set('ContentType', content_type)
        
        # Add override for parts from self._content_types
        for part_name, content_type in self._content_types.items():
            if not part_name.startswith('*.'):
                override_elem = ET.SubElement(root, '{http://schemas.openxmlformats.org/package/2006/content-types}Override')
                override_elem.set('PartName', f'/{part_name}')
                override_elem.set('ContentType', content_type)
        
        # Add override for all files in self._parts and self._media that are not yet in self._content_types
        # (ensures all files, including docProps/, are in [Content_Types].xml)
        all_parts = set(self._parts.keys()) | set(self._media.keys())
        known_content_types = {name for name in self._content_types.keys() if not name.startswith('*.')}
        
        # Mapping of extensions and paths to content types
        content_type_map = {
            # docProps
            'docProps/app.xml': 'application/vnd.openxmlformats-officedocument.extended-properties+xml',
            'docProps/core.xml': 'application/vnd.openxmlformats-package.core-properties+xml',
            'docProps/custom.xml': 'application/vnd.openxmlformats-officedocument.custom-properties+xml',
            # word
            'word/document.xml': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml',
            'word/styles.xml': 'application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml',
            'word/settings.xml': 'application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml',
            'word/webSettings.xml': 'application/vnd.openxmlformats-officedocument.wordprocessingml.webSettings+xml',
            'word/fontTable.xml': 'application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml',
            'word/theme/theme1.xml': 'application/vnd.openxmlformats-officedocument.theme+xml',
            # Media
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.wmf': 'image/x-wmf',
            '.emf': 'image/x-emf',
        }
        
        for part_name in all_parts:
            if part_name in known_content_types:
                continue  # Already added
            
            # Check path mapping
            content_type = None
            if part_name in content_type_map:
                content_type = content_type_map[part_name]
            else:
                # Check extension
                ext = Path(part_name).suffix.lower()
                if ext in content_type_map:
                    content_type = content_type_map[ext]
                elif part_name.startswith('word/header') and part_name.endswith('.xml'):
                    content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml'
                elif part_name.startswith('word/footer') and part_name.endswith('.xml'):
                    content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml'
                elif part_name.startswith('_rels/') and part_name.endswith('.rels'):
                    content_type = 'application/vnd.openxmlformats-package.relationships+xml'
                elif part_name.endswith('.xml'):
                    content_type = 'application/xml'
            
            if content_type:
                override_elem = ET.SubElement(root, '{http://schemas.openxmlformats.org/package/2006/content-types}Override')
                override_elem.set('PartName', f'/{part_name}')
                override_elem.set('ContentType', content_type)
        
        # Formatuj XML
        ET.indent(root, space='  ')
        xml_str = ET.tostring(root, encoding='utf-8', xml_declaration=True)
        return xml_str
    
    def _generate_relationships_xml(self, relationships: List[tuple]) -> bytes:
        """Generuje XML relacji."""
        # Register namespace to avoid ns0: prefixes
        ET.register_namespace('', 'http://schemas.openxmlformats.org/package/2006/relationships')
        
        root = ET.Element('{http://schemas.openxmlformats.org/package/2006/relationships}Relationships')
        
        for rel_id, rel_type, target, target_mode in relationships:
            rel_elem = ET.SubElement(root, '{http://schemas.openxmlformats.org/package/2006/relationships}Relationship')
            rel_elem.set('Id', rel_id)
            rel_elem.set('Type', rel_type)
            rel_elem.set('Target', target)
            if target_mode == 'External':
                rel_elem.set('TargetMode', 'External')
        
        # Formatuj XML
        ET.indent(root, space='  ')
        xml_str = ET.tostring(root, encoding='utf-8', xml_declaration=True)
        return xml_str
    
    def _get_next_rel_id(self, source: str) -> str:
        """Generates next relationship ID for source."""
        if source not in self._rel_id_counters:
            self._rel_id_counters[source] = 1
        else:
            self._rel_id_counters[source] += 1
        
        return f"rId{self._rel_id_counters[source]}"
    
    def _get_relationship_path(self, part_name: str) -> str:
        """Determines relationship file path for part."""
        # Example: word/document.xml -> word/_rels/document.xml.rels
        if '/' in part_name:
            dir_part = '/'.join(part_name.split('/')[:-1])
            file_part = part_name.split('/')[-1]
            return f"{dir_part}/_rels/{file_part}.rels"
        else:
            return f"_rels/{part_name}.rels"
    
    def _generate_styles_xml(self) -> Optional[str]:
        """

        Generates styles.xml from document models using StyleNormalizer.

        """
        try:
            from ..normalize import StyleNormalizer
            
            # Get original styles.xml if exists
            original_styles_xml = None
            if hasattr(self.document, '_package_reader') and self.document._package_reader:
                package_reader = self.document._package_reader
                original_styles_xml = package_reader.get_xml_content('word/styles.xml')
            
            # For documents from JSON, try to get styles from source_docx first
            if not original_styles_xml and hasattr(self.document, '_source_docx') and self.document._source_docx:
                from ..parser.package_reader import PackageReader
                try:
                    source_reader = PackageReader(self.document._source_docx)
                    original_styles_xml = source_reader.get_xml_content('word/styles.xml')
                    logger.debug(f"Loaded styles.xml from source_docx: {self.document._source_docx}")
                except Exception as e:
                    logger.warning(f"Failed to load styles.xml from source_docx: {e}")
            
            # For documents with original styles.xml (not from JSON), just return it as-is
            # to preserve all styles including list styles, character styles etc.
            if original_styles_xml and hasattr(self.document, '_package_reader') and self.document._package_reader:
                # Document loaded from DOCX - return original styles.xml
                return original_styles_xml
            
            # For documents from JSON (source_docx), also return original styles
            if original_styles_xml and hasattr(self.document, '_source_docx') and self.document._source_docx:
                return original_styles_xml
            
            # Only for new documents without original styles, generate styles.xml
            # Create StyleNormalizer
            style_normalizer = StyleNormalizer(original_styles_xml)
            
            # Zarejestruj wszystkie paragrafy i runy z dokumentu
            body = self._get_body()
            if body:
                paragraphs = self._get_paragraphs(body)
                
                # Get numbering parser if available
                numbering_parser = None
                if hasattr(self.document, 'parser') and hasattr(self.document.parser, 'numbering_parser'):
                    numbering_parser = self.document.parser.numbering_parser
                
                for para in paragraphs:
                    style_normalizer.register_paragraph(para, numbering_parser)
                    
                    # Zarejestruj runy
                    runs = self._get_runs(para)
                    for run in runs:
                        style_normalizer.register_run(run)
            
            # Generate XML with all registered styles
            if style_normalizer.has_custom_styles():
                return style_normalizer.to_xml(None)  # Return all styles
            else:
                # If no custom styles and no original XML, return None
                return None
                
        except Exception as e:
            logger.warning(f"Failed to generate styles.xml: {e}")
            # Fallback: use original styles.xml
            if hasattr(self.document, '_package_reader'):
                package_reader = self.document._package_reader
                return package_reader.get_xml_content('word/styles.xml')
            return None
    
    def _generate_numbering_xml(self) -> Optional[str]:
        """

        Generates numbering.xml from document models using NumberingNormalizer.

        """
        try:
            from ..normalize import NumberingNormalizer
            
            # Pobierz numbering parser
            numbering_parser = None
            if hasattr(self.document, 'parser') and hasattr(self.document.parser, 'numbering_parser'):
                numbering_parser = self.document.parser.numbering_parser
            
            if not numbering_parser:
                # Check if document has paragraphs with numbering (e.g. created from JSON)
                body = self._get_body()
                has_numbering = False
                if body:
                    paragraphs = self._get_paragraphs(body)
                    for para in paragraphs:
                        if hasattr(para, 'numbering') and para.numbering:
                            has_numbering = True
                            break
                
                if has_numbering:
                    # Dokument ma numbering, ale nie ma parsera - wygeneruj podstawowy numbering.xml
                    return self._generate_basic_numbering_xml()
                
                # Fallback: use original numbering.xml
                if hasattr(self.document, '_package_reader'):
                    package_reader = self.document._package_reader
                    return package_reader.get_xml_content('word/numbering.xml')
                return None
            
            # Get original numbering.xml if exists
            original_numbering_xml = None
            if hasattr(self.document, '_package_reader'):
                package_reader = self.document._package_reader
                original_numbering_xml = package_reader.get_xml_content('word/numbering.xml')
            
            # Create NumberingNormalizer
            numbering_normalizer = NumberingNormalizer(numbering_parser, original_numbering_xml)
            
            # Register all paragraphs with numbering
            body = self._get_body()
            if body:
                paragraphs = self._get_paragraphs(body)
                for para in paragraphs:
                    numbering_normalizer.register_paragraph(para)
            
            # Generate XML only if there is custom numbering
            if numbering_normalizer.has_custom_numbering():
                return numbering_normalizer.to_xml()
            else:
                # Return original XML if no custom numbering
                return original_numbering_xml
                
        except Exception as e:
            logger.warning(f"Failed to generate numbering.xml: {e}")
            # Fallback: use original numbering.xml
            if hasattr(self.document, '_package_reader'):
                package_reader = self.document._package_reader
                return package_reader.get_xml_content('word/numbering.xml')
            return None
    
    def _generate_basic_numbering_xml(self) -> Optional[str]:
        """

        Generates basic numbering.xml for documents created from JSON.

        """
        try:
            import xml.etree.ElementTree as ET
            
            # Collect all unique numbering IDs from paragraphs
            body = self._get_body()
            numbering_ids = {}
            if body:
                paragraphs = self._get_paragraphs(body)
                for para in paragraphs:
                    if hasattr(para, 'numbering') and para.numbering:
                        num_info = para.numbering
                        if isinstance(num_info, dict):
                            num_id = str(num_info.get('id', '0'))
                            level = str(num_info.get('level', '0'))
                        else:
                            num_id = str(getattr(num_info, 'id', '0'))
                            level = str(getattr(num_info, 'level', '0'))
                        
                        if num_id and num_id != '0':
                            if num_id not in numbering_ids:
                                numbering_ids[num_id] = set()
                            numbering_ids[num_id].add(level)
            
            if not numbering_ids:
                return None
            
            # Create basic numbering.xml
            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            root = ET.Element('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}numbering')
            
            # For each numbering ID, create abstractNum and num
            abstract_num_id = 0
            for num_id, levels in numbering_ids.items():
                # Abstract numbering
                abstract_num = ET.SubElement(root, f'{{{ns["w"]}}}abstractNum')
                abstract_num.set(f'{{{ns["w"]}}}abstractNumId', str(abstract_num_id))
                
                # For each level, create lvl
                for level in sorted(levels, key=int):
                    lvl = ET.SubElement(abstract_num, f'{{{ns["w"]}}}lvl')
                    lvl.set(f'{{{ns["w"]}}}ilvl', str(level))
                    
                    # Podstawowy format - decimal
                    numFmt = ET.SubElement(lvl, f'{{{ns["w"]}}}numFmt')
                    numFmt.set(f'{{{ns["w"]}}}val', 'decimal')
                    
                    # Start value
                    start = ET.SubElement(lvl, f'{{{ns["w"]}}}start')
                    start.set(f'{{{ns["w"]}}}val', '1')
                    
                    # Text format
                    lvlText = ET.SubElement(lvl, f'{{{ns["w"]}}}lvlText')
                    lvlText.set(f'{{{ns["w"]}}}val', '%1.')
                
                # Numbering instance
                num = ET.SubElement(root, f'{{{ns["w"]}}}num')
                num.set(f'{{{ns["w"]}}}numId', num_id)
                abNumId = ET.SubElement(num, f'{{{ns["w"]}}}abstractNumId')
                abNumId.set(f'{{{ns["w"]}}}val', str(abstract_num_id))
                
                abstract_num_id += 1
            
            # Formatuj XML
            ET.indent(root, space='  ')
            xml_str = ET.tostring(root, encoding='utf-8', xml_declaration=True)
            return xml_str.decode('utf-8')
            
        except Exception as e:
            logger.warning(f"Failed to generate basic numbering.xml: {e}")
            return None
    
    def _get_body(self) -> Optional[Any]:
        """Pobiera body z dokumentu."""
        if hasattr(self.document, '_body'):
            return self.document._body
        elif hasattr(self.document, 'body'):
            return self.document.body
        elif hasattr(self.document, 'get_body'):
            return self.document.get_body()
        return None
    
    def _get_paragraphs(self, body: Any) -> List[Any]:
        """Pobiera paragrafy z body."""
        if hasattr(body, 'children'):
            return [child for child in body.children if hasattr(child, 'runs')]
        elif hasattr(body, 'paragraphs'):
            return body.paragraphs
        return []
    
    def _get_runs(self, paragraph: Any) -> List[Any]:
        """Pobiera runy z paragrafu."""
        if hasattr(paragraph, 'runs'):
            return paragraph.runs
        elif hasattr(paragraph, 'children'):
            return [child for child in paragraph.children if hasattr(child, 'text')]
        return []
    
    def _get_images(self, body: Any) -> List[Any]:
        """Pobiera obrazy z body."""
        if hasattr(body, 'images'):
            return body.images
        elif hasattr(body, 'children'):
            return [child for child in body.children if hasattr(child, 'path') or hasattr(child, 'rel_id')]
        return []
    
    def _prepare_media(self) -> None:
        """

        Prepares media (images) - copies existing and finds new.

        """
        # 1. Copy existing media from original document
        if hasattr(self.document, '_package_reader'):
            package_reader = self.document._package_reader
            # Get all image relationships
            if hasattr(package_reader, 'relationships'):
                for source, rels in package_reader.relationships.items():
                    # Handle different relationship formats
                    # Format 1: Dict[str, Dict] (rel_id -> rel_data)
                    # Format 2: List[Dict] (list of relationships)
                    rel_list = []
                    if isinstance(rels, dict):
                        # Convert dict format to list format
                        rel_list = list(rels.values())
                    elif isinstance(rels, list):
                        rel_list = rels
                    else:
                        continue
                    
                    for rel in rel_list:
                        # Handle both dict formats: {'Type': ...} or {'type': ...}
                        rel_type = rel.get('Type', '') or rel.get('type', '')
                        target = rel.get('Target', '') or rel.get('target', '')
                        
                        # Check if this is relationship to image
                        if 'image' in rel_type.lower() or target.startswith('media/'):
                            # Get image content
                            try:
                                img_data = package_reader.get_binary_content(target)
                                if img_data:
                                    self._media[target] = img_data
                                    # Determine content type based on extension
                                    ext = Path(target).suffix.lower()
                                    content_type_map = {
                                        '.png': 'image/png',
                                        '.jpg': 'image/jpeg',
                                        '.jpeg': 'image/jpeg',
                                        '.gif': 'image/gif',
                                        '.bmp': 'image/bmp',
                                    }
                                    self._content_types[target] = content_type_map.get(ext, 'image/png')
                            except Exception as e:
                                logger.warning(f"Failed to copy media {target}: {e}")
        
        # 1b. If document has no _package_reader (e.g. created from JSON), check images...
        # First try to copy media from source_docx if available
        # Also copy media from template_path if it's original DOCX
        source_docx_path = None
        if hasattr(self.document, '_source_docx') and self.document._source_docx:
            source_docx_path = self.document._source_docx
        elif self.template_path and self.template_path.exists() and self.template_path != self.TEMPLATE_PATH:
            # If template_path is original DOCX (not new_doc.docx), use it as source
            source_docx_path = self.template_path
        
        if source_docx_path:
            try:
                import zipfile
                with zipfile.ZipFile(source_docx_path, 'r') as z:
                    # Skopiuj wszystkie pliki z word/media/
                    for file_name in z.namelist():
                        if 'word/media/' in file_name and not file_name.endswith('/'):
                            try:
                                media_data = z.read(file_name)
                                # Add with full path (word/media/...)
                                self._media[file_name] = media_data
                                # Determine content type
                                ext = Path(file_name).suffix.lower()
                                content_type_map = {
                                    '.png': 'image/png',
                                    '.jpg': 'image/jpeg',
                                    '.jpeg': 'image/jpeg',
                                    '.gif': 'image/gif',
                                    '.bmp': 'image/bmp',
                                    '.wmf': 'image/x-wmf',
                                    '.emf': 'image/x-emf',
                                }
                                self._content_types[file_name] = content_type_map.get(ext, 'image/png')
                                logger.debug(f"Copied media from source DOCX: {file_name}")
                            except Exception as e:
                                logger.warning(f"Failed to copy media {file_name} from source DOCX: {e}")
            except Exception as e:
                logger.warning(f"Failed to open source DOCX for media copying: {e}")
        
        if not hasattr(self.document, '_package_reader') or not self.document._package_reader:
            # Check if document has body with images
            body = self._get_body()
            if body:
                images = self._get_images(body)
                for image in images:
                    # Check if image has path and data
                    img_path = None
                    img_data = None
                    rel_id = None
                    
                    if hasattr(image, 'path') and image.path:
                        img_path = image.path
                        # Try to read file if path exists
                        try:
                            from pathlib import Path as PathLib
                            path_obj = PathLib(img_path)
                            if path_obj.exists():
                                img_data = path_obj.read_bytes()
                        except Exception:
                            pass
                    
                    if hasattr(image, 'rel_id') and image.rel_id:
                        rel_id = image.rel_id
                    
                    # If we have path and data, add to media
                    if img_path and img_data:
                        # Normalize path (must be in word/media/... format)
                        if not img_path.startswith('word/'):
                            if 'media' in img_path:
                                # Extract only media part
                                media_part = img_path.split('media/')[-1] if 'media/' in img_path else Path(img_path).name
                                img_path = f'word/media/{media_part}'
                            else:
                                img_path = f'word/media/{Path(img_path).name}'
                        
                        self._media[img_path] = img_data
                        
                        # Determine content type
                        ext = Path(img_path).suffix.lower()
                        content_type_map = {
                            '.png': 'image/png',
                            '.jpg': 'image/jpeg',
                            '.jpeg': 'image/jpeg',
                            '.gif': 'image/gif',
                            '.bmp': 'image/bmp',
                            '.wmf': 'image/x-wmf',
                            '.emf': 'image/x-emf',
                        }
                        self._content_types[img_path] = content_type_map.get(ext, 'image/png')
                        
                        # Add relationship
                        rels_path = 'word/_rels/document.xml.rels'
                        if rels_path not in self._relationships:
                            self._relationships[rels_path] = []
                        
                        if not rel_id:
                            rel_id = self._get_next_rel_id(rels_path)
                        
                        rel_type = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/image'
                        self._relationships[rels_path].append((
                            rel_id, rel_type, img_path, 'Internal'
                        ))
        
        # 2. Find new images in documents (added by PlaceholderEngine or API)
        # Przeszukaj document.xml XML dla r:embed i r:link
        document_xml_str = self._parts.get('word/document.xml', b'').decode('utf-8', errors='ignore')
        if document_xml_str:
            import re
            # Find all r:embed and r:link in XML
            embed_pattern = r'r:embed="([^"]+)"'
            link_pattern = r'r:link="([^"]+)"'
            
            # Check if there are relationships to images not yet in media
            # To wymaga parsowania document.xml i sprawdzenia relacji
            # For now use simpler approach - check if there are images in models
        
        # 3. Find new images added by PlaceholderEngine or API
        # Check if document has list of new images
        if hasattr(self.document, '_new_images') and self.document._new_images:
            for img_info in self.document._new_images:
                media_path = img_info.get('path', '')
                img_data = img_info.get('data', b'')
                rel_id = img_info.get('rel_id', '')
                
                if media_path and img_data:
                    # Dodaj obraz do media
                    self._media[media_path] = img_data
                    
                    # Determine content type based on extension
                    ext = Path(media_path).suffix.lower()
                    content_type_map = {
                        '.png': 'image/png',
                        '.jpg': 'image/jpeg',
                        '.jpeg': 'image/jpeg',
                        '.gif': 'image/gif',
                        '.bmp': 'image/bmp',
                        '.webp': 'image/webp',
                    }
                    self._content_types[media_path] = content_type_map.get(ext, 'image/png')
                    
                    # Add relationship to document.xml.rels
                    rels_path = 'word/_rels/document.xml.rels'
                    if rels_path not in self._relationships:
                        self._relationships[rels_path] = []
                    
                    # Generate new rel_id if not provided
                    if not rel_id:
                        rel_id = self._get_next_rel_id(rels_path)
                    
                    rel_type = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/image'
                    self._relationships[rels_path].append((
                        rel_id, rel_type, media_path, None
                    ))
                    
                    # Zaktualizuj rel_id w modelu obrazu
                    # Search all runs and update rel_id for images with same part_path
                    body = self._get_body()
                    if body:
                        paragraphs = self._get_paragraphs(body)
                        for para in paragraphs:
                            runs = self._get_runs(para)
                            for run in runs:
                                if hasattr(run, 'image') and run.image:
                                    img = run.image
                                    if hasattr(img, 'part_path') and img.part_path == media_path:
                                        img.rel_id = rel_id
                    
                    logger.debug(f"Added new image to media: {media_path} with rel_id {rel_id}")
    
    def _use_relationship_merger_for_parts(self) -> None:
        """

        Uses RelationshipMerger for relationship management during export.

        """
        if not self.relationship_merger:
            return
        
        try:
            # Update relationships using RelationshipMerger
            # RelationshipMerger already has copied parts and relationships in its internal structures...
            
            # 1. Update relationships for parts using RelationshipMerger
            # RelationshipMerger przechowuje zaktualizowane relacje w _relationships_to_write
            if hasattr(self.relationship_merger, '_relationships_to_write'):
                for rels_path, rels_list in self.relationship_merger._relationships_to_write.items():
                    # Konwertuj format RelationshipMerger do formatu DOCXExporter
                    # RelationshipMerger uses Dict[str, str], DOCXExporter uses List[tuple]
                    converted_rels = []
                    for rel in rels_list:
                        rel_id = rel.get('Id', '')
                        rel_type = rel.get('Type', '')
                        target = rel.get('Target', '')
                        target_mode = rel.get('TargetMode', 'Internal')
                        converted_rels.append((rel_id, rel_type, target, target_mode))
                    
                    # Zaktualizuj relacje w DOCXExporter
                    if converted_rels:
                        self._relationships[rels_path] = converted_rels
            
            # 2. Update content types using RelationshipMerger
            if hasattr(self.relationship_merger, '_content_types_to_write'):
                for part_name, content_type in self.relationship_merger._content_types_to_write.items():
                    self._content_types[part_name] = content_type
            
            # 3. Update parts using RelationshipMerger
            if hasattr(self.relationship_merger, '_copied_parts_data'):
                for part_name, content in self.relationship_merger._copied_parts_data.items():
                    # Check if part wasn't already added by _prepare_parts
                    if part_name not in self._parts:
                        self._parts[part_name] = content
            
            logger.debug("RelationshipMerger integration completed")
            
        except Exception as e:
            logger.warning(f"Failed to use RelationshipMerger for parts: {e}")
            # Fallback: kontynuuj bez RelationshipMerger

