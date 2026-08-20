"""
File size optimizer and live size estimation utilities.
"""
from dataclasses import dataclass
from typing import Callable, Optional, Tuple
from PIL import Image
from engine.format_handler import ExportFormat, ExportOptions, FormatHandler


@dataclass
class SizeEstimate:
    estimated_bytes: int
    formatted_size: str
    savings_bytes: int
    savings_percentage: float  # Positive = reduced size, negative = increased size

    @staticmethod
    def format_bytes(num_bytes: int) -> str:
        if num_bytes <= 0:
            return "0 B"
        units = ["B", "KB", "MB", "GB"]
        size = float(num_bytes)
        unit_idx = 0
        while size >= 1024.0 and unit_idx < len(units) - 1:
            size /= 1024.0
            unit_idx += 1
        return f"{size:.2f} {units[unit_idx]}" if unit_idx > 0 else f"{int(size)} B"


class ImageOptimizer:
    """Provides file size estimation and intelligent auto-compression routines."""

    @classmethod
    def estimate_size(
        cls,
        img: Image.Image,
        options: ExportOptions,
        original_bytes: Optional[int] = None,
    ) -> SizeEstimate:
        """
        Calculates the exact byte size of exporting `img` with `options` in memory.
        """
        output_bytes = len(FormatHandler.export_to_bytes(img, options))
        formatted = SizeEstimate.format_bytes(output_bytes)

        if original_bytes is not None and original_bytes > 0:
            diff = original_bytes - output_bytes
            pct = (diff / original_bytes) * 100.0
        else:
            diff = 0
            pct = 0.0

        return SizeEstimate(
            estimated_bytes=output_bytes,
            formatted_size=formatted,
            savings_bytes=diff,
            savings_percentage=pct,
        )

    @classmethod
    def find_best_quality_for_target_size(
        cls,
        img: Image.Image,
        target_max_bytes: int,
        target_format: ExportFormat = ExportFormat.JPEG,
        progress_cb: Optional[Callable[[int], None]] = None,
    ) -> Tuple[int, int]:
        """
        Binary search for the highest quality (1-95) that stays under `target_max_bytes`.
        Returns (best_quality, resulting_bytes).
        """
        low = 5
        high = 95
        best_q = low
        best_size = 0

        options = ExportOptions(format=target_format, quality=high)

        # Check if high already fits
        options.quality = high
        size = len(FormatHandler.export_to_bytes(img, options))
        if size <= target_max_bytes:
            return high, size

        # Binary search
        for step in range(6):
            mid = (low + high) // 2
            options.quality = mid
            current_bytes = len(FormatHandler.export_to_bytes(img, options))

            if progress_cb:
                progress_cb(int((step + 1) / 6 * 100))

            if current_bytes <= target_max_bytes:
                best_q = mid
                best_size = current_bytes
                low = mid + 1
            else:
                high = mid - 1

        return best_q, best_size
