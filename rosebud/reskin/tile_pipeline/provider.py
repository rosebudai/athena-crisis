from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from PIL import Image

from .catalog import ANCHOR_INHERITANCE
from .postprocess import extract_from_reskinned
from .prompts import (
    ANCHOR_PROMPT_TEMPLATE,
    ANIM_BATCH_PROMPT_TEMPLATE,
    BATCH_PROMPT_TEMPLATE,
    MULTI_ANCHOR_BATCH_PROMPT_TEMPLATE,
    TILE_TYPE_HINTS,
    build_cell_legend,
)

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



def _reskin_batches(
    batches: list[dict],
    theme: dict,
    reskinned_dir: Path,
    workers: int,
    anchor_paths: dict[str, str] | None = None,
    style_sheet_path: str | None = None,
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
                # Use ANCHOR_INHERITANCE to find the right anchor for
                # sub-types that don't generate their own.
                type_anchor_key = ANCHOR_INHERITANCE.get(tile_type, tile_type)
                type_anchor = anchor_paths.get(type_anchor_key)
                if type_anchor:
                    batch_anchor_paths = [type_anchor]
                    # For transition types, include additional anchors so
                    # Gemini can match adjacent-terrain colors exactly.
                    plain_anchor = anchor_paths.get("plain")
                    water_anchor = anchor_paths.get("water")
                    if type_anchor_key in ("water", "river"):
                        # Water/river/reef/sea_object/floatingedge:
                        # add plain anchor for grass in coastlines/banks
                        if plain_anchor and plain_anchor != type_anchor:
                            batch_anchor_paths.append(plain_anchor)
                    elif type_anchor_key == "pier":
                        # Pier: add water anchor + plain anchor (borders touch both)
                        if water_anchor and water_anchor != type_anchor:
                            batch_anchor_paths.append(water_anchor)
                        if plain_anchor and plain_anchor != type_anchor:
                            batch_anchor_paths.append(plain_anchor)
                    elif type_anchor_key in ("street", "plain", "rail"):
                        # Street/trench/bridge/pipe/computer/lightning,
                        # rail, and plain-inheriting types: add plain anchor
                        # for grass context.
                        if plain_anchor and plain_anchor != type_anchor:
                            batch_anchor_paths.append(plain_anchor)
                    elif type_anchor_key in ("mountain", "forest", "campsite"):
                        # Mountain, Forest, Campsite: add plain anchor for grass
                        if plain_anchor and plain_anchor != type_anchor:
                            batch_anchor_paths.append(plain_anchor)
            reskinned_img = reskin_batch_gemini(
                batch_meta["path"], theme, batch_id, tile_type,
                anchor_paths=batch_anchor_paths,
                cells=batch_meta.get("cells"),
                style_sheet_path=style_sheet_path,
                is_animation_batch=batch_meta.get("is_animation_batch", False),
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

reskin_batches = _reskin_batches
