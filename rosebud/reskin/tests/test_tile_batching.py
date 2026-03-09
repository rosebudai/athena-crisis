"""Compatibility tests for the thin `reskin_tiles.py` wrapper."""

from .tile_pipeline_test_support import reskin_tiles


def test_wrapper_keeps_main_entrypoint():
    assert callable(reskin_tiles.main)


def test_wrapper_exposes_legacy_helpers():
    assert callable(reskin_tiles.classify_cell)
    assert callable(reskin_tiles.build_animation_batches)
    assert callable(reskin_tiles._init_anim_frame_set_conservative)


def test_wrapper_proxies_live_animation_globals():
    reskin_tiles._build_anim_cell_map_conservative()
    assert reskin_tiles._anim_cell_map is not None
    assert isinstance(reskin_tiles._anim_cell_map, dict)
