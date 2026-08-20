"""
Format-specific image exporters handling compression, optimization, and conversion.
"""
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple, Union
import io
from PIL import Image


class ExportFormat(str, Enum):
    JPEG = "JPEG (.jpg)"
    PNG = "PNG (.png)"
    WEBP = "WebP (.webp)"
    AVIF = "AVIF (.avif)"
    BMP = "BMP (.bmp)"
    TIFF = "TIFF (.tiff)"
    ICO = "ICO (.ico)"
    PDF = "PDF (.pdf)"
    GIF = "GIF (.gif)"


FORMAT_EXTENSION_MAP = {
    ExportFormat.JPEG: ".jpg",
    ExportFormat.PNG: ".png",
    ExportFormat.WEBP: ".webp",
    ExportFormat.AVIF: ".avif",
    ExportFormat.BMP: ".bmp",
    ExportFormat.TIFF: ".tiff",
    ExportFormat.ICO: ".ico",
    ExportFormat.PDF: ".pdf",
    ExportFormat.GIF: ".gif",
}


@dataclass
class ExportOptions:
    format: ExportFormat = ExportFormat.JPEG
    quality: int = 85               # 1-100 (for JPEG, WebP, AVIF)
    optimize: bool = True           # Optimize huffman tables / compress
    strip_metadata: bool = True     # Remove EXIF/GPS
    # PNG-specific
    png_compression_level: int = 6  # 0-9
    png_quantize_colors: Optional[int] = None  # None or 2-256 for palette reduction
    # WebP-specific
    webp_lossless: bool = False
    webp_method: int = 6            # 0 (fast) to 6 (slowest/best compression)
    # Background fill for formats without transparency (e.g. JPEG)
    background_color: Tuple[int, int, int] = (255, 255, 255)
    # ICO-specific sizes
    ico_sizes: Optional[List[Tuple[int, int]]] = None


class FormatHandler:
    """Handles saving and exporting images to various formats with advanced optimization."""

    @staticmethod
    def prepare_image_for_format(img: Image.Image, target_format: ExportFormat, bg_color: Tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
        """
        Prepares color mode and transparency according to the target format's capabilities.
        """
        if target_format in (ExportFormat.JPEG, ExportFormat.BMP, ExportFormat.PDF):
            # Formats that do not support transparency
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                # Composite over background color
                converted = img.convert("RGBA")
                background = Image.new("RGBA", converted.size, bg_color + (255,))
                composited = Image.alpha_composite(background, converted)
                return composited.convert("RGB")
            elif img.mode != "RGB":
                return img.convert("RGB")
            return img.copy()

        elif target_format == ExportFormat.PNG:
            if img.mode not in ("RGB", "RGBA", "L", "LA", "P"):
                return img.convert("RGBA")
            return img.copy()

        elif target_format == ExportFormat.WEBP:
            if img.mode not in ("RGB", "RGBA"):
                return img.convert("RGBA" if "A" in img.mode else "RGB")
            return img.copy()

        elif target_format == ExportFormat.ICO:
            # Icons require RGBA
            if img.mode != "RGBA":
                return img.convert("RGBA")
            return img.copy()

        return img.copy()

    @classmethod
    def export(
        cls,
        img: Image.Image,
        output_path: Union[str, Path],
        options: Optional[ExportOptions] = None,
    ) -> int:
        """
        Exports an image to disk using specified ExportOptions.
        Returns the final written file size in bytes.
        """
        if options is None:
            options = ExportOptions()

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        data = cls.export_to_bytes(img, options)
        with open(path, "wb") as f:
            f.write(data)

        return len(data)

    @classmethod
    def export_to_bytes(
        cls,
        img: Image.Image,
        options: Optional[ExportOptions] = None,
    ) -> bytes:
        """
        Exports the image into an in-memory byte buffer (useful for live size estimation & testing).
        """
        if options is None:
            options = ExportOptions()

        processed_img = cls.prepare_image_for_format(img, options.format, options.background_color)
        buf = io.BytesIO()

        fmt = options.format

        if fmt == ExportFormat.JPEG:
            save_kwargs = {
                "format": "JPEG",
                "quality": max(1, min(100, options.quality)),
                "optimize": options.optimize,
                "progressive": True,
            }
            if not options.strip_metadata and "exif" in img.info:
                save_kwargs["exif"] = img.info["exif"]
            processed_img.save(buf, **save_kwargs)

        elif fmt == ExportFormat.PNG:
            out = processed_img
            # Check if color quantization is requested
            if options.png_quantize_colors is not None and 2 <= options.png_quantize_colors <= 256:
                out = out.quantize(colors=options.png_quantize_colors, method=Image.Quantize.MEDIANCUT)

            save_kwargs = {
                "format": "PNG",
                "compress_level": max(0, min(9, options.png_compression_level)),
                "optimize": options.optimize,
            }
            out.save(buf, **save_kwargs)

        elif fmt == ExportFormat.WEBP:
            save_kwargs = {
                "format": "WEBP",
                "lossless": options.webp_lossless,
                "quality": max(1, min(100, options.quality)),
                "method": max(0, min(6, options.webp_method)),
            }
            if not options.strip_metadata and "exif" in img.info:
                save_kwargs["exif"] = img.info["exif"]
            processed_img.save(buf, **save_kwargs)

        elif fmt == ExportFormat.AVIF:
            # Fallback to WebP or PNG if AVIF plugin isn't active
            try:
                processed_img.save(
                    buf,
                    format="AVIF",
                    quality=max(1, min(100, options.quality)),
                )
            except Exception:
                # Fallback to WebP
                processed_img.save(
                    buf,
                    format="WEBP",
                    quality=max(1, min(100, options.quality)),
                )

        elif fmt == ExportFormat.BMP:
            processed_img.save(buf, format="BMP")

        elif fmt == ExportFormat.TIFF:
            processed_img.save(buf, format="TIFF", compression="tiff_lzw" if options.optimize else "raw")

        elif fmt == ExportFormat.ICO:
            sizes = options.ico_sizes or [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
            processed_img.save(buf, format="ICO", sizes=sizes)

        elif fmt == ExportFormat.PDF:
            processed_img.save(buf, format="PDF", resolution=100.0)

        elif fmt == ExportFormat.GIF:
            processed_img.save(buf, format="GIF", optimize=options.optimize)

        else:
            processed_img.save(buf, format=fmt.value)

        return buf.getvalue()
