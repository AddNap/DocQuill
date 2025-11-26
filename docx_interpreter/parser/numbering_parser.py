"""
Enhanced Numbering parser for DOCX documents.

Full implementation with numbering.xml parsing support.
"""

import xml.etree.ElementTree as ET
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)

class NumberingParser:
    """
    Enhanced parser for document numbering and lists.
    
    Full implementation with numbering.xml parsing support.
    """
    
    def __init__(self, package_reader):
        """
        Initialize numbering parser.
        
        Args:
            package_reader: PackageReader instance for accessing numbering.xml
        """
        self.package_reader = package_reader
        self.ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        self.abstract_numberings = {}
        self.numbering_instances = {}
        self.numbering_cache = {}
        
        logger.debug("Numbering parser initialized")
    
    def parse_numbering(self) -> Dict[str, Any]:
        """
        Parse numbering definitions from numbering.xml.
        
        Returns:
            Dictionary of parsed numbering data
        """
        try:
            numbering_xml = self.package_reader.get_xml_content('word/numbering.xml')
            if not numbering_xml:
                logger.warning("No numbering.xml found")
                return {}
            
            root = ET.fromstring(numbering_xml)
            
            # Parse abstract numberings
            for abstract_num in root.findall('.//w:abstractNum', self.ns):
                abstract_num_data = self.parse_abstract_numbering(abstract_num)
                if abstract_num_data:
                    self.abstract_numberings[abstract_num_data['abstractNumId']] = abstract_num_data
            
            # Parse numbering instances
            for num in root.findall('.//w:num', self.ns):
                num_data = self.parse_numbering_instance(num)
                if num_data:
                    self.numbering_instances[num_data['numId']] = num_data
            
            logger.info(f"Parsed {len(self.abstract_numberings)} abstract numberings and {len(self.numbering_instances)} numbering instances")
            return {
                'abstract_numberings': self.abstract_numberings,
                'numbering_instances': self.numbering_instances
            }
            
        except Exception as e:
            logger.error(f"Failed to parse numbering: {e}")
            return {}
    
    def parse_abstract_numbering(self, abstract_num: ET.Element) -> Optional[Dict[str, Any]]:
        """
        Parse abstract numbering definition.
        
        Args:
            abstract_num: Abstract numbering XML element
            
        Returns:
            Dictionary of abstract numbering data
        """
        try:
            abstract_num_id = abstract_num.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}abstractNumId', 
                                             abstract_num.get('abstractNumId', ''))
            
            abstract_num_data = {
                'abstractNumId': abstract_num_id,
                'name': '',
                'levels': {}
            }
            
            # Parse numbering name
            name_element = abstract_num.find('.//w:name', self.ns)
            if name_element is not None:
                abstract_num_data['name'] = name_element.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', 
                                                          name_element.get('val', ''))
            
            # Parse numbering levels
            for level in abstract_num.findall('.//w:lvl', self.ns):
                level_data = self.parse_numbering_level(level)
                if level_data:
                    abstract_num_data['levels'][level_data['level']] = level_data
            
            return abstract_num_data
            
        except Exception as e:
            logger.error(f"Failed to parse abstract numbering: {e}")
            return None
    
    def parse_numbering_level(self, level: ET.Element) -> Optional[Dict[str, Any]]:
        """
        Parse numbering level.
        
        Args:
            level: Numbering level XML element
            
        Returns:
            Dictionary of level data
        """
        try:
            # Get ilvl with namespace
            level_num = level.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}ilvl',
                                 level.get('ilvl', '0'))
            
            level_data = {
                'level': level_num,
                'format': 'decimal',
                'text': '%1.',
                'start': '1',
                'is_ordered': True,
                'alignment': 'left',
                'indent_left': '0',
                'indent_right': '0',
                'indent_first_line': '0',
                'indent_hanging': '0',
                'font': {},
                'paragraph_properties': {},
                'tabs': [],
                'suffix': 'tab'
            }
            
            # Parse numbering format
            num_fmt = level.find('.//w:numFmt', self.ns)
            if num_fmt is not None:
                # Get attribute with namespace
                format_val = num_fmt.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', 
                                        num_fmt.get('val', 'decimal'))
                level_data['format'] = format_val
                # Check if it's unordered (bullet points)
                level_data['is_ordered'] = format_val not in ['bullet', 'none', 'nothing']
                
                # Map format to HTML list type
                format_mapping = {
                    'decimal': 'decimal',
                    'lowerLetter': 'lower-alpha',
                    'upperLetter': 'upper-alpha',
                    'lowerRoman': 'lower-roman',
                    'upperRoman': 'upper-roman',
                    'bullet': 'disc',
                    'none': 'none',
                    'nothing': 'none'
                }
                level_data['html_type'] = format_mapping.get(format_val, 'decimal')
            
            # Parse numbering text
            lvl_text = level.find('.//w:lvlText', self.ns)
            if lvl_text is not None:
                level_data['text'] = lvl_text.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val',
                                                 lvl_text.get('val', '%1.'))
            
            # Parse start value
            start = level.find('.//w:start', self.ns)
            if start is not None:
                level_data['start'] = start.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val',
                                               start.get('val', '1'))
            
            # Parse suffix (character following marker)
            suffix = level.find('.//w:suff', self.ns)
            if suffix is not None:
                level_data['suffix'] = suffix.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val',
                                                 suffix.get('val', 'tab'))

            # Parse paragraph properties
            p_pr = level.find('.//w:pPr', self.ns)
            if p_pr is not None:
                # Alignment
                jc = p_pr.find('.//w:jc', self.ns)
                if jc is not None:
                    level_data['alignment'] = jc.get('val', 'left')
                
                # Indentation
                ind = p_pr.find('.//w:ind', self.ns)
                if ind is not None:
                    ns_left = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}left'
                    ns_right = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}right'
                    ns_first = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}firstLine'
                    ns_hanging = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}hanging'

                    level_data['indent_left'] = ind.get(ns_left, ind.get('left', level_data['indent_left']))
                    level_data['indent_right'] = ind.get(ns_right, ind.get('right', level_data['indent_right']))
                    level_data['indent_first_line'] = ind.get(ns_first, ind.get('firstLine', level_data['indent_first_line']))
                    level_data['indent_hanging'] = ind.get(ns_hanging, ind.get('hanging', level_data['indent_hanging']))

                # Tabs (tab stops)
                tabs = p_pr.find('.//w:tabs', self.ns)
                if tabs is not None:
                    tab_list = []
                    for tab in tabs.findall('.//w:tab', self.ns):
                        tab_list.append({
                            'val': tab.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val',
                                            tab.get('val', 'left')),
                            'pos': tab.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pos',
                                           tab.get('pos')),
                            'leader': tab.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}leader',
                                              tab.get('leader'))
                        })
                    level_data['tabs'] = tab_list
            
            # Parse font properties
            r_pr = level.find('.//w:rPr', self.ns)
            if r_pr is not None:
                # Font name
                font = r_pr.find('.//w:rFonts', self.ns)
                if font is not None:
                    level_data['font']['name'] = font.get('ascii', font.get('hAnsi', ''))
                
                # Font size
                sz = r_pr.find('.//w:sz', self.ns)
                if sz is not None:
                    level_data['font']['size'] = sz.get('val', '22')
                
                # Bold
                b = r_pr.find('.//w:b', self.ns)
                if b is not None:
                    level_data['font']['bold'] = True
                
                # Italic
                i = r_pr.find('.//w:i', self.ns)
                if i is not None:
                    level_data['font']['italic'] = True
            
            return level_data
            
        except Exception as e:
            logger.error(f"Failed to parse numbering level: {e}")
            return None
    
    def parse_numbering_instance(self, num: ET.Element) -> Optional[Dict[str, Any]]:
        """
        Parse numbering instance.
        
        Args:
            num: Numbering instance XML element
            
        Returns:
            Dictionary of numbering instance data
        """
        try:
            num_id = num.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}numId', 
                           num.get('numId', ''))
            
            num_data = {
                'numId': num_id,
                'abstractNumId': '',
                'levels': {}
            }
            
            # Parse abstract numbering reference
            abstract_num_id = num.find('.//w:abstractNumId', self.ns)
            if abstract_num_id is not None:
                num_data['abstractNumId'] = abstract_num_id.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', 
                                                              abstract_num_id.get('val', ''))
            
            # Parse level overrides
            for lvl_override in num.findall('.//w:lvlOverride', self.ns):
                level_data = self.parse_level_override(lvl_override)
                if level_data:
                    num_data['levels'][level_data['level']] = level_data
            
            return num_data
            
        except Exception as e:
            logger.error(f"Failed to parse numbering instance: {e}")
            return None
    
    def parse_level_override(self, lvl_override: ET.Element) -> Optional[Dict[str, Any]]:
        """
        Parse level override.
        
        Args:
            lvl_override: Level override XML element
            
        Returns:
            Dictionary of level override data
        """
        try:
            level = lvl_override.get('ilvl', '0')
            
            level_data = {
                'level': level,
                'format': None,
                'start': None,
                'text': None
            }
            
            # Parse format override
            num_fmt = lvl_override.find('.//w:numFmt', self.ns)
            if num_fmt is not None:
                level_data['format'] = num_fmt.get('val')
            
            # Parse start override
            start = lvl_override.find('.//w:start', self.ns)
            if start is not None:
                level_data['start'] = start.get('val')
            
            # Parse text override
            lvl_text = lvl_override.find('.//w:lvlText', self.ns)
            if lvl_text is not None:
                level_data['text'] = lvl_text.get('val')
            
            return level_data
            
        except Exception as e:
            logger.error(f"Failed to parse level override: {e}")
            return None
    
    def get_numbering_definition(self, num_id: str) -> Optional[Dict[str, Any]]:
        """
        Get numbering definition by ID.
        
        Args:
            num_id: Numbering instance ID
            
        Returns:
            Complete numbering definition with resolved inheritance
        """
        if num_id not in self.numbering_cache:
            num_instance = self.numbering_instances.get(num_id)
            if not num_instance:
                return None
            
            abstract_num_id = num_instance.get('abstractNumId')
            if not abstract_num_id:
                return None
            
            abstract_num = self.abstract_numberings.get(abstract_num_id)
            if not abstract_num:
                return None
            
            # Create resolved definition
            resolved_definition = abstract_num.copy()
            
            # Apply level overrides
            for level, override in num_instance.get('levels', {}).items():
                if level in resolved_definition['levels']:
                    base_level = resolved_definition['levels'][level]
                    # Apply overrides
                    if override.get('format'):
                        base_level['format'] = override['format']
                    if override.get('start'):
                        base_level['start'] = override['start']
                    if override.get('text'):
                        base_level['text'] = override['text']
            
            self.numbering_cache[num_id] = resolved_definition
        
        return self.numbering_cache[num_id]
    
    def get_level_format(self, num_id: str, level: str) -> Optional[Dict[str, Any]]:
        """
        Get formatting for specific numbering level.
        
        Args:
            num_id: Numbering instance ID
            level: Level number
            
        Returns:
            Level formatting data
        """
        definition = self.get_numbering_definition(num_id)
        if not definition:
            return None
        
        return definition.get('levels', {}).get(level)
    
    def is_ordered_list(self, num_id: str, level: str) -> bool:
        """
        Check if numbering level is ordered.
        
        Args:
            num_id: Numbering instance ID
            level: Level number
            
        Returns:
            True if ordered, False if bullet
        """
        level_format = self.get_level_format(num_id, level)
        if not level_format:
            return True  # Default to ordered
        
        return level_format.get('is_ordered', True)
    
    def get_list_level(self, num_id: str, level: str) -> int:
        """
        Get list level number.
        
        Args:
            num_id: Numbering instance ID
            level: Level number
            
        Returns:
            List level number
        """
        return int(level)
