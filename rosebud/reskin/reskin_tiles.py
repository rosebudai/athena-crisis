#!/usr/bin/env python3
"""Tile atlas reskin pipeline for Athena Crisis.

Splits a tile atlas (e.g. Tiles0.png) into individual 24x24 cells,
groups them by terrain type (water tiles together for coastline
consistency), batches into grids for AI reskinning, then reassembles.

Usage:
    python3 rosebud/reskin/reskin_tiles.py --atlas Tiles0 --theme cozy
    python3 rosebud/reskin/reskin_tiles.py --atlas Tiles0 --theme cozy --dry-run
    python3 rosebud/reskin/reskin_tiles.py --atlas Tiles0 --theme cozy --type-only water
"""

import os
import sys
import json
import math
import argparse
import time
from pathlib import Path
from collections import defaultdict
from PIL import Image, ImageDraw
import numpy as np

# Atlas constants
TILE_SIZE = 24
ATLAS_COLS = 12
CDN_BASE = "https://art.athenacrisis.com/v19/assets/render"

# Batch grid constants
GRID_COLS = 6
CELLS_PER_BATCH = 36  # 6x6
CELL_PADDING = 4
GRID_LINE_WIDTH = 2
BG_COLOR = (200, 200, 200, 255)
LINE_COLOR = (0, 0, 0, 255)

# Animation definitions from athena/info/Tile.tsx.
# For each animated tile: (base_col, base_row, frames, offset, horizontal, block_start_delta).
# block_start_delta: the frame block starts at base_row + block_start_delta.
#   -1 for tiles using AreaModifiers (modifier y range [-1, 1])
#    0 for tiles whose modifiers start at y=0
# After reskinning, base-frame pixels are copied to all other frames so that
# independently-reskinned frames don't flicker with different art styles.
ANIMATED_TILES = [
    # name              base_col  base_row  frames  offset  horizontal  block_start_delta
    ("Sea",                  8,       35,      4,      3,    False,      -1),
    ("DeepSea",              8,       47,      4,      3,    False,      -1),
    ("Beach",                3,       50,      4,      6,    False,      -1),
    ("River",                1,       73,     24,      3,    False,       0),
    ("Pier",                 0,       29,      4,      5,    False,       0),
    ("Campsite",             0,       28,      4,      1,    True,        0),
    ("StormCloud",           6,        7,      4,      3,    False,      -1),
    ("Reef",                 5,       18,      4,      1,    True,        0),
    ("Lightning",           10,        0,      4,      1,    False,       0),
    ("LightningV",          10,        6,      4,      1,    False,       0),
    ("RailBridge",           5,        0,      4,      1,    False,       0),
    ("GasBubbles",           5,       26,      4,      1,    True,        0),
    ("Teleporter",           0,       25,      2,      1,    False,       0),
    ("Computer",             0,       31,      4,      1,    False,       0),
    ("FloatingWaterEdge",    7,       58,      4,      2,    False,       0),
    ("Island",               5,       23,      4,      1,    True,        0),
    ("Iceberg/Weeds",        5,       22,      4,      1,    True,        0),
    # FloatingEdge border animations (getFloatingEdgeAnimation in Tile.tsx)
    # Waterfall modifiers on FloatingEdge (base sprite(8,32) + modifier offsets)
    # Absolute positions: cols 8-10, rows 73-75.  WaterfallAnimation = River anim.
    ("FE_Waterfall",         9,       73,     24,      3,    False,       0),
    # Sea wall decorators on FloatingEdge — offset=1, frames=4
    # Absolute: (9,12),(10,12) and (9,16),(10,16) — two separate row groups
    ("FE_WallDecorA",        9,       12,      4,      1,    False,       0),
    ("FE_WallDecorB",        9,       16,      4,      1,    False,       0),
    # Sea area decorators on FloatingEdge — offset=2, frames=4
    # Absolute: (9,20),(10,20),(9,21),(10,21) — 2-row base block
    ("FE_AreaDecor",         9,       20,      4,      2,    False,       0),
]

# Tile type row ranges — derived from sprite positions in athena/info/Tile.tsx.
# "water" merges sea + beach rows for coastline consistency.
TILE_TYPE_ROWS = {
    "plain":      (0, 2),
    "street":     (3, 6),
    "mountain":   (7, 18),
    "forest":     (19, 26),
    "campsite":   (27, 28),
    "pier":       (29, 34),
    "water":      (35, 72),   # sea (35-58) + beach frames (59-72)
    "river":      (73, 144),
}

# Type-specific prompt hints
TILE_TYPE_HINTS = {
    "plain": (
        "These are GRASS and PLAIN terrain tiles. They are flat ground tiles "
        "that tile seamlessly together. Keep them as simple, flat ground with "
        "subtle texture variation. All tiles in this batch must use the SAME "
        "base green tone so they blend together seamlessly when placed adjacent."
    ),
    "street": (
        "These are ROAD/STREET tiles showing paved paths with various "
        "connections (straight, corners, intersections, dead-ends). "
        "Keep the road width, line markings, and edge style CONSISTENT "
        "across all tiles. Roads must connect seamlessly at tile edges."
    ),
    "mountain": (
        "These are MOUNTAIN terrain tiles showing rocky peaks and elevated "
        "terrain. Keep the rock texture, snow caps, and shading style "
        "CONSISTENT across all tiles. Mountains connect to form ranges."
    ),
    "forest": (
        "These are FOREST/TREE tiles showing various tree arrangements "
        "(single trees, connected forests, edges). Keep the tree style, "
        "leaf color, and trunk style CONSISTENT. The ground beneath trees "
        "must match the plain grass tone."
    ),
    "campsite": (
        "These are CAMPSITE tiles showing camp structures and fire pits. "
        "Keep the warm, inviting aesthetic consistent."
    ),
    "pier": (
        "These are PIER/DOCK tiles showing wooden structures extending "
        "over water. Keep the wood texture and water style consistent. "
        "Piers connect to form walkways."
    ),
    "water": (
        "These are WATER tiles including open ocean (SEA), deep ocean, "
        "and coastline transitions (BEACH). Keep the water color, wave pattern, "
        "and foam style IDENTICAL across ALL tiles — sea, deep sea, and beach "
        "tiles must look like they belong to the same ocean. Beach sand must be "
        "a consistent warm tone. Coastline edges must blend seamlessly between "
        "sand and water."
    ),
    "river": (
        "These are RIVER tiles showing flowing water with banks. Keep the "
        "water color and flow pattern IDENTICAL to the sea tiles. River "
        "banks must match the plain grass tone. All river tiles must blend "
        "seamlessly when connected."
    ),
}

# Prompt templates for anchor generation and batch reskinning (v2 pipeline).
ANCHOR_PROMPT_TEMPLATE = (
    "Reskin this {type_name} game tile. "
    "Top-down orthogonal perspective, 16-bit modern retro pixel art style, "
    "warm and cozy color palette with soft saturation, "
    "flat cartoon shading, clean edges, storybook illustration aesthetic. "
    "{type_hint} "
    "RULES: "
    "1) Keep the exact same grid layout and tile position. "
    "2) Only change colors and textures — don't move or resize the tile. "
    "3) No text, labels, or watermarks. "
    "4) Keep black grid lines and gray padding as-is."
)

BATCH_PROMPT_TEMPLATE = (
    "Reskin the tiles in the second image to match the visual style of the first image. "
    "These are {type_name} game tiles, top-down orthogonal perspective, "
    "16-bit modern retro pixel art style, warm and cozy color palette "
    "with soft saturation, flat cartoon shading, clean edges, "
    "storybook illustration aesthetic. "
    "{type_hint} "
    "RULES: "
    "1) Keep the exact same grid layout and tile positions. "
    "2) Only change colors and textures — don't move or resize tiles. "
    "3) No text, labels, or watermarks. "
    "4) Keep black grid lines and gray padding as-is. "
    "5) Match the first image's palette and shading exactly."
)

MULTI_ANCHOR_BATCH_PROMPT_TEMPLATE = (
    "Reskin the tiles in the last image to match the visual style of the reference images. "
    "The first reference shows the target style for {type_name} tiles. "
    "The second reference shows the grass/land colors — any land or grass portions "
    "in these transition tiles MUST use those exact green tones. "
    "These are {type_name} game tiles, top-down orthogonal perspective, "
    "16-bit modern retro pixel art style, warm and cozy color palette "
    "with soft saturation, flat cartoon shading, clean edges, "
    "storybook illustration aesthetic. "
    "{type_hint} "
    "RULES: "
    "1) Keep the exact same grid layout and tile positions. "
    "2) Only change colors and textures — don't move or resize tiles. "
    "3) No text, labels, or watermarks. "
    "4) Keep black grid lines and gray padding as-is. "
    "5) Match the first reference's water/river palette and shading exactly. "
    "6) Match the second reference's grass/land colors for any land portions."
)


def download_atlas(atlas_name: str, work_dir: Path) -> Path:
    """Download the original atlas from CDN."""
    import urllib.request

    url = f"{CDN_BASE}/{atlas_name}.png"
    dest = work_dir / f"{atlas_name}_original.png"
    if dest.exists():
        print(f"  Using cached {dest}")
        return dest
    print(f"  Downloading {url}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        dest.write_bytes(resp.read())
    return dest


def classify_cell(row: int) -> str:
    """Classify a cell by its row into a tile type group."""
    for name, (rmin, rmax) in TILE_TYPE_ROWS.items():
        if rmin <= row <= rmax:
            return name
    return "water"  # rows beyond 144 (rare) go to water


# Pre-compute non-base animation frame positions for fast lookup.
# Animation frame (col, row) pairs are computed from the actual atlas in
# compute_anim_frame_set() — this avoids the row-overlap issue where
# different tile types share atlas rows but use different columns.
_anim_frame_set: set[tuple[int, int]] | None = None


def compute_anim_frame_set(atlas_img: Image.Image) -> set[tuple[int, int]]:
    """Scan the atlas to determine which (col, row) cells are animation frames.

    For each animation, the base frame block occupies `offset` contiguous rows
    starting at `base_row + block_start_delta`. Every non-empty cell in the
    base block (within the animation's column range) has corresponding animation
    frame cells at row + i*offset for i = 1..frames-1. We mark those as
    animation frames to exclude from AI batching.

    Column ranges from _ANIM_COL_OFFSETS prevent false positives where different
    tile types share the same atlas rows but use different column ranges.
    """
    anim_frames: set[tuple[int, int]] = set()
    atlas_arr = np.array(atlas_img)

    for entry in ANIMATED_TILES:
        name, base_col, base_row, frames, offset, horizontal, block_start_delta = entry
        if horizontal:
            for i in range(1, frames):
                anim_frames.add((base_col + i * offset, base_row))
        else:
            min_x, max_x = _ANIM_COL_OFFSETS.get(name, (-3, 6))
            block_start = base_row + block_start_delta
            for row_delta in range(offset):
                src_row = block_start + row_delta
                if src_row < 0 or src_row * TILE_SIZE >= atlas_arr.shape[0]:
                    continue
                for col_offset in range(min_x, max_x + 1):
                    col = base_col + col_offset
                    if not (0 <= col < ATLAS_COLS):
                        continue
                    # Check if cell is non-empty in original atlas
                    y0 = src_row * TILE_SIZE
                    x0 = col * TILE_SIZE
                    cell_alpha = atlas_arr[y0:y0 + TILE_SIZE, x0:x0 + TILE_SIZE, 3]
                    if cell_alpha.max() == 0:
                        continue
                    # Mark corresponding cells in non-base frames
                    for i in range(1, frames):
                        anim_frames.add((col, src_row + i * offset))

    return anim_frames


# ---------------------------------------------------------------------------
# Color-space conversion helpers (sRGB <-> CIELAB via D65 XYZ)
# ---------------------------------------------------------------------------

def _rgb_to_lab(rgb_array: np.ndarray) -> np.ndarray:
    """Convert RGB (0-255) array to CIELAB. Shape: (N, 3) -> (N, 3).

    Pipeline: sRGB uint8 -> linear RGB -> XYZ (D65) -> CIELAB.
    """
    # Normalize to 0-1 and apply sRGB companding (inverse gamma)
    rgb = rgb_array.astype(np.float64) / 255.0
    mask = rgb > 0.04045
    rgb = np.where(mask, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92)

    # Linear RGB -> XYZ (sRGB D65 matrix)
    #   http://www.brucelindbloom.com/index.html?Eqn_RGB_XYZ_Matrix.html
    m = np.array([
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ])
    xyz = rgb @ m.T  # (N, 3)

    # Normalize by D65 white point
    d65 = np.array([0.95047, 1.00000, 1.08883])
    xyz = xyz / d65

    # XYZ -> LAB
    epsilon = 216.0 / 24389.0
    kappa = 24389.0 / 27.0
    f = np.where(xyz > epsilon, np.cbrt(xyz), (kappa * xyz + 16.0) / 116.0)

    L = 116.0 * f[:, 1] - 16.0
    a = 500.0 * (f[:, 0] - f[:, 1])
    b = 200.0 * (f[:, 1] - f[:, 2])

    return np.stack([L, a, b], axis=1)


def _lab_to_rgb(lab_array: np.ndarray) -> np.ndarray:
    """Convert CIELAB array to RGB (0-255). Shape: (N, 3) -> (N, 3) uint8.

    Pipeline: CIELAB -> XYZ (D65) -> linear RGB -> sRGB uint8.
    Inverse of ``_rgb_to_lab()``.
    """
    L = lab_array[:, 0]
    a = lab_array[:, 1]
    b = lab_array[:, 2]

    # LAB -> f values
    fy = (L + 16.0) / 116.0
    fx = a / 500.0 + fy
    fz = fy - b / 200.0

    # f values -> XYZ (inverse of the forward transform)
    epsilon = 216.0 / 24389.0
    kappa = 24389.0 / 27.0
    x = np.where(fx ** 3 > epsilon, fx ** 3, (116.0 * fx - 16.0) / kappa)
    y = np.where(L > kappa * epsilon, ((L + 16.0) / 116.0) ** 3, L / kappa)
    z = np.where(fz ** 3 > epsilon, fz ** 3, (116.0 * fz - 16.0) / kappa)

    # Denormalize by D65 white point
    d65 = np.array([0.95047, 1.00000, 1.08883])
    xyz = np.stack([x, y, z], axis=1) * d65  # (N, 3)

    # XYZ -> linear RGB (inverse of the sRGB D65 matrix)
    m_inv = np.array([
        [ 3.2404542, -1.5371385, -0.4985314],
        [-0.9692660,  1.8760108,  0.0415560],
        [ 0.0556434, -0.2040259,  1.0572252],
    ])
    linear_rgb = xyz @ m_inv.T  # (N, 3)

    # Clip to [0, 1] before gamma to avoid NaN from negative values
    linear_rgb = np.clip(linear_rgb, 0.0, 1.0)

    # Apply sRGB gamma companding
    srgb = np.where(
        linear_rgb > 0.0031308,
        1.055 * np.power(linear_rgb, 1.0 / 2.4) - 0.055,
        12.92 * linear_rgb,
    )

    # Clamp and convert to uint8
    srgb = np.clip(srgb * 255.0, 0.0, 255.0)
    return np.round(srgb).astype(np.uint8)


# Modifier x-offset ranges for each animation (from Tile.tsx modifier definitions).
# Used by the conservative init to estimate which columns each animation uses.
_ANIM_COL_OFFSETS: dict[str, tuple[int, int]] = {
    "Sea": (-1, 3),             # AreaModifiers
    "DeepSea": (-1, 3),         # AreaModifiers
    "Beach": (-3, 3),           # AreaModifiers + area decorators (x: -3 to 3)
    "River": (-3, 3),           # RiverModifiers
    "Pier": (0, 6),             # Pier-specific modifiers
    "StormCloud": (-1, 2),      # StormCloud modifiers
    "Lightning": (0, 0),        # Horizontal only
    "LightningV": (0, 0),       # Vertical only
    "RailBridge": (0, 2),       # Bridge modifiers
    "Computer": (0, 0),         # No modifiers
    "Teleporter": (0, 0),       # No modifiers
    "FloatingWaterEdge": (0, 3),  # FWE modifiers
    "Campsite": (0, 0),         # Horizontal
    "Reef": (0, 3),             # With variants
    "GasBubbles": (0, 0),       # Horizontal
    "Island": (0, 4),           # With variants
    "Iceberg/Weeds": (0, 3),    # With variants
    # FloatingEdge border animations
    "FE_Waterfall": (-1, 1),     # cols 8-10 (base_col=9, offsets -1 to +1)
    "FE_WallDecorA": (0, 1),     # cols 9-10 (base_col=9, offsets 0 to +1)
    "FE_WallDecorB": (0, 1),     # cols 9-10
    "FE_AreaDecor": (0, 1),      # cols 9-10
}


def _init_anim_frame_set_conservative():
    """Initialize animation frame set using estimated column ranges.

    Used by tests that don't have a real atlas available. Uses per-animation
    column offset ranges to approximate which (col, row) pairs are animation
    frames, avoiding false positives from overlapping row ranges.
    """
    global _anim_frame_set
    anim_frames: set[tuple[int, int]] = set()
    for entry in ANIMATED_TILES:
        name, base_col, base_row, frames, offset, horizontal, block_start_delta = entry
        min_x, max_x = _ANIM_COL_OFFSETS.get(name, (-3, 6))
        if horizontal:
            for i in range(1, frames):
                anim_frames.add((base_col + i * offset, base_row))
        else:
            block_start = base_row + block_start_delta
            for row_delta in range(offset):
                src_row = block_start + row_delta
                for col_offset in range(min_x, max_x + 1):
                    col = base_col + col_offset
                    if 0 <= col < ATLAS_COLS:
                        for i in range(1, frames):
                            anim_frames.add((col, src_row + i * offset))
    _anim_frame_set = anim_frames


def is_animation_frame(col: int, row: int) -> bool:
    """Return True if this cell is a non-base animation frame.

    These cells should be excluded from AI batching since they'll be
    filled in by copy_base_frames_to_anim_frames() from the base frame.

    Uses per-(col, row) tracking computed from the actual atlas to avoid
    false positives where different tile types share atlas rows.
    """
    global _anim_frame_set
    if _anim_frame_set is None:
        raise RuntimeError("compute_anim_frame_set() must be called before is_animation_frame()")
    return (col, row) in _anim_frame_set


def extract_cells(atlas_path: Path, work_dir: Path) -> list[dict]:
    """Split atlas into individual cells, skipping fully transparent ones."""
    global _anim_frame_set
    img = Image.open(atlas_path).convert("RGBA")
    w, h = img.size
    rows = h // TILE_SIZE

    # Compute animation frame set from actual atlas data
    _anim_frame_set = compute_anim_frame_set(img)

    cells_dir = work_dir / "cells"
    cells_dir.mkdir(exist_ok=True)

    cells = []
    for row in range(rows):
        for col in range(ATLAS_COLS):
            x = col * TILE_SIZE
            y = row * TILE_SIZE
            cell = img.crop((x, y, x + TILE_SIZE, y + TILE_SIZE))

            arr = np.array(cell)
            if arr[:, :, 3].max() == 0:
                continue

            cell_id = f"r{row:03d}_c{col:02d}"
            cell_path = cells_dir / f"{cell_id}.png"
            cell.save(cell_path)

            cells.append({
                "id": cell_id,
                "row": row,
                "col": col,
                "x": x,
                "y": y,
                "path": str(cell_path),
                "type": classify_cell(row),
                "is_anim_frame": is_animation_frame(col, row),
            })

    anim_count = sum(1 for c in cells if c["is_anim_frame"])
    print(f"  Extracted {len(cells)} non-empty cells from {rows} rows x {ATLAS_COLS} cols")
    print(f"  {anim_count} cells are animation frames (excluded from AI batching)")

    from collections import Counter
    type_counts = Counter(c["type"] for c in cells)
    for t in sorted(type_counts.keys()):
        print(f"    {t}: {type_counts[t]} cells")

    return cells


def create_typed_batches(cells: list[dict], work_dir: Path) -> list[dict]:
    """Group cells by terrain type, then batch into 6x6 grids.

    Animation frame cells (is_anim_frame=True) are excluded from batching.
    They will be filled in later by copy_base_frames_to_anim_frames().
    """
    batches_dir = work_dir / "batches"
    batches_dir.mkdir(exist_ok=True)
    # Clean old batch files
    for f in batches_dir.iterdir():
        f.unlink()

    # Filter out animation frame cells — only base frames go to AI
    excluded = sum(1 for c in cells if c.get("is_anim_frame"))
    batchable = [c for c in cells if not c.get("is_anim_frame")]
    if excluded:
        print(f"  Excluded {excluded} animation frame cells from batching")

    by_type = defaultdict(list)
    for c in batchable:
        by_type[c["type"]].append(c)

    cell_w = TILE_SIZE + CELL_PADDING * 2
    cell_h = TILE_SIZE + CELL_PADDING * 2

    batches = []
    batch_counter = 0

    for tile_type in sorted(by_type.keys()):
        type_cells = by_type[tile_type]
        for chunk_idx in range(0, len(type_cells), CELLS_PER_BATCH):
            batch_cells = type_cells[chunk_idx:chunk_idx + CELLS_PER_BATCH]
            n = len(batch_cells)
            cols = min(GRID_COLS, n)
            rows = math.ceil(n / GRID_COLS)

            canvas_w = cols * cell_w + (cols + 1) * GRID_LINE_WIDTH
            canvas_h = rows * cell_h + (rows + 1) * GRID_LINE_WIDTH

            canvas = Image.new("RGBA", (canvas_w, canvas_h), LINE_COLOR)
            draw = ImageDraw.Draw(canvas)

            batch_id = f"batch_{batch_counter:03d}_{tile_type}"
            batch_meta = {
                "batch_id": batch_id,
                "tile_type": tile_type,
                "cols": cols,
                "rows": rows,
                "canvas_w": canvas_w,
                "canvas_h": canvas_h,
                "cell_w": cell_w,
                "cell_h": cell_h,
                "cells": [],
            }

            for idx, cell_info in enumerate(batch_cells):
                row = idx // GRID_COLS
                col = idx % GRID_COLS

                cx = GRID_LINE_WIDTH + col * (cell_w + GRID_LINE_WIDTH)
                cy = GRID_LINE_WIDTH + row * (cell_h + GRID_LINE_WIDTH)

                draw.rectangle(
                    [cx, cy, cx + cell_w - 1, cy + cell_h - 1],
                    fill=BG_COLOR,
                )

                tile_img = Image.open(cell_info["path"]).convert("RGBA")
                paste_x = cx + CELL_PADDING
                paste_y = cy + CELL_PADDING
                canvas.paste(tile_img, (paste_x, paste_y), tile_img)

                batch_meta["cells"].append({
                    **cell_info,
                    "grid_row": row,
                    "grid_col": col,
                })

            # Scale up 4x for AI visibility
            scale_factor = 4
            scaled = canvas.resize(
                (canvas_w * scale_factor, canvas_h * scale_factor),
                Image.NEAREST,
            )

            batch_path = batches_dir / f"{batch_id}.png"
            scaled.save(batch_path)
            batch_meta["path"] = str(batch_path)
            batch_meta["scale_factor"] = scale_factor
            batches.append(batch_meta)
            batch_counter += 1

    # Summary
    type_batch_counts = {}
    for b in batches:
        t = b["tile_type"]
        type_batch_counts[t] = type_batch_counts.get(t, 0) + 1
    print(f"  Created {len(batches)} batches grouped by type:")
    for t in sorted(type_batch_counts.keys()):
        print(f"    {t}: {type_batch_counts[t]} batches")

    return batches


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

    terrain_order = ["plain", "street", "mountain", "forest",
                     "campsite", "pier", "water", "river"]

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


def extract_palette(
    anchor_paths: dict[str, str],
    work_dir: Path,
    max_colors: int = 16,
) -> np.ndarray:
    """Extract a quantized color palette from anchor tiles in LAB space.

    Gemini-generated anchors have smooth gradients with 100K+ unique colors.
    We quantize each anchor down to ``max_colors`` using PIL median-cut, then
    combine and deduplicate across all anchors.

    Returns numpy array of shape (N, 3) in LAB color space.
    Also saves palette.json with hex colors.
    """
    all_colors = set()

    for terrain_type, path in anchor_paths.items():
        img = Image.open(path).convert("RGBA")
        arr = np.array(img)

        # Only consider visible pixels (alpha > 0)
        visible = arr[:, :, 3] > 0
        if not visible.any():
            continue

        # Exclude exact grid-line color (0,0,0) and exact padding color (200,200,200)
        rgb = arr[:, :, :3]
        is_grid_line = (rgb == LINE_COLOR[:3]).all(axis=2)
        is_padding = (rgb == BG_COLOR[:3]).all(axis=2)
        tile_pixels = visible & ~is_grid_line & ~is_padding
        if not tile_pixels.any():
            tile_pixels = visible  # fallback

        # Quantize the filtered tile pixels via PIL median-cut
        pixel_rgb = rgb[tile_pixels]  # (P, 3)
        row_img = Image.fromarray(pixel_rgb.reshape(1, -1, 3))
        quantized = row_img.quantize(
            colors=max_colors, method=Image.Quantize.MEDIANCUT,
        )

        # Extract the actually-used colors from the quantized result
        qpal = quantized.getpalette()
        quantized_arr = np.array(quantized)
        used_indices = set(quantized_arr.flat)
        for idx in used_indices:
            r, g, b = qpal[idx * 3], qpal[idx * 3 + 1], qpal[idx * 3 + 2]
            all_colors.add((r, g, b))

    if not all_colors:
        print("WARNING: No visible pixels found in anchor tiles")
        return np.zeros((0, 3), dtype=np.float64)

    # Convert to numpy arrays
    palette_rgb = np.array(sorted(all_colors), dtype=np.uint8)  # (M, 3)
    palette_lab = _rgb_to_lab(palette_rgb)

    # Save as palette.json with hex values
    hex_colors = [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in palette_rgb]
    palette_json = {
        "colors": hex_colors,
        "count": len(hex_colors),
    }
    palette_path = work_dir / "palette.json"
    palette_path.write_text(json.dumps(palette_json, indent=2))

    print(f"  Quantized to {len(palette_rgb)} unique colors from {len(anchor_paths)} anchors")
    print(f"  Saved palette to {palette_path}")

    return palette_lab


def snap_to_palette(
    reskinned_cells: list[tuple[dict, Image.Image]],
    palette_lab: np.ndarray,
    palette_rgb: np.ndarray,
) -> list[tuple[dict, Image.Image]]:
    """Snap every visible pixel to nearest palette color in LAB space.

    For each cell image:
    - Convert visible pixels to LAB
    - Find nearest palette color by Euclidean distance
    - Replace RGB with palette color
    - Preserve alpha unchanged

    Returns new list of (cell_info, snapped_image) tuples.

    Note: If the palette is large (80+ colors) and cells are many, this
    could use significant memory due to the (P, M, 3) distance matrix.
    For typical atlas sizes (~840 cells, ~80 palette colors) this is fine.
    """
    if len(palette_lab) == 0:
        print("  WARNING: Empty palette, skipping snap")
        return list(reskinned_cells)

    result = []

    for cell_info, img in reskinned_cells:
        arr = np.array(img).copy()  # (H, W, 4) uint8
        visible = arr[:, :, 3] > 0

        if not visible.any():
            result.append((cell_info, img))
            continue

        # Get visible pixel RGB values
        visible_rgb = arr[:, :, :3][visible]  # (P, 3)

        # Convert to LAB
        visible_lab = _rgb_to_lab(visible_rgb)  # (P, 3)

        # Find nearest palette color by Euclidean distance in LAB space
        # visible_lab: (P, 3), palette_lab: (M, 3)
        diffs = visible_lab[:, np.newaxis, :] - palette_lab[np.newaxis, :, :]  # (P, M, 3)
        distances = np.sum(diffs ** 2, axis=2)  # (P, M)
        nearest_idx = np.argmin(distances, axis=1)  # (P,)
        new_rgb = palette_rgb[nearest_idx]  # (P, 3)

        # Replace visible pixel RGB values, keep alpha unchanged
        arr[:, :, :3][visible] = new_rgb

        snapped_img = Image.fromarray(arr)
        result.append((cell_info, snapped_img))

    print(f"  Snapped {len(result)} cells to {len(palette_lab)}-color palette")

    return result


def harmonize_transitions(
    reskinned_cells: list[tuple[dict, Image.Image]],
    original_atlas_path: Path,
    strength: float = 0.6,
) -> list[tuple[dict, Image.Image]]:
    """Shift transition-tile pixel colors toward reference terrain colors.

    Transition tiles (beach, riverbank, sea edges) contain pixels from two
    terrain types (e.g. grass + water).  Because they are batched by their
    primary type, the AI reskins the secondary-type portions with slightly
    different tones than actual plain/water tiles.  This function detects
    grass-like and water-like pixels in each transition cell using the
    *original* atlas and shifts the corresponding reskinned pixels toward
    the mean color of real plain / water cells.

    Parameters
    ----------
    reskinned_cells : list of (cell_info, Image) tuples
    original_atlas_path : path to the original (un-reskinned) atlas PNG
    strength : blending strength in [0, 1]; 0 = no change, 1 = full shift

    Returns
    -------
    list of (cell_info, Image) tuples with harmonized images.
    """
    original_atlas = Image.open(original_atlas_path).convert("RGBA")

    # ------------------------------------------------------------------
    # 1. Extract reference LAB colors from reskinned cells
    # ------------------------------------------------------------------
    grass_pixels: list[np.ndarray] = []
    water_pixels: list[np.ndarray] = []

    for cell_info, img in reskinned_cells:
        arr = np.array(img)
        visible = arr[:, :, 3] > 0
        if not visible.any():
            continue

        ctype = cell_info.get("type", "")
        row = cell_info.get("row", -1)

        if ctype == "plain":
            grass_pixels.append(arr[:, :, :3][visible])
        elif ctype == "water" and row < 50:
            water_pixels.append(arr[:, :, :3][visible])

    # Compute mean LAB for each reference group
    grass_ref_lab: np.ndarray | None = None
    water_ref_lab: np.ndarray | None = None

    if grass_pixels:
        all_grass = np.concatenate(grass_pixels, axis=0).astype(np.float64)
        grass_lab = _rgb_to_lab(all_grass)
        grass_ref_lab = grass_lab.mean(axis=0)  # (3,)

    if water_pixels:
        all_water = np.concatenate(water_pixels, axis=0).astype(np.float64)
        water_lab = _rgb_to_lab(all_water)
        water_ref_lab = water_lab.mean(axis=0)  # (3,)

    if grass_ref_lab is None and water_ref_lab is None:
        print("  WARNING: No reference colors found, skipping harmonize")
        return list(reskinned_cells)

    # ------------------------------------------------------------------
    # 2-3. For each transition cell, classify & shift pixels
    # ------------------------------------------------------------------
    result: list[tuple[dict, Image.Image]] = []
    harmonized_count = 0

    for cell_info, img in reskinned_cells:
        ctype = cell_info.get("type", "")
        row = cell_info.get("row", -1)

        # Determine if this is a transition cell
        is_transition = False
        if ctype == "water" and row >= 50:
            is_transition = True  # beach
        elif ctype == "river":
            is_transition = True  # riverbank
        elif ctype == "water" and 34 <= row <= 49:
            # Edge columns of sea tiles
            col = cell_info.get("col", -1)
            if col == 0 or col == ATLAS_COLS - 1:
                is_transition = True

        if not is_transition:
            result.append((cell_info, img))
            continue

        reskinned_arr = np.array(img).copy()  # (H, W, 4) uint8
        visible = reskinned_arr[:, :, 3] > 0
        if not visible.any():
            result.append((cell_info, img))
            continue

        # Extract the matching cell from the original atlas
        x = cell_info["x"]
        y = cell_info["y"]
        orig_cell = original_atlas.crop((x, y, x + TILE_SIZE, y + TILE_SIZE))
        orig_arr = np.array(orig_cell)

        # Classify original pixels using HSV
        orig_rgb = orig_arr[:, :, :3].astype(np.float64) / 255.0

        # Manual RGB -> HSV (vectorized)
        cmax = orig_rgb.max(axis=2)
        cmin = orig_rgb.min(axis=2)
        delta = cmax - cmin

        # Hue calculation
        hue = np.zeros_like(cmax)
        r, g, b = orig_rgb[:, :, 0], orig_rgb[:, :, 1], orig_rgb[:, :, 2]

        mask_r = (cmax == r) & (delta > 0)
        mask_g = (cmax == g) & (delta > 0) & ~mask_r
        mask_b = (delta > 0) & ~mask_r & ~mask_g

        hue[mask_r] = 60.0 * (((g[mask_r] - b[mask_r]) / delta[mask_r]) % 6.0)
        hue[mask_g] = 60.0 * ((b[mask_g] - r[mask_g]) / delta[mask_g] + 2.0)
        hue[mask_b] = 60.0 * ((r[mask_b] - g[mask_b]) / delta[mask_b] + 4.0)

        # Saturation (0-1 scale)
        sat = np.where(cmax > 0, delta / cmax, 0.0)

        # Classify: grass-like and water-like masks (only for visible pixels)
        grass_mask = visible & (hue >= 60) & (hue <= 160) & (sat > 0.20)
        water_mask = visible & (hue >= 180) & (hue <= 260) & (sat > 0.20)

        modified = False

        # Shift grass-like pixels
        if grass_ref_lab is not None and grass_mask.any():
            px_rgb = reskinned_arr[:, :, :3][grass_mask].astype(np.float64)
            px_lab = _rgb_to_lab(px_rgb)
            shift = (grass_ref_lab[np.newaxis, :] - px_lab) * strength
            shifted_lab = px_lab + shift
            shifted_rgb = _lab_to_rgb(shifted_lab)
            reskinned_arr[:, :, :3][grass_mask] = shifted_rgb
            modified = True

        # Shift water-like pixels
        if water_ref_lab is not None and water_mask.any():
            px_rgb = reskinned_arr[:, :, :3][water_mask].astype(np.float64)
            px_lab = _rgb_to_lab(px_rgb)
            shift = (water_ref_lab[np.newaxis, :] - px_lab) * strength
            shifted_lab = px_lab + shift
            shifted_rgb = _lab_to_rgb(shifted_lab)
            reskinned_arr[:, :, :3][water_mask] = shifted_rgb
            modified = True

        if modified:
            harmonized_count += 1

        result.append((cell_info, Image.fromarray(reskinned_arr)))

    print(f"  Harmonized {harmonized_count} transition cells (strength={strength})")
    return result


def reskin_batch_gemini(
    batch_path: str,
    theme: dict,
    batch_id: str,
    tile_type: str,
    anchor_paths: list[str] | None = None,
) -> Image.Image | None:
    """Send a batch grid to Gemini Flash for reskinning.

    When *anchor_paths* contains one path, uses the two-image
    ``BATCH_PROMPT_TEMPLATE`` (anchor + batch).  When it contains multiple
    paths (e.g. type anchor + plain anchor for transition tiles), uses the
    ``MULTI_ANCHOR_BATCH_PROMPT_TEMPLATE`` with all anchors then the batch.
    When ``None`` or empty, falls back to the single-image
    ``ANCHOR_PROMPT_TEMPLATE``.
    """
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    type_hint = TILE_TYPE_HINTS.get(tile_type, "")

    if anchor_paths and len(anchor_paths) > 1:
        # Multi-anchor prompt: type anchor + plain anchor + batch to reskin
        prompt = MULTI_ANCHOR_BATCH_PROMPT_TEMPLATE.format(
            type_name=tile_type, type_hint=type_hint,
        )

        contents: list = [prompt]
        for ap in anchor_paths:
            data = open(ap, "rb").read()
            contents.append(types.Part.from_bytes(data=data, mime_type="image/png"))
        batch_data = open(batch_path, "rb").read()
        contents.append(types.Part.from_bytes(data=batch_data, mime_type="image/png"))
    elif anchor_paths and len(anchor_paths) == 1:
        # Two-image prompt: anchor tile + batch to reskin
        prompt = BATCH_PROMPT_TEMPLATE.format(
            type_name=tile_type, type_hint=type_hint,
        )

        anchor_data = open(anchor_paths[0], "rb").read()
        anchor_part = types.Part.from_bytes(data=anchor_data, mime_type="image/png")
        batch_data = open(batch_path, "rb").read()
        batch_part = types.Part.from_bytes(data=batch_data, mime_type="image/png")
        contents = [prompt, anchor_part, batch_part]
    else:
        # Single-image prompt (backward compat fallback)
        prompt = ANCHOR_PROMPT_TEMPLATE.format(
            type_name=tile_type, type_hint=type_hint,
        )

        img_data = open(batch_path, "rb").read()
        image_part = types.Part.from_bytes(data=img_data, mime_type="image/png")
        contents = [prompt, image_part]

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.1-flash-image-preview",
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                ),
            )

            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    import io
                    return Image.open(io.BytesIO(part.inline_data.data)).convert("RGBA")

            print(f"    {batch_id}: No image in response (attempt {attempt + 1})")
        except Exception as e:
            print(f"    {batch_id}: Error (attempt {attempt + 1}): {e}")
            if attempt < 2:
                time.sleep(5 * (attempt + 1))

    return None


def normalize_colors_by_type(
    reskinned_cells: list[tuple[dict, Image.Image]],
) -> list[tuple[dict, Image.Image]]:
    """Normalize colors within each tile type to reduce batch-to-batch drift.

    Computes the average visible RGB for each type, then shifts each tile's
    colors so its mean moves 50% toward the type-wide mean.
    """
    by_type: dict[str, list[int]] = defaultdict(list)
    for i, (cell_info, _) in enumerate(reskinned_cells):
        by_type[cell_info["type"]].append(i)

    result = list(reskinned_cells)

    for tile_type, indices in by_type.items():
        if len(indices) < 2:
            continue

        tile_means = []
        for idx in indices:
            _, img = reskinned_cells[idx]
            arr = np.array(img).astype(np.float32)
            visible = arr[:, :, 3] > 0
            if not visible.any():
                tile_means.append(None)
                continue
            mean_rgb = arr[:, :, :3][visible].mean(axis=0)
            tile_means.append(mean_rgb)

        valid_means = [m for m in tile_means if m is not None]
        if not valid_means:
            continue
        target_mean = np.mean(valid_means, axis=0)

        correction_strength = 0.5
        for j, idx in enumerate(indices):
            if tile_means[j] is None:
                continue
            cell_info, img = reskinned_cells[idx]
            arr = np.array(img).astype(np.float32)
            visible = arr[:, :, 3] > 0

            shift = (target_mean - tile_means[j]) * correction_strength

            arr[:, :, 0][visible] = np.clip(arr[:, :, 0][visible] + shift[0], 0, 255)
            arr[:, :, 1][visible] = np.clip(arr[:, :, 1][visible] + shift[1], 0, 255)
            arr[:, :, 2][visible] = np.clip(arr[:, :, 2][visible] + shift[2], 0, 255)

            result[idx] = (cell_info, Image.fromarray(arr.astype(np.uint8)))

    normalized_types = [t for t, idxs in by_type.items() if len(idxs) >= 2]
    print(f"  Normalized colors for {len(normalized_types)} tile types")

    return result


def extract_from_reskinned(
    reskinned_img: Image.Image,
    batch_meta: dict,
) -> list[tuple[dict, Image.Image]]:
    """Extract individual reskinned cells from the AI output grid."""
    scale_factor = batch_meta["scale_factor"]
    cell_w = batch_meta["cell_w"]
    cell_h = batch_meta["cell_h"]

    native_w = batch_meta["canvas_w"]
    native_h = batch_meta["canvas_h"]

    scaled_w = native_w * scale_factor
    scaled_h = native_h * scale_factor

    if reskinned_img.size != (scaled_w, scaled_h):
        reskinned_img = reskinned_img.resize((scaled_w, scaled_h), Image.LANCZOS)

    native_img = reskinned_img.resize((native_w, native_h), Image.LANCZOS)

    results = []
    for cell_info in batch_meta["cells"]:
        row = cell_info["grid_row"]
        col = cell_info["grid_col"]

        cx = GRID_LINE_WIDTH + col * (cell_w + GRID_LINE_WIDTH)
        cy = GRID_LINE_WIDTH + row * (cell_h + GRID_LINE_WIDTH)

        tile_x = cx + CELL_PADDING
        tile_y = cy + CELL_PADDING

        tile_crop = native_img.crop((
            tile_x, tile_y,
            tile_x + TILE_SIZE, tile_y + TILE_SIZE,
        ))

        original = Image.open(cell_info["path"]).convert("RGBA")
        r, g, b, _ = tile_crop.split()
        _, _, _, orig_alpha = original.split()
        tile_final = Image.merge("RGBA", (r, g, b, orig_alpha))

        results.append((cell_info, tile_final))

    return results


def _alpha_similarity(img_a: Image.Image, img_b: Image.Image) -> float:
    """Return fraction of pixels where alpha channels match (both >0 or both ==0)."""
    a = np.array(img_a)[:, :, 3] > 0
    b = np.array(img_b)[:, :, 3] > 0
    return float(np.mean(a == b))


def copy_base_frames_to_anim_frames(
    reskinned_cells: list[tuple[dict, Image.Image]],
    original_atlas_path: Path,
) -> list[tuple[dict, Image.Image]]:
    """Copy base animation frame pixels to all other frames.

    The AI reskins each batch independently, so animation frames of the same
    tile can end up with completely different patterns. This post-processing
    step ensures all frames of an animated tile use the base frame's art,
    eliminating flickering.

    For vertical animations with offset > 1, the animation reads a BLOCK of
    rows per frame (e.g. Sea offset=3 reads 3 rows). The block starts at
    base_row + block_start_delta. We iterate ALL rows in the base block and
    copy each to the corresponding row in every subsequent frame block.

    Uses alpha-channel similarity to verify that a cell at a frame row is
    actually an animation frame (same shape as base) rather than a different
    tile type that shares the same row range.
    """
    orig_atlas = Image.open(original_atlas_path).convert("RGBA")

    # Index reskinned cells by (col, row)
    by_pos: dict[tuple[int, int], int] = {}
    for i, (cell_info, _) in enumerate(reskinned_cells):
        by_pos[(cell_info["col"], cell_info["row"])] = i

    # Snapshot source images before any copies (so one animation's write
    # doesn't corrupt another animation's base lookup).
    source_imgs: dict[tuple[int, int], Image.Image] = {}
    for i, (cell_info, img) in enumerate(reskinned_cells):
        source_imgs[(cell_info["col"], cell_info["row"])] = img

    result = list(reskinned_cells)
    # Track which frame cells have been written (base cells can be read
    # by multiple animations).
    claimed_frames: set[tuple[int, int]] = set()
    copied = 0

    # Threshold: animation frames should have very similar alpha masks
    ALPHA_THRESHOLD = 0.83

    # Multi-pass: one animation's frame cells may be another's base cells
    # (e.g. Computer frame cells overlap with Pier base rows). Keep iterating
    # until no new copies are produced.
    for pass_num in range(5):
        pass_copied = 0
        for entry in ANIMATED_TILES:
            name, base_col, base_row, frames, offset, horizontal, block_start_delta = entry
            if horizontal:
                base_img = source_imgs.get((base_col, base_row))
                if base_img is None:
                    continue
                for i in range(1, frames):
                    frame_col = base_col + i * offset
                    pos = (frame_col, base_row)
                    if pos in claimed_frames:
                        continue
                    frame_idx = by_pos.get(pos)
                    if frame_idx is not None:
                        cell_info, _ = result[frame_idx]
                        result[frame_idx] = (cell_info, base_img.copy())
                    else:
                        cell_info = {
                            "col": frame_col, "row": base_row,
                            "x": frame_col * TILE_SIZE, "y": base_row * TILE_SIZE,
                        }
                        result.append((cell_info, base_img.copy()))
                    claimed_frames.add(pos)
                    source_imgs[pos] = base_img
                    pass_copied += 1
            else:
                # Iterate ALL rows in the base frame block, restricted to
                # columns that belong to this animation type.
                block_start = base_row + block_start_delta
                col_lo, col_hi = _ANIM_COL_OFFSETS.get(name, (0, ATLAS_COLS - 1 - base_col))
                min_col = max(0, base_col + col_lo)
                max_col = min(ATLAS_COLS - 1, base_col + col_hi)
                # Skip alpha check for single-row animations (offset=1) where
                # each frame intentionally has a different silhouette (e.g.
                # Lightning, Teleporter). The column range restriction is
                # sufficient to prevent cross-type contamination.
                check_alpha = offset > 1

                for row_delta in range(offset):
                    src_row = block_start + row_delta
                    for col in range(min_col, max_col + 1):
                        base_img = source_imgs.get((col, src_row))
                        if base_img is None:
                            continue

                        # Get original alpha of base cell
                        bx, by_ = col * TILE_SIZE, src_row * TILE_SIZE
                        orig_base = orig_atlas.crop((bx, by_, bx + TILE_SIZE, by_ + TILE_SIZE))

                        for i in range(1, frames):
                            frame_row = src_row + i * offset
                            pos = (col, frame_row)
                            if pos in claimed_frames:
                                continue

                            if check_alpha:
                                # Check alpha similarity to verify this is
                                # the same tile shape (not a different type)
                                fx, fy = col * TILE_SIZE, frame_row * TILE_SIZE
                                orig_frame = orig_atlas.crop((fx, fy, fx + TILE_SIZE, fy + TILE_SIZE))
                                if _alpha_similarity(orig_base, orig_frame) < ALPHA_THRESHOLD:
                                    continue

                            frame_idx = by_pos.get(pos)
                            if frame_idx is not None:
                                cell_info, _ = result[frame_idx]
                                result[frame_idx] = (cell_info, base_img.copy())
                            else:
                                cell_info = {
                                    "col": col, "row": frame_row,
                                    "x": col * TILE_SIZE, "y": frame_row * TILE_SIZE,
                                }
                                result.append((cell_info, base_img.copy()))
                                by_pos[pos] = len(result) - 1
                            claimed_frames.add(pos)
                            source_imgs[pos] = base_img
                            pass_copied += 1
        copied += pass_copied
        if pass_copied == 0:
            break

    print(f"  Copied base frame to {copied} animation frame cells")
    return result


def reassemble_atlas(
    original_atlas_path: Path,
    reskinned_cells: list[tuple[dict, Image.Image]],
    output_path: Path,
):
    """Patch reskinned cells back into the atlas at exact positions."""
    atlas = Image.open(original_atlas_path).convert("RGBA")

    for cell_info, tile_img in reskinned_cells:
        x = cell_info["x"]
        y = cell_info["y"]

        clear = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))
        atlas.paste(clear, (x, y))
        atlas.paste(tile_img, (x, y), tile_img)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(output_path)
    print(f"  Saved reskinned atlas to {output_path}")


def _reskin_batches(
    batches: list[dict],
    theme: dict,
    reskinned_dir: Path,
    workers: int,
    anchor_paths: dict[str, str] | None = None,
) -> list[tuple[dict, Image.Image]]:
    """Reskin batches using parallel workers."""
    import concurrent.futures
    import threading

    print_lock = threading.Lock()
    all_reskinned: list[tuple[dict, Image.Image]] = []

    def process_batch(batch_meta: dict) -> list[tuple[dict, Image.Image]]:
        batch_id = batch_meta["batch_id"]
        tile_type = batch_meta["tile_type"]
        reskinned_path = reskinned_dir / f"{batch_id}_reskinned.png"
        meta_path = reskinned_dir / f"{batch_id}_reskinned.meta.json"

        # Build fingerprint of current batch layout
        current_fp = {
            "n_cells": len(batch_meta["cells"]),
            "canvas_w": batch_meta["canvas_w"],
            "canvas_h": batch_meta["canvas_h"],
            "cell_positions": [
                [c["col"], c["row"]] for c in batch_meta["cells"]
            ],
        }

        cache_valid = False
        if reskinned_path.exists() and meta_path.exists():
            try:
                saved_fp = json.loads(meta_path.read_text())
                if (saved_fp.get("n_cells") == current_fp["n_cells"]
                        and saved_fp.get("canvas_w") == current_fp["canvas_w"]
                        and saved_fp.get("canvas_h") == current_fp["canvas_h"]
                        and saved_fp.get("cell_positions") == current_fp["cell_positions"]):
                    cache_valid = True
                    reskinned_img = Image.open(reskinned_path).convert("RGBA")
                    with print_lock:
                        print(f"  {batch_id}: Using cached result")
                else:
                    with print_lock:
                        print(f"  {batch_id}: Stale cache (layout changed), regenerating")
            except (json.JSONDecodeError, KeyError):
                with print_lock:
                    print(f"  {batch_id}: Invalid cache metadata, regenerating")
        elif reskinned_path.exists():
            with print_lock:
                print(f"  {batch_id}: No cache metadata, regenerating")

        if not cache_valid:
            with print_lock:
                print(
                    f"  {batch_id}: Sending to Gemini Flash "
                    f"({len(batch_meta['cells'])} {tile_type} cells)"
                )
            batch_anchor_paths = None
            if anchor_paths:
                type_anchor = anchor_paths.get(tile_type)
                if type_anchor:
                    batch_anchor_paths = [type_anchor]
                    # For transition types (water, river), include the plain
                    # anchor as a second reference so Gemini matches the
                    # grass/land colors in coastline and riverbank tiles.
                    if tile_type in ("water", "river"):
                        plain_anchor = anchor_paths.get("plain")
                        if plain_anchor and plain_anchor != type_anchor:
                            batch_anchor_paths.append(plain_anchor)
            reskinned_img = reskin_batch_gemini(
                batch_meta["path"], theme, batch_id, tile_type,
                anchor_paths=batch_anchor_paths,
            )
            if reskinned_img is None:
                with print_lock:
                    print(f"  {batch_id}: FAILED — skipping")
                return []
            reskinned_img.save(reskinned_path)
            meta_path.write_text(json.dumps(current_fp))

        extracted = extract_from_reskinned(reskinned_img, batch_meta)
        with print_lock:
            print(f"  {batch_id}: Extracted {len(extracted)} cells")
        return extracted

    if workers <= 1 or len(batches) <= 1:
        for batch_meta in batches:
            result = process_batch(batch_meta)
            all_reskinned.extend(result)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(process_batch, bm): bm
                for bm in batches
            }
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    all_reskinned.extend(result)
                except Exception as e:
                    batch_meta = futures[future]
                    with print_lock:
                        print(f"  {batch_meta['batch_id']}: Worker error: {e}")

    return all_reskinned


def _load_env_and_theme(args):
    """Load .env file and theme config.  Returns (theme, work_dir, atlas_path equivalent is done later)."""
    # Load .env if present
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

    # Load theme
    theme_path = Path(__file__).parent / "themes" / f"{args.theme}.json"
    if not theme_path.exists():
        print(f"ERROR: Theme file not found: {theme_path}")
        sys.exit(1)
    theme = json.loads(theme_path.read_text())
    print(f"Theme: {theme['name']} — {theme['description']}")
    return theme


def _download_and_extract(args, work_dir: Path):
    """Download atlas and extract cells.  Returns (atlas_path, cells)."""
    print("\n1. Downloading original atlas...")
    atlas_path = download_atlas(args.atlas, work_dir)

    print("\n2. Extracting cells...")
    cells_manifest = work_dir / "cells_manifest.json"
    cells = None
    if cells_manifest.exists() and (work_dir / "cells").exists():
        cached = json.loads(cells_manifest.read_text())
        if cached and "type" in cached[0]:
            first_type = classify_cell(cached[0]["row"])
            if cached[0]["type"] == first_type:
                print("  Using cached cells manifest")
                cells = cached
    if cells is None:
        cells = extract_cells(atlas_path, work_dir)
        cells_manifest.write_text(json.dumps(cells, indent=2))

    return atlas_path, cells


def _update_manifest(args, output_path: Path):
    """Update the reskin manifest.json to point to the new atlas."""
    manifest_path = (
        Path(__file__).parent.parent / "public" / "reskin" / "manifest.json"
    )
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
    else:
        manifest = {}

    relative_path = f"reskin/{args.theme}/{args.atlas}.png"
    if "tiles" not in manifest:
        manifest["tiles"] = {}
    manifest["tiles"][args.atlas] = relative_path
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"  Updated manifest: {args.atlas} -> {relative_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Reskin tile atlases for Athena Crisis"
    )
    parser.add_argument("--atlas", required=True, help="Atlas name (e.g. Tiles0)")
    parser.add_argument("--theme", required=True, help="Theme name (e.g. cozy)")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Extract and batch only, no AI calls",
    )
    parser.add_argument(
        "--type-only", type=str, default=None,
        help="Process only this tile type (e.g. water, river, plain)",
    )
    parser.add_argument(
        "--fresh", action="store_true",
        help="Clear cached reskinned batches and regenerate",
    )
    parser.add_argument(
        "--workers", type=int, default=8,
        help="Number of parallel workers for API calls (default: 8)",
    )
    parser.add_argument(
        "--stage", type=str, default="full",
        choices=["1", "2", "full"],
        help=(
            "Pipeline stage to run. "
            "1: generate anchor tiles and extract palette, exit. "
            "2: reskin all batches with anchors, palette snap, reassemble atlas, exit. "
            "full: all stages sequentially (default)."
        ),
    )
    parser.add_argument(
        "--skip-harmonize", action="store_true",
        help="Skip the transition-tile color harmonization step",
    )
    args = parser.parse_args()

    theme = _load_env_and_theme(args)

    # Working directory
    work_dir = Path(__file__).parent / "output" / f"{args.atlas}_{args.theme}"
    work_dir.mkdir(parents=True, exist_ok=True)

    # Common steps: download atlas and extract cells
    atlas_path, cells = _download_and_extract(args, work_dir)

    # Create type-grouped batches
    print("\n3. Creating type-grouped batches...")
    batches = create_typed_batches(cells, work_dir)
    batches_manifest = work_dir / "batches_manifest.json"
    batches_manifest.write_text(json.dumps(batches, indent=2))

    if args.dry_run:
        print(f"\nDry run complete. {len(cells)} cells in {len(batches)} batches.")
        print(f"Batch grids saved to {work_dir / 'batches'}/")
        return

    # ---- Stage 1: Generate anchors + extract palette ----
    if args.stage in ("1", "full"):
        print("\n--- Stage 1: Generating anchor tiles ---")
        anchor_paths = generate_anchors(cells, theme, work_dir)

        print("\n--- Stage 1: Extracting palette from anchors ---")
        palette_lab = extract_palette(anchor_paths, work_dir)

        if args.stage == "1":
            print(f"\nStage 1 complete. Review anchor tiles at {work_dir}/anchor_*.png")
            print(f"Palette saved to {work_dir}/palette.json")
            print("If anchors look good, run --stage 2.")
            return

    # ---- Stage 2: Full reskin + palette snap + reassemble ----
    if args.stage in ("2", "full"):
        print("\n--- Stage 2: Full reskin with palette snap ---")
        reskinned_dir = work_dir / "reskinned"
        reskinned_dir.mkdir(exist_ok=True)

        if args.fresh:
            for f in reskinned_dir.iterdir():
                if args.type_only and args.type_only not in f.name:
                    continue
                f.unlink()
            print("  Cleared cached reskinned batches")

        # Load anchor paths from existing files (if not already from stage 1)
        if args.stage == "2":
            anchor_paths = {}
            for ttype in [
                "plain", "street", "mountain", "forest",
                "campsite", "pier", "water", "river",
            ]:
                anchor_file = work_dir / f"anchor_{ttype}.png"
                if anchor_file.exists():
                    anchor_paths[ttype] = str(anchor_file)
            if not anchor_paths:
                print("ERROR: No anchor tiles found. Run --stage 1 first.")
                sys.exit(1)

        # Load palette (always from palette.json for consistency)
        palette_json_path = work_dir / "palette.json"
        if not palette_json_path.exists():
            print("ERROR: palette.json not found. Run --stage 1 first.")
            sys.exit(1)
        palette_data = json.loads(palette_json_path.read_text())
        palette_rgb = np.array([
            [int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)]
            for h in palette_data["colors"]
        ], dtype=np.uint8)
        palette_lab = _rgb_to_lab(palette_rgb.astype(np.float64))

        # Reskin batches
        target_batches = batches
        if args.type_only:
            target_batches = [b for b in batches if b["tile_type"] == args.type_only]
            print(f"\n  Reskinning {len(target_batches)} {args.type_only} batches...")
        else:
            print(f"\n  Reskinning {len(target_batches)} batches with Gemini Flash...")

        all_reskinned_cells = _reskin_batches(
            target_batches, theme, reskinned_dir, args.workers,
            anchor_paths=anchor_paths,
        )

        # If --type-only, load non-targeted types from cache
        if args.type_only:
            other_batches = [b for b in batches if b["tile_type"] != args.type_only]
            for batch_meta in other_batches:
                rp = reskinned_dir / f"{batch_meta['batch_id']}_reskinned.png"
                if rp.exists():
                    reskinned_img = Image.open(rp).convert("RGBA")
                    extracted = extract_from_reskinned(reskinned_img, batch_meta)
                    all_reskinned_cells.extend(extracted)

        # Palette snap (replaces normalize_colors_by_type)
        print(f"\n  Snapping colors to master palette...")
        all_reskinned_cells = snap_to_palette(
            all_reskinned_cells, palette_lab, palette_rgb,
        )

        # Harmonize transition tile colors
        if not args.skip_harmonize:
            print(f"\n  Harmonizing transition tile colors...")
            all_reskinned_cells = harmonize_transitions(
                all_reskinned_cells, atlas_path,
            )

        # Copy base frame art to all animation frames to prevent flickering
        print(f"\n  Copying base frames to animation frames...")
        all_reskinned_cells = copy_base_frames_to_anim_frames(
            all_reskinned_cells, atlas_path,
        )

        print(f"\n  Reassembling atlas ({len(all_reskinned_cells)} cells)...")
        output_path = (
            Path(__file__).parent.parent
            / "public" / "reskin" / args.theme / f"{args.atlas}.png"
        )
        reassemble_atlas(atlas_path, all_reskinned_cells, output_path)

        # Update manifest
        _update_manifest(args, output_path)

        if args.stage == "2":
            print(f"\nStage 2 complete. Atlas reassembled at {output_path}")
            print("Start dev server and playtest.")
            return

    print(f"\nDone! Reskinned {args.atlas} with {args.theme} theme.")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
