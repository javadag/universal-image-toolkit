"""
Unit tests for the image engine (resizing, cropping, formats, compression, optimization).
"""
import io
import pytest
from PIL import Image
from engine.processor import ImageProcessor, ResampleFilter
from engine.format_handler import FormatHandler, ExportFormat, ExportOptions
from engine.optimizer import ImageOptimizer


@pytest.fixture
def sample_rgb_image():
    """Creates a 800x600 test RGB image with colorful gradients."""
    img = Image.new("RGB", (800, 600), color=(100, 150, 200))
    # Draw simple content
    for x in range(0, 800, 50):
        for y in range(0, 600, 50):
            img.putpixel((x, y), (255, 255, 255))
    return img


@pytest.fixture
def sample_rgba_image():
    """Creates a 400x400 RGBA image with alpha transparency."""
    img = Image.new("RGBA", (400, 400), color=(255, 0, 0, 128))
    return img


def test_resize_exact_dimensions(sample_rgb_image):
    resized = ImageProcessor.resize(sample_rgb_image, target_width=400, target_height=300, keep_aspect_ratio=False)
    assert resized.size == (400, 300)


def test_resize_keep_aspect_ratio(sample_rgb_image):
    # 800x600 is 4:3 aspect ratio
    resized = ImageProcessor.resize(sample_rgb_image, target_width=400, target_height=400, keep_aspect_ratio=True)
    # Should fit within 400x400 as 400x300
    assert resized.size == (400, 300)


def test_resize_percentage(sample_rgb_image):
    resized = ImageProcessor.resize(sample_rgb_image, scale_percent=50)
    assert resized.size == (400, 300)


def test_crop_box(sample_rgb_image):
    cropped = ImageProcessor.crop(sample_rgb_image, (100, 100, 500, 400))
    assert cropped.size == (400, 300)


def test_crop_aspect_ratio_16_9(sample_rgb_image):
    # 800x600 cropped to 16:9 -> height = 800 / (16/9) = 450
    cropped = ImageProcessor.crop_aspect_ratio(sample_rgb_image, 16 / 9)
    assert cropped.size == (800, 450)


def test_crop_aspect_ratio_1_1(sample_rgb_image):
    # 800x600 cropped to 1:1 -> 600x600
    cropped = ImageProcessor.crop_aspect_ratio(sample_rgb_image, 1.0)
    assert cropped.size == (600, 600)


def test_rotate_and_flip(sample_rgb_image):
    rotated = ImageProcessor.rotate(sample_rgb_image, 90)
    assert rotated.size == (600, 800)

    flipped_h = ImageProcessor.flip_horizontal(sample_rgb_image)
    assert flipped_h.size == (800, 600)

    flipped_v = ImageProcessor.flip_vertical(sample_rgb_image)
    assert flipped_v.size == (800, 600)


@pytest.mark.parametrize("fmt", [
    ExportFormat.JPEG,
    ExportFormat.PNG,
    ExportFormat.WEBP,
    ExportFormat.BMP,
    ExportFormat.TIFF,
    ExportFormat.ICO,
    ExportFormat.PDF,
])
def test_export_formats(sample_rgb_image, fmt):
    options = ExportOptions(format=fmt, quality=80)
    data = FormatHandler.export_to_bytes(sample_rgb_image, options)
    assert len(data) > 0

    if fmt == ExportFormat.PDF:
        assert data.startswith(b"%PDF")
    else:
        # Verify Pillow can open the exported bytes
        opened = Image.open(io.BytesIO(data))
        assert opened.width > 0
        assert opened.height > 0


def test_export_rgba_to_jpeg_with_white_bg(sample_rgba_image):
    options = ExportOptions(format=ExportFormat.JPEG, quality=85)
    data = FormatHandler.export_to_bytes(sample_rgba_image, options)
    opened = Image.open(io.BytesIO(data))
    assert opened.mode == "RGB"
    assert opened.size == (400, 400)


def test_png_color_quantization(sample_rgb_image):
    # Standard PNG vs Quantized PNG (e.g., 32 colors)
    std_options = ExportOptions(format=ExportFormat.PNG)
    std_data = FormatHandler.export_to_bytes(sample_rgb_image, std_options)

    quant_options = ExportOptions(format=ExportFormat.PNG, png_quantize_colors=32)
    quant_data = FormatHandler.export_to_bytes(sample_rgb_image, quant_options)

    assert len(quant_data) > 0
    # Quantized image is valid
    opened = Image.open(io.BytesIO(quant_data))
    assert opened.size == sample_rgb_image.size


def test_optimizer_size_estimate(sample_rgb_image):
    options = ExportOptions(format=ExportFormat.JPEG, quality=75)
    estimate = ImageOptimizer.estimate_size(sample_rgb_image, options, original_bytes=500_000)
    assert estimate.estimated_bytes > 0
    assert "KB" in estimate.formatted_size or "MB" in estimate.formatted_size or "B" in estimate.formatted_size
    assert estimate.savings_percentage != 0.0


def test_optimizer_find_best_quality(sample_rgb_image):
    target_bytes = 20_000
    best_q, resulting_size = ImageOptimizer.find_best_quality_for_target_size(
        sample_rgb_image,
        target_max_bytes=target_bytes,
        target_format=ExportFormat.JPEG,
    )
    assert 1 <= best_q <= 95
