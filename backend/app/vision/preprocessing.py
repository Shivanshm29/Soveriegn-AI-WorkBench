"""Local image preprocessing, normalization, and tile generation for large engineering drawings."""

import os
from typing import List, Tuple, Dict, Any, Optional
from PIL import Image, ImageOps, ImageFilter

from backend.app.vision.schemas import ImageTile
from backend.app.vision.errors import (
    CorruptImageError,
    OversizedImageError,
    TileGenerationError,
    InvalidBoundingBoxError,
)

DEFAULT_TILE_CACHE_DIR = os.path.abspath(os.path.join("data", "cache", "vision_tiles"))


class ImagePreprocessor:
    """Performs deterministic local image transformations, tiling, and resolution normalization."""

    def __init__(
        self,
        max_dimension: int = 8192,
        max_file_size_bytes: int = 50 * 1024 * 1024,  # 50MB
        max_tiles: int = 16,
        tile_cache_dir: str = DEFAULT_TILE_CACHE_DIR,
    ):
        self.max_dimension = max_dimension
        self.max_file_size_bytes = max_file_size_bytes
        self.max_tiles = max_tiles
        self.tile_cache_dir = tile_cache_dir
        os.makedirs(self.tile_cache_dir, exist_ok=True)

    def validate_file(self, file_path_or_img: Any) -> Tuple[int, int]:
        """Validate local image file existence, size, and readable dimensions."""
        if isinstance(file_path_or_img, Image.Image):
            w, h = file_path_or_img.size
            if w > self.max_dimension or h > self.max_dimension:
                raise OversizedImageError(
                    f"Image dimensions ({w}x{h}) exceed maximum allowed dimension ({self.max_dimension}px).",
                    width=w,
                    height=h,
                    max_dim=self.max_dimension,
                )
            return w, h

        file_path = str(file_path_or_img)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Image file not found: {file_path}")

        file_size = os.path.getsize(file_path)
        if file_size > self.max_file_size_bytes:
            raise OversizedImageError(
                f"Image file size ({file_size} bytes) exceeds limit ({self.max_file_size_bytes} bytes).",
                width=0,
                height=0,
                max_dim=self.max_dimension,
            )

        try:
            with Image.open(file_path) as img:
                w, h = img.size
                if w > self.max_dimension or h > self.max_dimension:
                    raise OversizedImageError(
                        f"Image dimensions ({w}x{h}) exceed maximum allowed dimension ({self.max_dimension}px).",
                        width=w,
                        height=h,
                        max_dim=self.max_dimension,
                    )
                return w, h
        except OversizedImageError:
            raise
        except Exception as e:
            raise CorruptImageError(f"Failed to open or decode image file at {file_path}: {e}") from e

    def validate_image(self, file_path_or_img: Any) -> Tuple[int, int, str]:
        """Validate image and return (width, height, format)."""
        if isinstance(file_path_or_img, Image.Image):
            w, h = self.validate_file(file_path_or_img)
            fmt = file_path_or_img.format or "PNG"
            return w, h, fmt

        w, h = self.validate_file(file_path_or_img)
        try:
            with Image.open(file_path_or_img) as img:
                fmt = img.format or "PNG"
            return w, h, fmt
        except Exception:
            return w, h, "PNG"

    def load_image(self, file_path_or_img: Any) -> Image.Image:
        """Safely load and transpose orientation for local image."""
        if isinstance(file_path_or_img, Image.Image):
            return ImageOps.exif_transpose(file_path_or_img)
        self.validate_file(file_path_or_img)
        try:
            img = Image.open(file_path_or_img)
            img = ImageOps.exif_transpose(img)
            return img
        except Exception as e:
            raise CorruptImageError(f"Error loading image {file_path_or_img}: {e}") from e

    @staticmethod
    def to_grayscale(image: Image.Image) -> Image.Image:
        """Convert image to single-channel grayscale."""
        return image.convert("L")

    @staticmethod
    def normalize_contrast(image: Image.Image) -> Image.Image:
        """Apply local histogram autocontrast normalization."""
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        return ImageOps.autocontrast(image)

    @staticmethod
    def denoise(image: Image.Image) -> Image.Image:
        """Apply local median filter denoising."""
        return image.filter(ImageFilter.MedianFilter(size=3))

    @staticmethod
    def crop_region(image: Image.Image, bounding_box: List[float]) -> Image.Image:
        """Crop sub-region bounded by [x0, y0, x1, y1]."""
        if len(bounding_box) != 4:
            raise InvalidBoundingBoxError(f"Bounding box must contain exactly 4 coordinates, got {bounding_box}")

        x0, y0, x1, y1 = [int(round(c)) for c in bounding_box]
        w, h = image.size

        # Clamp coordinates to image boundaries
        x0 = max(0, min(w, x0))
        y0 = max(0, min(h, y0))
        x1 = max(x0, min(w, x1))
        y1 = max(y0, min(h, y1))

        if x1 - x0 <= 0 or y1 - y0 <= 0:
            raise InvalidBoundingBoxError(f"Invalid bounding box with zero area: {bounding_box}")

        return image.crop((x0, y0, x1, y1))

    def preprocess(
        self,
        image: Image.Image,
        to_grayscale: bool = False,
        normalize_contrast: bool = True,
        denoise: bool = False,
    ) -> Tuple[Image.Image, Dict[str, Any]]:
        """Run standard preprocessing transformations returning image and metadata dict."""
        meta = {
            "converted_grayscale": False,
            "contrast_normalized": False,
            "denoised": False,
        }
        res_img = image
        if to_grayscale and res_img.mode != "L":
            res_img = self.to_grayscale(res_img)
            meta["converted_grayscale"] = True
        if normalize_contrast:
            res_img = self.normalize_contrast(res_img)
            meta["contrast_normalized"] = True
        if denoise:
            res_img = self.denoise(res_img)
            meta["denoised"] = True
        return res_img, meta

    def generate_tiles(
        self,
        image_or_path: Any,
        document_id: str,
        source_hash: str,
        page_number: int = 1,
        tile_size: Any = (1024, 1024),
        overlap: int = 128,
    ) -> List[ImageTile]:
        """Tiling for large drawings. Preserves original coordinate bounding boxes and metadata."""
        img = self.load_image(image_or_path)
        w, h = img.size
        if isinstance(tile_size, int):
            tile_w, tile_h = tile_size, tile_size
        else:
            tile_w, tile_h = tile_size

        tiles: List[ImageTile] = []

        # If drawing fits comfortably within a single tile, return single tile
        if w <= tile_w and h <= tile_h:
            tile_filename = f"{source_hash}_p{page_number}_tile_0_0.png"
            tile_path = os.path.join(self.tile_cache_dir, tile_filename)
            img.save(tile_path, format="PNG")
            tiles.append(
                ImageTile(
                    document_id=document_id,
                    source_hash=source_hash,
                    page_number=page_number,
                    bounding_box=[0.0, 0.0, float(w), float(h)],
                    original_dimensions=(w, h),
                    tile_path=tile_path,
                    tile_col=0,
                    tile_row=0,
                    preprocessing_metadata={"tile_type": "full_image"},
                )
            )
            return tiles

        step_x = max(100, tile_w - overlap)
        step_y = max(100, tile_h - overlap)

        # Estimate tile count and fail early if resource limit exceeded
        import math
        est_cols = math.ceil((w - overlap) / step_x)
        est_rows = math.ceil((h - overlap) / step_y)
        est_tiles = est_cols * est_rows
        if est_tiles > self.max_tiles:
            raise TileGenerationError(
                f"Drawing of {w}x{h} would require approximately {est_tiles} tiles, exceeding limit of {self.max_tiles}.",
                requested_tiles=est_tiles,
                max_tiles=self.max_tiles,
            )

        row_idx = 0
        y = 0
        while y < h:
            col_idx = 0
            x = 0
            while x < w:
                if len(tiles) >= self.max_tiles:
                    raise TileGenerationError(
                        f"Generated tile count exceeded maximum limit of {self.max_tiles}.",
                        requested_tiles=len(tiles) + 1,
                        max_tiles=self.max_tiles,
                    )

                x1 = min(w, x + tile_w)
                y1 = min(h, y + tile_h)
                x0 = max(0, x1 - tile_w)
                y0 = max(0, y1 - tile_h)

                tile_crop = img.crop((x0, y0, x1, y1))
                tile_filename = f"{source_hash}_p{page_number}_tile_{row_idx}_{col_idx}.png"
                tile_path = os.path.join(self.tile_cache_dir, tile_filename)
                tile_crop.save(tile_path, format="PNG")

                tiles.append(
                    ImageTile(
                        document_id=document_id,
                        source_hash=source_hash,
                        page_number=page_number,
                        bounding_box=[float(x0), float(y0), float(x1), float(y1)],
                        original_dimensions=(w, h),
                        tile_path=tile_path,
                        tile_col=col_idx,
                        tile_row=row_idx,
                        preprocessing_metadata={
                            "tile_width": tile_crop.width,
                            "tile_height": tile_crop.height,
                            "step_x": step_x,
                            "step_y": step_y,
                        },
                    )
                )

                if x1 >= w:
                    break
                x += step_x
                col_idx += 1

            if len(tiles) >= self.max_tiles or y + tile_h >= h:
                break
            y += step_y
            row_idx += 1

        return tiles
