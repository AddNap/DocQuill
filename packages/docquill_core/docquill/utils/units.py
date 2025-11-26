"""
Units converter for DOCX documents.

Handles units converter functionality, EMU conversion, twip conversion, pixel conversion, and millimeter conversion.
"""

from typing import Union, Dict, Any
import logging

logger = logging.getLogger(__name__)

class UnitsConverter:
    """
    Converts between different units used in DOCX documents.
    
    Handles units converter functionality, unit conversion, unit validation, and unit constants.
    """
    
    def __init__(self, dpi: int = 96):
        """
        Initialize units converter.
        
        Args:
            dpi: Dots per inch for pixel conversions
        """
        self.dpi = dpi
        self.conversion_factors = {
            'emu_to_mm': 0.000027778,  # 1 EMU = 0.000027778 mm (914400 EMU = 1 inch = 25.4 mm)
            'twip_to_mm': 0.0176389,   # 1 TWIP = 0.0176389 mm
            'pt_to_mm': 0.352778,      # 1 point = 0.352778 mm
            'mm_to_pt': 2.834645669,   # 1 mm = 2.834645669 points
            'px_to_pt': 0.75,          # 1 pixel = 0.75 points (at 96 DPI)
            'pt_to_px': 1.333333333    # 1 point = 1.333333333 pixels (at 96 DPI)
        }
        
        logger.debug(f"Units converter initialized with DPI: {dpi}")
    
    def emu_to_pixels(self, emu_value: float, dpi: int = None) -> float:
        """
        Convert EMU to pixels.
        
        Args:
            emu_value: EMU value to convert
            dpi: Dots per inch (uses instance DPI if not provided)
            
        Returns:
            Pixels value
        """
        if not isinstance(emu_value, (int, float)):
            raise ValueError("EMU value must be a number")
        
        if dpi is None:
            dpi = self.dpi
        
        # Convert EMU to mm first
        mm = emu_value * self.conversion_factors['emu_to_mm']
        # Convert mm to pixels
        pixels = (mm * dpi) / 25.4  # 25.4 mm per inch
        
        logger.debug(f"EMU to pixels: {emu_value} -> {pixels} (DPI: {dpi})")
        return pixels
    
    def emu_to_mm(self, emu_value: float) -> float:
        """
        Convert EMU to millimeters.
        
        Args:
            emu_value: EMU value to convert
            
        Returns:
            Millimeters value
        """
        if not isinstance(emu_value, (int, float)):
            raise ValueError("EMU value must be a number")
        
        mm = emu_value * self.conversion_factors['emu_to_mm']
        logger.debug(f"EMU to mm: {emu_value} -> {mm}")
        return mm
    
    def twip_to_pixels(self, twip_value: float, dpi: int = None) -> float:
        """
        Convert twips to pixels.
        
        Args:
            twip_value: TWIP value to convert
            dpi: Dots per inch (uses instance DPI if not provided)
            
        Returns:
            Pixels value
        """
        if not isinstance(twip_value, (int, float)):
            raise ValueError("TWIP value must be a number")
        
        if dpi is None:
            dpi = self.dpi
        
        # Convert TWIP to mm first
        mm = twip_value * self.conversion_factors['twip_to_mm']
        # Convert mm to pixels
        pixels = (mm * dpi) / 25.4  # 25.4 mm per inch
        
        logger.debug(f"TWIP to pixels: {twip_value} -> {pixels} (DPI: {dpi})")
        return pixels
    
    def twip_to_mm(self, twip_value: float) -> float:
        """
        Convert twips to millimeters.
        
        Args:
            twip_value: TWIP value to convert
            
        Returns:
            Millimeters value
        """
        if not isinstance(twip_value, (int, float)):
            raise ValueError("TWIP value must be a number")
        
        mm = twip_value * self.conversion_factors['twip_to_mm']
        logger.debug(f"TWIP to mm: {twip_value} -> {mm}")
        return mm
    
    def pixels_to_emu(self, pixel_value: float, dpi: int = None) -> float:
        """
        Convert pixels to EMU.
        
        Args:
            pixel_value: Pixels value to convert
            dpi: Dots per inch (uses instance DPI if not provided)
            
        Returns:
            EMU value
        """
        if not isinstance(pixel_value, (int, float)):
            raise ValueError("Pixel value must be a number")
        
        if dpi is None:
            dpi = self.dpi
        
        # Convert pixels to mm first
        mm = (pixel_value * 25.4) / dpi  # 25.4 mm per inch
        # Convert mm to EMU
        emu = mm / self.conversion_factors['emu_to_mm']
        
        logger.debug(f"Pixels to EMU: {pixel_value} -> {emu} (DPI: {dpi})")
        return emu
    
    def mm_to_emu(self, mm_value: float) -> float:
        """
        Convert millimeters to EMU.
        
        Args:
            mm_value: Millimeters value to convert
            
        Returns:
            EMU value
        """
        if not isinstance(mm_value, (int, float)):
            raise ValueError("Millimeters value must be a number")
        
        emu = mm_value / self.conversion_factors['emu_to_mm']
        logger.debug(f"MM to EMU: {mm_value} -> {emu}")
        return emu
    
    def pixels_to_mm(self, pixel_value: float, dpi: int = None) -> float:
        """
        Convert pixels to millimeters.
        
        Args:
            pixel_value: Pixels value to convert
            dpi: Dots per inch (uses instance DPI if not provided)
            
        Returns:
            Millimeters value
        """
        if not isinstance(pixel_value, (int, float)):
            raise ValueError("Pixel value must be a number")
        
        if dpi is None:
            dpi = self.dpi
        
        mm = (pixel_value * 25.4) / dpi  # 25.4 mm per inch
        logger.debug(f"Pixels to mm: {pixel_value} -> {mm} (DPI: {dpi})")
        return mm
    
    def mm_to_pixels(self, mm_value: float, dpi: int = None) -> float:
        """
        Convert millimeters to pixels.
        
        Args:
            mm_value: Millimeters value to convert
            dpi: Dots per inch (uses instance DPI if not provided)
            
        Returns:
            Pixels value
        """
        if not isinstance(mm_value, (int, float)):
            raise ValueError("Millimeters value must be a number")
        
        if dpi is None:
            dpi = self.dpi
        
        pixels = (mm_value * dpi) / 25.4  # 25.4 mm per inch
        logger.debug(f"MM to pixels: {mm_value} -> {pixels} (DPI: {dpi})")
        return pixels
    
    def twip_to_emu(self, twip_value: float) -> float:
        """
        Convert TWIP to EMU.
        
        Args:
            twip_value: TWIP value to convert
            
        Returns:
            EMU value
        """
        if not isinstance(twip_value, (int, float)):
            raise ValueError("TWIP value must be a number")
        
        mm = self.twip_to_mm(twip_value)
        emu = self.mm_to_emu(mm)
        logger.debug(f"TWIP to EMU: {twip_value} -> {emu}")
        return emu
    
    def emu_to_twip(self, emu_value: float) -> float:
        """
        Convert EMU to TWIP.
        
        Args:
            emu_value: EMU value to convert
            
        Returns:
            TWIP value
        """
        if not isinstance(emu_value, (int, float)):
            raise ValueError("EMU value must be a number")
        
        mm = self.emu_to_mm(emu_value)
        twip = mm / self.conversion_factors['twip_to_mm']
        logger.debug(f"EMU to TWIP: {emu_value} -> {twip}")
        return twip
    
    def set_dpi(self, dpi: int) -> None:
        """
        Set DPI for pixel conversions.
        
        Args:
            dpi: Dots per inch
        """
        if not isinstance(dpi, int) or dpi <= 0:
            raise ValueError("DPI must be a positive integer")
        
        self.dpi = dpi
        logger.debug(f"DPI set to: {dpi}")
    
    def get_dpi(self) -> int:
        """
        Get current DPI.
        
        Returns:
            Current DPI value
        """
        return self.dpi
    
    def get_conversion_factors(self) -> Dict[str, float]:
        """
        Get all conversion factors.
        
        Returns:
            Dictionary with conversion factors
        """
        return self.conversion_factors.copy()
    
    def validate_unit(self, value: float, unit: str) -> bool:
        """
        Validate unit value.
        
        Args:
            value: Value to validate
            unit: Unit type
            
        Returns:
            True if valid, False otherwise
        """
        if not isinstance(value, (int, float)):
            return False
        
        if unit not in ['emu', 'twip', 'pt', 'mm', 'px']:
            return False
        
        return True
    
    def convert(self, value: float, from_unit: str, to_unit: str, dpi: int = None) -> float:
        """
        Convert between any supported units.
        
        Args:
            value: Value to convert
            from_unit: Source unit
            to_unit: Target unit
            dpi: Dots per inch for pixel conversions
            
        Returns:
            Converted value
        """
        if not self.validate_unit(value, from_unit):
            raise ValueError(f"Invalid value or unit: {value} {from_unit}")
        
        if to_unit not in ['emu', 'twip', 'pt', 'mm', 'px']:
            raise ValueError(f"Invalid target unit: {to_unit}")
        
        if dpi is None:
            dpi = self.dpi
        
        # Convert to millimeters first
        if from_unit == 'emu':
            mm = self.emu_to_mm(value)
        elif from_unit == 'twip':
            mm = self.twip_to_mm(value)
        elif from_unit == 'pt':
            mm = value / self.conversion_factors['mm_to_pt']
        elif from_unit == 'mm':
            mm = value
        elif from_unit == 'px':
            mm = self.pixels_to_mm(value, dpi)
        
        # Convert from millimeters to target unit
        if to_unit == 'emu':
            result = self.mm_to_emu(mm)
        elif to_unit == 'twip':
            result = mm / self.conversion_factors['twip_to_mm']
        elif to_unit == 'pt':
            result = mm * self.conversion_factors['mm_to_pt']
        elif to_unit == 'mm':
            result = mm
        elif to_unit == 'px':
            result = self.mm_to_pixels(mm, dpi)
        
        logger.debug(f"Unit conversion: {value} {from_unit} -> {result} {to_unit}")
        return result
    
    def get_unit_info(self) -> Dict[str, Any]:
        """
        Get unit converter information.
        
        Returns:
            Dictionary with unit converter information
        """
        return {
            'dpi': self.dpi,
            'conversion_factors': self.conversion_factors.copy(),
            'supported_units': ['emu', 'twip', 'pt', 'mm', 'px']
        }
    
    # Convenience methods for common conversions
    def mm_to_pt(self, mm_value: float) -> float:
        """Convert millimeters to points."""
        return mm_value * self.conversion_factors['mm_to_pt']
    
    def pt_to_mm(self, pt_value: float) -> float:
        """Convert points to millimeters."""
        return pt_value * self.conversion_factors['pt_to_mm']
    
    def px_to_pt(self, px_value: float, dpi: int = None) -> float:
        """Convert pixels to points."""
        if dpi is None:
            dpi = self.dpi
        return px_value * (72.0 / dpi)
    
    def pt_to_px(self, pt_value: float, dpi: int = None) -> float:
        """Convert points to pixels."""
        if dpi is None:
            dpi = self.dpi
        return pt_value * (dpi / 72.0)
