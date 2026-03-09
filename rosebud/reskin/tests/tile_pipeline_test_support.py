"""Shared helpers for focused tile pipeline tests."""

import pytest
import numpy as np
from PIL import Image
from pathlib import Path
from collections import defaultdict
import json
import io
import os
import sys
import types

# Import the module under test
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "reskin_tiles",
    str(Path(__file__).parent.parent / "reskin_tiles.py"),
)
reskin_tiles = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reskin_tiles)

# Initialize animation frame set for tests (no real atlas available)
reskin_tiles._init_anim_frame_set_conservative()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cell(col, row, cell_id=None, cell_type=None, tmp_path=None,
               is_anim_frame=None):
    """Create a minimal cell dict with a real 24x24 PNG."""
    cid = cell_id or f"r{row:03d}_c{col:02d}"
    x, y = col * 24, row * 24
    t = cell_type or reskin_tiles.classify_cell(col, row) or "plain"

    if tmp_path is not None:
        img = Image.new("RGBA", (24, 24), (100, 150, 200, 255))
        path = tmp_path / f"{cid}.png"
        img.save(path)
        path_str = str(path)
    else:
        path_str = f"/fake/{cid}.png"

    anim = is_anim_frame if is_anim_frame is not None else reskin_tiles.is_animation_frame(col, row)

    # Tag animation metadata
    anim_info = reskin_tiles.get_anim_cell_info(col, row)
    anim_name = anim_info[0] if anim_info else None
    anim_frame_idx = anim_info[1] if anim_info else None
    anim_cell_idx = anim_info[2] if anim_info else None

    return {
        "id": cid,
        "row": row,
        "col": col,
        "x": x,
        "y": y,
        "path": path_str,
        "type": t,
        "is_anim_frame": anim,
        "anim_name": anim_name,
        "anim_frame_idx": anim_frame_idx,
        "anim_cell_idx": anim_cell_idx,
    }


__all__ = [
    'Image',
    'Path',
    '_make_cell',
    'defaultdict',
    'io',
    'json',
    'np',
    'os',
    'pytest',
    'reskin_tiles',
    'sys',
    'types',
]
