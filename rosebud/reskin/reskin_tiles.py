#!/usr/bin/env python3
"""Compatibility wrapper for the tile reskin pipeline.

The implementation now lives in ``rosebud.reskin.tile_pipeline``.
This module preserves the historical script entrypoint and test-facing exports.
"""

from __future__ import annotations

import os
import sys

CURRENT_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.join(CURRENT_DIR, '..', '..')
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from rosebud.reskin import tile_pipeline as _tile_pipeline
from rosebud.reskin.tile_pipeline import *  # noqa: F401,F403

for _name in dir(_tile_pipeline):
    if _name.startswith('__'):
        continue
    globals().setdefault(_name, getattr(_tile_pipeline, _name))

for _dynamic_name in ('_anim_cell_map', '_anim_frame_set'):
    globals().pop(_dynamic_name, None)


def __getattr__(name: str):
    if hasattr(_tile_pipeline, name):
        return getattr(_tile_pipeline, name)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


if __name__ == '__main__':
    main()
