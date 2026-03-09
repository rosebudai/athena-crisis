from __future__ import annotations

from . import catalog as _catalog
from .assemble import reassemble_atlas, update_reskin_manifest
from .anchors import _extract_plain_tile_from_anchor, generate_anchors, generate_style_reference_sheet
from .batching import _partition_cells_for_batching, build_animation_batches, create_typed_batches
from .catalog import *
from .cli import build_parser, config_from_args, main
from .debug import _draw_outlined_text, generate_debug_atlas
from .extract import download_atlas, extract_cells
from .models import AnchorSet, AnimationMetadata, ReskinnedCell, RunArtifacts, RunConfig, TileBatch, TileCell
from .pipeline import assemble_stage, anchor_stage, batch_stage, debug_stage, extract_stage, load_env_and_theme, prepare_run, reskin_stage, run_pipeline
from .postprocess import _alpha_similarity, _lab_to_rgb, _rgb_to_hsv_arrays, _rgb_to_lab, _shift_masked_pixels, composite_feature_backgrounds, copy_base_frames_to_anim_frames, extract_from_reskinned, harmonize_transitions, normalize_colors_by_type
from .prompts import *
from .provider import _reskin_batches, reskin_batch_gemini, reskin_batches


def __getattr__(name: str):
    if hasattr(_catalog, name):
        return getattr(_catalog, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
