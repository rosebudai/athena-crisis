from __future__ import annotations

import math
import shutil
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from .catalog import (
    ANIMATED_TILES,
    BG_COLOR,
    CELL_PADDING,
    CELLS_PER_BATCH,
    GRID_COLS,
    GRID_LINE_WIDTH,
    LINE_COLOR,
    TILE_SIZE,
)

SEA_OBJECT_FRAME_START_COL = 5
SEA_OBJECT_FRAME_COUNT = 4
SEA_OBJECT_ROW_METADATA: dict[int, tuple[str, str, int]] = {
    22: ("sea_object_iceberg_weeds_anim", "Iceberg/Weeds", 0),
    23: ("sea_object_iceberg_weeds_anim", "Iceberg/Weeds", 1),
    24: ("sea_object_island_anim", "Island", 0),
    25: ("sea_object_island_anim", "Island", 1),
    26: ("sea_object_gas_bubbles_anim", "GasBubbles", 0),
    27: ("sea_object_gas_bubbles_anim", "GasBubbles", 1),
}
@dataclass(frozen=True, slots=True)
class BatchFamilyPolicy:
    batch_family: str
    tile_type: str
    layout_strategy: str
    is_animation_batch: bool


BATCH_FAMILY_POLICIES: dict[str, BatchFamilyPolicy] = {
    "sea_object_static": BatchFamilyPolicy(
        batch_family="sea_object_static",
        tile_type="sea_object",
        layout_strategy="packed",
        is_animation_batch=False,
    ),
    "sea_object_island_anim": BatchFamilyPolicy(
        batch_family="sea_object_island_anim",
        tile_type="sea_object",
        layout_strategy="frame_strip",
        is_animation_batch=True,
    ),
    "sea_object_iceberg_weeds_anim": BatchFamilyPolicy(
        batch_family="sea_object_iceberg_weeds_anim",
        tile_type="sea_object",
        layout_strategy="frame_strip",
        is_animation_batch=True,
    ),
    "sea_object_gas_bubbles_anim": BatchFamilyPolicy(
        batch_family="sea_object_gas_bubbles_anim",
        tile_type="sea_object",
        layout_strategy="frame_strip",
        is_animation_batch=True,
    ),
}


def _slugify_batch_family(value: str) -> str:
    return value.lower().replace("/", "_").replace(" ", "_")


def assign_batch_family(cell: dict) -> str:
    """Return the semantic batch family for a cell."""
    tile_type = cell["type"]
    anim_name = cell.get("anim_name")

    if tile_type == "sea_object":
        metadata = SEA_OBJECT_ROW_METADATA.get(cell["row"])
        if metadata is not None:
            return metadata[0]
        return "sea_object_static"

    if anim_name:
        return f"anim_{_slugify_batch_family(anim_name)}"

    return tile_type


def get_batch_family_policy(cell: dict) -> BatchFamilyPolicy:
    """Resolve layout/animation policy for a cell's assigned family."""
    batch_family = cell.get("batch_family") or assign_batch_family(cell)
    policy = BATCH_FAMILY_POLICIES.get(batch_family)
    if policy is not None:
        return policy

    if cell.get("anim_name"):
        return BatchFamilyPolicy(
            batch_family=batch_family,
            tile_type=cell["type"],
            layout_strategy="frame_strip",
            is_animation_batch=True,
        )

    return BatchFamilyPolicy(
        batch_family=batch_family,
        tile_type=cell["type"],
        layout_strategy="packed",
        is_animation_batch=False,
    )


def _annotate_cells_for_batching(cells: list[dict]) -> list[dict]:
    annotated: list[dict] = []
    for cell in cells:
        enriched = dict(cell)
        if enriched["type"] == "sea_object":
            metadata = SEA_OBJECT_ROW_METADATA.get(enriched["row"])
            if metadata is not None:
                batch_family, anim_name, cell_idx = metadata
                frame_idx = enriched["col"] - SEA_OBJECT_FRAME_START_COL
                if 0 <= frame_idx < SEA_OBJECT_FRAME_COUNT:
                    enriched["batch_family"] = batch_family
                    enriched["anim_name"] = anim_name
                    enriched["anim_frame_idx"] = frame_idx
                    enriched["anim_cell_idx"] = cell_idx
                    enriched["layout_strategy"] = "frame_strip"
        policy = get_batch_family_policy(enriched)
        enriched["batch_family"] = policy.batch_family
        enriched["layout_strategy"] = policy.layout_strategy
        annotated.append(enriched)
    return annotated


def _packed_grid_positions(batch_cells: list[dict]) -> tuple[int, int, list[tuple[dict, int, int]]]:
    """Return dense left-to-right packed placements for a batch."""
    n = len(batch_cells)
    cols = min(GRID_COLS, n)
    rows = math.ceil(n / GRID_COLS)
    placements = []
    for idx, cell in enumerate(batch_cells):
        row = idx // GRID_COLS
        col = idx % GRID_COLS
        placements.append((cell, col, row))
    return cols, rows, placements


def _static_grid_positions(batch_cells: list[dict]) -> tuple[int, int, list[tuple[dict, int, int]]]:
    """Preserve atlas-local row/column offsets for a batch."""
    if batch_cells:
        min_col = min(cell["col"] for cell in batch_cells)
        max_col = max(cell["col"] for cell in batch_cells)
        min_row = min(cell["row"] for cell in batch_cells)
        max_row = max(cell["row"] for cell in batch_cells)
        placements = [
            (cell, cell["col"] - min_col, cell["row"] - min_row)
            for cell in sorted(batch_cells, key=lambda c: (c["row"], c["col"]))
        ]
        cols = max_col - min_col + 1
        rows = max_row - min_row + 1
        return cols, rows, placements

    return 0, 0, []


def _grid_positions_for_layout(
    layout_strategy: str,
    batch_cells: list[dict],
) -> tuple[int, int, list[tuple[dict, int, int]]]:
    if layout_strategy == "packed":
        return _packed_grid_positions(batch_cells)
    if layout_strategy == "static_grid":
        return _static_grid_positions(batch_cells)
    raise ValueError(f"Unsupported typed layout strategy: {layout_strategy}")


def _partition_cells_for_batching(
    cells: list[dict],
) -> tuple[list[dict], dict[str, dict[int, list[dict]]], int]:
    """Split cells into static cells and animation cells grouped by frame.

    Animation cells are grouped by ``anim_name`` and ``anim_frame_idx`` and
    sorted by ``anim_cell_idx`` so animation batch rows stay aligned across
    frames, even if some cells are missing from a later frame.
    """
    static_cells: list[dict] = []
    anim_cells: dict[str, dict[int, list[dict]]] = defaultdict(lambda: defaultdict(list))
    excluded = 0

    for cell in _annotate_cells_for_batching(cells):
        policy = get_batch_family_policy(cell)
        if policy.is_animation_batch:
            excluded += 1
            anim_name = cell.get("anim_name")
            frame_idx = cell.get("anim_frame_idx")
            if anim_name is not None and frame_idx is not None:
                anim_cells[anim_name][frame_idx].append(cell)
            continue

        if cell.get("is_anim_frame"):
            excluded += 1
            continue

        static_cells.append(cell)

    for frames in anim_cells.values():
        for frame_cells in frames.values():
            frame_cells.sort(
                key=lambda cell: (
                    cell.get("anim_cell_idx") if cell.get("anim_cell_idx") is not None else float("inf"),
                    cell["row"],
                    cell["col"],
                ),
            )

    return static_cells, anim_cells, excluded



def create_typed_batches(cells: list[dict], work_dir: Path) -> list[dict]:
    """Group cells by terrain type, then batch into 6x6 grids.

    Type batches are driven by explicit semantic ``batch_family`` assignments
    instead of raw ``tile_type`` alone.
    """
    batches_dir = work_dir / "batches"
    batches_dir.mkdir(exist_ok=True)
    # Clean old batch files — only type batch files, preserve anim_ files
    for f in batches_dir.iterdir():
        if not f.name.startswith("anim_"):
            f.unlink()

    # Filter out ALL animation cells (base + non-base) — they go to animation batches
    batchable, _, excluded = _partition_cells_for_batching(cells)
    if excluded:
        print(f"  Excluded {excluded} animation cells from type batching (handled by animation batches)")

    by_family = defaultdict(list)
    for c in batchable:
        by_family[c["batch_family"]].append(c)

    cell_w = TILE_SIZE + CELL_PADDING * 2
    cell_h = TILE_SIZE + CELL_PADDING * 2

    batches = []
    batch_counter = 0

    for batch_family in sorted(by_family.keys()):
        family_cells = by_family[batch_family]
        family_policy = get_batch_family_policy(family_cells[0])
        tile_type = family_policy.tile_type
        layout_strategy = family_policy.layout_strategy

        for chunk_idx in range(0, len(family_cells), CELLS_PER_BATCH):
            batch_cells = family_cells[chunk_idx:chunk_idx + CELLS_PER_BATCH]
            cols, rows, placements = _grid_positions_for_layout(layout_strategy, batch_cells)

            canvas_w = cols * cell_w + (cols + 1) * GRID_LINE_WIDTH
            canvas_h = rows * cell_h + (rows + 1) * GRID_LINE_WIDTH

            canvas = Image.new("RGBA", (canvas_w, canvas_h), LINE_COLOR)
            draw = ImageDraw.Draw(canvas)

            batch_id = f"batch_{batch_counter:03d}_{batch_family}"
            batch_meta = {
                "batch_id": batch_id,
                "tile_type": tile_type,
                "batch_family": batch_family,
                "layout_strategy": layout_strategy,
                "cols": cols,
                "rows": rows,
                "canvas_w": canvas_w,
                "canvas_h": canvas_h,
                "cell_w": cell_w,
                "cell_h": cell_h,
                "cells": [],
            }

            for cell_info, col, row in placements:
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
    type_batch_counts: dict[str, int] = {}
    for b in batches:
        family = b["batch_family"]
        type_batch_counts[family] = type_batch_counts.get(family, 0) + 1
    print(f"  Created {len(batches)} batches grouped by family:")
    for family in sorted(type_batch_counts.keys()):
        print(f"    {family}: {type_batch_counts[family]} batches")

    return batches


def build_animation_batches(cells: list[dict], work_dir: Path) -> list[dict]:
    """Build animation-specific batches with frames laid out as columns.

    For each animation in ANIMATED_TILES, collects all frame cells from the
    cells list and arranges them into a grid where columns = frames and
    rows = cells within one frame.

    Large animations (>6 frames) are sub-batched into groups of 6 frames,
    with frame 0 included as a reference column in each sub-batch.

    Parameters
    ----------
    cells : list[dict]
        All extracted cells (from extract_cells).
    work_dir : Path
        Working directory for saving batch grid images.

    Returns
    -------
    list[dict]
        List of batch metadata dicts with animation-specific fields.
    """
    batches_dir = work_dir / "batches"
    batches_dir.mkdir(exist_ok=True)
    preview_dir = work_dir / "batch_previews"
    if preview_dir.exists():
        shutil.rmtree(preview_dir)
    preview_dir.mkdir(exist_ok=True)

    for stale_path in work_dir.glob("anim_*"):
        if stale_path.is_dir():
            shutil.rmtree(stale_path)
        elif stale_path.exists():
            stale_path.unlink()
    for stale_path in batches_dir.iterdir():
        if not stale_path.name.startswith("anim_"):
            continue
        if stale_path.is_dir():
            shutil.rmtree(stale_path)
        else:
            stale_path.unlink()

    cell_w = TILE_SIZE + CELL_PADDING * 2
    cell_h = TILE_SIZE + CELL_PADDING * 2

    _, anim_cells_by_name, _ = _partition_cells_for_batching(cells)
    batches = []
    MAX_FRAMES_PER_BATCH = 6
    MAX_ROWS_PER_BATCH = 20  # Gemini fails on very tall grids (e.g. Pier at 35 rows)

    for entry in ANIMATED_TILES:
        name, _, _, n_frames, _, _, _ = entry
        frame_map = anim_cells_by_name.get(name)
        if not frame_map:
            continue

        frames = [frame_map.get(i, []) for i in range(n_frames)]

        if not frames or not frames[0]:
            continue

        cells_per_frame = max(
            (
                max(
                    (
                        cell.get("anim_cell_idx")
                        if cell.get("anim_cell_idx") is not None
                        else idx
                    )
                    for idx, cell in enumerate(frame_cells)
                ) + 1
            )
            for frame_cells in frames
            if frame_cells
        )

        # Determine the tile type for anchor routing from base frame cells
        base_types = [c["type"] for c in frames[0]] if frames[0] else []
        tile_type = base_types[0] if base_types else "water"

        # Sub-batch large animations (>6 frames) into groups of MAX_FRAMES_PER_BATCH
        if n_frames > MAX_FRAMES_PER_BATCH:
            # Split into sub-batches: each includes frame 0 as reference + up to
            # (MAX_FRAMES_PER_BATCH - 1) additional frames
            non_base_indices = list(range(1, n_frames))
            sub_batches_indices = []
            for chunk_start in range(0, len(non_base_indices), MAX_FRAMES_PER_BATCH - 1):
                chunk = non_base_indices[chunk_start:chunk_start + MAX_FRAMES_PER_BATCH - 1]
                sub_batches_indices.append([0] + chunk)
        else:
            sub_batches_indices = [list(range(n_frames))]

        # Build row chunks: split tall grids into sub-batches by row
        if cells_per_frame > MAX_ROWS_PER_BATCH:
            row_chunks = []
            for start in range(0, cells_per_frame, MAX_ROWS_PER_BATCH):
                row_chunks.append((start, min(start + MAX_ROWS_PER_BATCH, cells_per_frame)))
        else:
            row_chunks = [(0, cells_per_frame)]

        for sub_idx, frame_indices in enumerate(sub_batches_indices):
            for row_chunk_idx, (row_start, row_end) in enumerate(row_chunks):
                n_cols = len(frame_indices)
                n_rows = row_end - row_start

                canvas_w = n_cols * cell_w + (n_cols + 1) * GRID_LINE_WIDTH
                canvas_h = n_rows * cell_h + (n_rows + 1) * GRID_LINE_WIDTH

                canvas = Image.new("RGBA", (canvas_w, canvas_h), LINE_COLOR)
                draw = ImageDraw.Draw(canvas)

                safe_name = name.replace("/", "_")
                if len(row_chunks) > 1:
                    batch_id = f"anim_{safe_name}_{sub_idx}r{row_chunk_idx}"
                else:
                    batch_id = f"anim_{safe_name}_{sub_idx}"
                batch_cells = []
                first_frame_cells = next((frame_cells for frame_cells in frames if frame_cells), [])
                family_policy = get_batch_family_policy(first_frame_cells[0])

                for grid_col_idx, frame_idx in enumerate(frame_indices):
                    frame_cell_list = frames[frame_idx] if frame_idx < len(frames) else []
                    for local_row in range(n_rows):
                        cx = GRID_LINE_WIDTH + grid_col_idx * (cell_w + GRID_LINE_WIDTH)
                        cy = GRID_LINE_WIDTH + local_row * (cell_h + GRID_LINE_WIDTH)

                        draw.rectangle(
                            [cx, cy, cx + cell_w - 1, cy + cell_h - 1],
                            fill=BG_COLOR,
                        )

                    used_rows: set[int] = set()
                    for fallback_row_idx, cell_info in enumerate(frame_cell_list):
                        global_row = cell_info.get("anim_cell_idx")
                        if global_row is None:
                            global_row = fallback_row_idx

                        # Skip cells outside this row chunk
                        if global_row < row_start or global_row >= row_end:
                            continue

                        local_row = global_row - row_start
                        if local_row in used_rows:
                            continue

                        used_rows.add(local_row)
                        cx = GRID_LINE_WIDTH + grid_col_idx * (cell_w + GRID_LINE_WIDTH)
                        cy = GRID_LINE_WIDTH + local_row * (cell_h + GRID_LINE_WIDTH)

                        tile_img = Image.open(cell_info["path"]).convert("RGBA")
                        paste_x = cx + CELL_PADDING
                        paste_y = cy + CELL_PADDING
                        canvas.paste(tile_img, (paste_x, paste_y), tile_img)

                        include_in_batch_meta = not (
                            frame_idx == 0 and sub_idx > 0 and n_frames > MAX_FRAMES_PER_BATCH
                        )
                        if not include_in_batch_meta:
                            continue

                        batch_cells.append({
                            **cell_info,
                            "grid_row": local_row,
                            "grid_col": grid_col_idx,
                        })

                # Scale up 4x for AI visibility
                scale_factor = 4
                scaled = canvas.resize(
                    (canvas_w * scale_factor, canvas_h * scale_factor),
                    Image.NEAREST,
                )

                batch_path = batches_dir / f"{batch_id}.png"
                scaled.save(batch_path)

                batch_meta = {
                    "batch_id": batch_id,
                    "tile_type": tile_type,
                    "batch_family": family_policy.batch_family,
                    "layout_strategy": family_policy.layout_strategy,
                    "cols": n_cols,
                    "rows": n_rows,
                    "canvas_w": canvas_w,
                    "canvas_h": canvas_h,
                    "cell_w": cell_w,
                    "cell_h": cell_h,
                    "cells": batch_cells,
                    "path": str(batch_path),
                    "scale_factor": scale_factor,
                    "is_animation_batch": True,
                    "anim_name": name,
                    "frame_indices": frame_indices,
                    "cells_per_frame": n_rows,
                }
                batches.append(batch_meta)

    # Summary
    print(f"  Created {len(batches)} animation batches:")
    for b in batches:
        print(f"    {b['anim_name']}: {len(b['frame_indices'])} frames, "
              f"{b['cells_per_frame']} cells/frame")

    return batches
