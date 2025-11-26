"""
Numbering resolver for DOCX documents.

Handles numbering resolution, continuity, validation, and management.
"""

from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class NumberingResolver:
    """
    Resolves numbering order and continuity.
    
    Handles numbering resolution, continuity, validation, and management.
    """
    
    def __init__(self):
        """
        Initialize numbering resolver.
        
        Sets up numbering resolution, continuity tracking, and validation.
        """
        self.numbering_contexts = {}
        self.numbering_sequences = {}
        self.numbering_levels = {}
        self.continuity_tracker = {}
        
        logger.debug("Numbering resolver initialized")
    
    def resolve_numbering(self, element, numbering_context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Resolve numbering for element.
        
        Args:
            element: Element to resolve numbering for
            numbering_context: Numbering context information (optional)
            
        Returns:
            Dictionary with resolved numbering information
        """
        if numbering_context is None:
            numbering_context = {}
        try:
            numbering_info = {
                'element_id': element.get('id', ''),
                'numbering_level': numbering_context.get('level', 0),
                'numbering_value': 0,
                'numbering_format': numbering_context.get('format', 'decimal'),
                'is_continuation': False,
                'is_restart': False
            }
            
            # Calculate numbering value
            numbering_info['numbering_value'] = self.calculate_numbering_value(element, numbering_info['numbering_level'])
            numbering_info['value'] = numbering_info['numbering_value']  # Alias for compatibility
            numbering_info['level'] = numbering_info['numbering_level']  # Alias for compatibility
            numbering_info['formatted'] = str(numbering_info['numbering_value'])  # Formatted value
            
            # Check for continuation or restart
            numbering_info['is_continuation'] = self._check_continuation(element, numbering_context)
            numbering_info['is_restart'] = self._check_restart(element, numbering_context)
            
            # Update numbering context
            self._update_numbering_context(element, numbering_info)
            
            return numbering_info
            
        except Exception as e:
            logger.error(f"Failed to resolve numbering for element: {e}")
            return {'error': str(e)}
    
    def calculate_numbering_value(self, element: Dict[str, Any], numbering_level: int) -> int:
        """
        Calculate numbering value for element.
        
        Args:
            element: Element to calculate numbering for
            numbering_level: Numbering level
            
        Returns:
            Calculated numbering value
        """
        try:
            # Get current numbering sequence for this level
            sequence_key = f"level_{numbering_level}"
            if sequence_key not in self.numbering_sequences:
                self.numbering_sequences[sequence_key] = 0
            
            # Increment sequence
            self.numbering_sequences[sequence_key] += 1
            
            return self.numbering_sequences[sequence_key]
            
        except Exception as e:
            logger.error(f"Failed to calculate numbering value: {e}")
            return 0
    
    def maintain_numbering_continuity(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Maintain numbering continuity across elements.
        
        Args:
            elements: List of elements to maintain continuity for
            
        Returns:
            List of elements with maintained numbering continuity
        """
        try:
            processed_elements = []
            current_levels = {}
            
            for element in elements:
                # Get numbering context for element
                numbering_context = self.get_numbering_context(element)
                
                if numbering_context:
                    # Resolve numbering
                    numbering_info = self.resolve_numbering(element, numbering_context)
                    
                    # Update element with numbering info
                    element['numbering'] = numbering_info
                    
                    # Track current levels
                    level = numbering_info.get('numbering_level', 0)
                    current_levels[level] = numbering_info.get('numbering_value', 0)
                    
                    # Reset higher levels if restarting
                    if numbering_info.get('is_restart', False):
                        for higher_level in range(level + 1, max(current_levels.keys(), default=0) + 1):
                            if higher_level in self.numbering_sequences:
                                self.numbering_sequences[f"level_{higher_level}"] = 0
                
                processed_elements.append(element)
            
            return processed_elements
            
        except Exception as e:
            logger.error(f"Failed to maintain numbering continuity: {e}")
            return elements
    
    def validate_numbering_sequence(self, numbering_sequence: List[Dict[str, Any]]) -> bool:
        """
        Validate numbering sequence.
        
        Args:
            numbering_sequence: Numbering sequence to validate
            
        Returns:
            True if sequence is valid, False otherwise
        """
        try:
            # Check sequence continuity
            for i, item in enumerate(numbering_sequence):
                if i > 0:
                    prev_item = numbering_sequence[i - 1]
                    if hasattr(item, 'numbering_value') and hasattr(prev_item, 'numbering_value'):
                        if item.numbering_value < prev_item.numbering_value:
                            return False
            return True
        except Exception as e:
            logger.error(f"Numbering sequence validation failed: {e}")
            return False
        
        try:
            # Check sequence continuity
            for i, item in enumerate(numbering_sequence):
                if i > 0:
                    prev_item = numbering_sequence[i - 1]
                    current_level = item.get('numbering_level', 0)
                    prev_level = prev_item.get('numbering_level', 0)
                    
                    # Check for level consistency
                    if current_level < prev_level:
                        # Lower level should reset higher levels
                        validation_results['checks'].append(f"Level {current_level} resets higher levels")
                    elif current_level == prev_level:
                        # Same level should continue sequence
                        current_value = item.get('numbering_value', 0)
                        prev_value = prev_item.get('numbering_value', 0)
                        if current_value != prev_value + 1:
                            validation_results['warnings'].append(f"Non-consecutive numbering at level {current_level}")
                    else:
                        # Higher level should start new sequence
                        validation_results['checks'].append(f"Level {current_level} starts new sequence")
            
            # Check for missing numbering
            missing_numbering = [item for item in numbering_sequence if 'numbering' not in item]
            if missing_numbering:
                validation_results['warnings'].append(f"Found {len(missing_numbering)} items without numbering")
            
            validation_results['checks'].append(f"Validated {len(numbering_sequence)} numbering items")
            
        except Exception as e:
            validation_results['errors'].append(f"Numbering sequence validation failed: {e}")
            validation_results['valid'] = False
        
        return validation_results
    
    def get_numbering_context(self, element) -> Optional[Dict[str, Any]]:
        """
        Get numbering context for element.
        
        Args:
            element: Element to get numbering context for
            
        Returns:
            Numbering context or None if not found
        """
        try:
            if isinstance(element, dict):
                element_id = element.get('id', '')
                if element_id in self.numbering_contexts:
                    return self.numbering_contexts[element_id]
                
                # Try to determine context from element properties
                if 'numbering' in element:
                    return element['numbering']
                
                # Check for numbering properties in element
                if 'properties' in element and 'numbering' in element['properties']:
                    return element['properties']['numbering']
            else:
                # Handle object element
                element_id = getattr(element, 'id', '')
                if element_id in self.numbering_contexts:
                    return self.numbering_contexts[element_id]
                
                # Check for numbering properties in element
                if hasattr(element, 'numbering_id') and hasattr(element, 'numbering_level'):
                    return {
                        'id': element.numbering_id,
                        'level': element.numbering_level,
                        'format': getattr(element, 'numbering_format', 'decimal')
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get numbering context: {e}")
            return None
    
    def set_numbering_context(self, element, context: Dict[str, Any]) -> None:
        """
        Set numbering context for element.
        
        Args:
            element: Element or element identifier
            context: Numbering context
        """
        if isinstance(element, str):
            element_id = element
        else:
            element_id = getattr(element, 'numbering_id', str(element))
        
        self.numbering_contexts[element_id] = context
        logger.debug(f"Set numbering context for element {element_id}")
    
    def reset_numbering_sequences(self) -> None:
        """Reset all numbering sequences."""
        self.numbering_sequences.clear()
        self.numbering_levels.clear()
        self.continuity_tracker.clear()
        logger.debug("Numbering sequences reset")
    
    def get_numbering_summary(self) -> Dict[str, Any]:
        """
        Get numbering summary.
        
        Returns:
            Dictionary with numbering summary
        """
        return {
            'total_contexts': len(self.numbering_contexts),
            'total_sequences': len(self.numbering_sequences),
            'total_levels': len(self.numbering_levels),
            'sequences': self.numbering_sequences,
            'sequence_levels': list(self.numbering_sequences.keys()),
            'continuity_tracked': len(self.continuity_tracker)
        }
    
    def _check_continuation(self, element: Dict[str, Any], numbering_context: Dict[str, Any]) -> bool:
        """Check if element is a continuation of previous numbering."""
        # Implementation for checking continuation
        return False
    
    def _check_restart(self, element: Dict[str, Any], numbering_context: Dict[str, Any]) -> bool:
        """Check if element should restart numbering."""
        # Implementation for checking restart
        return False
    
    def _update_numbering_context(self, element: Dict[str, Any], numbering_info: Dict[str, Any]) -> None:
        """Update numbering context for element."""
        element_id = element.get('id', '')
        if element_id:
            self.numbering_contexts[element_id] = numbering_info
