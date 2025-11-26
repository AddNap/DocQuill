"""
Settings parser for DOCX documents.

Handles settings.xml parsing, document settings, compatibility settings, and validation.
"""

import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class SettingsParser:
    """
    Parser for document settings from settings.xml.
    
    Handles settings parsing, validation, and access.
    """
    
    def __init__(self, package_reader):
        """
        Initialize settings parser.
        
        Args:
            package_reader: PackageReader instance for accessing settings.xml
        """
        self.package_reader = package_reader
        self.settings = {}
        self.default_settings = self._get_default_settings()
        
        # Parse settings if available
        self._parse_settings()
        
        logger.debug("Settings parser initialized")
    
    def parse_settings(self) -> Dict[str, Any]:
        """
        Parse settings from settings.xml.
        
        Returns:
            Dictionary of parsed settings
        """
        return self.settings.copy()
    
    def parse_document_settings(self, settings_element: ET.Element) -> Dict[str, Any]:
        """
        Parse document settings.
        
        Args:
            settings_element: Settings XML element
            
        Returns:
            Dictionary of document settings
        """
        document_settings = {}
        
        # Default tab stop
        default_tab_stop = settings_element.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}defaultTabStop')
        if default_tab_stop is not None:
            document_settings['default_tab_stop'] = int(default_tab_stop.get('val', '720'))
        
        # Auto hyphenation
        auto_hyphenation = settings_element.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}autoHyphenation')
        if auto_hyphenation is not None:
            document_settings['auto_hyphenation'] = auto_hyphenation.get('val', '1') == '1'
        
        # Consecutive hyphen limit
        consecutive_hyphen_limit = settings_element.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}consecutiveHyphenLimit')
        if consecutive_hyphen_limit is not None:
            document_settings['consecutive_hyphen_limit'] = int(consecutive_hyphen_limit.get('val', '0'))
        
        # Document protection
        doc_protection = settings_element.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}documentProtection')
        if doc_protection is not None:
            document_settings['document_protection'] = {
                'enforcement': doc_protection.get('enforcement', '0') == '1',
                'crypt_provider_type': doc_protection.get('cryptProviderType', ''),
                'crypt_algorithm_class': doc_protection.get('cryptAlgorithmClass', ''),
                'crypt_algorithm_type': doc_protection.get('cryptAlgorithmType', ''),
                'crypt_algorithm_sid': doc_protection.get('cryptAlgorithmSid', ''),
                'crypt_spin_count': doc_protection.get('cryptSpinCount', '0'),
                'hash': doc_protection.get('hash', ''),
                'salt': doc_protection.get('salt', ''),
                'format': doc_protection.get('format', '')
            }
        
        return document_settings
    
    def parse_compatibility_settings(self, compatibility_element: ET.Element) -> Dict[str, Any]:
        """
        Parse compatibility settings.
        
        Args:
            compatibility_element: Compatibility XML element
            
        Returns:
            Dictionary of compatibility settings
        """
        compatibility = {}
        
        if compatibility_element is not None:
            for child in compatibility_element:
                tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                compatibility[tag_name] = child.get('val', '1') == '1'
        
        return compatibility
    
    def get_setting(self, setting_name: str, default_value: Any = None) -> Any:
        """
        Get specific setting value.
        
        Args:
            setting_name: Name of the setting
            default_value: Default value if setting not found
            
        Returns:
            Setting value or default
        """
        return self.settings.get(setting_name, default_value)
    
    def has_setting(self, setting_name: str) -> bool:
        """
        Check if a setting exists.
        
        Args:
            setting_name: Name of the setting
            
        Returns:
            True if setting exists
        """
        return setting_name in self.settings
    
    def get_all_settings(self) -> Dict[str, Any]:
        """
        Get all settings.
        
        Returns:
            Dictionary of all settings
        """
        return self.settings.copy()
    
    def get_settings_info(self) -> Dict[str, Any]:
        """
        Get settings information.
        
        Returns:
            Dictionary with settings metadata
        """
        return {
            'total_settings': len(self.settings),
            'has_defaults': bool(self.default_settings),
            'settings_keys': list(self.settings.keys())
        }
    
    def _parse_settings(self) -> None:
        """Parse settings from settings.xml."""
        try:
            settings_xml = self.package_reader.get_xml_content('word/settings.xml')
            if settings_xml:
                self.settings = self._parse_settings_xml(settings_xml)
                logger.info(f"Parsed {len(self.settings)} settings")
            else:
                logger.warning("No settings.xml found, using defaults")
                self.settings = self.default_settings.copy()
                
        except Exception as e:
            logger.error(f"Failed to parse settings: {e}")
            self.settings = self.default_settings.copy()
    
    def _parse_settings_xml(self, settings_xml: str) -> Dict[str, Any]:
        """Parse settings XML content."""
        settings = {}
        
        try:
            root = ET.fromstring(settings_xml)
            
            # Parse document settings
            settings.update(self.parse_document_settings(root))
            
            # Parse compatibility settings
            compat = root.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}compat')
            if compat is not None:
                settings['compatibility'] = self.parse_compatibility_settings(compat)
            
            # Parse other settings
            settings.update(self._parse_zoom_settings(root))
            settings.update(self._parse_print_settings(root))
            settings.update(self._parse_web_settings(root))
            settings.update(self._parse_mail_merge_settings(root))
            
        except ET.ParseError as e:
            logger.error(f"Failed to parse settings XML: {e}")
        
        return settings
    
    def _parse_zoom_settings(self, root: ET.Element) -> Dict[str, Any]:
        """Parse zoom settings."""
        zoom = {}
        
        # Zoom percentage
        zoom_percentage = root.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}zoom')
        if zoom_percentage is not None:
            zoom['zoom_percentage'] = int(zoom_percentage.get('percent', '100'))
        
        return zoom
    
    def _parse_print_settings(self, root: ET.Element) -> Dict[str, Any]:
        """Parse print settings."""
        print_settings = {}
        
        # Print settings
        print_settings_elem = root.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}printSettings')
        if print_settings_elem is not None:
            print_settings['print'] = {}
            for child in print_settings_elem:
                tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                print_settings['print'][tag_name] = child.get('val', '1') == '1'
        
        return print_settings
    
    def _parse_web_settings(self, root: ET.Element) -> Dict[str, Any]:
        """Parse web settings."""
        web = {}
        
        # Web settings
        web_settings = root.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}webSettings')
        if web_settings is not None:
            web['web'] = {}
            for child in web_settings:
                tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                web['web'][tag_name] = child.get('val', '1') == '1'
        
        return web
    
    def _parse_mail_merge_settings(self, root: ET.Element) -> Dict[str, Any]:
        """Parse mail merge settings."""
        mail_merge = {}
        
        # Mail merge settings
        mail_merge_elem = root.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}mailMerge')
        if mail_merge_elem is not None:
            mail_merge['mail_merge'] = {}
            for child in mail_merge_elem:
                tag_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                mail_merge['mail_merge'][tag_name] = child.get('val', '1') == '1'
        
        return mail_merge
    
    def _get_default_settings(self) -> Dict[str, Any]:
        """Get default document settings."""
        return {
            'default_tab_stop': 720,  # 0.5 inch in twips
            'auto_hyphenation': False,
            'consecutive_hyphen_limit': 0,
            'zoom_percentage': 100,
            'document_protection': {
                'enforcement': False,
                'crypt_provider_type': '',
                'crypt_algorithm_class': '',
                'crypt_algorithm_type': '',
                'crypt_algorithm_sid': '',
                'crypt_spin_count': 0,
                'hash': '',
                'salt': '',
                'format': ''
            },
            'compatibility': {},
            'print': {},
            'web': {},
            'mail_merge': {}
        }
    
    def validate_settings(self) -> List[str]:
        """
        Validate settings.
        
        Returns:
            List of validation errors
        """
        errors = []
        
        # Validate tab stop
        if 'default_tab_stop' in self.settings:
            tab_stop = self.settings['default_tab_stop']
            if not isinstance(tab_stop, int) or tab_stop < 0:
                errors.append("Invalid default tab stop value")
        
        # Validate zoom percentage
        if 'zoom_percentage' in self.settings:
            zoom = self.settings['zoom_percentage']
            if not isinstance(zoom, int) or zoom < 10 or zoom > 500:
                errors.append("Invalid zoom percentage")
        
        # Validate hyphen limit
        if 'consecutive_hyphen_limit' in self.settings:
            limit = self.settings['consecutive_hyphen_limit']
            if not isinstance(limit, int) or limit < 0:
                errors.append("Invalid consecutive hyphen limit")
        
        return errors
    
    def clear_settings(self) -> None:
        """Clear all settings."""
        self.settings.clear()
        logger.debug("Settings cleared")
