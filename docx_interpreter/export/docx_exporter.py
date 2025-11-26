"""
DOCX exporter - tworzy pliki DOCX z modeli dokumentów.

Wykorzystuje XMLExporter do generowania WordML XML i pakuje wszystko
do pakietu DOCX (ZIP) z relacjami i [Content_Types].xml.
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
    Eksporter DOCX - tworzy pliki DOCX z modeli dokumentów.
    
    Wykorzystuje XMLExporter do generowania WordML XML i pakuje wszystko
    do pakietu DOCX (ZIP) z relacjami i [Content_Types].xml.
    
    Używa pustego szablonu (new_doc.docx) jako podstawy i uzupełnia go zawartością.
    """
    
    # Ścieżka do szablonu pustego dokumentu
    TEMPLATE_PATH = Path(__file__).parent / "new_doc.docx"
    
    def __init__(
        self, 
        document: Any, 
        use_relationship_merger: bool = True, 
        template_path: Optional[Union[str, Path]] = None,
        source_docx_path: Optional[Union[str, Path]] = None
    ):
        """
        Inicjalizuje eksporter DOCX.
        
        Args:
            document: Dokument do eksportu (z PackageReader lub model)
            use_relationship_merger: Czy używać RelationshipMerger do zarządzania relacjami
            template_path: Opcjonalna ścieżka do szablonu DOCX (nadpisuje source_docx_path)
            source_docx_path: Opcjonalna ścieżka do źródłowego DOCX (używana jako szablon jeśli istnieje)
        """
        self.document = document
        self.xml_exporter = XMLExporter(document)
        self.use_relationship_merger = use_relationship_merger
        
        # Priorytet wyboru szablonu:
        # 1. template_path (jeśli podano - najwyższy priorytet)
        # 2. source_docx_path (jeśli istnieje - używamy oryginalnego DOCX jako szablonu, kopiujemy WSZYSTKIE pliki)
        # 3. TEMPLATE_PATH (domyślny new_doc.docx dla nowych dokumentów)
        if template_path:
            self.template_path = Path(template_path)
        elif source_docx_path and Path(source_docx_path).exists():
            # Użyj oryginalnego DOCX jako szablonu (dla round-trip: JSON → DOCX)
            # Kopiujemy WSZYSTKIE pliki z niego (oprócz document.xml, który generujemy)
            self.template_path = Path(source_docx_path)
        else:
            # Użyj domyślnego szablonu (dla nowych dokumentów)
            self.template_path = self.TEMPLATE_PATH
        
        # Części pakietu (part_name -> content)
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
        
        # RelationshipMerger dla zaawansowanego zarządzania relacjami
        self.relationship_merger = None
        if self.use_relationship_merger and hasattr(document, '_package_reader'):
            try:
                from ..merger.relationship_merger import RelationshipMerger
                # Utwórz mock target_reader (używamy tego samego dokumentu jako target)
                # W rzeczywistości RelationshipMerger będzie zarządzał relacjami podczas eksportu
                self.relationship_merger = RelationshipMerger(
                    target_package_reader=document._package_reader,
                    source_package_reader=document._package_reader
                )
            except Exception as e:
                logger.warning(f"Failed to initialize RelationshipMerger: {e}")
                self.relationship_merger = None
        
        logger.debug("DOCXExporter initialized")
    
    def _get_package_reader(self):
        """Pobiera package_reader z różnych możliwych lokalizacji."""
        if hasattr(self.document, '_package_reader') and self.document._package_reader:
            return self.document._package_reader
        elif hasattr(self.document, 'parser') and hasattr(self.document.parser, 'package_reader'):
            return self.document.parser.package_reader
        return None
    
    def export(self, output_path: Union[str, Path]) -> bool:
        """
        Eksportuje dokument do pliku DOCX.
        
        Używa pustego szablonu (new_doc.docx) jako podstawy i uzupełnia go zawartością.
        
        Args:
            output_path: Ścieżka do pliku wyjściowego DOCX
            
        Returns:
            True jeśli eksport się powiódł
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 0. Załaduj szablon (jeśli istnieje)
            self._load_template()
            
            # 1. Przygotuj części pakietu (nadpisze document.xml, doda nowe pliki)
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
        """Ładuje szablon DOCX jako podstawę dla eksportu."""
        if not self.template_path.exists():
            logger.warning(f"Template not found: {self.template_path}, creating DOCX from scratch")
            return
        
        try:
            # Otwórz szablon jako ZIP
            with zipfile.ZipFile(self.template_path, 'r') as template_zip:
                # Skopiuj wszystkie pliki z szablonu
                # WAŻNE: Jeśli używamy oryginalnego DOCX jako szablonu, kopiuj WSZYSTKIE pliki
                # (oprócz document.xml, który zostanie wygenerowany)
                for item in template_zip.namelist():
                    # Pomiń document.xml - zostanie wygenerowany
                    if item == 'word/document.xml':
                        continue
                    
                    # Skopiuj plik z szablonu
                    try:
                        content = template_zip.read(item)
                        self._parts[item] = content
                        
                        # Określ content type na podstawie rozszerzenia
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
                                # Relacje - zachowaj z szablonu jako podstawę
                                # _prepare_relationships doda nowe relacje, ale zachowa istniejące
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
                        
                        # Skopiuj też content types z [Content_Types].xml
                        if item == '[Content_Types].xml':
                            try:
                                ct_xml = ET.fromstring(content)
                                for override in ct_xml.findall('.//{http://schemas.openxmlformats.org/package/2006/content-types}Override'):
                                    part_name = override.get('PartName')
                                    content_type = override.get('ContentType')
                                    if part_name and content_type:
                                        # Usuń leading slash jeśli jest
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
        """Przygotowuje części pakietu (document.xml, styles.xml, etc.)."""
        # 1. Generuj document.xml używając XMLExporter
        document_xml = self.xml_exporter.regenerate_wordml(self.document)
        self._parts['word/document.xml'] = document_xml.encode('utf-8')
        self._content_types['word/document.xml'] = (
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'
        )
        
        # 2. Generuj styles.xml z modeli (używa StyleNormalizer z normalize.py)
        styles_xml = self._generate_styles_xml()
        if styles_xml:
            self._parts['word/styles.xml'] = styles_xml.encode('utf-8')
            self._content_types['word/styles.xml'] = (
                'application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml'
            )
        
        # 3. Generuj numbering.xml z modeli (używa NumberingNormalizer z normalize.py)
        # Tylko jeśli nie został już załadowany z szablonu
        if 'word/numbering.xml' not in self._parts:
            numbering_xml = self._generate_numbering_xml()
            if numbering_xml:
                self._parts['word/numbering.xml'] = numbering_xml.encode('utf-8')
                self._content_types['word/numbering.xml'] = (
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml'
                )
        
        # 4. Kopiuj settings.xml jeśli istnieje (tylko jeśli nie został już załadowany z szablonu)
        if 'word/settings.xml' not in self._parts:
            if hasattr(self.document, '_package_reader'):
                package_reader = self.document._package_reader
                settings_xml = package_reader.get_xml_content('word/settings.xml')
                if settings_xml:
                    self._parts['word/settings.xml'] = settings_xml.encode('utf-8')
                    self._content_types['word/settings.xml'] = (
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml'
                    )
        
        # 5. Kopiuj media (obrazy) jeśli istnieją i znajdź nowe obrazy w dokumentach
        self._prepare_media()
        
        # 6. Użyj RelationshipMerger do zarządzania relacjami jeśli dostępny
        if self.relationship_merger:
            self._use_relationship_merger_for_parts()
        
        # 7. Kopiuj headers i footers jeśli istnieją
        # Najpierw z oryginalnego dokumentu (jeśli istnieje)
        if hasattr(self.document, '_package_reader'):
            package_reader = self.document._package_reader
            # Sprawdź relacje headers/footers w document.xml.rels
            if hasattr(package_reader, 'relationships'):
                doc_rels = package_reader.relationships.get('document', [])
                for rel in doc_rels:
                    rel_type = rel.get('Type', '')
                    target = rel.get('Target', '')
                    
                    if 'header' in rel_type.lower() or 'footer' in rel_type.lower():
                        # Pobierz zawartość header/footer
                        try:
                            hf_xml = package_reader.get_xml_content(target)
                            if hf_xml:
                                self._parts[target] = hf_xml.encode('utf-8')
                                if 'header' in target.lower():
                                    self._content_types[target] = (
                                        'application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml'
                                    )
                                else:
                                    self._content_types[target] = (
                                        'application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml'
                                    )
                        except Exception as e:
                            logger.warning(f"Failed to copy header/footer {target}: {e}")
        
        # Jeśli dokument nie ma _package_reader (np. utworzony z JSON), sprawdź headers/footers w modelu
        if not hasattr(self.document, '_package_reader') or not self.document._package_reader:
            # Sprawdź czy dokument ma headers/footers w modelu
            # Headers/footers mogą być w różnych miejscach w zależności od struktury modelu
            headers_dict = {}
            footers_dict = {}
            
            # Sprawdź różne możliwe lokalizacje headers/footers
            # Najpierw sprawdź bezpośrednio w document (może być SimpleNamespace z to_document_model)
            if hasattr(self.document, 'headers'):
                headers_dict = self.document.headers if isinstance(self.document.headers, dict) else {}
            elif hasattr(self.document, '_headers'):
                headers_dict = self.document._headers if isinstance(self.document._headers, dict) else {}
            # Sprawdź w _model (jeśli document to Document API)
            elif hasattr(self.document, '_model') and hasattr(self.document._model, 'headers'):
                headers_dict = self.document._model.headers if isinstance(self.document._model.headers, dict) else {}
            # Sprawdź bezpośrednio w document (jeśli document to model z to_document_model)
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
                    # Utwórz prosty model header z listą elementów
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
                    # Utwórz prosty model footer z listą elementów
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
        """Przygotowuje relacje dla wszystkich części."""
        # 1. Główne relacje (_rels/.rels) - zachowaj z szablonu jeśli istnieją
        if '_rels/.rels' not in self._relationships:
            self._relationships['_rels/.rels'] = []
        
        # Dodaj relację do document.xml
        doc_rel_id = self._get_next_rel_id('_rels/.rels')
        self._relationships['_rels/.rels'].append((
            doc_rel_id,
            'http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument',
            'word/document.xml',
            'Internal'
        ))
        
        # 2. Relacje document.xml (word/_rels/document.xml.rels)
        self._relationships['word/_rels/document.xml.rels'] = []
        
        # Zbiór targetów, które już mają relacje (aby uniknąć duplikatów)
        existing_rel_targets = set()
        
        # Najpierw skopiuj relacje z oryginalnego dokumentu jeśli istnieją
        package_reader = self._get_package_reader()
        if package_reader and hasattr(package_reader, 'relationships'):
                doc_rels = package_reader.relationships.get('document', [])
                # doc_rels może być listą lub słownikiem
                if isinstance(doc_rels, dict):
                    # Jeśli to słownik, iteruj przez wartości (lub items, aby mieć dostęp do ID)
                    rels_iter = doc_rels.items()
                else:
                    # Jeśli to lista, iteruj bezpośrednio
                    rels_iter = enumerate(doc_rels) if isinstance(doc_rels, list) else []
                
                for rel_key, rel in rels_iter:
                    # Jeśli rel_key to ID (string), użyj go jako old_rel_id
                    old_rel_id_from_key = rel_key if isinstance(rel_key, str) and rel_key.startswith('rId') else None
                    
                    # Relacja może być słownikiem lub obiektem
                    if isinstance(rel, dict):
                        rel_type = rel.get('Type', '') or rel.get('type', '')
                        target = rel.get('Target', '') or rel.get('target', '')
                        target_mode = rel.get('TargetMode', 'Internal') or rel.get('target_mode', 'Internal')
                        rel_id_from_rel = rel.get('Id', '') or rel.get('id', '')
                    else:
                        # Jeśli relacja to obiekt, spróbuj pobrać atrybuty
                        rel_type = getattr(rel, 'Type', '') or getattr(rel, 'type', '')
                        target = getattr(rel, 'Target', '') or getattr(rel, 'target', '')
                        target_mode = getattr(rel, 'TargetMode', 'Internal') or getattr(rel, 'target_mode', 'Internal')
                        rel_id_from_rel = getattr(rel, 'Id', '') or getattr(rel, 'id', '')
                    
                    # Użyj ID z klucza lub z relacji
                    old_rel_id = old_rel_id_from_key or rel_id_from_rel
                    
                    # Normalizuj target (usuń leading slash jeśli jest)
                    if target.startswith('/'):
                        target = target[1:]
                    
                    # Sprawdź czy część istnieje w naszym pakiecie
                    # Target może być względny (media/image.png) lub pełny (word/media/image.png)
                    target_exists = False
                    normalized_target = target
                    
                    # Sprawdź bezpośrednio
                    if target in self._parts or target in self._media:
                        target_exists = True
                        normalized_target = target
                    # Sprawdź z prefiksem word/
                    elif not target.startswith('word/'):
                        full_target = f'word/{target}'
                        if full_target in self._parts or full_target in self._media:
                            target_exists = True
                            normalized_target = target  # Zostaw oryginalny target (względny dla relacji)
                    # Sprawdź bez prefiksu word/
                    elif target.startswith('word/'):
                        short_target = target[5:]  # Usuń "word/"
                        if short_target in self._parts or short_target in self._media:
                            target_exists = True
                            normalized_target = short_target  # Użyj krótszej wersji dla relacji
                    
                    # Dla headers/footers, sprawdź też czy istnieje w _parts z różnymi wariantami ścieżki
                    if not target_exists and ('header' in rel_type.lower() or 'footer' in rel_type.lower()):
                        # Sprawdź wszystkie możliwe warianty dla headers/footers
                        variants = [
                            target,
                            f'word/{target}',
                            target.replace('word/', ''),
                        ]
                        for variant in variants:
                            if variant in self._parts:
                                target_exists = True
                                # Dla relacji używamy nazwy pliku (bez ścieżki)
                                normalized_target = Path(target).name
                                break
                    
                    # Dla mediów, sprawdź też czy istnieje w _media z różnymi wariantami ścieżki
                    if not target_exists and ('media' in target or 'image' in rel_type.lower()):
                        # Sprawdź wszystkie możliwe warianty
                        variants = [
                            target,
                            f'word/{target}',
                            target.replace('word/', ''),
                            target if target.startswith('media/') else f'media/{Path(target).name}',
                            f'word/media/{Path(target).name}'
                        ]
                        for variant in variants:
                            if variant in self._media:
                                target_exists = True
                                # Dla relacji używamy oryginalnego target (względnego)
                                # ale sprawdzamy czy media istnieje w _media
                                normalized_target = target  # Zostaw oryginalny target dla relacji
                                break
                        
                        # Jeśli nadal nie znaleziono, sprawdź wszystkie klucze w _media
                        if not target_exists:
                            for media_key in self._media.keys():
                                # Sprawdź czy nazwa pliku się zgadza
                                if Path(media_key).name == Path(target).name:
                                    target_exists = True
                                    normalized_target = target  # Zostaw oryginalny target dla relacji
                                    break
                    
                    if target_exists:
                        # Sprawdź czy relacja już istnieje (używając normalized_target)
                        # Dla headers/footers używamy nazwy pliku (bez ścieżki)
                        check_target = normalized_target
                        if 'header' in rel_type.lower() or 'footer' in rel_type.lower():
                            # Dla headers/footers sprawdzamy po nazwie pliku
                            check_target = Path(normalized_target).name
                        
                        if check_target not in existing_rel_targets:
                            rel_id = self._get_next_rel_id('word/_rels/document.xml.rels')
                            
                            # Dla headers/footers używamy nazwy pliku w relacji
                            rel_target = normalized_target
                            if 'header' in rel_type.lower() or 'footer' in rel_type.lower():
                                rel_target = Path(normalized_target).name
                            
                            self._relationships['word/_rels/document.xml.rels'].append((
                                rel_id, rel_type, rel_target, target_mode
                            ))
                            existing_rel_targets.add(check_target)
                            
                            # Zapisz mapowanie ID dla headers/footers
                            if old_rel_id and ('header' in rel_type.lower() or 'footer' in rel_type.lower()):
                                self._header_footer_id_mapping[old_rel_id] = rel_id
                                logger.debug(f"Mapped {rel_type.split('/')[-1]} ID: {old_rel_id} -> {rel_id} for {rel_target} (target={target}, normalized={normalized_target})")
                        else:
                            logger.debug(f"Skipping duplicate relationship for {check_target}")
                    else:
                        if 'header' in rel_type.lower() or 'footer' in rel_type.lower():
                            logger.debug(f"Target not found for {rel_type.split('/')[-1]}: {target} (normalized: {normalized_target})")
        
        # Dodaj relacje dla części, które są w pakiecie, ale nie mają relacji
        # (np. dla dokumentów utworzonych z JSON)
        existing_targets = {rel[2] for rel in self._relationships['word/_rels/document.xml.rels']}
        
        # Relacja do styles.xml (tylko jeśli nie ma już relacji)
        # Sprawdź zarówno pełną ścieżkę jak i względną
        styles_targets = {'word/styles.xml', 'styles.xml'}
        if 'word/styles.xml' in self._parts and not any(t in existing_targets for t in styles_targets):
            rel_id = self._get_next_rel_id('word/_rels/document.xml.rels')
            self._relationships['word/_rels/document.xml.rels'].append((
                rel_id,
                'http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles',
                'styles.xml',  # W relacjach document.xml używamy względnej ścieżki
                'Internal'
            ))
            existing_targets.add('styles.xml')
        
        # Relacja do numbering.xml
        if 'word/numbering.xml' in self._parts and 'word/numbering.xml' not in existing_targets:
            rel_id = self._get_next_rel_id('word/_rels/document.xml.rels')
            self._relationships['word/_rels/document.xml.rels'].append((
                rel_id,
                'http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering',
                'numbering.xml',  # W relacjach document.xml używamy względnej ścieżki
                'Internal'
            ))
        
        # Relacje do headers - znajdź stare ID z sekcji
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
                        # Znajdź nazwę pliku header na podstawie target w relacjach
                        package_reader = self._get_package_reader()
                        if package_reader and hasattr(package_reader, 'relationships'):
                            doc_rels = package_reader.relationships.get('document', [])
                            # doc_rels może być listą lub słownikiem
                            if isinstance(doc_rels, dict):
                                # Jeśli to słownik, sprawdź bezpośrednio po kluczu (ID)
                                if hdr['id'] in doc_rels:
                                    rel = doc_rels[hdr['id']]
                                    if isinstance(rel, dict):
                                        target = rel.get('Target', '') or rel.get('target', '')
                                    else:
                                        target = getattr(rel, 'Target', '') or getattr(rel, 'target', '')
                                    header_file_to_old_id[Path(target).name] = hdr['id']
                                    logger.debug(f"Found header mapping: {hdr['id']} -> {Path(target).name}")
                            else:
                                # Jeśli to lista, iteruj przez elementy
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
                            # doc_rels może być listą lub słownikiem
                            if isinstance(doc_rels, dict):
                                # Jeśli to słownik, sprawdź bezpośrednio po kluczu (ID)
                                if ftr['id'] in doc_rels:
                                    rel = doc_rels[ftr['id']]
                                    if isinstance(rel, dict):
                                        target = rel.get('Target', '') or rel.get('target', '')
                                    else:
                                        target = getattr(rel, 'Target', '') or getattr(rel, 'target', '')
                                    footer_file_to_old_id[Path(target).name] = ftr['id']
                                    logger.debug(f"Found footer mapping: {ftr['id']} -> {Path(target).name}")
                            else:
                                # Jeśli to lista, iteruj przez elementy
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
        
        # Relacje do headers (pomiń pliki .rels)
        for part_name in self._parts:
            if 'header' in part_name.lower() and part_name.endswith('.xml') and not part_name.endswith('.rels'):
                header_name = Path(part_name).name
                # Sprawdź czy relacja już istnieje (po nazwie pliku)
                if header_name not in existing_targets:
                    rel_id = self._get_next_rel_id('word/_rels/document.xml.rels')
                    self._relationships['word/_rels/document.xml.rels'].append((
                        rel_id,
                        'http://schemas.openxmlformats.org/officeDocument/2006/relationships/header',
                        header_name,
                        'Internal'
                    ))
                    existing_targets.add(header_name)
                    # Zapisz mapowanie ID jeśli znaleźliśmy stare ID
                    if header_name in header_file_to_old_id:
                        old_id = header_file_to_old_id[header_name]
                        self._header_footer_id_mapping[old_id] = rel_id
                        logger.debug(f"Mapped header ID: {old_id} -> {rel_id} for {header_name}")
                    else:
                        logger.debug(f"No old ID found for header {header_name} in mapping: {header_file_to_old_id}")
                else:
                    logger.debug(f"Header {header_name} already in existing_targets")
        
        # Relacje do footers (pomiń pliki .rels)
        for part_name in self._parts:
            if 'footer' in part_name.lower() and part_name.endswith('.xml') and not part_name.endswith('.rels'):
                footer_name = Path(part_name).name
                # Sprawdź czy relacja już istnieje (po nazwie pliku)
                if footer_name not in existing_targets:
                    rel_id = self._get_next_rel_id('word/_rels/document.xml.rels')
                    self._relationships['word/_rels/document.xml.rels'].append((
                        rel_id,
                        'http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer',
                        footer_name,
                        'Internal'
                    ))
                    existing_targets.add(footer_name)
                    # Zapisz mapowanie ID jeśli znaleźliśmy stare ID
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
                # W relacjach document.xml używamy względnej ścieżki
                # Jeśli media_name to "word/media/image.png", to target to "media/image.png"
                if media_name.startswith('word/'):
                    media_target = media_name[5:]  # Usuń "word/"
                else:
                    media_target = media_name
                self._relationships['word/_rels/document.xml.rels'].append((
                    rel_id,
                    'http://schemas.openxmlformats.org/officeDocument/2006/relationships/image',
                    media_target,
                    'Internal'
                ))
        
        # 3. Relacje dla headers/footers (jeśli istnieją)
        for part_name in self._parts:
            if 'header' in part_name.lower() or 'footer' in part_name.lower():
                rels_path = self._get_relationship_path(part_name)
                if rels_path not in self._relationships:
                    self._relationships[rels_path] = []
                    
                    # Skopiuj relacje z oryginalnego dokumentu
                    if hasattr(self.document, '_package_reader'):
                        package_reader = self.document._package_reader
                        if hasattr(package_reader, 'relationships'):
                            # Określ source name dla header/footer
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
            
            # Znajdź wszystkie sectPr w dokumencie (mogą być w różnych miejscach)
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
        # Domyślne typy zawartości (tylko jeśli nie zostały załadowane z szablonu)
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
            
            # Dodaj domyślne typy dla rozszerzeń
            for ext, content_type in default_types.items():
                self._default_content_types[ext] = content_type
        
        # Dodaj domyślne typy do _content_types z prefiksem *. dla _generate_content_types_xml
        for ext, content_type in self._default_content_types.items():
            self._content_types[f'*.{ext}'] = content_type
    
    def _write_package(self, output_path: Path) -> None:
        """Zapisuje pakiet DOCX do pliku ZIP."""
        # Zbierz wszystkie pliki do zapisania (bez duplikatów)
        files_to_write = {}
        
        # 1. [Content_Types].xml (zawsze nadpisujemy)
        content_types_xml = self._generate_content_types_xml()
        files_to_write['[Content_Types].xml'] = content_types_xml
        
        # 2. Główne relacje
        if '_rels/.rels' in self._relationships:
            rels_xml = self._generate_relationships_xml(self._relationships['_rels/.rels'])
            files_to_write['_rels/.rels'] = rels_xml
        
        # 3. Części (parts) - nadpisują jeśli już istnieją
        for part_name, content in self._parts.items():
            files_to_write[part_name] = content
        
        # 4. Media
        for media_name, content in self._media.items():
            files_to_write[media_name] = content
        
        # 5. Relacje dla części
        for rels_path, rels in self._relationships.items():
            if rels_path != '_rels/.rels' and rels:  # Główne relacje już zapisane
                rels_xml = self._generate_relationships_xml(rels)
                files_to_write[rels_path] = rels_xml
        
        # Zapisz wszystko do ZIP (bez duplikatów)
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_name, content in files_to_write.items():
                zip_file.writestr(file_name, content)
    
    def _generate_content_types_xml(self) -> bytes:
        """Generuje [Content_Types].xml."""
        # Rejestruj namespace, aby uniknąć prefiksów ns0:
        ET.register_namespace('', 'http://schemas.openxmlformats.org/package/2006/content-types')
        
        root = ET.Element('{http://schemas.openxmlformats.org/package/2006/content-types}Types')
        
        # Dodaj domyślne typy
        default_extensions: Set[str] = set()
        for part_name, content_type in self._content_types.items():
            if part_name.startswith('*.'):
                ext = part_name[2:]
                default_extensions.add(ext)
                default_elem = ET.SubElement(root, '{http://schemas.openxmlformats.org/package/2006/content-types}Default')
                default_elem.set('Extension', ext)
                default_elem.set('ContentType', content_type)
        
        # Dodaj override dla części z self._content_types
        for part_name, content_type in self._content_types.items():
            if not part_name.startswith('*.'):
                override_elem = ET.SubElement(root, '{http://schemas.openxmlformats.org/package/2006/content-types}Override')
                override_elem.set('PartName', f'/{part_name}')
                override_elem.set('ContentType', content_type)
        
        # Dodaj override dla wszystkich plików w self._parts i self._media, które nie są jeszcze w self._content_types
        # (zapewnia to, że wszystkie pliki, w tym docProps/, są w [Content_Types].xml)
        all_parts = set(self._parts.keys()) | set(self._media.keys())
        known_content_types = {name for name in self._content_types.keys() if not name.startswith('*.')}
        
        # Mapowanie rozszerzeń i ścieżek do content types
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
                continue  # Już dodany
            
            # Sprawdź mapowanie ścieżki
            content_type = None
            if part_name in content_type_map:
                content_type = content_type_map[part_name]
            else:
                # Sprawdź rozszerzenie
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
        # Rejestruj namespace, aby uniknąć prefiksów ns0:
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
        """Generuje następny ID relacji dla źródła."""
        if source not in self._rel_id_counters:
            self._rel_id_counters[source] = 1
        else:
            self._rel_id_counters[source] += 1
        
        return f"rId{self._rel_id_counters[source]}"
    
    def _get_relationship_path(self, part_name: str) -> str:
        """Określa ścieżkę pliku relacji dla części."""
        # Przykład: word/document.xml -> word/_rels/document.xml.rels
        if '/' in part_name:
            dir_part = '/'.join(part_name.split('/')[:-1])
            file_part = part_name.split('/')[-1]
            return f"{dir_part}/_rels/{file_part}.rels"
        else:
            return f"_rels/{part_name}.rels"
    
    def _generate_styles_xml(self) -> Optional[str]:
        """
        Generuje styles.xml z modeli dokumentu używając StyleNormalizer.
        
        Returns:
            XML string lub None jeśli nie ma stylów do wygenerowania
        """
        try:
            from ..normalize import StyleNormalizer
            
            # Pobierz oryginalny styles.xml jeśli istnieje
            original_styles_xml = None
            if hasattr(self.document, '_package_reader'):
                package_reader = self.document._package_reader
                original_styles_xml = package_reader.get_xml_content('word/styles.xml')
            
            # Dla dokumentów z JSON, spróbuj pobrać style z importera
            if not original_styles_xml and hasattr(self.document, '_importer'):
                importer = self.document._importer
                if hasattr(importer, 'styles_list') and importer.styles_list:
                    # Style są w JSON - użyj ich do utworzenia podstawowego styles.xml
                    # Albo użyj source_docx jeśli dostępny
                    if hasattr(self.document, '_source_docx') and self.document._source_docx:
                        from ..parser.package_reader import PackageReader
                        try:
                            source_reader = PackageReader(self.document._source_docx)
                            original_styles_xml = source_reader.get_xml_content('word/styles.xml')
                        except Exception:
                            pass
            
            # Utwórz StyleNormalizer
            style_normalizer = StyleNormalizer(original_styles_xml)
            
            # Zarejestruj wszystkie paragrafy i runy z dokumentu
            body = self._get_body()
            if body:
                paragraphs = self._get_paragraphs(body)
                
                # Pobierz numbering parser jeśli dostępny
                numbering_parser = None
                if hasattr(self.document, 'parser') and hasattr(self.document.parser, 'numbering_parser'):
                    numbering_parser = self.document.parser.numbering_parser
                
                for para in paragraphs:
                    style_normalizer.register_paragraph(para, numbering_parser)
                    
                    # Zarejestruj runy
                    runs = self._get_runs(para)
                    for run in runs:
                        style_normalizer.register_run(run)
            
            # Dla dokumentów z JSON (source_docx), jeśli nie ma custom stylów, zwróć wszystkie style z oryginalnego
            if not style_normalizer.has_custom_styles() and original_styles_xml:
                # Zwróć wszystkie style z oryginalnego dokumentu
                return original_styles_xml
            
            # Generuj XML tylko jeśli są custom style
            if style_normalizer.has_custom_styles():
                # Zbierz używane style IDs i style names
                used_style_ids = set()
                used_style_names = set()
                
                if hasattr(self.document, '_body'):
                    body = self._get_body()
                    if body:
                        paragraphs = self._get_paragraphs(body)
                        for para in paragraphs:
                            if hasattr(para, 'style') and isinstance(para.style, dict):
                                style_id = para.style.get('style_id') or para.style.get('id') or para.style.get('styleId')
                                style_name = para.style.get('style_name') or para.style.get('name')
                                
                                if style_id:
                                    used_style_ids.add(style_id)
                                if style_name:
                                    used_style_names.add(style_name)
                
                # Jeśli mamy source_docx, dodaj wszystkie style z oryginalnego dokumentu
                # (nie tylko używane, bo mogą być potrzebne dla innych elementów)
                if hasattr(self.document, '_source_docx') and self.document._source_docx and original_styles_xml:
                    # Dla dokumentów z JSON, zwróć wszystkie style z oryginalnego + nowe custom style
                    # Użyj None jako used_style_ids, aby skopiować wszystkie style
                    return style_normalizer.to_xml(None)
                else:
                    return style_normalizer.to_xml(used_style_ids)
            else:
                # Jeśli nie ma custom stylów i nie ma oryginalnego XML, zwróć None
                return None
                
        except Exception as e:
            logger.warning(f"Failed to generate styles.xml: {e}")
            # Fallback: użyj oryginalnego styles.xml
            if hasattr(self.document, '_package_reader'):
                package_reader = self.document._package_reader
                return package_reader.get_xml_content('word/styles.xml')
            return None
    
    def _generate_numbering_xml(self) -> Optional[str]:
        """
        Generuje numbering.xml z modeli dokumentu używając NumberingNormalizer.
        
        Returns:
            XML string lub None jeśli nie ma numeracji do wygenerowania
        """
        try:
            from ..normalize import NumberingNormalizer
            
            # Pobierz numbering parser
            numbering_parser = None
            if hasattr(self.document, 'parser') and hasattr(self.document.parser, 'numbering_parser'):
                numbering_parser = self.document.parser.numbering_parser
            
            if not numbering_parser:
                # Sprawdź czy dokument ma paragrafy z numbering (np. utworzony z JSON)
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
                
                # Fallback: użyj oryginalnego numbering.xml
                if hasattr(self.document, '_package_reader'):
                    package_reader = self.document._package_reader
                    return package_reader.get_xml_content('word/numbering.xml')
                return None
            
            # Pobierz oryginalny numbering.xml jeśli istnieje
            original_numbering_xml = None
            if hasattr(self.document, '_package_reader'):
                package_reader = self.document._package_reader
                original_numbering_xml = package_reader.get_xml_content('word/numbering.xml')
            
            # Utwórz NumberingNormalizer
            numbering_normalizer = NumberingNormalizer(numbering_parser, original_numbering_xml)
            
            # Zarejestruj wszystkie paragrafy z numeracją
            body = self._get_body()
            if body:
                paragraphs = self._get_paragraphs(body)
                for para in paragraphs:
                    numbering_normalizer.register_paragraph(para)
            
            # Generuj XML tylko jeśli jest custom numbering
            if numbering_normalizer.has_custom_numbering():
                return numbering_normalizer.to_xml()
            else:
                # Zwróć oryginalny XML jeśli nie ma custom numbering
                return original_numbering_xml
                
        except Exception as e:
            logger.warning(f"Failed to generate numbering.xml: {e}")
            # Fallback: użyj oryginalnego numbering.xml
            if hasattr(self.document, '_package_reader'):
                package_reader = self.document._package_reader
                return package_reader.get_xml_content('word/numbering.xml')
            return None
    
    def _generate_basic_numbering_xml(self) -> Optional[str]:
        """
        Generuje podstawowy numbering.xml dla dokumentów utworzonych z JSON.
        
        Returns:
            XML string z podstawową definicją numeracji
        """
        try:
            import xml.etree.ElementTree as ET
            
            # Zbierz wszystkie unikalne numbering IDs z paragrafów
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
            
            # Utwórz podstawowy numbering.xml
            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            root = ET.Element('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}numbering')
            
            # Dla każdego numbering ID, utwórz abstractNum i num
            abstract_num_id = 0
            for num_id, levels in numbering_ids.items():
                # Abstract numbering
                abstract_num = ET.SubElement(root, f'{{{ns["w"]}}}abstractNum')
                abstract_num.set(f'{{{ns["w"]}}}abstractNumId', str(abstract_num_id))
                
                # Dla każdego poziomu, utwórz lvl
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
        Przygotowuje media (obrazy) - kopiuje istniejące i znajduje nowe.
        
        Automatycznie tworzy relacje dla nowych obrazów dodanych do dokumentu.
        """
        # 1. Kopiuj istniejące media z oryginalnego dokumentu
        if hasattr(self.document, '_package_reader'):
            package_reader = self.document._package_reader
            # Pobierz wszystkie relacje obrazów
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
                        
                        # Sprawdź czy to relacja do obrazu
                        if 'image' in rel_type.lower() or target.startswith('media/'):
                            # Pobierz zawartość obrazu
                            try:
                                img_data = package_reader.get_binary_content(target)
                                if img_data:
                                    self._media[target] = img_data
                                    # Określ content type na podstawie rozszerzenia
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
        
        # 1b. Jeśli dokument nie ma _package_reader (np. utworzony z JSON), sprawdź obrazy w modelu
        # Najpierw spróbuj skopiować media z source_docx jeśli dostępne
        # Również skopiuj media z template_path jeśli jest to oryginalny DOCX
        source_docx_path = None
        if hasattr(self.document, '_source_docx') and self.document._source_docx:
            source_docx_path = self.document._source_docx
        elif self.template_path and self.template_path.exists() and self.template_path != self.TEMPLATE_PATH:
            # Jeśli template_path to oryginalny DOCX (nie new_doc.docx), użyj go jako source
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
                                # Dodaj z pełną ścieżką (word/media/...)
                                self._media[file_name] = media_data
                                # Określ content type
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
            # Sprawdź czy dokument ma body z obrazami
            body = self._get_body()
            if body:
                images = self._get_images(body)
                for image in images:
                    # Sprawdź czy obraz ma path i dane
                    img_path = None
                    img_data = None
                    rel_id = None
                    
                    if hasattr(image, 'path') and image.path:
                        img_path = image.path
                        # Spróbuj odczytać plik jeśli path istnieje
                        try:
                            from pathlib import Path as PathLib
                            path_obj = PathLib(img_path)
                            if path_obj.exists():
                                img_data = path_obj.read_bytes()
                        except Exception:
                            pass
                    
                    if hasattr(image, 'rel_id') and image.rel_id:
                        rel_id = image.rel_id
                    
                    # Jeśli mamy path i dane, dodaj do media
                    if img_path and img_data:
                        # Normalizuj path (musi być w formacie word/media/...)
                        if not img_path.startswith('word/'):
                            if 'media' in img_path:
                                # Wyciągnij tylko część z media
                                media_part = img_path.split('media/')[-1] if 'media/' in img_path else Path(img_path).name
                                img_path = f'word/media/{media_part}'
                            else:
                                img_path = f'word/media/{Path(img_path).name}'
                        
                        self._media[img_path] = img_data
                        
                        # Określ content type
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
                        
                        # Dodaj relację
                        rels_path = 'word/_rels/document.xml.rels'
                        if rels_path not in self._relationships:
                            self._relationships[rels_path] = []
                        
                        if not rel_id:
                            rel_id = self._get_next_rel_id(rels_path)
                        
                        rel_type = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/image'
                        self._relationships[rels_path].append((
                            rel_id, rel_type, img_path, 'Internal'
                        ))
        
        # 2. Znajdź nowe obrazy w dokumentach (dodane przez PlaceholderEngine lub API)
        # Przeszukaj document.xml XML dla r:embed i r:link
        document_xml_str = self._parts.get('word/document.xml', b'').decode('utf-8', errors='ignore')
        if document_xml_str:
            import re
            # Znajdź wszystkie r:embed i r:link w XML
            embed_pattern = r'r:embed="([^"]+)"'
            link_pattern = r'r:link="([^"]+)"'
            
            # Sprawdź czy są relacje do obrazów które nie są jeszcze w media
            # To wymaga parsowania document.xml i sprawdzenia relacji
            # Na razie używamy prostszego podejścia - sprawdzamy czy są obrazy w modelach
        
        # 3. Znajdź nowe obrazy dodane przez PlaceholderEngine lub API
        # Sprawdź czy dokument ma listę nowych obrazów
        if hasattr(self.document, '_new_images') and self.document._new_images:
            for img_info in self.document._new_images:
                media_path = img_info.get('path', '')
                img_data = img_info.get('data', b'')
                rel_id = img_info.get('rel_id', '')
                
                if media_path and img_data:
                    # Dodaj obraz do media
                    self._media[media_path] = img_data
                    
                    # Określ content type na podstawie rozszerzenia
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
                    
                    # Dodaj relację do document.xml.rels
                    rels_path = 'word/_rels/document.xml.rels'
                    if rels_path not in self._relationships:
                        self._relationships[rels_path] = []
                    
                    # Generuj nowy rel_id jeśli nie został podany
                    if not rel_id:
                        rel_id = self._get_next_rel_id(rels_path)
                    
                    rel_type = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/image'
                    self._relationships[rels_path].append((
                        rel_id, rel_type, media_path, None
                    ))
                    
                    # Zaktualizuj rel_id w modelu obrazu
                    # Przeszukaj wszystkie runs i zaktualizuj rel_id dla obrazów z tym samym part_path
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
        Używa RelationshipMerger do zarządzania relacjami podczas eksportu.
        
        RelationshipMerger zapewnia lepsze zarządzanie relacjami OPC,
        szczególnie dla złożonych dokumentów z wieloma częściami i zależnościami.
        """
        if not self.relationship_merger:
            return
        
        try:
            # Aktualizuj relacje używając RelationshipMerger
            # RelationshipMerger ma już skopiowane części i relacje w swoich strukturach wewnętrznych
            
            # 1. Zaktualizuj relacje dla części używając RelationshipMerger
            # RelationshipMerger przechowuje zaktualizowane relacje w _relationships_to_write
            if hasattr(self.relationship_merger, '_relationships_to_write'):
                for rels_path, rels_list in self.relationship_merger._relationships_to_write.items():
                    # Konwertuj format RelationshipMerger do formatu DOCXExporter
                    # RelationshipMerger używa Dict[str, str], DOCXExporter używa List[tuple]
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
            
            # 2. Zaktualizuj content types używając RelationshipMerger
            if hasattr(self.relationship_merger, '_content_types_to_write'):
                for part_name, content_type in self.relationship_merger._content_types_to_write.items():
                    self._content_types[part_name] = content_type
            
            # 3. Zaktualizuj części używając RelationshipMerger
            if hasattr(self.relationship_merger, '_copied_parts_data'):
                for part_name, content in self.relationship_merger._copied_parts_data.items():
                    # Sprawdź czy część nie została już dodana przez _prepare_parts
                    if part_name not in self._parts:
                        self._parts[part_name] = content
            
            logger.debug("RelationshipMerger integration completed")
            
        except Exception as e:
            logger.warning(f"Failed to use RelationshipMerger for parts: {e}")
            # Fallback: kontynuuj bez RelationshipMerger

