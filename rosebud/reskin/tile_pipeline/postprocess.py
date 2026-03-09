from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

from .anchors import _extract_plain_tile_from_anchor
from .catalog import ATLAS_COLS, CELL_PADDING, GRID_LINE_WIDTH, TILE_SIZE

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


def _rgb_to_hsv_arrays(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert RGB uint8 array (H,W,3) to hue (0-360), saturation (0-1), value (0-1) arrays.

    Parameters
    ----------
    rgb : np.ndarray of shape (H, W, 3), dtype uint8

    Returns
    -------
    hue : np.ndarray (H, W) float64, degrees 0-360
    sat : np.ndarray (H, W) float64, 0-1
    val : np.ndarray (H, W) float64, 0-1
    """
    rgb_f = rgb.astype(np.float64) / 255.0

    cmax = rgb_f.max(axis=2)
    cmin = rgb_f.min(axis=2)
    delta = cmax - cmin

    hue = np.zeros_like(cmax)
    r, g, b = rgb_f[:, :, 0], rgb_f[:, :, 1], rgb_f[:, :, 2]

    mask_r = (cmax == r) & (delta > 0)
    mask_g = (cmax == g) & (delta > 0) & ~mask_r
    mask_b = (delta > 0) & ~mask_r & ~mask_g

    hue[mask_r] = 60.0 * (((g[mask_r] - b[mask_r]) / delta[mask_r]) % 6.0)
    hue[mask_g] = 60.0 * ((b[mask_g] - r[mask_g]) / delta[mask_g] + 2.0)
    hue[mask_b] = 60.0 * ((r[mask_b] - g[mask_b]) / delta[mask_b] + 4.0)

    with np.errstate(invalid="ignore", divide="ignore"):
        sat = np.where(cmax > 0, delta / cmax, 0.0)

    return hue, sat, cmax


def _shift_masked_pixels(arr: np.ndarray, mask: np.ndarray, ref_lab: np.ndarray, strength: float) -> bool:
    """Shift pixels identified by mask toward ref_lab in LAB space.

    Extracts RGB pixels from *arr* at positions where *mask* is True,
    converts to LAB, blends toward *ref_lab* by *strength*, converts
    back, and writes the result into *arr* in-place.

    Parameters
    ----------
    arr : np.ndarray (H, W, 4) uint8 — the RGBA image array (modified in-place)
    mask : np.ndarray (H, W) bool — which pixels to shift
    ref_lab : np.ndarray (3,) — target LAB color to shift toward
    strength : float in [0, 1] — 0 = no change, 1 = full shift

    Returns
    -------
    bool : True if any pixels were modified
    """
    if not mask.any():
        return False
    px_rgb = arr[:, :, :3][mask].astype(np.float64)
    px_lab = _rgb_to_lab(px_rgb)
    shift = (ref_lab[np.newaxis, :] - px_lab) * strength
    shifted_lab = px_lab + shift
    shifted_rgb = _lab_to_rgb(shifted_lab)
    arr[:, :, :3][mask] = shifted_rgb
    return True


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



def composite_feature_backgrounds(
    cells: list[dict],
    anchor_paths: dict[str, str],
    original_atlas_path: Path,
) -> int:
    """Replace grass-like background pixels in feature tiles with the reskinned plain tile.

    For each extracted cell that is NOT type ``plain`` and NOT type ``water``,
    identify background pixels by comparing the original cell to the original
    plain tile using HSV hue classification (grass-like: hue 60-160 deg,
    saturation > 0.20).  Replace those pixels in the cell PNG with the
    corresponding pixels from the reskinned plain tile.

    Operates in-place on cell PNG files in the ``cells/`` directory.

    Parameters
    ----------
    cells : list of cell info dicts (from extract_cells / manifest)
    anchor_paths : dict mapping terrain type -> anchor image path
    original_atlas_path : path to the original (un-reskinned) atlas PNG

    Returns
    -------
    int : number of cells composited
    """
    if "plain" not in anchor_paths:
        print("[composite] WARNING: No plain anchor found, skipping compositing")
        return 0

    # Extract the 24x24 reskinned plain tile from the anchor grid
    reskinned_plain = _extract_plain_tile_from_anchor(anchor_paths["plain"])
    reskinned_plain_arr = np.array(reskinned_plain)  # (24, 24, 4)

    # Load the original atlas to get original plain tile pixels
    original_atlas = Image.open(original_atlas_path).convert("RGBA")

    # Types to skip — plain (is the source) and water (has its own harmonization)
    skip_types = {"plain", "water"}

    composited_count = 0

    for cell_info in cells:
        ctype = cell_info.get("type", "")
        if ctype in skip_types:
            continue
        if cell_info.get("is_anim_frame"):
            continue

        # Load current cell image
        cell_path = cell_info["path"]
        cell_img = Image.open(cell_path).convert("RGBA")
        cell_arr = np.array(cell_img)  # (H, W, 4)

        # Get the original cell from the atlas for HSV classification
        x = cell_info["x"]
        y = cell_info["y"]
        orig_cell = original_atlas.crop((x, y, x + TILE_SIZE, y + TILE_SIZE))
        orig_arr = np.array(orig_cell)

        # Only consider visible pixels in the original cell
        visible = orig_arr[:, :, 3] > 0
        if not visible.any():
            continue

        # Classify original pixels using HSV
        hue, sat, _ = _rgb_to_hsv_arrays(orig_arr[:, :, :3])

        # Grass-like mask: visible, hue 60-160, sat > 0.20
        grass_mask = visible & (hue >= 60) & (hue <= 160) & (sat > 0.20)

        if not grass_mask.any():
            continue

        # Also require the reskinned plain tile pixel to be visible at that position
        plain_visible = reskinned_plain_arr[:, :, 3] > 0
        replace_mask = grass_mask & plain_visible

        if not replace_mask.any():
            continue

        # Replace grass-like pixels with reskinned plain tile pixels
        cell_arr[replace_mask] = reskinned_plain_arr[replace_mask]

        # Save the composited cell back to the same path
        composited_img = Image.fromarray(cell_arr)
        composited_img.save(cell_path)
        composited_count += 1

    print(f"[composite] Composited {composited_count} feature tile backgrounds")
    return composited_count




def harmonize_transitions(
    reskinned_cells: list[tuple[dict, Image.Image]],
    original_atlas_path: Path,
    strength: float = 0.6,
    water_strength: float = 0.4,
) -> list[tuple[dict, Image.Image]]:
    """Shift transition-tile pixel colors toward reference terrain colors.

    Transition tiles (beach, riverbank, sea edges) contain pixels from two
    terrain types (e.g. grass + water).  Because they are batched by their
    primary type, the AI reskins the secondary-type portions with slightly
    different tones than actual plain/water tiles.  This function detects
    grass-like and water-like pixels in each transition cell using the
    *original* atlas and shifts the corresponding reskinned pixels toward
    the mean color of real plain / water cells.

    Non-transition water cells (deep sea, shallow sea) also have their
    water-hue pixels shifted toward the water reference, but at a lower
    strength (``water_strength``) since they need less correction.

    Parameters
    ----------
    reskinned_cells : list of (cell_info, Image) tuples
    original_atlas_path : path to the original (un-reskinned) atlas PNG
    strength : blending strength in [0, 1] for transition cells;
        0 = no change, 1 = full shift
    water_strength : blending strength in [0, 1] for non-transition water
        cells; only water-hue pixels are shifted.  Default 0.4.

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
    water_harmonized_count = 0

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

        # Non-transition, non-water cells are passed through unchanged
        is_water_cell = ctype == "water"
        if not is_transition and not is_water_cell:
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
        hue, sat, _ = _rgb_to_hsv_arrays(orig_arr[:, :, :3])

        modified = False

        if is_transition:
            # Transition cells: shift both grass-like and water-like pixels
            grass_mask = visible & (hue >= 60) & (hue <= 160) & (sat > 0.20)
            water_mask = visible & (hue >= 180) & (hue <= 260) & (sat > 0.20)

            # Shift grass-like pixels
            if grass_ref_lab is not None and grass_mask.any():
                modified |= _shift_masked_pixels(
                    reskinned_arr, grass_mask, grass_ref_lab, strength)

            # Shift water-like pixels
            if water_ref_lab is not None and water_mask.any():
                modified |= _shift_masked_pixels(
                    reskinned_arr, water_mask, water_ref_lab, strength)

            if modified:
                harmonized_count += 1
        else:
            # Non-transition water cells: only shift water-hue pixels
            water_mask = visible & (hue >= 180) & (hue <= 260) & (sat > 0.20)

            if water_ref_lab is not None and water_mask.any():
                modified |= _shift_masked_pixels(
                    reskinned_arr, water_mask, water_ref_lab, water_strength)

            if modified:
                water_harmonized_count += 1

        result.append((cell_info, Image.fromarray(reskinned_arr)))

    print(f"  Harmonized {harmonized_count} transition cells (strength={strength})")
    if water_harmonized_count:
        print(f"  Harmonized {water_harmonized_count} non-transition water cells (water_strength={water_strength})")
    return result


def reskin_batch_gemini(
    batch_path: str,
    theme: dict,
    batch_id: str,
    tile_type: str,
    anchor_paths: list[str] | None = None,
    cells: list[dict] | None = None,
    style_sheet_path: str | None = None,
    is_animation_batch: bool = False,
) -> Image.Image | None:
    """Send a batch grid to Gemini Flash for reskinning.

    When *is_animation_batch* is True, uses ``ANIM_BATCH_PROMPT_TEMPLATE``.

    When *anchor_paths* contains one path, uses the two-image
    ``BATCH_PROMPT_TEMPLATE`` (anchor + batch).  When it contains multiple
    paths (e.g. type anchor + plain anchor for transition tiles), uses the
    ``MULTI_ANCHOR_BATCH_PROMPT_TEMPLATE`` with all anchors then the batch.
    When ``None`` or empty, falls back to the single-image
    ``ANCHOR_PROMPT_TEMPLATE``.

    When *cells* is provided, a per-cell legend is built from
    ``TILE_DESCRIPTIONS`` and injected into the prompt so the model knows
    what each tile in the grid depicts.

    When *style_sheet_path* is provided, the style reference sheet image is
    prepended as the first image in the ``contents`` list and a matching
    instruction is added to the prompt for global coherence.
    """
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    type_hint = TILE_TYPE_HINTS.get(tile_type, "")

    # Build cell legend from TILE_DESCRIPTIONS when cells are available.
    cell_legend = ""
    if cells:
        cell_legend = build_cell_legend(cells, tile_type)

    # Build style sheet instruction and image part
    style_sheet_instruction = ""
    style_sheet_part = None
    if style_sheet_path:
        style_sheet_instruction = (
            "The first image is a world style reference showing all terrain "
            "types in this theme. Your output must visually belong in this "
            "world — match the overall color temperature, shading style, "
            "and level of detail. "
        )
        sheet_data = open(style_sheet_path, "rb").read()
        style_sheet_part = types.Part.from_bytes(
            data=sheet_data, mime_type="image/png",
        )

    if is_animation_batch:
        # Animation batch: use ANIM_BATCH_PROMPT_TEMPLATE
        prompt = ANIM_BATCH_PROMPT_TEMPLATE.format(
            cell_legend=cell_legend,
            style_sheet_instruction=style_sheet_instruction,
        )

        contents: list = [prompt]
        if style_sheet_part is not None:
            contents.append(style_sheet_part)
        for ap in anchor_paths or []:
            data = open(ap, "rb").read()
            contents.append(types.Part.from_bytes(data=data, mime_type="image/png"))
        batch_data = open(batch_path, "rb").read()
        contents.append(types.Part.from_bytes(data=batch_data, mime_type="image/png"))
    elif anchor_paths and len(anchor_paths) > 1:
        # Multi-anchor prompt: type anchor + plain anchor + batch to reskin
        prompt = MULTI_ANCHOR_BATCH_PROMPT_TEMPLATE.format(
            type_name=tile_type, type_hint=type_hint,
            theme_prompt=theme.get("prompt", ""),
            cell_legend=cell_legend,
            style_sheet_instruction=style_sheet_instruction,
        )

        contents: list = [prompt]
        if style_sheet_part is not None:
            contents.append(style_sheet_part)
        for ap in anchor_paths:
            data = open(ap, "rb").read()
            contents.append(types.Part.from_bytes(data=data, mime_type="image/png"))
        batch_data = open(batch_path, "rb").read()
        contents.append(types.Part.from_bytes(data=batch_data, mime_type="image/png"))
    elif anchor_paths and len(anchor_paths) == 1:
        # Two-image prompt: anchor tile + batch to reskin
        prompt = BATCH_PROMPT_TEMPLATE.format(
            type_name=tile_type, type_hint=type_hint,
            theme_prompt=theme.get("prompt", ""),
            cell_legend=cell_legend,
            style_sheet_instruction=style_sheet_instruction,
        )

        contents = [prompt]
        if style_sheet_part is not None:
            contents.append(style_sheet_part)
        anchor_data = open(anchor_paths[0], "rb").read()
        anchor_part = types.Part.from_bytes(data=anchor_data, mime_type="image/png")
        batch_data = open(batch_path, "rb").read()
        batch_part = types.Part.from_bytes(data=batch_data, mime_type="image/png")
        contents.extend([anchor_part, batch_part])
    else:
        # Single-image prompt (backward compat fallback)
        prompt = ANCHOR_PROMPT_TEMPLATE.format(
            type_name=tile_type, type_hint=type_hint,
            theme_prompt=theme.get("prompt", ""),
            style_sheet_instruction=style_sheet_instruction,
        )

        contents = [prompt]
        if style_sheet_part is not None:
            contents.append(style_sheet_part)
        img_data = open(batch_path, "rb").read()
        image_part = types.Part.from_bytes(data=img_data, mime_type="image/png")
        contents.append(image_part)

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
    """Extract individual reskinned cells from the AI output grid.

    Uses proportional coordinate scaling to map expected grid positions
    to the AI output resolution (which may differ from the input).
    """
    scale_factor = batch_meta["scale_factor"]
    cell_w = batch_meta["cell_w"]
    cell_h = batch_meta["cell_h"]
    canvas_w = batch_meta["canvas_w"]
    canvas_h = batch_meta["canvas_h"]

    img_w, img_h = reskinned_img.size
    x_ratio = img_w / (canvas_w * scale_factor)
    y_ratio = img_h / (canvas_h * scale_factor)

    results: list[tuple[dict, Image.Image]] = []
    for cell_info in batch_meta["cells"]:
        row = cell_info["grid_row"]
        col = cell_info["grid_col"]

        # Compute expected native positions then scale
        cx = GRID_LINE_WIDTH + col * (cell_w + GRID_LINE_WIDTH)
        cy = GRID_LINE_WIDTH + row * (cell_h + GRID_LINE_WIDTH)
        tile_x = cx + CELL_PADDING
        tile_y = cy + CELL_PADDING

        # Scale to AI output coords
        sx = tile_x * scale_factor * x_ratio
        sy = tile_y * scale_factor * y_ratio
        sw = TILE_SIZE * scale_factor * x_ratio
        sh = TILE_SIZE * scale_factor * y_ratio

        tile_crop = reskinned_img.crop((
            int(round(sx)),
            int(round(sy)),
            int(round(sx + sw)),
            int(round(sy + sh)),
        ))
        tile_crop = tile_crop.resize((TILE_SIZE, TILE_SIZE), Image.NEAREST)

        # Alpha from original cell, RGB from AI output
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
