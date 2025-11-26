"""

Layout Validator - UnifiedLayout validation.

Checks:
- whether blocks don't exceed page boundaries
- whether spacing is not negative
- whether every LayoutBlock has style
- whether positions are correct

"""

from typing import List, Dict, Any
from .unified_layout import UnifiedLayout, LayoutPage, LayoutBlock


class LayoutValidator:
    """Layout validator - checks UnifiedLayout integrity."""
    
    def __init__(self, unified_layout: UnifiedLayout):
        """
        Args:
            unified_layout: UnifiedLayout do walidacji
        """
        self.unified_layout = unified_layout
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def validate(self) -> tuple[bool, List[str], List[str]]:
        """

        Performs full layout validation.

        Returns:
        Tuple (is_valid, errors, warnings)

        """
        self.errors.clear()
        self.warnings.clear()
        
        self._validate_pages_exist()
        self._validate_blocks_in_bounds()
        self._validate_block_styles()
        self._validate_spacing()
        self._validate_page_consistency()
        self._validate_block_overflow()
        self._validate_spacing_conflicts()
        self._validate_empty_pages()
        
        is_valid = len(self.errors) == 0
        return is_valid, self.errors.copy(), self.warnings.copy()
    
    def _validate_pages_exist(self) -> None:
        """Checks if pages exist."""
        if not self.unified_layout.pages:
            self.errors.append("UnifiedLayout nie zawiera żadnych stron")
    
    def _validate_blocks_in_bounds(self) -> None:
        """Checks if all blocks fit within page boundaries."""
        for page in self.unified_layout.pages:
            page_number = page.number
            
            for block in page.blocks:
                frame = block.frame
                
                # Check if block exceeds page width
                if frame.x < 0:
                    self.errors.append(
                        f"Blok {block.block_type} na stronie {page_number} "
                        f"wychodzi poza lewą krawędź strony (x={frame.x})"
                    )
                
                if frame.x + frame.width > page.size.width:
                    self.errors.append(
                        f"Blok {block.block_type} na stronie {page_number} "
                        f"wychodzi poza prawą krawędź strony "
                        f"(x={frame.x}, width={frame.width}, page_width={page.size.width})"
                    )
                
                # Check if block exceeds page height
                if frame.y < 0:
                    self.errors.append(
                        f"Blok {block.block_type} na stronie {page_number} "
                        f"wychodzi poza dolną krawędź strony (y={frame.y})"
                    )
                
                if frame.y + frame.height > page.size.height:
                    self.errors.append(
                        f"Blok {block.block_type} na stronie {page_number} "
                        f"wychodzi poza górną krawędź strony "
                        f"(y={frame.y}, height={frame.height}, page_height={page.size.height})"
                    )
                
                # Check if dimensions are positive
                if frame.width <= 0:
                    self.errors.append(
                        f"Blok {block.block_type} na stronie {page_number} "
                        f"ma nieprawidłową szerokość: {frame.width}"
                    )
                
                if frame.height <= 0:
                    self.errors.append(
                        f"Blok {block.block_type} na stronie {page_number} "
                        f"ma nieprawidłową wysokość: {frame.height}"
                    )
    
    def _validate_block_styles(self) -> None:
        """Checks if every block has style."""
        for page in self.unified_layout.pages:
            page_number = page.number
            
            for block in page.blocks:
                if not block.style:
                    self.warnings.append(
                        f"Blok {block.block_type} na stronie {page_number} "
                        f"nie ma przypisanego stylu"
                    )
                
                if not isinstance(block.style, dict):
                    self.warnings.append(
                        f"Blok {block.block_type} na stronie {page_number} "
                        f"ma styl niebędący słownikiem: {type(block.style)}"
                    )
    
    def _validate_spacing(self) -> None:
        """Sprawdza czy spacing nie jest ujemny."""
        for page in self.unified_layout.pages:
            page_number = page.number
            
            for block in page.blocks:
                style = block.style
                if not isinstance(style, dict):
                    continue
                
                spacing_before = style.get("spacing_before", 0)
                spacing_after = style.get("spacing_after", 0)
                
                if spacing_before < 0:
                    self.warnings.append(
                        f"Blok {block.block_type} na stronie {page_number} "
                        f"ma ujemny spacing_before: {spacing_before}"
                    )
                
                if spacing_after < 0:
                    self.warnings.append(
                        f"Blok {block.block_type} na stronie {page_number} "
                        f"ma ujemny spacing_after: {spacing_after}"
                    )
    
    def _validate_page_consistency(self) -> None:
        """Checks page numbering consistency."""
        expected_page_number = 1
        
        for page in self.unified_layout.pages:
            if page.number != expected_page_number:
                self.warnings.append(
                    f"Nieprawidłowa numeracja stron: oczekiwano {expected_page_number}, "
                    f"otrzymano {page.number}"
                )
            expected_page_number += 1
    
    def _validate_block_overflow(self) -> None:
        """Checks if blocks don't exceed bottom margins."""
        for page in self.unified_layout.pages:
            page_number = page.number
            bottom_margin = page.margins.bottom
            
            for block in page.blocks:
                # Check if block goes below bottom margin
                if block.frame.y < bottom_margin:
                    self.errors.append(
                        f"Blok {block.block_type} na stronie {page_number} "
                        f"wychodzi poza dolny margines "
                        f"(y={block.frame.y}, bottom_margin={bottom_margin})"
                    )
    
    def _validate_spacing_conflicts(self) -> None:
        """Checks if spacing_before + spacing_after don't conflict."""
        for page in self.unified_layout.pages:
            page_number = page.number
            
            for i, block in enumerate(page.blocks):
                if i == 0:
                    continue  # Pierwszy blok nie ma poprzedniego
                
                prev_block = page.blocks[i - 1]
                style = block.style
                prev_style = prev_block.style
                
                if not isinstance(style, dict) or not isinstance(prev_style, dict):
                    continue
                
                spacing_after = prev_style.get("spacing_after", 0)
                spacing_before = style.get("spacing_before", 0)
                
                # Check if blocks overlap
                prev_bottom = prev_block.frame.y + prev_block.frame.height
                current_top = block.frame.y
                
                # If spacing is too large, there may be conflicts
                gap = current_top - prev_bottom
                expected_gap = spacing_after + spacing_before
                
                if gap < 0:
                    self.errors.append(
                        f"Bloki na stronie {page_number} nakładają się: "
                        f"blok {prev_block.block_type} i {block.block_type}"
                    )
                elif gap < expected_gap * 0.5:  # Gap is significantly smaller than expected
                    self.warnings.append(
                        f"Bloki na stronie {page_number} mają zbyt mały odstęp: "
                        f"oczekiwano {expected_gap}, otrzymano {gap}"
                    )
    
    def _validate_empty_pages(self) -> None:
        """Sprawdza czy nie ma pustych stron."""
        for page in self.unified_layout.pages:
            page_number = page.number
            
            # Count blocks that are not header/footer
            content_blocks = [
                b for b in page.blocks
                if b.block_type not in ("header", "footer")
            ]
            
            if not content_blocks and page_number > 1:  # First page can be empty
                self.warnings.append(
                    f"Strona {page_number} jest pusta (bez bloków treści)"
                )
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Zwraca podsumowanie walidacji.
        
        Returns:
            Dict z informacjami o walidacji
        """
        is_valid, errors, warnings = self.validate()
        
        return {
            "is_valid": is_valid,
            "total_errors": len(errors),
            "total_warnings": len(warnings),
            "total_pages": len(self.unified_layout.pages),
            "total_blocks": sum(len(page.blocks) for page in self.unified_layout.pages),
            "errors": errors,
            "warnings": warnings,
        }

