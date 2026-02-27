import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import io
import pytest
from PIL import Image

from reskin.providers.echo import EchoProvider
from reskin.providers.fal_gemini import FalGeminiProvider


def _make_test_png(path, size=(64, 64), color="red"):
    """Create a minimal test PNG image."""
    img = Image.new("RGBA", size, color)
    img.save(str(path), format="PNG")
    return str(path)


def test_echo_transform_returns_bytes(tmp_path):
    """Echo transform should return valid PNG bytes for a test image."""
    src = tmp_path / "input.png"
    _make_test_png(src)

    provider = EchoProvider()
    result = provider.transform(str(src), "ignored prompt", {})

    assert isinstance(result, bytes)
    assert len(result) > 0
    # Verify it's a valid PNG by opening it
    img = Image.open(io.BytesIO(result))
    assert img.format == "PNG"
    assert img.size == (64, 64)


def test_echo_transform_grid_copies_file(tmp_path):
    """Echo transform_grid should copy the file unchanged."""
    src = tmp_path / "grid_input.png"
    dst = tmp_path / "grid_output.png"
    _make_test_png(src, size=(256, 256), color="blue")

    provider = EchoProvider()
    ok = provider.transform_grid(str(src), "ignored prompt", str(dst))

    assert ok is True
    assert dst.exists()
    # Verify the output is a valid image with same dimensions
    img = Image.open(str(dst))
    assert img.size == (256, 256)


def test_fal_gemini_requires_fal_key(monkeypatch):
    """FalGeminiProvider should raise ValueError when FAL_KEY is not set."""
    monkeypatch.delenv("FAL_KEY", raising=False)
    # Patch fal_client to be available so we hit the FAL_KEY check
    import reskin.providers.fal_gemini as fal_mod
    monkeypatch.setattr(fal_mod, "fal_client", object())

    with pytest.raises(ValueError, match="FAL_KEY"):
        FalGeminiProvider()
