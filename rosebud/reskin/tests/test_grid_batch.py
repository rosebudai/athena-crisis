import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from PIL import Image

from reskin.discovery import AssetInfo
from reskin.transforms.grid_batch import (
    group_into_batches,
    render_grid,
    extract_sprites_from_grid,
    restore_alpha,
    CANVAS_SIZE,
)


def _make_asset(tmp_path, name, width, height, color, category="unit-sprite"):
    """Create a test AssetInfo with a synthetic PNG."""
    img = Image.new("RGBA", (width, height), color)
    path = str(tmp_path / f"{name}.png")
    img.save(path)
    return AssetInfo(
        name=name,
        source_path=path,
        source_url=f"https://example.com/{name}.png",
        category=category,
    )


@pytest.fixture
def four_assets(tmp_path):
    """Create 4 tiny 32x32 AssetInfo objects."""
    colors = [
        (255, 0, 0, 255),
        (0, 255, 0, 255),
        (0, 0, 255, 255),
        (255, 255, 0, 255),
    ]
    return [
        _make_asset(tmp_path, f"sprite_{i}", 32, 32, colors[i])
        for i in range(4)
    ]


def test_group_into_batches(four_assets):
    """All 4 same-sized sprites should land in a single batch."""
    batches = group_into_batches(four_assets)
    assert len(batches) == 1
    assert len(batches[0]["sprites"]) == 4
    assert batches[0]["bucket"] == (64, 64)  # 32 rounded up to 64


def test_group_into_batches_splits_different_sizes(tmp_path):
    """Different-sized sprites should be split into separate buckets."""
    small = _make_asset(tmp_path, "small", 32, 32, (255, 0, 0, 255))
    big = _make_asset(tmp_path, "big", 128, 128, (0, 255, 0, 255))

    batches = group_into_batches([small, big])
    assert len(batches) == 2
    buckets = {b["bucket"] for b in batches}
    assert (64, 64) in buckets
    assert (128, 128) in buckets


def test_group_into_batches_separates_categories(tmp_path):
    unit_asset = _make_asset(
        tmp_path, "unit", 32, 32, (255, 0, 0, 255), category="unit-sprite"
    )
    building_asset = _make_asset(
        tmp_path, "building", 32, 32, (0, 255, 0, 255), category="building"
    )

    batches = group_into_batches([unit_asset, building_asset])

    assert len(batches) == 2
    categories = {batch["category"] for batch in batches}
    assert categories == {"unit-sprite", "building"}


def test_group_into_batches_respects_max_per_batch(tmp_path):
    """More than max_per_batch sprites should be split."""
    assets = [
        _make_asset(tmp_path, f"s_{i}", 32, 32, (i * 10, 100, 100, 255))
        for i in range(20)
    ]
    batches = group_into_batches(assets, max_per_batch=16)
    assert len(batches) == 2
    total = sum(len(b["sprites"]) for b in batches)
    assert total == 20


def test_render_and_extract_roundtrip(four_assets):
    """Build a grid, then extract sprites and verify dimensions match."""
    batches = group_into_batches(four_assets)
    assert len(batches) == 1

    batch = batches[0]
    grid_img, batch_meta = render_grid(batch, "test_batch")

    assert grid_img.size == (CANVAS_SIZE, CANVAS_SIZE)
    assert len(batch_meta["sprites"]) == 4

    # Save grid to a temp file so we can extract from it
    buf = io.BytesIO()
    grid_img.save(buf, format="PNG")
    buf.seek(0)

    # Write to a temp path for extraction
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(buf.getvalue())
        grid_path = f.name

    try:
        extracted = extract_sprites_from_grid(grid_path, batch_meta, CANVAS_SIZE)
        assert len(extracted) == 4

        for sprite_info, sprite_img in extracted:
            assert sprite_img.size == (
                sprite_info["original_w"],
                sprite_info["original_h"],
            )
            assert sprite_img.size == (32, 32)
    finally:
        os.unlink(grid_path)


def test_restore_alpha(tmp_path):
    """RGB from restyled + alpha from original should produce correct result."""
    # Create original with partial transparency
    original = Image.new("RGBA", (16, 16), (100, 50, 50, 128))
    # Make some pixels fully transparent
    pixels = original.load()
    for x in range(8):
        for y in range(16):
            pixels[x, y] = (100, 50, 50, 0)

    original_path = str(tmp_path / "original.png")
    original.save(original_path)

    # Create a "restyled" sprite with different colors and opaque alpha
    restyled = Image.new("RGBA", (16, 16), (200, 100, 50, 255))

    result = restore_alpha(restyled, original_path)

    assert result.size == (16, 16)
    assert result.mode == "RGBA"

    result_pixels = result.load()
    # Left half should be transparent (alpha=0)
    assert result_pixels[0, 0][3] == 0
    assert result_pixels[4, 8][3] == 0
    # Right half should have alpha=128 from original
    assert result_pixels[8, 0][3] == 128
    assert result_pixels[12, 8][3] == 128
    # RGB should come from the restyled image
    assert result_pixels[8, 0][0] == 200
    assert result_pixels[8, 0][1] == 100
    assert result_pixels[8, 0][2] == 50


def test_restore_alpha_resizes_if_needed(tmp_path):
    """restore_alpha should handle size mismatch by resizing."""
    original = Image.new("RGBA", (32, 32), (100, 50, 50, 200))
    original_path = str(tmp_path / "original.png")
    original.save(original_path)

    # Restyled is different size
    restyled = Image.new("RGBA", (64, 64), (200, 100, 50, 255))

    result = restore_alpha(restyled, original_path)
    assert result.size == (32, 32)


def test_batch_meta_uses_name_and_source_path(four_assets):
    """Verify batch_meta sprite entries use 'name' and 'source_path' keys."""
    batches = group_into_batches(four_assets)
    _, batch_meta = render_grid(batches[0], "test_batch")

    for sprite_info in batch_meta["sprites"]:
        assert "name" in sprite_info
        assert "source_path" in sprite_info
        assert "category" in sprite_info
        # Should NOT have Wesnoth-style keys
        assert "relative_path" not in sprite_info
        assert "original_file" not in sprite_info
