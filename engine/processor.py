"""
Core image processing engine for resizing, cropping, rotating, and transforming images.
"""
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple, Union
from PIL import Image, ImageOps


class ResampleFilter(str, Enum):
    LANCZOS = "Lanczos (High Quality)"
    BICUBIC = "Bicubic (Balanced)"
    BILINEAR = "Bilinear (Fast)"
    NEAREST = "Nearest Neighbor (Pixel Art)"


FILTER_MAP = {
    ResampleFilter.LANCZOS: Image.Resampling.LANCZOS,
    ResampleFilter.BICUBIC: Image.Resampling.BICUBIC,
    ResampleFilter.BILINEAR: Image.Resampling.BILINEAR,
    ResampleFilter.NEAREST: Image.Resampling.NEAREST,
}


@dataclass
class ImageInfo:
    filepath: Optional[Path]
    filename: str
    width: int
    height: int
    format: str
    mode: str
    file_size_bytes: int

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height if self.height > 0 else 1.0

    @property
    def formatted_file_size(self) -> str:
        if self.file_size_bytes <= 0:
            return "0 B"
        units = ["B", "KB", "MB", "GB"]
        size = float(self.file_size_bytes)
        unit_idx = 0
        while size >= 1024.0 and unit_idx < len(units) - 1:
            size /= 1024.0
            unit_idx += 1
        return f"{size:.2f} {units[unit_idx]}" if unit_idx > 0 else f"{int(size)} B"


class ImageProcessor:
    """Handles image manipulation operations."""

    @staticmethod
    def load_image(filepath: Union[str, Path]) -> Tuple[Image.Image, ImageInfo]:
        """Loads an image from disk and normalizes orientation based on EXIF."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {filepath}")

        # Open and apply EXIF orientation transpose if present
        raw_img = Image.open(path)
        img = ImageOps.exif_transpose(raw_img)
        if img is None:
            img = raw_img

        # Ensure image is loaded in memory
        img.load()

        info = ImageInfo(
            filepath=path,
            filename=path.name,
            width=img.width,
            height=img.height,
            format=(img.format or path.suffix.strip(".").upper() or "UNKNOWN"),
            mode=img.mode,
            file_size_bytes=path.stat().st_size,
        )
        return img, info

    @staticmethod
    def resize(
        img: Image.Image,
        target_width: Optional[int] = None,
        target_height: Optional[int] = None,
        scale_percent: Optional[float] = None,
        keep_aspect_ratio: bool = True,
        resample: ResampleFilter = ResampleFilter.LANCZOS,
    ) -> Image.Image:
        """
        Resizes an image by pixel dimensions or scale percentage.
        """
        orig_w, orig_h = img.size

        if scale_percent is not None and scale_percent > 0:
            factor = scale_percent / 100.0
            new_w = max(1, int(orig_w * factor))
            new_h = max(1, int(orig_h * factor))
        elif target_width is not None and target_height is not None:
            if keep_aspect_ratio:
                aspect = orig_w / orig_h
                # Fit within bounding box
                if (target_width / target_height) > aspect:
                    new_h = max(1, target_height)
                    new_w = max(1, int(new_h * aspect))
                else:
                    new_w = max(1, target_width)
                    new_h = max(1, int(new_w / aspect))
            else:
                new_w = max(1, target_width)
                new_h = max(1, target_height)
        elif target_width is not None:
            new_w = max(1, target_width)
            aspect = orig_w / orig_h
            new_h = max(1, int(new_w / aspect))
        elif target_height is not None:
            new_h = max(1, target_height)
            aspect = orig_w / orig_h
            new_w = max(1, int(new_h * aspect))
        else:
            return img.copy()

        pillow_filter = FILTER_MAP.get(resample, Image.Resampling.LANCZOS)
        return img.resize((new_w, new_h), pillow_filter)

    @staticmethod
    def crop(
        img: Image.Image,
        box: Tuple[int, int, int, int],
    ) -> Image.Image:
        """
        Crops an image using pixel coordinates: (left, top, right, bottom).
        """
        left, top, right, bottom = box
        # Clamp coordinates to image boundaries
        left = max(0, min(left, img.width - 1))
        top = max(0, min(top, img.height - 1))
        right = max(left + 1, min(right, img.width))
        bottom = max(top + 1, min(bottom, img.height))

        return img.crop((left, top, right, bottom))

    @staticmethod
    def crop_aspect_ratio(
        img: Image.Image,
        aspect_ratio: float,
        anchor: str = "center",
    ) -> Image.Image:
        """
        Crops an image to a specific aspect ratio (width / height) centered.
        """
        orig_w, orig_h = img.size
        target_aspect = aspect_ratio
        current_aspect = orig_w / orig_h

        if abs(current_aspect - target_aspect) < 1e-4:
            return img.copy()

        if current_aspect > target_aspect:
            # Current image is wider than target: trim left/right
            new_w = int(orig_h * target_aspect)
            new_h = orig_h
        else:
            # Current image is taller than target: trim top/bottom
            new_w = orig_w
            new_h = int(orig_w / target_aspect)

        new_w = max(1, min(new_w, orig_w))
        new_h = max(1, min(new_h, orig_h))

        if anchor == "center":
            left = (orig_w - new_w) // 2
            top = (orig_h - new_h) // 2
        else:
            left = 0
            top = 0

        right = left + new_w
        bottom = top + new_h

        return img.crop((left, top, right, bottom))

    @staticmethod
    def rotate(img: Image.Image, degrees: int) -> Image.Image:
        """Rotates an image by 90, 180, or 270 degrees clockwise."""
        degrees = degrees % 360
        if degrees == 90:
            return img.transpose(Image.Transpose.ROTATE_270)
        elif degrees == 180:
            return img.transpose(Image.Transpose.ROTATE_180)
        elif degrees == 270:
            return img.transpose(Image.Transpose.ROTATE_90)
        return img.copy()

    @staticmethod
    def flip_horizontal(img: Image.Image) -> Image.Image:
        """Flips an image horizontally."""
        return img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

    @staticmethod
    def flip_vertical(img: Image.Image) -> Image.Image:
        """Flips an image vertically."""
        return img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

    @staticmethod
    def strip_metadata(img: Image.Image) -> Image.Image:
        """
        Returns a fresh copy of the image without any EXIF or metadata tags.
        """
        data = list(img.getdata())
        clean_img = Image.new(img.mode, img.size)
        clean_img.putdata(data)
        return clean_img
