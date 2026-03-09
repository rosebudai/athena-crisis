from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image

from .catalog import TILE_SIZE


def reassemble_atlas(
    original_atlas_path: Path,
    reskinned_cells: list[tuple[dict, Image.Image]],
    output_path: Path,
):
    """Patch reskinned cells back into the atlas at exact positions."""
    atlas = Image.open(original_atlas_path).convert("RGBA")
    orig_arr = np.array(atlas)

    for cell_info, tile_img in reskinned_cells:
        x = cell_info["x"]
        y = cell_info["y"]

        orig_alpha = orig_arr[y:y + TILE_SIZE, x:x + TILE_SIZE, 3]
        tile_arr = np.array(tile_img.convert("RGBA"))
        tile_arr[:, :, 3] = orig_alpha
        tile_img = Image.fromarray(tile_arr)
        atlas.paste(tile_img, (x, y))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(output_path)
    print(f"  Saved reskinned atlas to {output_path}")


def update_reskin_manifest(atlas: str, theme_name: str, output_path: Path):
    """Update the reskin manifest.json to point to the new atlas."""
    manifest_path = (
        Path(__file__).parent.parent / "public" / "reskin" / "manifest.json"
    )
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    else:
        manifest = {}

    relative_path = f"reskin/{theme_name}/{atlas}.png"
    if "tiles" not in manifest:
        manifest["tiles"] = {}
    manifest["tiles"][atlas] = relative_path
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"  Updated manifest: {atlas} -> {relative_path}")
