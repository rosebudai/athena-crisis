import os
import sys
from types import SimpleNamespace

import pytest
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import reskin.reskin as reskin_cli


class WrongSizeProvider:
    def transform(self, image_path, prompt, params):
        import io

        image = Image.new("RGBA", (128, 128), (255, 0, 255, 255))
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()


def test_process_asset_rejects_size_mismatch(tmp_path):
    source_path = tmp_path / "Units-Infantry.png"
    Image.new("RGBA", (64, 64), (255, 255, 255, 255)).save(source_path)

    asset = SimpleNamespace(
        name="Units-Infantry",
        source_path=str(source_path),
        category="unit-sprite",
    )
    theme = SimpleNamespace(
        name="cyberpunk",
        prompt="cyberpunk",
        palette={},
    )

    with pytest.raises(ValueError, match="Provider returned"):
        reskin_cli.process_asset(
            asset,
            theme,
            WrongSizeProvider(),
            str(tmp_path / "output"),
        )
