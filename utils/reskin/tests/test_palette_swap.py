import io
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from PIL import Image

from reskin.transforms.palette_swap import palette_swap


@pytest.fixture
def red_icon(tmp_path):
    """Create a small icon that is mostly red."""
    img = Image.new("RGBA", (16, 16), (200, 50, 50, 255))
    path = tmp_path / "red_icon.png"
    img.save(str(path))
    return str(path)


@pytest.fixture
def palette():
    return {"reds": "#00ff88"}


def test_palette_swap_returns_bytes(red_icon, palette):
    result = palette_swap(red_icon, palette)
    assert isinstance(result, bytes)


def test_palette_swap_produces_valid_image(red_icon, palette):
    result = palette_swap(red_icon, palette)
    img = Image.open(io.BytesIO(result))
    assert img.size == (16, 16)
    assert img.mode == "RGBA"


def test_palette_swap_changes_colors(red_icon, palette):
    result = palette_swap(red_icon, palette)
    img = Image.open(io.BytesIO(result))
    pixel = img.getpixel((8, 8))
    # Should have shifted away from red toward green
    assert pixel[1] > pixel[0]  # green channel > red channel


def test_palette_swap_preserves_transparency(tmp_path):
    """Transparent pixels must stay transparent."""
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    path = tmp_path / "transparent.png"
    img.save(str(path))

    result = palette_swap(str(path), {"reds": "#ff0000"})
    result_img = Image.open(io.BytesIO(result))
    pixel = result_img.getpixel((8, 8))
    assert pixel[3] == 0  # alpha stays 0
