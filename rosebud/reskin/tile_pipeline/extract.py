from __future__ import annotations

from pathlib import Path

from PIL import Image

import urllib.request

from .catalog import (
    CDN_BASE,
    TILE_SIZE,
    classify_cell,
    compute_anim_frame_set,
    get_anim_cell_info,
    is_animation_frame,
)

def download_atlas(atlas_name: str, work_dir: Path) -> Path:
    """Download the original atlas from CDN."""
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

def extract_cells(atlas_path: Path, work_dir: Path) -> list[dict]:
    """Split atlas into individual cells, skipping fully transparent ones."""
    global _anim_frame_set, _anim_cell_map
    img = Image.open(atlas_path).convert("RGBA")
    w, h = img.size
    rows = h // TILE_SIZE

    # Compute animation frame set from actual atlas data
    _anim_frame_set = compute_anim_frame_set(img)
    # Also build the animation cell map for metadata tagging
    _build_anim_cell_map_conservative()

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

            cell_type = classify_cell(col, row)
            if cell_type is None:
                raise ValueError(
                    f"Cell (col={col}, row={row}) is occupied but has no type mapping in TILE_CELL_MAP. "
                    f"Update TILE_CELL_MAP to include this cell."
                )

            # Tag animation metadata
            anim_info = get_anim_cell_info(col, row)
            anim_name = anim_info[0] if anim_info else None
            anim_frame_idx = anim_info[1] if anim_info else None
            anim_cell_idx = anim_info[2] if anim_info else None

            cells.append({
                "id": cell_id,
                "row": row,
                "col": col,
                "x": x,
                "y": y,
                "path": str(cell_path),
                "type": cell_type,
                "is_anim_frame": is_animation_frame(col, row),
                "anim_name": anim_name,
                "anim_frame_idx": anim_frame_idx,
                "anim_cell_idx": anim_cell_idx,
            })

    anim_count = sum(1 for c in cells if c["is_anim_frame"])
    print(f"  Extracted {len(cells)} non-empty cells from {rows} rows x {ATLAS_COLS} cols")
    print(f"  {anim_count} cells are animation frames (excluded from AI batching)")

    from collections import Counter
    type_counts = Counter(c["type"] for c in cells)
    for t in sorted(type_counts.keys()):
        print(f"    {t}: {type_counts[t]} cells")

    return cells

