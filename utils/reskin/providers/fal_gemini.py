"""FAL.ai Gemini 3 Pro provider for grid-based AI restyling.

Uses the fal-ai/gemini-3-pro-image-preview/edit endpoint to restyle
sprite grids.  Cost-efficient: ~$0.008 per grid of 16 sprites.

Requires:
    pip install fal-client
    FAL_KEY environment variable
"""

import os
import time
import urllib.request

from PIL import Image

from .base import ReskinProvider

try:
    import fal_client
except ImportError:
    fal_client = None


class FalGeminiProvider(ReskinProvider):
    """FAL.ai Gemini 3 Pro image-edit provider.

    Supports two modes:
      1. Single-image transform (``ReskinProvider`` interface).
      2. Grid transform for batch processing (``transform_grid``).
    """

    def __init__(self, retries=3):
        if fal_client is None:
            raise ImportError(
                "fal-client not installed.  Run: pip install fal-client"
            )
        self.api_key = os.environ.get("FAL_KEY")
        if not self.api_key:
            raise ValueError(
                "FAL_KEY environment variable is required.  "
                "Get a key at https://fal.ai/"
            )
        self.retries = retries

    # -- ReskinProvider interface (single image) --

    def transform(self, image_path, prompt, params=None):
        """Transform a single image.  Returns PNG bytes."""
        output_path = "/tmp/fal_single_output.png"
        if params and "output_path" in params:
            output_path = params["output_path"]

        ok = self._call_fal(prompt, image_path, output_path)
        if not ok:
            raise RuntimeError(
                f"FAL.ai generation failed after {self.retries} retries"
            )
        with open(output_path, "rb") as f:
            return f.read()

    # -- Grid mode --

    def transform_grid(self, grid_path, prompt, output_path):
        """Transform a grid image.  Returns True on success."""
        return self._call_fal(prompt, grid_path, output_path)

    # -- Internal --

    def _call_fal(self, prompt, image_path, output_path):
        """Call FAL.ai Gemini 3 Pro edit API with retries."""
        image_url = fal_client.upload_file(str(image_path))

        for attempt in range(self.retries):
            try:
                result = fal_client.subscribe(
                    "fal-ai/gemini-3-pro-image-preview/edit",
                    arguments={
                        "prompt": prompt,
                        "image_urls": [image_url],
                        "num_images": 1,
                        "aspect_ratio": "1:1",
                        "resolution": "4K",
                        "output_format": "png",
                    },
                    with_logs=True,
                )

                if result and result.get("images"):
                    url = result["images"][0]["url"]
                    urllib.request.urlretrieve(url, output_path)
                    img = Image.open(output_path)
                    if img.size[0] < 1024 or img.size[1] < 1024:
                        print(
                            f"    WARNING: Output too small "
                            f"({img.size}), retrying..."
                        )
                        continue
                    return True

                print(
                    f"    No images in result, "
                    f"attempt {attempt + 1}/{self.retries}"
                )

            except Exception as e:
                print(f"    FAL Error (attempt {attempt + 1}): {e}")
                time.sleep(5 * (attempt + 1))

        return False
