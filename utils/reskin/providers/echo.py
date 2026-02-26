"""Echo provider — returns the original image unchanged. For testing."""

import io
import shutil

from PIL import Image

from .base import ReskinProvider


class EchoProvider(ReskinProvider):
    """Returns the original image unchanged. Useful for testing the pipeline."""

    def transform(self, image_path: str, prompt: str, params: dict) -> bytes:
        img = Image.open(image_path)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def transform_grid(self, grid_path: str, prompt: str,
                       output_path: str) -> bool:
        """Copy the grid image unchanged (for dry-run batch testing)."""
        shutil.copy2(grid_path, output_path)
        return True
