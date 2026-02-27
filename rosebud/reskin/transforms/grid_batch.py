"""Grid-based batch reskinning -- group sprites into 4x4 grids for AI restyling.

Adapted from the OpenTTD reskin pipeline (batch_env.py + parse_and_replace.py).
Key insight: sending 16 sprites per API call in a 4x4 grid reduces cost ~16x
while maintaining quality through per-cell context and alpha mask restoration.

Flow:
  1. group_into_batches() -- bucket assets by similar dimensions
  2. build_grids()        -- render each batch onto a 2048x2048 canvas
  3. [send grids to AI provider]
  4. extract_and_save()   -- crop sprites from restyled grids, restore alpha
"""

import io
import json
import math
import os
from collections import defaultdict

from PIL import Image, ImageDraw

CANVAS_SIZE = 2048
CELL_PADDING = 16
GRID_LINE_WIDTH = 6
BG_COLOR = (200, 200, 200, 255)
LINE_COLOR = (0, 0, 0, 255)
# Athena Crisis sprites vary in size; a 64px bucket step groups similar
# sizes together efficiently.
BUCKET_STEP = 64
MAX_PER_BATCH = 16


# ---------------------------------------------------------------------------
# Grid building
# ---------------------------------------------------------------------------


def group_into_batches(assets, bucket_step=BUCKET_STEP,
                       max_per_batch=MAX_PER_BATCH):
    """Group assets by similar size into batches of up to *max_per_batch*.

    Args:
        assets: List of AssetInfo (name, source_path, category).
        bucket_step: Round dimensions up to this multiple for grouping.
        max_per_batch: Max sprites per grid (4x4 = 16).

    Returns:
        List of dicts with 'bucket' (w, h) and 'sprites' keys.
    """
    buckets = defaultdict(list)
    for asset in assets:
        img = Image.open(asset.source_path)
        w, h = img.size
        bw = ((w + bucket_step - 1) // bucket_step) * bucket_step
        bh = ((h + bucket_step - 1) // bucket_step) * bucket_step
        buckets[(bw, bh)].append({"asset": asset, "w": w, "h": h})

    for key in buckets:
        buckets[key].sort(key=lambda s: s["w"] * s["h"], reverse=True)

    batches = []
    for (bw, bh), sprites in sorted(buckets.items()):
        for i in range(0, len(sprites), max_per_batch):
            batches.append({
                "bucket": (bw, bh),
                "sprites": sprites[i:i + max_per_batch],
            })
    return batches


def render_grid(batch, batch_id, canvas_size=CANVAS_SIZE):
    """Render a batch onto a grid canvas.

    Returns (grid_image, batch_meta) where *batch_meta* contains exact
    coordinates needed to extract sprites after AI restyling.
    """
    bw, bh = batch["bucket"]
    sprites = batch["sprites"]
    n = len(sprites)
    cols = min(4, n)
    rows = math.ceil(n / 4)

    cell_w = bw + CELL_PADDING * 2
    cell_h = bh + CELL_PADDING * 2

    native_w = cols * cell_w + (cols + 1) * GRID_LINE_WIDTH
    native_h = rows * cell_h + (rows + 1) * GRID_LINE_WIDTH

    scale = min(canvas_size / native_w, canvas_size / native_h, 3.0)
    actual_w = int(native_w * scale)
    actual_h = int(native_h * scale)
    offset_x = (canvas_size - actual_w) // 2
    offset_y = (canvas_size - actual_h) // 2

    canvas = Image.new("RGBA", (native_w, native_h), LINE_COLOR)
    draw = ImageDraw.Draw(canvas)

    batch_meta = {
        "batch_id": batch_id,
        "bucket": [bw, bh],
        "cols": cols,
        "rows": rows,
        "scale": scale,
        "offset_x": offset_x,
        "offset_y": offset_y,
        "native_w": native_w,
        "native_h": native_h,
        "cell_w": cell_w,
        "cell_h": cell_h,
        "sprites": [],
    }

    for idx, sprite_info in enumerate(sprites):
        row = idx // 4
        col = idx % 4
        asset = sprite_info["asset"]

        cx = GRID_LINE_WIDTH + col * (cell_w + GRID_LINE_WIDTH)
        cy = GRID_LINE_WIDTH + row * (cell_h + GRID_LINE_WIDTH)

        draw.rectangle(
            [cx, cy, cx + cell_w - 1, cy + cell_h - 1], fill=BG_COLOR
        )

        img = Image.open(asset.source_path).convert("RGBA")
        paste_x = cx + (cell_w - sprite_info["w"]) // 2
        paste_y = cy + (cell_h - sprite_info["h"]) // 2
        canvas.paste(img, (paste_x, paste_y), img)

        label = f"{chr(65 + row)}{col + 1}"
        batch_meta["sprites"].append({
            "cell_row": row,
            "cell_col": col,
            "cell_label": label,
            "source_path": asset.source_path,
            "name": asset.name,
            "category": asset.category,
            "original_w": sprite_info["w"],
            "original_h": sprite_info["h"],
        })

    scaled = canvas.resize((actual_w, actual_h), Image.LANCZOS)
    final = Image.new("RGBA", (canvas_size, canvas_size), (255, 255, 255, 255))
    final.paste(scaled, (offset_x, offset_y))

    return final, batch_meta


def build_grids(assets, output_dir, canvas_size=CANVAS_SIZE):
    """Build grids for all assets and write manifest.

    Returns:
        Manifest dict with all batch metadata.
    """
    os.makedirs(output_dir, exist_ok=True)
    batches = group_into_batches(assets)

    manifest = {
        "version": 1,
        "canvas_size": canvas_size,
        "grid_line_width": GRID_LINE_WIDTH,
        "cell_padding": CELL_PADDING,
        "batches": [],
    }

    for i, batch in enumerate(batches):
        batch_id = f"batch_{i + 1:03d}"
        grid_path = os.path.join(output_dir, f"{batch_id}.png")

        grid_img, batch_meta = render_grid(batch, batch_id, canvas_size)
        batch_meta["grid_file"] = grid_path
        grid_img.save(grid_path)
        manifest["batches"].append(batch_meta)

        n = len(batch["sprites"])
        bw, bh = batch["bucket"]
        print(f"  {batch_id}: {n:2d} sprites, bucket {bw}x{bh}")

    manifest_path = os.path.join(output_dir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    total = sum(len(b["sprites"]) for b in manifest["batches"])
    print(f"  Total: {total} sprites in {len(manifest['batches'])} batches")

    return manifest


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------


def build_grid_prompt(batch_meta, style_prompt, descriptions=None):
    """Build a per-cell prompt for a sprite grid.

    Args:
        batch_meta: Batch metadata from build_grids().
        style_prompt: Theme style description.
        descriptions: Optional dict mapping cell_label -> description.

    Returns:
        Prompt string suitable for image-edit APIs.
    """
    cols = batch_meta["cols"]
    rows = batch_meta["rows"]

    cell_descs = []
    for s in batch_meta["sprites"]:
        label = s["cell_label"]
        row_label = chr(65 + s["cell_row"])
        col_label = s["cell_col"] + 1

        if descriptions and label in descriptions:
            desc = descriptions[label]
        else:
            # Auto-describe from name and category
            name = s["name"]
            name = os.path.splitext(name)[0].replace("-", " ").replace("_", " ")
            desc = f"{s['category']} -- {name}"

        cell_descs.append(f"  Row {row_label} Col {col_label}: {desc}")

    cell_text = "\n".join(cell_descs)

    return (
        f"This is a {cols}x{rows} grid of game sprites on gray background, "
        f"separated by black grid lines.\n\n"
        f"Each cell contains:\n{cell_text}\n\n"
        f"Restyle every sprite to: {style_prompt}\n\n"
        f"You MUST keep the exact same silhouette, shape, size, and "
        f"proportions of every object. Only change colors and textures. "
        f"No text, no labels, no new objects. Keep grid lines and gray "
        f"backgrounds."
    )


# ---------------------------------------------------------------------------
# Extraction (post AI-generation)
# ---------------------------------------------------------------------------


def extract_sprites_from_grid(restyled_path, batch_meta, canvas_size):
    """Extract individual sprites from a restyled grid image.

    Performs the exact inverse of render_grid() to recover each sprite
    at its original dimensions.

    Returns:
        List of (sprite_info, sprite_image) tuples.
    """
    img = Image.open(restyled_path).convert("RGBA")
    img_w, img_h = img.size

    scale = batch_meta["scale"]
    offset_x = batch_meta["offset_x"]
    offset_y = batch_meta["offset_y"]
    native_w = batch_meta["native_w"]
    native_h = batch_meta["native_h"]
    cell_w = batch_meta["cell_w"]
    cell_h = batch_meta["cell_h"]

    # The AI may return a different resolution than canvas_size
    img_scale = img_w / canvas_size
    actual_offset_x = int(offset_x * img_scale)
    actual_offset_y = int(offset_y * img_scale)
    actual_w = int(native_w * scale * img_scale)
    actual_h = int(native_h * scale * img_scale)

    grid_crop = img.crop((
        actual_offset_x, actual_offset_y,
        actual_offset_x + actual_w, actual_offset_y + actual_h,
    ))
    grid_native = grid_crop.resize((native_w, native_h), Image.LANCZOS)

    extracted = []
    for sprite_info in batch_meta["sprites"]:
        row = sprite_info["cell_row"]
        col = sprite_info["cell_col"]
        orig_w = sprite_info["original_w"]
        orig_h = sprite_info["original_h"]

        cx = GRID_LINE_WIDTH + col * (cell_w + GRID_LINE_WIDTH)
        cy = GRID_LINE_WIDTH + row * (cell_h + GRID_LINE_WIDTH)
        paste_x = cx + (cell_w - orig_w) // 2
        paste_y = cy + (cell_h - orig_h) // 2

        sprite_crop = grid_native.crop((
            paste_x, paste_y,
            paste_x + orig_w, paste_y + orig_h,
        ))
        extracted.append((sprite_info, sprite_crop))

    return extracted


def restore_alpha(restyled_sprite, original_path):
    """Apply original sprite's alpha channel to the restyled sprite.

    AI models generate RGB colors but may alter transparency.  We take
    RGB from the AI output and alpha from the original to preserve
    exact silhouettes.
    """
    original = Image.open(original_path).convert("RGBA")
    restyled = restyled_sprite.convert("RGBA")

    if restyled.size != original.size:
        restyled = restyled.resize(original.size, Image.LANCZOS)

    r, g, b, _ = restyled.split()
    _, _, _, original_alpha = original.split()
    return Image.merge("RGBA", (r, g, b, original_alpha))


def blend_tile_edges(restyled, original, edge_pixels=6):
    """Blend outer edge pixels back to original for seamless tiling.

    For terrain tiles the AI may alter edge colors, breaking
    tile-to-tile seamlessness.  This linearly blends the outermost
    *edge_pixels* rows/columns back towards the original.
    """
    import numpy as np

    res = np.array(restyled).astype(float)
    orig = np.array(original).astype(float)
    h, w = res.shape[:2]

    edge_pixels = min(edge_pixels, h // 2, w // 2)
    if edge_pixels <= 0:
        return restyled

    mask = np.ones((h, w), dtype=float)
    for i in range(edge_pixels):
        a = i / edge_pixels
        mask[i, :] = np.minimum(mask[i, :], a)
        mask[h - 1 - i, :] = np.minimum(mask[h - 1 - i, :], a)
        mask[:, i] = np.minimum(mask[:, i], a)
        mask[:, w - 1 - i] = np.minimum(mask[:, w - 1 - i], a)

    m = mask[:, :, np.newaxis]
    blended = res * m + orig * (1.0 - m)
    return Image.fromarray(blended.astype(np.uint8))


def validate_sprite(restyled, original_path):
    """Check that the restyled sprite actually changed.

    Returns (ok, message).  Catches two common AI failures:
    - Too similar to original (AI didn't restyle)
    - Size mismatch
    """
    import numpy as np

    original = Image.open(original_path).convert("RGBA")
    if restyled.size != original.size:
        return False, f"Size mismatch: {restyled.size} vs {original.size}"

    orig_arr = np.array(original)
    rest_arr = np.array(restyled)
    visible = orig_arr[:, :, 3] > 0

    if not visible.any():
        return True, "OK (fully transparent)"

    diff = np.abs(
        rest_arr[:, :, :3].astype(float) - orig_arr[:, :, :3].astype(float)
    )
    mean_diff = diff[visible].mean()

    if mean_diff < 3:
        return False, f"Too similar (diff={mean_diff:.1f})"
    return True, f"OK (diff={mean_diff:.1f})"


# ---------------------------------------------------------------------------
# Full extraction pipeline
# ---------------------------------------------------------------------------


def extract_and_save(manifest, restyled_dir, output_dir,
                     tiling=False, edge_pixels=6):
    """Extract sprites from all restyled grids and save individual files.

    Args:
        manifest: Manifest dict from build_grids().
        restyled_dir: Directory containing ``<batch_id>_restyled.png`` files.
        output_dir: Directory to write individual sprites.
        tiling: Apply tile-edge blending for terrain sprites.
        edge_pixels: Blend width for tile edges.

    Returns:
        List of (name, output_path) for extracted sprites.
    """
    canvas_size = manifest["canvas_size"]
    os.makedirs(output_dir, exist_ok=True)

    results = []
    skipped = 0

    for batch_meta in manifest["batches"]:
        batch_id = batch_meta["batch_id"]
        restyled_path = os.path.join(restyled_dir, f"{batch_id}_restyled.png")

        if not os.path.exists(restyled_path):
            print(f"  {batch_id}: MISSING, skipping")
            continue

        try:
            extracted = extract_sprites_from_grid(
                restyled_path, batch_meta, canvas_size
            )
        except Exception as e:
            print(f"  {batch_id}: ERROR ({e}), skipping")
            continue

        batch_ok = 0
        for sprite_info, sprite_img in extracted:
            original_path = sprite_info["source_path"]
            name = sprite_info["name"]

            sprite_img = restore_alpha(sprite_img, original_path)

            if tiling:
                original = Image.open(original_path).convert("RGBA")
                sprite_img = blend_tile_edges(
                    sprite_img, original, edge_pixels
                )

            ok, msg = validate_sprite(sprite_img, original_path)
            if not ok:
                print(f"    WARNING: {name}: {msg}")
                skipped += 1
                continue

            out_path = os.path.join(output_dir, f"{name}.png")
            os.makedirs(os.path.dirname(out_path), exist_ok=True)

            buf = io.BytesIO()
            sprite_img.save(buf, format="PNG")
            with open(out_path, "wb") as f:
                f.write(buf.getvalue())

            results.append((name, out_path))
            batch_ok += 1

        total_batch = len(batch_meta["sprites"])
        print(f"  {batch_id}: {batch_ok} OK, {total_batch - batch_ok} skipped")

    print(f"  Total: {len(results)} extracted, {skipped} skipped")
    return results
