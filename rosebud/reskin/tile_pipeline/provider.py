from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from PIL import Image

from .catalog import ANCHOR_INHERITANCE
from .postprocess import extract_from_reskinned
from .prompts import (
    ANCHOR_PROMPT_TEMPLATE,
    ANIM_BATCH_PROMPT_TEMPLATE,
    BATCH_PROMPT_TEMPLATE,
    MULTI_ANCHOR_BATCH_PROMPT_TEMPLATE,
    PREVIEW_ANIM_BATCH_PROMPT_TEMPLATE,
    TILE_TYPE_HINTS,
    build_cell_legend,
)

MODEL_NAME = "gemini-3.1-flash-image-preview"
PROMPT_TEMPLATE_VERSION = "minimal-cache-v1"

TRANSITION_REFERENCE_BUNDLES: dict[str, list[str]] = {
    "water": ["water", "plain", "river"],
    "river": ["river", "water", "plain"],
    "pier": ["pier", "water", "plain"],
    "floatingedge": ["water", "plain", "river", "pier"],
    "reef": ["water", "plain"],
    "sea_object": ["water", "plain"],
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: str | Path | None) -> str | None:
    if path is None:
        return None
    return _sha256_bytes(Path(path).read_bytes())


def _resolve_anchor_paths(
    tile_type: str,
    anchor_paths: dict[str, str] | None,
) -> list[str]:
    if not anchor_paths:
        return []

    def _append(anchor_key: str, resolved: list[str]) -> None:
        path = anchor_paths.get(anchor_key)
        if path and path not in resolved:
            resolved.append(path)

    if tile_type in TRANSITION_REFERENCE_BUNDLES:
        resolved: list[str] = []
        for anchor_key in TRANSITION_REFERENCE_BUNDLES[tile_type]:
            _append(anchor_key, resolved)
        return resolved

    batch_anchor_paths: list[str] = []
    type_anchor_key = ANCHOR_INHERITANCE.get(tile_type, tile_type)
    _append(type_anchor_key, batch_anchor_paths)
    if not batch_anchor_paths:
        return batch_anchor_paths

    if type_anchor_key in ("street", "plain", "rail", "mountain", "forest", "campsite"):
        _append("plain", batch_anchor_paths)

    return batch_anchor_paths


def _build_batch_cache_context(
    batch_meta: dict[str, Any],
    theme: dict[str, Any],
    batch_anchor_paths: list[str],
    style_sheet_path: str | None,
) -> dict[str, Any]:
    prompt_bundle_hash = _sha256_bytes(
        json.dumps(
            ({
                "anchor": ANCHOR_PROMPT_TEMPLATE,
                "anim": ANIM_BATCH_PROMPT_TEMPLATE,
                "batch": BATCH_PROMPT_TEMPLATE,
                "multi": MULTI_ANCHOR_BATCH_PROMPT_TEMPLATE,
            } | (
                {"preview_anim": PREVIEW_ANIM_BATCH_PROMPT_TEMPLATE}
                if batch_meta.get("preview_path")
                else {}
            )),
            sort_keys=True,
        ).encode("utf-8")
    )
    resolved_anchor_hashes = [
        _sha256_file(path)
        for path in batch_anchor_paths
    ]

    context = {
        "model_name": MODEL_NAME,
        "prompt_template_version": PROMPT_TEMPLATE_VERSION,
        "prompt_bundle_hash": prompt_bundle_hash,
        "theme_name": theme.get("name"),
        "theme_prompt": theme.get("prompt", ""),
        "tile_type": batch_meta["tile_type"],
        "batch_family": batch_meta.get("batch_family", batch_meta["tile_type"]),
        "layout_strategy": batch_meta.get("layout_strategy"),
        "is_animation_batch": batch_meta.get("is_animation_batch", False),
        "animation_name": batch_meta.get("anim_name"),
        "batch_image_sha256": _sha256_file(batch_meta["path"]),
        "preview_image_sha256": _sha256_file(batch_meta.get("preview_path")),
        "cell_ids": [cell["id"] for cell in batch_meta["cells"]],
        "cell_positions": [[cell["col"], cell["row"]] for cell in batch_meta["cells"]],
        "anchor_hashes": resolved_anchor_hashes,
        "style_sheet_sha256": _sha256_file(style_sheet_path),
    }
    return context


def _build_batch_cache_entry(
    batch_meta: dict[str, Any],
    theme: dict[str, Any],
    reskinned_dir: Path,
    anchor_paths: dict[str, str] | None = None,
    style_sheet_path: str | None = None,
) -> dict[str, Any]:
    batch_anchor_paths = _resolve_anchor_paths(batch_meta["tile_type"], anchor_paths)
    context = _build_batch_cache_context(
        batch_meta,
        theme,
        batch_anchor_paths,
        style_sheet_path,
    )
    cache_key = _sha256_bytes(
        json.dumps(context, sort_keys=True).encode("utf-8")
    )

    cache_dir = reskinned_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    identity = _sha256_bytes(
        json.dumps(
            {
                "tile_type": batch_meta["tile_type"],
                "batch_family": batch_meta.get("batch_family", batch_meta["tile_type"]),
                "layout_strategy": batch_meta.get("layout_strategy"),
                "is_animation_batch": batch_meta.get("is_animation_batch", False),
                "animation_name": batch_meta.get("anim_name"),
                "batch_image_sha256": _sha256_file(batch_meta["path"]),
                "preview_image_sha256": _sha256_file(batch_meta.get("preview_path")),
                "cell_ids": [cell["id"] for cell in batch_meta["cells"]],
                "cell_positions": [[cell["col"], cell["row"]] for cell in batch_meta["cells"]],
            },
            sort_keys=True,
        ).encode("utf-8")
    )
    index_dir = cache_dir / "index"
    index_dir.mkdir(parents=True, exist_ok=True)
    return {
        "cache_key": cache_key,
        "identity": identity,
        "context": context,
        "batch_anchor_paths": batch_anchor_paths,
        "image_path": cache_dir / f"{cache_key}.png",
        "meta_path": cache_dir / f"{cache_key}.json",
        "index_path": index_dir / f"{identity}.json",
    }


def _describe_context_changes(
    previous: dict[str, Any],
    current: dict[str, Any],
) -> str:
    changed_fields = [
        key
        for key in sorted(current.keys())
        if previous.get(key) != current.get(key)
    ]
    if not changed_fields:
        return "cache miss (no exact-match entry)"
    return f"cache miss (changed: {', '.join(changed_fields)})"


def load_cached_batch_image(
    batch_meta: dict[str, Any],
    theme: dict[str, Any],
    reskinned_dir: Path,
    anchor_paths: dict[str, str] | None = None,
    style_sheet_path: str | None = None,
    fresh: bool = False,
) -> tuple[dict[str, Any], Image.Image | None, str]:
    entry = _build_batch_cache_entry(
        batch_meta,
        theme,
        reskinned_dir,
        anchor_paths=anchor_paths,
        style_sheet_path=style_sheet_path,
    )
    if fresh:
        return entry, None, "cache bypassed (--fresh)"

    image_path = entry["image_path"]
    meta_path = entry["meta_path"]
    if not image_path.exists() or not meta_path.exists():
        if entry["index_path"].exists():
            try:
                previous_meta = json.loads(entry["index_path"].read_text())
                previous_context = previous_meta.get("context", {})
                return entry, None, _describe_context_changes(previous_context, entry["context"])
            except json.JSONDecodeError:
                return entry, None, "cache miss (invalid diagnostic metadata)"
        return entry, None, "cache miss (no exact-match entry)"

    try:
        saved_meta = json.loads(meta_path.read_text())
    except json.JSONDecodeError:
        return entry, None, "cache miss (invalid metadata)"

    if saved_meta.get("cache_key") != entry["cache_key"]:
        return entry, None, "cache miss (cache key mismatch)"

    return entry, Image.open(image_path).convert("RGBA"), "cache hit (exact visual input match)"


def reskin_batch_gemini(
    batch_path: str,
    theme: dict,
    batch_id: str,
    tile_type: str,
    anchor_paths: list[str] | None = None,
    cells: list[dict] | None = None,
    style_sheet_path: str | None = None,
    is_animation_batch: bool = False,
    preview_path: str | None = None,
) -> Image.Image | None:
    """Send a batch grid to Gemini Flash for reskinning.

    When *preview_path* is provided for an animation batch, uses
    ``PREVIEW_ANIM_BATCH_PROMPT_TEMPLATE`` with preview image context and the
    atlas-target grid last. Otherwise animation batches use
    ``ANIM_BATCH_PROMPT_TEMPLATE``.

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

    if is_animation_batch and preview_path:
        prompt = PREVIEW_ANIM_BATCH_PROMPT_TEMPLATE.format(
            cell_legend=cell_legend,
            style_sheet_instruction=style_sheet_instruction,
        )

        contents: list = [prompt]
        if style_sheet_part is not None:
            contents.append(style_sheet_part)
        for ap in anchor_paths or []:
            data = open(ap, "rb").read()
            contents.append(types.Part.from_bytes(data=data, mime_type="image/png"))
        preview_data = open(preview_path, "rb").read()
        contents.append(types.Part.from_bytes(data=preview_data, mime_type="image/png"))
        batch_data = open(batch_path, "rb").read()
        contents.append(types.Part.from_bytes(data=batch_data, mime_type="image/png"))
    elif is_animation_batch:
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
                model=MODEL_NAME,
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
    fresh: bool = False,
) -> list[tuple[dict, Image.Image]]:
    """Reskin batches using parallel workers."""
    import concurrent.futures
    import threading

    print_lock = threading.Lock()
    all_reskinned: list[tuple[dict, Image.Image]] = []

    def process_batch(batch_meta: dict) -> list[tuple[dict, Image.Image]]:
        batch_id = batch_meta["batch_id"]
        tile_type = batch_meta["tile_type"]
        entry, reskinned_img, cache_message = load_cached_batch_image(
            batch_meta,
            theme,
            reskinned_dir,
            anchor_paths=anchor_paths,
            style_sheet_path=style_sheet_path,
            fresh=fresh,
        )

        if reskinned_img is not None:
            with print_lock:
                print(f"  {batch_id}: {cache_message}")
        else:
            with print_lock:
                print(f"  {batch_id}: {cache_message}")
                print(
                    f"  {batch_id}: Sending to Gemini Flash "
                    f"({len(batch_meta['cells'])} {tile_type} cells)"
                )
            reskinned_img = reskin_batch_gemini(
                batch_meta["path"], theme, batch_id, tile_type,
                anchor_paths=entry["batch_anchor_paths"],
                cells=batch_meta.get("cells"),
                style_sheet_path=style_sheet_path,
                is_animation_batch=batch_meta.get("is_animation_batch", False),
                preview_path=batch_meta.get("preview_path"),
            )
            if reskinned_img is None:
                with print_lock:
                    print(f"  {batch_id}: FAILED — skipping")
                return []
            reskinned_img.save(entry["image_path"])
            entry["meta_path"].write_text(
                json.dumps(
                    {
                        "cache_key": entry["cache_key"],
                        "context": entry["context"],
                    },
                    indent=2,
                ) + "\n"
            )
            entry["index_path"].write_text(
                json.dumps(
                    {
                        "cache_key": entry["cache_key"],
                        "context": entry["context"],
                    },
                    indent=2,
                ) + "\n"
            )

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
