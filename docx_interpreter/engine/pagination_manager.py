"""

Pagination Manager for UnifiedLayout.

Handles:
- page-break-before, page-break-after
- assigning headers and footers to specific pages
- different page variants (first, even, odd)

"""

from typing import Dict, List, Optional, Any, Tuple
from .unified_layout import UnifiedLayout, LayoutPage, LayoutBlock
from .layout_primitives import BlockContent, GenericLayout
from .geometry import Rect, Size, Margins
from .assembler.layout_assembler import LayoutAssembler
from .page_variator import Placement


class HeaderFooterResolver:
    """

    Resolves headers and footers for specific pages.

    Handles different page variants:
    - first: first page
    - even: even pages
    - odd: odd pages (except first)
    - default: default header/footer

    """
    
    def __init__(self, layout_structure):
        """

        Args:
        layout_structure: LayoutStructure with headers and footers

        """
        import logging
        logger = logging.getLogger(__name__)
        
        self.headers = layout_structure.headers
        self.footers = layout_structure.footers
        
        logger.info(f"HeaderFooterResolver initialized: headers={list(self.headers.keys()) if isinstance(self.headers, dict) else 'N/A'}, "
                   f"footers={list(self.footers.keys()) if isinstance(self.footers, dict) else 'N/A'}")
        if isinstance(self.headers, dict):
            for key, value in self.headers.items():
                logger.info(f"  Header '{key}': {len(value) if isinstance(value, list) else 'N/A'} items")
    
    def resolve(self, page_number: int, section_info: Optional[Dict[str, Any]] = None) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """

        Resolves header and footer for given page.

        Args:
        page_number: Page number (1-based)
        section_info: Optional section information (may contain specific headers/footers)

        Returns:
        Tuple (header, footer) - both can be None

        """
        header = self.get_header_for_page(page_number, section_info)
        footer = self.get_footer_for_page(page_number, section_info)
        return header, footer
    
    def get_header_for_page(
        self,
        page_number: int,
        section_info: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """

        Returns header for given page.

        Args:
        page_number: Page number (1-based)
        section_info: Optional section information

        Returns:
        Dict with header data or None

        """
        # Check if section has specific headers
        if section_info and "headers" in section_info:
            section_headers = section_info["headers"]
            if isinstance(section_headers, dict):
                # Use headers from section
                headers = section_headers
            else:
                headers = self.headers
        else:
            headers = self.headers
        
        # Dla pierwszej strony
        if page_number == 1:
            if "first" in headers:
                header_list = headers["first"]
                if header_list and len(header_list) > 0:
                    return header_list[0]
            # Fallback na default
            if "default" in headers:
                header_list = headers["default"]
                if header_list and len(header_list) > 0:
                    return header_list[0]
            return None
        
        # Dla parzystych stron
        if page_number % 2 == 0:
            if "even" in headers:
                header_list = headers["even"]
                if header_list and len(header_list) > 0:
                    return header_list[0]
            # Fallback na default
            if "default" in headers:
                header_list = headers["default"]
                if header_list and len(header_list) > 0:
                    return header_list[0]
            return None
        
        # For odd pages (except first)
        if page_number % 2 == 1:
            if "odd" in headers:
                header_list = headers["odd"]
                if header_list and len(header_list) > 0:
                    return header_list[0]
            # Fallback na default
            if "default" in headers:
                header_list = headers["default"]
                if header_list and len(header_list) > 0:
                    return header_list[0]
            return None
        
        return None
    
    def get_footer_for_page(
        self,
        page_number: int,
        section_info: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """

        Returns footer for given page.

        Args:
        page_number: Page number (1-based)
        section_info: Optional section information

        Returns:
        Dict with footer data or None

        """
        # Check if section has specific footers
        if section_info and "footers" in section_info:
            section_footers = section_info["footers"]
            if isinstance(section_footers, dict):
                # Use footers from section
                footers = section_footers
            else:
                footers = self.footers
        else:
            footers = self.footers
        
        # Dla pierwszej strony
        if page_number == 1:
            if "first" in footers:
                footer_list = footers["first"]
                if footer_list and len(footer_list) > 0:
                    return footer_list  # Return entire list of elements
            # Fallback na default
            if "default" in footers:
                footer_list = footers["default"]
                if footer_list and len(footer_list) > 0:
                    return footer_list  # Return entire list of elements
            return None
        
        # Dla parzystych stron
        if page_number % 2 == 0:
            if "even" in footers:
                footer_list = footers["even"]
                if footer_list and len(footer_list) > 0:
                    return footer_list  # Return entire list of elements
            # Fallback na default
            if "default" in footers:
                footer_list = footers["default"]
                if footer_list and len(footer_list) > 0:
                    return footer_list  # Return entire list of elements
            return None
        
        # For odd pages (except first)
        if page_number % 2 == 1:
            if "odd" in footers:
                footer_list = footers["odd"]
                if footer_list and len(footer_list) > 0:
                    return footer_list  # Return entire list of elements
            # Fallback na default
            if "default" in footers:
                footer_list = footers["default"]
                if footer_list and len(footer_list) > 0:
                    return footer_list  # Return entire list of elements
            return None
        
        return None


class PaginationManager:
    """

    Pagination manager for UnifiedLayout.

    Handles:
    - page-break-before/after (already in LayoutAssembler, but can be used here)
    - assigning headers and footers
    - different page variants

    """
    
    def __init__(
        self,
        unified_layout: UnifiedLayout,
        layout_assembler: Optional[LayoutAssembler] = None,
        header_footer_resolver: Optional[HeaderFooterResolver] = None,
        page_variator: Optional[Any] = None,
    ):
        """

        Args:
        unified_layout: UnifiedLayout to manage
        header_footer_resolver: Optional headers/footers resolver

        """
        self.unified_layout = unified_layout
        self.header_footer_resolver = header_footer_resolver
        self.layout_assembler = layout_assembler
        self.page_variator = page_variator
    
    def apply_headers_footers(self, layout_structure=None):
        """

        Applies headers and footers to pages in UnifiedLayout.

        Adds LayoutBlock with type "header" or "footer" to appropriate pages.

        Args:
        layout_structure: Optional LayoutStructure (if no resolver)

        """
        # If no resolver but layout_structure exists, create it
        if not self.header_footer_resolver and layout_structure:
            self.header_footer_resolver = HeaderFooterResolver(layout_structure)
        
        if not self.header_footer_resolver:
            return
        
        import logging
        logger = logging.getLogger(__name__)
        
        # Get section information from layout_structure if available
        # IMPORTANT: Use section information from parser (xml_parser.parse_sections) if available
        sections_info = None
        if layout_structure and hasattr(layout_structure, 'sections'):
            sections_info = layout_structure.sections
        
        # Alternatively, try to get sections from parser if available
        if not sections_info and hasattr(self, 'layout_assembler') and hasattr(self.layout_assembler, 'package_reader'):
            try:
                from ..parser.xml_parser import XMLParser
                if self.layout_assembler.package_reader:
                    parser = XMLParser(self.layout_assembler.package_reader)
                    if hasattr(parser, 'parse_sections'):
                        parsed_sections = parser.parse_sections()
                        if parsed_sections:
                            sections_info = parsed_sections
            except Exception as e:
                logger.debug(f"Failed to get sections from parser: {e}")
        
        for page in self.unified_layout.pages:
            page_number = page.number
            blocks_before = len(page.blocks)
            
            # Check if page should skip headers and footers
            skip_headers_footers = getattr(page, 'skip_headers_footers', False)
            if skip_headers_footers:
                logger.info(f"Page {page_number}: Skipping headers and footers (skip_headers_footers=True)")
                continue

            variant = None
            if self.page_variator:
                variant = self.page_variator.get_variant(page_number)

            # Determine section for page (for simplicity use first section)
            # TODO: Improve section determination logic based on page number
            section_info = None
            if sections_info:
                # Use first section (can be extended later with page -> section mapping)
                if isinstance(sections_info, dict) and sections_info:
                    first_section_key = list(sections_info.keys())[0]
                    section_info = sections_info[first_section_key]
                elif isinstance(sections_info, list) and sections_info:
                    section_info = sections_info[0]

            # Headers
            header_placements = variant.header_placements if variant else []
            if not header_placements:
                header_data = self.header_footer_resolver.get_header_for_page(page_number, section_info)
                if header_data:
                    header_placements = self._fallback_header_placements(header_data, page)
            insert_index = 0
            for placement in header_placements:
                header_blocks = self._create_header_blocks(placement.element, page, placement.y, placement.height)
                for block in header_blocks:
                    page.blocks.insert(insert_index, block)
                    insert_index += 1

            # Footers
            footer_placements = variant.footer_placements if variant else []
            if not footer_placements:
                footer_data = self.header_footer_resolver.get_footer_for_page(page_number, section_info)
                if footer_data:
                    footer_placements = self._fallback_footer_placements(footer_data, page)

            for placement in footer_placements:
                footer_blocks = self._create_footer_blocks(
                    placement.element,
                    page,
                    placement.y,
                    placement.height,
                )
                for block in footer_blocks:
                    page.blocks.append(block)

            blocks_after = len(page.blocks)
            logger.info(
                f"Page {page_number}: Blocks before={blocks_before}, after={blocks_after}, added={blocks_after - blocks_before}"
            )
    
    def _create_header_blocks(
        self,
        header_data: Dict[str, Any],
        page: LayoutPage,
        frame_y: float,
        block_height: Optional[float] = None,
    ) -> List[LayoutBlock]:
        blocks: List[LayoutBlock] = []

        header_height = block_height or header_data.get("height") or header_data.get("style", {}).get("height") or 20.0

        header_rect = Rect(
            x=page.margins.left,
            y=frame_y,
            width=page.size.width - page.margins.left - page.margins.right,
            height=header_height,
        )

        header_payload = dict(header_data)
        header_payload["header_footer_context"] = "header"

        if self.layout_assembler:
            content = self.layout_assembler._prepare_block_content(header_payload, header_rect)
        else:
            generic_payload = GenericLayout(frame=header_rect, data=header_payload)
            content = BlockContent(payload=generic_payload, raw=header_payload)

        primary_block = LayoutBlock(
            frame=header_rect,
            block_type=header_payload.get("type", "header"),
            content=content,
            style=header_payload.get("style", {}),
            page_number=page.number,
        )
        blocks.append(primary_block)

        blocks.append(
            LayoutBlock(
                frame=header_rect,
                block_type="header",
                content=BlockContent(
                    payload=GenericLayout(frame=header_rect, data={"type": "header_marker"}),
                    raw={"type": "header_marker"},
                ),
                style={},
                page_number=page.number,
            )
        )

        return blocks
    
    def _create_footer_blocks(
        self,
        footer_data: Dict[str, Any],
        page: LayoutPage,
        frame_y: float,
        block_height: Optional[float] = None,
    ) -> List[LayoutBlock]:
        blocks = []
 
        footer_height = block_height or footer_data.get("height") or footer_data.get("style", {}).get("height") or 20.0
 
        footer_rect = Rect(
            x=page.margins.left,
            y=frame_y,
            width=page.size.width - page.margins.left - page.margins.right,
            height=footer_height,
        )
 
        prepared_footer = dict(footer_data)
        prepared_footer["header_footer_context"] = "footer"
 
        if self.layout_assembler:
            content = self.layout_assembler._prepare_block_content(prepared_footer, footer_rect)
        else:
            generic_payload = GenericLayout(frame=footer_rect, data=prepared_footer)
            content = BlockContent(payload=generic_payload, raw=prepared_footer)
 
        footer_block = LayoutBlock(
            frame=footer_rect,
            block_type=prepared_footer.get("type", "footer"),
            content=content,
            style=prepared_footer.get("style", {}),
            page_number=page.number,
        )
        blocks.append(footer_block)
 
        blocks.append(
            LayoutBlock(
                frame=footer_rect,
                block_type="footer",
                content=BlockContent(payload=GenericLayout(frame=footer_rect, data={"type": "footer_marker"}), raw={"type": "footer_marker"}),
                style={},
                page_number=page.number,
            )
        )
 
        return blocks

    def _fallback_header_placements(self, header_data: Any, page: LayoutPage) -> List[Placement]:
        items = header_data if isinstance(header_data, list) else [header_data]
        placements: List[Placement] = []
        cursor = page.size.height - page.margins.top

        for element in items:
            style = element.get("style", {}) if isinstance(element, dict) else {}
            spacing_before = float(style.get("spacing_before", 0.0) or 0.0)
            spacing_after = float(style.get("spacing_after", 0) or 0)
            height = float(style.get("height", 0) or 0) or 20.0
            if self.layout_assembler:
                try:
                    measured = self.layout_assembler._measure_block_height(element)
                    if measured:
                        height = measured
                except Exception:
                    pass

            cursor -= spacing_before
            y = cursor - height
            placements.append(Placement(element=element, height=height, y=y))
            cursor = y - spacing_after

        return placements

    def _fallback_footer_placements(self, footer_data: Any, page: LayoutPage) -> List[Placement]:
        items = footer_data if isinstance(footer_data, list) else [footer_data]
        reversed_items = list(reversed(items))
        placements_reversed: List[Placement] = []
        cursor = page.margins.bottom

        for element in reversed_items:
            style = element.get("style", {}) if isinstance(element, dict) else {}
            spacing_before = float(style.get("spacing_before", 0.0) or 0.0)
            spacing_after = float(style.get("spacing_after", 0) or 0)
            height = float(style.get("height", 0) or 0) or 20.0
            if self.layout_assembler:
                try:
                    measured = self.layout_assembler._measure_block_height(element)
                    if measured:
                        height = measured
                except Exception:
                    pass

            cursor += spacing_after
            y = cursor
            placements_reversed.append(Placement(element=element, height=height, y=y))
            cursor += height + spacing_before

        return list(reversed(placements_reversed))
    
    def validate_pagination(self) -> List[str]:
        """

        Validates pagination - checks if all blocks fit on pages.

        Returns:
        List of error messages (empty if all OK)

        """
        errors = []
        
        for page in self.unified_layout.pages:
            for block in page.blocks:
                # Check if block exceeds page boundaries
                if block.frame.x + block.frame.width > page.size.width:
                    errors.append(
                        f"Blok {block.block_type} na stronie {page.number} "
                        f"wychodzi poza szerokość strony"
                    )
                
                if block.frame.y < 0:
                    errors.append(
                        f"Blok {block.block_type} na stronie {page.number} "
                        f"wychodzi poza dolną krawędź strony"
                    )
                
                if block.frame.y + block.frame.height > page.size.height:
                    errors.append(
                        f"Blok {block.block_type} na stronie {page.number} "
                        f"wychodzi poza górną krawędź strony"
                    )
        
        return errors

