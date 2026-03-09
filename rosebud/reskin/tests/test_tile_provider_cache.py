"""Focused tests for exact-match tile batch caching."""

from pathlib import Path

from PIL import Image

from rosebud.reskin.tile_pipeline import provider
from rosebud.reskin.tile_pipeline.catalog import CELL_PADDING, GRID_LINE_WIDTH, TILE_SIZE


def _make_cell_image(path: Path, color: tuple[int, int, int, int]) -> None:
    Image.new("RGBA", (TILE_SIZE, TILE_SIZE), color).save(path)


def _make_batch_meta(tmp_path: Path, batch_id: str = "batch_000_plain") -> dict:
    cell_path = tmp_path / f"{batch_id}_cell.png"
    _make_cell_image(cell_path, (100, 150, 200, 255))

    cell_w = TILE_SIZE + CELL_PADDING * 2
    cell_h = cell_w
    canvas_w = cell_w + GRID_LINE_WIDTH * 2
    canvas_h = cell_h + GRID_LINE_WIDTH * 2
    native = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 255))
    for y in range(GRID_LINE_WIDTH + CELL_PADDING, GRID_LINE_WIDTH + CELL_PADDING + TILE_SIZE):
        for x in range(GRID_LINE_WIDTH + CELL_PADDING, GRID_LINE_WIDTH + CELL_PADDING + TILE_SIZE):
            native.putpixel((x, y), (10, 20, 30, 255))

    batch_path = tmp_path / f"{batch_id}.png"
    native.resize((canvas_w * 4, canvas_h * 4), Image.NEAREST).save(batch_path)
    return {
        "batch_id": batch_id,
        "tile_type": "plain",
        "path": str(batch_path),
        "cells": [
            {
                "id": f"{batch_id}_cell",
                "row": 0,
                "col": 0,
                "x": 0,
                "y": 0,
                "type": "plain",
                "path": str(cell_path),
                "grid_row": 0,
                "grid_col": 0,
            },
        ],
        "cell_w": cell_w,
        "cell_h": cell_h,
        "canvas_w": canvas_w,
        "canvas_h": canvas_h,
        "scale_factor": 4,
    }


def _make_reference_image(path: Path, color: tuple[int, int, int, int]) -> None:
    Image.new("RGBA", (24, 24), color).save(path)


def test_reskin_batches_reuses_exact_match_cache(tmp_path, monkeypatch):
    theme = {"name": "cozy", "prompt": "cozy autumn"}
    batch_meta = _make_batch_meta(tmp_path)
    reskinned_dir = tmp_path / "reskinned"
    anchor_path = tmp_path / "anchor_plain.png"
    style_sheet_path = tmp_path / "style_reference_sheet.png"
    _make_reference_image(anchor_path, (1, 2, 3, 255))
    _make_reference_image(style_sheet_path, (4, 5, 6, 255))

    calls: list[str] = []

    def fake_reskin(batch_path, *args, **kwargs):
        calls.append(batch_path)
        return Image.open(batch_path).convert("RGBA")

    monkeypatch.setattr(provider, "reskin_batch_gemini", fake_reskin)

    provider.reskin_batches(
        [batch_meta],
        theme,
        reskinned_dir,
        workers=1,
        anchor_paths={"plain": str(anchor_path)},
        style_sheet_path=str(style_sheet_path),
    )
    provider.reskin_batches(
        [batch_meta],
        theme,
        reskinned_dir,
        workers=1,
        anchor_paths={"plain": str(anchor_path)},
        style_sheet_path=str(style_sheet_path),
    )

    assert len(calls) == 1
    cache_files = list((reskinned_dir / "cache").glob("*.png"))
    assert len(cache_files) == 1


def test_reskin_batches_invalidates_cache_when_theme_prompt_changes(tmp_path, monkeypatch):
    batch_meta = _make_batch_meta(tmp_path)
    reskinned_dir = tmp_path / "reskinned"
    calls: list[str] = []

    def fake_reskin(batch_path, *args, **kwargs):
        calls.append(batch_path)
        return Image.open(batch_path).convert("RGBA")

    monkeypatch.setattr(provider, "reskin_batch_gemini", fake_reskin)

    provider.reskin_batches(
        [batch_meta],
        {"name": "cozy", "prompt": "cozy autumn"},
        reskinned_dir,
        workers=1,
    )
    provider.reskin_batches(
        [batch_meta],
        {"name": "cozy", "prompt": "cozy winter"},
        reskinned_dir,
        workers=1,
    )

    assert len(calls) == 2


def test_reskin_batches_invalidates_cache_when_anchor_changes(tmp_path, monkeypatch):
    theme = {"name": "cozy", "prompt": "cozy autumn"}
    batch_meta = _make_batch_meta(tmp_path)
    reskinned_dir = tmp_path / "reskinned"
    anchor_path = tmp_path / "anchor_plain.png"
    _make_reference_image(anchor_path, (1, 2, 3, 255))
    calls: list[str] = []

    def fake_reskin(batch_path, *args, **kwargs):
        calls.append(batch_path)
        return Image.open(batch_path).convert("RGBA")

    monkeypatch.setattr(provider, "reskin_batch_gemini", fake_reskin)

    provider.reskin_batches(
        [batch_meta],
        theme,
        reskinned_dir,
        workers=1,
        anchor_paths={"plain": str(anchor_path)},
    )

    _make_reference_image(anchor_path, (9, 9, 9, 255))

    provider.reskin_batches(
        [batch_meta],
        theme,
        reskinned_dir,
        workers=1,
        anchor_paths={"plain": str(anchor_path)},
    )

    assert len(calls) == 2


def test_reskin_batches_invalidates_cache_when_style_sheet_changes(tmp_path, monkeypatch):
    theme = {"name": "cozy", "prompt": "cozy autumn"}
    batch_meta = _make_batch_meta(tmp_path)
    reskinned_dir = tmp_path / "reskinned"
    style_sheet_path = tmp_path / "style_reference_sheet.png"
    _make_reference_image(style_sheet_path, (4, 5, 6, 255))
    calls: list[str] = []

    def fake_reskin(batch_path, *args, **kwargs):
        calls.append(batch_path)
        return Image.open(batch_path).convert("RGBA")

    monkeypatch.setattr(provider, "reskin_batch_gemini", fake_reskin)

    provider.reskin_batches(
        [batch_meta],
        theme,
        reskinned_dir,
        workers=1,
        style_sheet_path=str(style_sheet_path),
    )

    _make_reference_image(style_sheet_path, (7, 8, 9, 255))

    provider.reskin_batches(
        [batch_meta],
        theme,
        reskinned_dir,
        workers=1,
        style_sheet_path=str(style_sheet_path),
    )

    assert len(calls) == 2


def test_reskin_batches_invalidates_cache_when_model_changes(tmp_path, monkeypatch):
    theme = {"name": "cozy", "prompt": "cozy autumn"}
    batch_meta = _make_batch_meta(tmp_path)
    reskinned_dir = tmp_path / "reskinned"
    calls: list[str] = []

    def fake_reskin(batch_path, *args, **kwargs):
        calls.append(batch_path)
        return Image.open(batch_path).convert("RGBA")

    monkeypatch.setattr(provider, "reskin_batch_gemini", fake_reskin)

    provider.reskin_batches([batch_meta], theme, reskinned_dir, workers=1)
    monkeypatch.setattr(provider, "MODEL_NAME", "gemini-test-model")
    provider.reskin_batches([batch_meta], theme, reskinned_dir, workers=1)

    assert len(calls) == 2


def test_reskin_batches_invalidates_cache_when_prompt_version_changes(tmp_path, monkeypatch):
    theme = {"name": "cozy", "prompt": "cozy autumn"}
    batch_meta = _make_batch_meta(tmp_path)
    reskinned_dir = tmp_path / "reskinned"
    calls: list[str] = []

    def fake_reskin(batch_path, *args, **kwargs):
        calls.append(batch_path)
        return Image.open(batch_path).convert("RGBA")

    monkeypatch.setattr(provider, "reskin_batch_gemini", fake_reskin)

    provider.reskin_batches([batch_meta], theme, reskinned_dir, workers=1)
    monkeypatch.setattr(provider, "PROMPT_TEMPLATE_VERSION", "minimal-cache-v2")
    provider.reskin_batches([batch_meta], theme, reskinned_dir, workers=1)

    assert len(calls) == 2


def test_reskin_batches_fresh_bypasses_cache_reads(tmp_path, monkeypatch):
    theme = {"name": "cozy", "prompt": "cozy autumn"}
    batch_meta = _make_batch_meta(tmp_path)
    reskinned_dir = tmp_path / "reskinned"
    calls: list[str] = []

    def fake_reskin(batch_path, *args, **kwargs):
        calls.append(batch_path)
        return Image.open(batch_path).convert("RGBA")

    monkeypatch.setattr(provider, "reskin_batch_gemini", fake_reskin)

    provider.reskin_batches([batch_meta], theme, reskinned_dir, workers=1)
    provider.reskin_batches([batch_meta], theme, reskinned_dir, workers=1, fresh=True)

    assert len(calls) == 2


def test_load_cached_batch_image_reports_changed_inputs(tmp_path):
    theme = {"name": "cozy", "prompt": "cozy autumn"}
    batch_meta = _make_batch_meta(tmp_path)
    reskinned_dir = tmp_path / "reskinned"

    entry = provider._build_batch_cache_entry(batch_meta, theme, reskinned_dir)
    entry["index_path"].write_text(
        provider.json.dumps(
            {
                "cache_key": "old",
                "context": {
                    **entry["context"],
                    "theme_prompt": "cozy winter",
                    "style_sheet_sha256": "different",
                },
            },
            indent=2,
        ) + "\n"
    )

    _, image, message = provider.load_cached_batch_image(
        batch_meta,
        theme,
        reskinned_dir,
    )

    assert image is None
    assert "theme_prompt" in message
    assert "style_sheet_sha256" in message
