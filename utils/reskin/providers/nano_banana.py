"""Nano Banana 2 (Gemini 3.1 Flash Image) provider for AI reskinning.

Uses Google's genai SDK to call the Gemini image editing API directly.
Supports both single-image and grid transforms.

Requires:
    pip install google-genai Pillow
    GEMINI_API_KEY environment variable
"""

import io
import os

from PIL import Image

from .base import ReskinProvider

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None


class NanoBananaProvider(ReskinProvider):
    """Nano Banana 2 (Gemini 3.1 Flash Image Preview) provider."""

    MODEL = "gemini-3.1-flash-image-preview"

    def __init__(self, retries=3):
        if genai is None:
            raise ImportError(
                "google-genai not installed. Run: pip install google-genai"
            )
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable is required. "
                "Get a key at https://aistudio.google.com/apikey"
            )
        self.client = genai.Client(api_key=api_key)
        self.retries = retries

    def transform(self, image_path, prompt, params=None):
        """Transform a single image. Returns PNG bytes."""
        source = Image.open(image_path).convert("RGBA")

        for attempt in range(self.retries):
            try:
                response = self.client.models.generate_content(
                    model=self.MODEL,
                    contents=[prompt, source],
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                    ),
                )

                for part in response.candidates[0].content.parts:
                    if part.inline_data is not None:
                        return part.inline_data.data

                print(
                    f"    No image in response, "
                    f"attempt {attempt + 1}/{self.retries}"
                )

            except Exception as e:
                print(f"    Nano Banana error (attempt {attempt + 1}): {e}")
                import time
                time.sleep(2 * (attempt + 1))

        raise RuntimeError(
            f"Nano Banana generation failed after {self.retries} retries"
        )

    def transform_grid(self, grid_path, prompt, output_path):
        """Transform a grid image. Returns True on success."""
        try:
            image_bytes = self.transform(grid_path, prompt)
            with open(output_path, "wb") as f:
                f.write(image_bytes)
            return True
        except RuntimeError:
            return False
