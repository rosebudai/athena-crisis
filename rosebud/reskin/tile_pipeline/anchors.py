from __future__ import annotations

import math
import os
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .catalog import BG_COLOR, CELL_PADDING, GRID_LINE_WIDTH, LINE_COLOR, TILE_SIZE
from .prompts import ANCHOR_PROMPT_TEMPLATE, TILE_TYPE_HINTS

def generate_anchors(
    cells: list[dict],
    theme: dict,
    work_dir: Path,
) -> dict[str, str]:
    """Generate one anchor tile per terrain type via Gemini.

    Returns dict mapping terrain type -> anchor image path.
    """
    from google import genai
    from google.genai import types
    import io

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    terrain_order = ["plain", "street", "rail", "mountain", "forest",
                     "campsite", "pier", "water", "river",
                     "stormcloud", "teleporter"]

    # Pick one representative non-animation-frame cell per terrain type
    representatives = {}
    for desired_type in terrain_order:
        for c in cells:
            if (c["type"] == desired_type
                    and not c.get("is_anim_frame")
                    and desired_type not in representatives):
                representatives[desired_type] = c
                break

    if not representatives:
        print("ERROR: No representative cells found")
        sys.exit(1)

    print(f"  Selected {len(representatives)} representative cells for anchors:")
    for t, c in representatives.items():
        print(f"    {t}: {c['id']}")

    anchors = {}

    for terrain_type, cell_info in representatives.items():
        anchor_path = work_dir / f"anchor_{terrain_type}.png"

        # Cache: skip if already generated
        if anchor_path.exists():
            print(f"  Using cached anchor for {terrain_type}: {anchor_path}")
            anchors[terrain_type] = str(anchor_path)
            continue

        # Build single-cell grid (same padding/scaling as batches)
        cell_w = TILE_SIZE + CELL_PADDING * 2
        cell_h = TILE_SIZE + CELL_PADDING * 2
        canvas_w = 1 * cell_w + 2 * GRID_LINE_WIDTH
        canvas_h = 1 * cell_h + 2 * GRID_LINE_WIDTH

        canvas = Image.new("RGBA", (canvas_w, canvas_h), LINE_COLOR)
        draw = ImageDraw.Draw(canvas)

        cx = GRID_LINE_WIDTH
        cy = GRID_LINE_WIDTH
        draw.rectangle(
            [cx, cy, cx + cell_w - 1, cy + cell_h - 1],
            fill=BG_COLOR,
        )

        tile_img = Image.open(cell_info["path"]).convert("RGBA")
        canvas.paste(tile_img, (cx + CELL_PADDING, cy + CELL_PADDING), tile_img)

        # Scale 4x for AI visibility
        scale_factor = 4
        scaled = canvas.resize(
            (canvas_w * scale_factor, canvas_h * scale_factor),
            Image.NEAREST,
        )

        # Save original for reference
        original_path = work_dir / f"anchor_{terrain_type}_original.png"
        scaled.save(original_path)

        # Build prompt from template
        type_hint = TILE_TYPE_HINTS.get(terrain_type, "")
        prompt = ANCHOR_PROMPT_TEMPLATE.format(
            type_name=terrain_type,
            type_hint=type_hint,
            theme_prompt=theme.get("prompt", ""),
            style_sheet_instruction="",
        )

        img_data = open(str(original_path), "rb").read()
        image_part = types.Part.from_bytes(data=img_data, mime_type="image/png")

        # Send to Gemini with retries
        success = False
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model="gemini-3.1-flash-image-preview",
                    contents=[prompt, image_part],
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE", "TEXT"],
                    ),
                )

                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                        result_img = Image.open(
                            io.BytesIO(part.inline_data.data)
                        ).convert("RGBA")
                        result_img.save(anchor_path)
                        print(f"  Generated anchor for {terrain_type}: {anchor_path}")
                        anchors[terrain_type] = str(anchor_path)
                        success = True
                        break

                if success:
                    break

                print(f"  No image in response for {terrain_type} (attempt {attempt + 1})")
            except Exception as e:
                print(f"  Error generating anchor for {terrain_type} (attempt {attempt + 1}): {e}")
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))

        if not success:
            print(f"WARNING: Failed to generate anchor for {terrain_type} after 3 attempts")

    print(f"  Generated {len(anchors)}/{len(representatives)} anchors")
    return anchors

def generate_style_reference_sheet(
    anchor_paths: dict[str, str],
    work_dir: Path,
) -> Path:
    """Create a reference sheet grid of all anchor tiles for global coherence.

    Composes all generated anchor tiles into a labeled grid image so that
    every batch API call can see the full world palette at a glance.

    Parameters
    ----------
    anchor_paths : dict[str, str]
        Mapping of terrain type name to path of the anchor PNG.
    work_dir : Path
        Directory to save the sheet in.

    Returns
    -------
    Path
        Path to the saved ``style_reference_sheet.png``.
    """
    # Canonical display order — matches terrain_order in generate_anchors()
    display_order = [
        "plain", "street", "mountain", "forest", "campsite",
        "pier", "water", "river", "stormcloud", "teleporter", "rail",
    ]

    # Filter to anchors that actually exist
    ordered_types = [t for t in display_order if t in anchor_paths]
    if not ordered_types:
        # Fallback: use whatever is available, sorted
        ordered_types = sorted(anchor_paths.keys())

    n = len(ordered_types)
    if n == 0:
        raise ValueError("No anchor paths provided for style reference sheet")

    # Grid layout: up to 5 columns
    grid_cols = min(n, 5)
    grid_rows = math.ceil(n / grid_cols)

    # Each cell: tile scaled 5× (24×5=120) + 20px label area below
    scale = 5
    tile_display = TILE_SIZE * scale  # 120
    label_height = 20
    cell_w = tile_display
    cell_h = tile_display + label_height

    # Sheet dimensions with 4px margin
    margin = 4
    sheet_w = grid_cols * cell_w + margin * 2
    sheet_h = grid_rows * cell_h + margin * 2

    # Dark background
    sheet = Image.new("RGBA", (sheet_w, sheet_h), (30, 30, 30, 255))
    draw = ImageDraw.Draw(sheet)

    # Load a small font for labels
    try:
        label_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 12
        )
    except Exception:
        label_font = ImageFont.load_default()

    for idx, terrain_type in enumerate(ordered_types):
        row = idx // grid_cols
        col = idx % grid_cols

        x0 = margin + col * cell_w
        y0 = margin + row * cell_h

        # Extract the 24×24 tile from the anchor (handles any Gemini output
        # resolution by downscaling to native grid size first).
        native = _extract_plain_tile_from_anchor(anchor_paths[terrain_type])
        tile_display_img = native.resize(
            (tile_display, tile_display), Image.NEAREST,
        )

        sheet.paste(tile_display_img, (x0, y0), tile_display_img)

        # Draw label centered below tile
        label = terrain_type
        label_x = x0 + tile_display // 2
        label_y = y0 + tile_display + label_height // 2
        draw.text(
            (label_x, label_y), label,
            font=label_font, fill=(220, 220, 220, 255), anchor="mm",
        )

    sheet_path = work_dir / "style_reference_sheet.png"
    sheet.save(sheet_path)
    print(f"  Generated style reference sheet: {sheet_path}")
    return sheet_path

def _extract_plain_tile_from_anchor(anchor_path: str) -> Image.Image:
    """Extract the 24x24 plain tile from the reskinned anchor grid image.

    The anchor is a single-cell grid saved at 4x scale.  Layout at native
    resolution:  GRID_LINE_WIDTH border, then CELL_PADDING, then TILE_SIZE
    pixels of actual tile content.  We downscale to native, crop the tile
    region, and return a 24x24 RGBA image.
    """
    anchor_img = Image.open(anchor_path).convert("RGBA")

    # Native (1x) dimensions for a single-cell grid
    cell_w = TILE_SIZE + CELL_PADDING * 2
    cell_h = TILE_SIZE + CELL_PADDING * 2
    native_w = 1 * cell_w + 2 * GRID_LINE_WIDTH
    native_h = 1 * cell_h + 2 * GRID_LINE_WIDTH

    # Downscale from 4x to native
    native_img = anchor_img.resize((native_w, native_h), Image.NEAREST)

    # The tile content starts after the grid line and padding
    tile_x = GRID_LINE_WIDTH + CELL_PADDING
    tile_y = GRID_LINE_WIDTH + CELL_PADDING
    tile_crop = native_img.crop((
        tile_x, tile_y,
        tile_x + TILE_SIZE, tile_y + TILE_SIZE,
    ))

    return tile_crop.copy()
