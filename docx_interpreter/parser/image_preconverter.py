"""
Image pre-converter for detecting and converting WMF/EMF images during parsing.
"""

import logging
from typing import Any, Optional, Dict, List
from pathlib import Path

logger = logging.getLogger(__name__)


def preconvert_images_from_model(
    model: Any,
    package_reader: Any,
    image_cache: Any,
    media_converter: Any,
    include_watermarks: bool = True,
) -> None:
    """
    Pre-convert WMF/EMF images found in the parsed model.
    
    This function recursively searches through the model for images and
    schedules asynchronous conversion for WMF/EMF images.
    
    Args:
        model: Parsed document model (Body, Paragraph, etc.)
        package_reader: PackageReader instance
        image_cache: ImageConversionCache instance
        media_converter: MediaConverter instance
        include_watermarks: If True, also pre-convert watermark images (default: True)
    """
    if not image_cache or not media_converter:
        return
    
    # Recursively find all images in the model (including watermarks if include_watermarks=True)
    images = _find_images_in_model(model, include_watermarks=include_watermarks)
    
    logger.info(f"preconvert_images_from_model: Found {len(images)} images (include_watermarks={include_watermarks})")
    
    for image_info in images:
        logger.debug(f"Processing image_info: relationship_id={image_info.get('relationship_id')}, type={image_info.get('type')}, is_watermark={image_info.get('is_watermark')}")
        relationship_id = image_info.get("relationship_id")
        if not relationship_id:
            continue
        
        # Check if it's WMF/EMF
        image_path = image_info.get("path") or image_info.get("filename") or image_info.get("image_path")
        
        # Try to get path from relationship if not available
        if not image_path:
            try:
                # Try different relationship sources
                relationship_source = image_info.get("relationship_source") or image_info.get("part_path")
                if relationship_source:
                    rels_dict = package_reader.get_relationships(relationship_source)
                    if isinstance(rels_dict, dict):
                        relationship = rels_dict.get(relationship_id)
                        if relationship:
                            image_path = relationship.get("target") or relationship.get("Target")
                # Fallback to document relationships
                if not image_path:
                    rels_dict = package_reader.get_relationships("document")
                    if isinstance(rels_dict, dict):
                        relationship = rels_dict.get(relationship_id)
                        if relationship:
                            image_path = relationship.get("target") or relationship.get("Target")
            except Exception:
                pass
        
        # Normalize path (remove leading /tmp/... if present) BEFORE checking extension
        if image_path:
            # Remove temporary directory prefix if present
            if "/tmp/" in image_path and "word/" in image_path:
                # Extract word/... part
                word_idx = image_path.find("word/")
                if word_idx >= 0:
                    image_path = image_path[word_idx:]
            elif not image_path.startswith("word/"):
                image_path = f"word/{image_path}"
        
        if not image_path:
            continue
        
        # Check file extension AFTER normalization
        path_lower = str(image_path).lower()
        is_wmf_emf = path_lower.endswith(".wmf") or path_lower.endswith(".emf")
        if not is_wmf_emf:
            logger.debug(f"Skipping image {relationship_id}: not WMF/EMF (path={image_path})")
            continue
        
        logger.debug(f"Processing WMF/EMF image {relationship_id} (path={image_path})")
        
        # Load image data
        try:
            image_data = package_reader.get_binary_content(image_path)
            
            if not image_data:
                logger.debug(f"No image data for {relationship_id} at {image_path}")
                continue
            
            logger.debug(f"Loaded {len(image_data)} bytes for {relationship_id}")
            
            # Get dimensions for conversion
            width_pt = image_info.get("width", 0)
            height_pt = image_info.get("height", 0)
            
            # Convert to float if needed
            try:
                width_pt = float(width_pt) if width_pt else 0
            except (TypeError, ValueError):
                width_pt = 0
            try:
                height_pt = float(height_pt) if height_pt else 0
            except (TypeError, ValueError):
                height_pt = 0
            
            # Convert EMU to pixels if needed (EMU > 10000)
            from ..engine.geometry import emu_to_points
            if width_pt > 10000:
                width_pt = emu_to_points(width_pt)
            if height_pt > 10000:
                height_pt = emu_to_points(height_pt)
            
            # Convert points to pixels (1 point = 1/72 inch, assume 96 DPI for pixels)
            # 1 point = 96/72 = 1.333 pixels
            def points_to_pixels(pt: float) -> float:
                return pt * (96.0 / 72.0)
            
            width_px = int(points_to_pixels(width_pt)) if width_pt > 0 else None
            height_px = int(points_to_pixels(height_pt)) if height_pt > 0 else None
            
            # Schedule async conversion
            logger.info(f"Pre-converting image {relationship_id} ({image_path}), size={len(image_data)} bytes, dimensions={width_px}x{height_px}")
            image_cache.convert_async(
                relationship_id=relationship_id,
                image_data=image_data,
                image_path=image_path,
                converter_fn=media_converter.convert_emf_to_png,
                width_px=width_px,
                height_px=height_px,
            )
            logger.debug(f"Pre-conversion scheduled for {relationship_id} ({image_path})")
            
        except Exception as e:
            logger.debug(f"Failed to pre-convert image {relationship_id}: {e}")


def _find_images_in_model(model: Any, images: Optional[List[Dict[str, Any]]] = None, include_watermarks: bool = True) -> List[Dict[str, Any]]:
    """
    Recursively find all images in the model.
    
    Args:
        model: Model object to search
        images: Accumulator list (created automatically)
        include_watermarks: If True, also find watermark images (default: True)
        
    Returns:
        List of image dictionaries with relationship_id, path, width, height
    """
    if images is None:
        images = []
    
    # Check if model is an Image (or watermark image if include_watermarks=True)
    is_image = hasattr(model, "relationship_id") or (isinstance(model, dict) and model.get("type") in ("image", "Image"))
    
    # Check if it's a watermark image (by is_watermark flag or behindDoc property)
    is_watermark_image = False
    if include_watermarks and isinstance(model, dict):
        # Check explicit is_watermark flag
        if model.get("is_watermark", False):
            is_watermark_image = True
        # Check behindDoc property (watermarks are behind document)
        elif model.get("properties", {}).get("behindDoc") == "1" or model.get("properties", {}).get("behindDoc") == 1:
            is_watermark_image = True
        # Check if it's a drawing_anchor with behindDoc and has relationship_id (image watermark)
        elif model.get("type") == "drawing_anchor" and model.get("relationship_id"):
            props = model.get("properties", {})
            if props and (props.get("behindDoc") == "1" or props.get("behindDoc") == 1):
                is_watermark_image = True
    
    # Include watermark images if they have relationship_id (for image conversion)
    if is_image or (is_watermark_image and model.get("relationship_id")):
        image_info = {}
        if isinstance(model, dict):
            image_info = model.copy()
        else:
            image_info = {
                "relationship_id": getattr(model, "relationship_id", None),
                "path": getattr(model, "path", None),
                "filename": getattr(model, "filename", None),
                "width": getattr(model, "width", 0),
                "height": getattr(model, "height", 0),
            }
        if image_info.get("relationship_id"):
            images.append(image_info)
    
    # Check if model is a dict with images or drawings list
    if isinstance(model, dict):
        # Check for images list directly
        if "images" in model and isinstance(model["images"], list):
            for img in model["images"]:
                if isinstance(img, dict) and img.get("relationship_id"):
                    images.append(img)
        # Check for drawings list (used in runs)
        if "drawings" in model and isinstance(model["drawings"], list):
            for drawing in model["drawings"]:
                if isinstance(drawing, dict):
                    # Drawing may contain images
                    if "images" in drawing and isinstance(drawing["images"], list):
                        for img in drawing["images"]:
                            if isinstance(img, dict) and img.get("relationship_id"):
                                images.append(img)
                    # Or drawing itself may be an image
                    if drawing.get("relationship_id"):
                        images.append(drawing)
                    # Check drawing content (drawing_anchor, etc.)
                    if "content" in drawing and isinstance(drawing["content"], list):
                        for item in drawing["content"]:
                            if isinstance(item, dict) and item.get("relationship_id"):
                                images.append(item)
    
    # Recursively search children
    children = []
    if hasattr(model, "children"):
        children = model.children
    elif hasattr(model, "elements"):
        children = model.elements
    elif isinstance(model, dict):
        # Check for common image containers (elements first, as it's used in headers)
        for key in ["elements", "content", "runs", "children"]:
            if key in model:
                children = model[key] if isinstance(model[key], list) else [model[key]]
                break
    
    for child in children:
        if child:
            _find_images_in_model(child, images, include_watermarks=include_watermarks)
    
    return images

