import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import io
import pytest
from PIL import Image

from reskin.providers.echo import EchoProvider
from reskin.providers.nano_banana import NanoBananaProvider


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


def test_nano_banana_requires_api_key(monkeypatch):
    """NanoBananaProvider should raise ValueError when GEMINI_API_KEY is not set."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    import reskin.providers.nano_banana as banana_mod
    monkeypatch.setattr(banana_mod, "genai", object())

    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        NanoBananaProvider()
