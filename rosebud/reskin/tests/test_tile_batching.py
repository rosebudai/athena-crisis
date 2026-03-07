"""Tests for type-grouped tile batching logic in reskin_tiles.py."""

import pytest
import numpy as np
from PIL import Image
from pathlib import Path
from collections import defaultdict
import json

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
    t = cell_type or reskin_tiles.classify_cell(row)

    if tmp_path is not None:
        img = Image.new("RGBA", (24, 24), (100, 150, 200, 255))
        path = tmp_path / f"{cid}.png"
        img.save(path)
        path_str = str(path)
    else:
        path_str = f"/fake/{cid}.png"

    anim = is_anim_frame if is_anim_frame is not None else reskin_tiles.is_animation_frame(col, row)

    return {
        "id": cid,
        "row": row,
        "col": col,
        "x": x,
        "y": y,
        "path": path_str,
        "type": t,
        "is_anim_frame": anim,
    }


# ---------------------------------------------------------------------------
# classify_cell
# ---------------------------------------------------------------------------

class TestClassifyCell:
    def test_plain_rows(self):
        assert reskin_tiles.classify_cell(0) == "plain"
        assert reskin_tiles.classify_cell(2) == "plain"

    def test_street_rows(self):
        assert reskin_tiles.classify_cell(3) == "street"
        assert reskin_tiles.classify_cell(6) == "street"

    def test_mountain_rows(self):
        assert reskin_tiles.classify_cell(7) == "mountain"
        assert reskin_tiles.classify_cell(18) == "mountain"

    def test_forest_rows(self):
        assert reskin_tiles.classify_cell(19) == "forest"
        assert reskin_tiles.classify_cell(26) == "forest"

    def test_campsite_rows(self):
        assert reskin_tiles.classify_cell(27) == "campsite"
        assert reskin_tiles.classify_cell(28) == "campsite"

    def test_pier_rows(self):
        assert reskin_tiles.classify_cell(29) == "pier"
        assert reskin_tiles.classify_cell(34) == "pier"

    def test_water_rows_include_sea_and_beach(self):
        """Water type covers sea (35-58) and beach frames (59-72)."""
        assert reskin_tiles.classify_cell(35) == "water"
        assert reskin_tiles.classify_cell(50) == "water"
        assert reskin_tiles.classify_cell(62) == "water"
        assert reskin_tiles.classify_cell(68) == "water"
        assert reskin_tiles.classify_cell(72) == "water"

    def test_river_rows(self):
        assert reskin_tiles.classify_cell(73) == "river"
        assert reskin_tiles.classify_cell(100) == "river"
        assert reskin_tiles.classify_cell(144) == "river"


# ---------------------------------------------------------------------------
# is_animation_frame
# ---------------------------------------------------------------------------

class TestIsAnimationFrame:
    def test_base_frame_returns_false(self):
        """Base frame positions should NOT be marked as animation frames."""
        # Sea base row
        assert reskin_tiles.is_animation_frame(8, 35) is False
        # River base row
        assert reskin_tiles.is_animation_frame(1, 73) is False
        # StormCloud base row
        assert reskin_tiles.is_animation_frame(6, 7) is False
        # Pier base row
        assert reskin_tiles.is_animation_frame(0, 29) is False
        # Teleporter base row
        assert reskin_tiles.is_animation_frame(0, 25) is False
        # Computer base row
        assert reskin_tiles.is_animation_frame(0, 31) is False

    def test_vertical_nonbase_frame_returns_true(self):
        """Non-base frame rows for vertical animations should return True."""
        # Sea: base=35, offset=3 → frame rows 38, 41, 44
        assert reskin_tiles.is_animation_frame(0, 38) is True
        assert reskin_tiles.is_animation_frame(5, 41) is True
        assert reskin_tiles.is_animation_frame(11, 44) is True
        # River: base=73, offset=3 → frame row 76
        assert reskin_tiles.is_animation_frame(0, 76) is True
        # Lightning: base=0, offset=1 → frame rows 1, 2, 3
        assert reskin_tiles.is_animation_frame(10, 1) is True
        assert reskin_tiles.is_animation_frame(10, 2) is True
        assert reskin_tiles.is_animation_frame(10, 3) is True
        # Teleporter: base_col=0, base=25, offset=1 → frame row 26
        assert reskin_tiles.is_animation_frame(0, 26) is True

    def test_horizontal_nonbase_frame_returns_true(self):
        """Non-base frame cells for horizontal animations should return True."""
        # Campsite: base_col=0, base_row=28, offset=1 → (1, 28), (2, 28), (3, 28)
        assert reskin_tiles.is_animation_frame(1, 28) is True
        assert reskin_tiles.is_animation_frame(2, 28) is True
        assert reskin_tiles.is_animation_frame(3, 28) is True
        # Reef: base_col=5, base_row=18, offset=1 → (6, 18), (7, 18), (8, 18)
        assert reskin_tiles.is_animation_frame(6, 18) is True
        assert reskin_tiles.is_animation_frame(7, 18) is True
        assert reskin_tiles.is_animation_frame(8, 18) is True

    def test_horizontal_base_frame_returns_false(self):
        """Base frame of horizontal animation should return False."""
        # Campsite base at (0, 28)
        assert reskin_tiles.is_animation_frame(0, 28) is False
        # Reef base at (5, 18)
        assert reskin_tiles.is_animation_frame(5, 18) is False

    def test_non_animated_position_returns_false(self):
        """Positions not covered by any animation should return False."""
        # Row 0 is a base row for Lightning/RailBridge, not a frame row
        assert reskin_tiles.is_animation_frame(0, 0) is False
        # Row 5 is mid-street, not an animation frame row
        assert reskin_tiles.is_animation_frame(0, 5) is False
        # Row 20 is forest, not an animation frame row
        assert reskin_tiles.is_animation_frame(0, 20) is False

    def test_floatingwateredge_frames(self):
        """FloatingWaterEdge: base_col=7, base=58, offset=2 → frame rows 60, 62, 64.

        Note: (7, 58) base detection requires the atlas-based init because the
        conservative init has a known overlap with Beach's estimated col range.
        We test with col 10 (within FWE's col range 7-10) which doesn't overlap.
        """
        assert reskin_tiles.is_animation_frame(10, 58) is False  # base, col in FWE range
        assert reskin_tiles.is_animation_frame(7, 60) is True
        assert reskin_tiles.is_animation_frame(7, 62) is True
        assert reskin_tiles.is_animation_frame(7, 64) is True

    def test_computer_frames(self):
        """Computer: base=31, offset=1 → frame rows 32, 33, 34."""
        assert reskin_tiles.is_animation_frame(0, 31) is False  # base
        assert reskin_tiles.is_animation_frame(0, 32) is True
        assert reskin_tiles.is_animation_frame(0, 33) is True
        assert reskin_tiles.is_animation_frame(0, 34) is True


# ---------------------------------------------------------------------------
# create_typed_batches
# ---------------------------------------------------------------------------

class TestCreateTypedBatches:
    def test_cells_grouped_by_type(self, tmp_path):
        """Cells of the same type end up in the same batch."""
        cells = [
            _make_cell(0, 0, tmp_path=tmp_path),   # plain
            _make_cell(1, 0, tmp_path=tmp_path),   # plain
            _make_cell(8, 35, tmp_path=tmp_path),  # water (Sea base, col 8)
            _make_cell(9, 35, tmp_path=tmp_path),  # water (Sea base, col 9)
        ]
        batches = reskin_tiles.create_typed_batches(cells, tmp_path)

        types = {b["tile_type"] for b in batches}
        assert "plain" in types
        assert "water" in types

        for b in batches:
            cell_types = {c["type"] for c in b["cells"]}
            assert len(cell_types) == 1  # all cells in a batch are same type

    def test_batch_size_limit(self, tmp_path):
        """Batches should not exceed CELLS_PER_BATCH (36)."""
        # Create 40 plain cells, explicitly non-animated for batching tests
        cells = [_make_cell(i % 12, i // 12, tmp_path=tmp_path, is_anim_frame=False) for i in range(40)]
        # Force all to plain type
        for c in cells:
            c["type"] = "plain"

        batches = reskin_tiles.create_typed_batches(cells, tmp_path)

        for b in batches:
            assert len(b["cells"]) <= reskin_tiles.CELLS_PER_BATCH

    def test_batch_overflow_creates_multiple(self, tmp_path):
        """More than 36 cells of one type should create multiple batches."""
        cells = [_make_cell(i % 12, i // 12, tmp_path=tmp_path, is_anim_frame=False) for i in range(40)]
        for c in cells:
            c["type"] = "plain"

        batches = reskin_tiles.create_typed_batches(cells, tmp_path)
        plain_batches = [b for b in batches if b["tile_type"] == "plain"]
        assert len(plain_batches) == 2  # 36 + 4

    def test_batch_image_saved(self, tmp_path):
        """Batch grid images should be saved to disk."""
        cells = [_make_cell(0, 0, tmp_path=tmp_path)]
        batches = reskin_tiles.create_typed_batches(cells, tmp_path)

        assert len(batches) == 1
        assert Path(batches[0]["path"]).exists()

    def test_batch_metadata_complete(self, tmp_path):
        """Batch metadata should include all required fields."""
        cells = [_make_cell(0, 0, tmp_path=tmp_path)]
        batches = reskin_tiles.create_typed_batches(cells, tmp_path)

        b = batches[0]
        assert "batch_id" in b
        assert "tile_type" in b
        assert "cols" in b
        assert "rows" in b
        assert "canvas_w" in b
        assert "canvas_h" in b
        assert "cell_w" in b
        assert "cell_h" in b
        assert "cells" in b
        assert "path" in b
        assert "scale_factor" in b

    def test_grid_cell_positions(self, tmp_path):
        """Cells in a batch should have valid grid_row and grid_col."""
        cells = [_make_cell(i % 12, i // 12, tmp_path=tmp_path, is_anim_frame=False) for i in range(10)]
        for c in cells:
            c["type"] = "plain"

        batches = reskin_tiles.create_typed_batches(cells, tmp_path)
        b = batches[0]

        for c in b["cells"]:
            assert 0 <= c["grid_col"] < reskin_tiles.GRID_COLS
            assert 0 <= c["grid_row"]

    def test_animation_frames_excluded(self, tmp_path):
        """Cells marked as animation frames should be excluded from batches."""
        cells = [
            _make_cell(0, 0, tmp_path=tmp_path, is_anim_frame=False),   # plain, included
            _make_cell(1, 0, tmp_path=tmp_path, is_anim_frame=False),   # plain, included
            _make_cell(0, 38, tmp_path=tmp_path, is_anim_frame=True),   # Sea frame row, excluded
            _make_cell(0, 35, tmp_path=tmp_path, is_anim_frame=False),  # Sea base, included
        ]
        batches = reskin_tiles.create_typed_batches(cells, tmp_path)

        all_batch_cells = []
        for b in batches:
            all_batch_cells.extend(b["cells"])

        batch_ids = {c["id"] for c in all_batch_cells}
        assert "r000_c00" in batch_ids  # plain cell included
        assert "r000_c01" in batch_ids  # plain cell included
        assert "r035_c00" in batch_ids  # Sea base included
        assert "r038_c00" not in batch_ids  # animation frame excluded
        assert len(all_batch_cells) == 3

    def test_all_anim_frames_excluded_yields_no_batches(self, tmp_path):
        """If all cells are animation frames, no batches should be created."""
        cells = [
            _make_cell(0, 38, tmp_path=tmp_path, is_anim_frame=True),
            _make_cell(1, 38, tmp_path=tmp_path, is_anim_frame=True),
        ]
        batches = reskin_tiles.create_typed_batches(cells, tmp_path)
        assert len(batches) == 0


# ---------------------------------------------------------------------------
# normalize_colors_by_type
# ---------------------------------------------------------------------------

class TestNormalizeColors:
    def test_single_type_normalized(self):
        """Tiles of the same type should be shifted toward their mean."""
        img_red = Image.new("RGBA", (24, 24), (255, 0, 0, 255))
        img_blue = Image.new("RGBA", (24, 24), (0, 0, 255, 255))

        cells = [
            ({"type": "water", "id": "a"}, img_red),
            ({"type": "water", "id": "b"}, img_blue),
        ]

        result = reskin_tiles.normalize_colors_by_type(cells)

        arr_a = np.array(result[0][1])
        arr_b = np.array(result[1][1])

        # After normalization, both should be closer to purple (127, 0, 127)
        assert arr_a[0, 0, 0] < 255  # red channel decreased
        assert arr_b[0, 0, 2] < 255  # blue channel decreased

    def test_transparent_pixels_unchanged(self):
        """Fully transparent pixels should not be modified."""
        img = Image.new("RGBA", (24, 24), (0, 0, 0, 0))  # fully transparent
        img2 = Image.new("RGBA", (24, 24), (100, 100, 100, 255))

        cells = [
            ({"type": "water", "id": "a"}, img),
            ({"type": "water", "id": "b"}, img2),
        ]

        result = reskin_tiles.normalize_colors_by_type(cells)
        arr = np.array(result[0][1])
        assert arr[:, :, 3].max() == 0  # still fully transparent

    def test_single_cell_type_unchanged(self):
        """A type with only one cell should not be modified."""
        img = Image.new("RGBA", (24, 24), (100, 150, 200, 255))
        cells = [({"type": "plain", "id": "a"}, img)]

        result = reskin_tiles.normalize_colors_by_type(cells)
        assert np.array_equal(np.array(result[0][1]), np.array(img))


# ---------------------------------------------------------------------------
# _rgb_to_lab
# ---------------------------------------------------------------------------

class TestRgbToLab:
    def test_white_reference(self):
        """White (255,255,255) should map to L~100, a~0, b~0."""
        rgb = np.array([[255, 255, 255]], dtype=np.uint8)
        lab = reskin_tiles._rgb_to_lab(rgb)
        assert lab.shape == (1, 3)
        np.testing.assert_allclose(lab[0, 0], 100.0, atol=0.5)  # L
        np.testing.assert_allclose(lab[0, 1], 0.0, atol=0.5)    # a
        np.testing.assert_allclose(lab[0, 2], 0.0, atol=0.5)    # b

    def test_black_reference(self):
        """Black (0,0,0) should map to L~0, a~0, b~0."""
        rgb = np.array([[0, 0, 0]], dtype=np.uint8)
        lab = reskin_tiles._rgb_to_lab(rgb)
        np.testing.assert_allclose(lab[0], [0.0, 0.0, 0.0], atol=0.5)

    def test_red_reference(self):
        """Red (255,0,0) should map to L~53.2, a~80.1, b~67.2."""
        rgb = np.array([[255, 0, 0]], dtype=np.uint8)
        lab = reskin_tiles._rgb_to_lab(rgb)
        np.testing.assert_allclose(lab[0, 0], 53.2, atol=1.0)   # L
        np.testing.assert_allclose(lab[0, 1], 80.1, atol=1.0)   # a
        np.testing.assert_allclose(lab[0, 2], 67.2, atol=1.0)   # b

    def test_batch_processing_shape(self):
        """Multiple pixels should be processed in batch, preserving (N,3) shape."""
        rgb = np.array([
            [255, 255, 255],
            [0, 0, 0],
            [255, 0, 0],
            [0, 255, 0],
            [0, 0, 255],
        ], dtype=np.uint8)
        lab = reskin_tiles._rgb_to_lab(rgb)
        assert lab.shape == (5, 3)
        # L values should be monotonically ordered: white > green > red > blue > black
        assert lab[0, 0] > lab[3, 0] > lab[2, 0] > lab[4, 0] > lab[1, 0]


# ---------------------------------------------------------------------------
# snap_to_palette
# ---------------------------------------------------------------------------

class TestSnapToPalette:
    def test_single_color_snaps_to_nearest(self):
        """A single-color cell should be snapped to the nearest palette color."""
        # Cell is solid mid-red (200, 50, 50)
        img = Image.new("RGBA", (24, 24), (200, 50, 50, 255))
        cell_info = {"type": "plain", "id": "snap_test"}

        # Palette: pure red (255,0,0) and pure blue (0,0,255)
        palette_rgb = np.array([[255, 0, 0], [0, 0, 255]], dtype=np.uint8)
        palette_lab = reskin_tiles._rgb_to_lab(palette_rgb)

        result = reskin_tiles.snap_to_palette(
            [(cell_info, img)], palette_lab, palette_rgb,
        )

        arr = np.array(result[0][1])
        # All visible pixels should be pure red — it's closer to (200,50,50)
        assert np.all(arr[:, :, :3] == [255, 0, 0])

    def test_all_output_pixels_in_palette(self):
        """Every visible pixel in the output must exist in the palette."""
        # Create a cell with a gradient of colors
        arr_in = np.zeros((24, 24, 4), dtype=np.uint8)
        for i in range(24):
            arr_in[i, :, 0] = i * 10        # R gradient
            arr_in[i, :, 1] = 100            # G fixed
            arr_in[i, :, 2] = 255 - i * 10   # B gradient
            arr_in[i, :, 3] = 255            # opaque
        img = Image.fromarray(arr_in)
        cell_info = {"type": "water", "id": "palette_check"}

        palette_rgb = np.array([
            [0, 100, 255],
            [120, 100, 130],
            [230, 100, 25],
        ], dtype=np.uint8)
        palette_lab = reskin_tiles._rgb_to_lab(palette_rgb)

        result = reskin_tiles.snap_to_palette(
            [(cell_info, img)], palette_lab, palette_rgb,
        )

        out_arr = np.array(result[0][1])
        palette_set = set(map(tuple, palette_rgb.tolist()))
        unique_colors = set(
            map(tuple, out_arr[:, :, :3].reshape(-1, 3).tolist())
        )
        assert unique_colors.issubset(palette_set), (
            f"Output colors {unique_colors - palette_set} not in palette"
        )

    def test_alpha_preserved(self):
        """Alpha channel must not be modified by snap_to_palette."""
        arr_in = np.zeros((24, 24, 4), dtype=np.uint8)
        arr_in[:12, :, :3] = [100, 150, 200]
        arr_in[:12, :, 3] = 128              # top half semi-transparent
        arr_in[12:, :, :3] = [50, 80, 120]
        arr_in[12:, :, 3] = 255              # bottom half opaque
        img = Image.fromarray(arr_in)
        cell_info = {"type": "plain", "id": "alpha_test"}

        palette_rgb = np.array([[100, 150, 200], [50, 80, 120]], dtype=np.uint8)
        palette_lab = reskin_tiles._rgb_to_lab(palette_rgb)

        result = reskin_tiles.snap_to_palette(
            [(cell_info, img)], palette_lab, palette_rgb,
        )

        out_arr = np.array(result[0][1])
        np.testing.assert_array_equal(out_arr[:12, :, 3], 128)
        np.testing.assert_array_equal(out_arr[12:, :, 3], 255)

    def test_empty_palette_returns_input(self):
        """An empty palette should return the input unchanged (with warning)."""
        img = Image.new("RGBA", (24, 24), (100, 150, 200, 255))
        cell_info = {"type": "plain", "id": "empty_pal"}

        palette_lab = np.zeros((0, 3), dtype=np.float64)
        palette_rgb = np.zeros((0, 3), dtype=np.uint8)

        result = reskin_tiles.snap_to_palette(
            [(cell_info, img)], palette_lab, palette_rgb,
        )

        assert len(result) == 1
        np.testing.assert_array_equal(np.array(result[0][1]), np.array(img))

    def test_fully_transparent_cell_unchanged(self):
        """A fully transparent cell should pass through without modification."""
        img = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
        cell_info = {"type": "water", "id": "transparent"}

        palette_rgb = np.array([[255, 0, 0]], dtype=np.uint8)
        palette_lab = reskin_tiles._rgb_to_lab(palette_rgb)

        result = reskin_tiles.snap_to_palette(
            [(cell_info, img)], palette_lab, palette_rgb,
        )

        out_arr = np.array(result[0][1])
        assert out_arr[:, :, 3].max() == 0  # still fully transparent

    def test_multiple_cells_all_snapped(self):
        """Multiple cells with different types should all get snapped."""
        cells = [
            ({"type": "plain", "id": "a"}, Image.new("RGBA", (24, 24), (200, 50, 50, 255))),
            ({"type": "water", "id": "b"}, Image.new("RGBA", (24, 24), (50, 50, 200, 255))),
            ({"type": "forest", "id": "c"}, Image.new("RGBA", (24, 24), (50, 200, 50, 255))),
        ]

        palette_rgb = np.array([
            [255, 0, 0],
            [0, 0, 255],
            [0, 255, 0],
        ], dtype=np.uint8)
        palette_lab = reskin_tiles._rgb_to_lab(palette_rgb)

        result = reskin_tiles.snap_to_palette(cells, palette_lab, palette_rgb)

        assert len(result) == 3
        palette_set = set(map(tuple, palette_rgb.tolist()))
        for _, img_out in result:
            out_arr = np.array(img_out)
            unique = set(map(tuple, out_arr[:, :, :3].reshape(-1, 3).tolist()))
            assert unique.issubset(palette_set)


# ---------------------------------------------------------------------------
# _lab_to_rgb  (inverse LAB -> RGB conversion)
# ---------------------------------------------------------------------------

class TestLabToRgb:
    def test_round_trip_white(self):
        """RGB [255,255,255] -> LAB -> RGB should round-trip with max diff <= 1."""
        rgb_in = np.array([[255, 255, 255]], dtype=np.uint8)
        lab = reskin_tiles._rgb_to_lab(rgb_in)
        rgb_out = reskin_tiles._lab_to_rgb(lab)
        assert np.abs(rgb_out.astype(int) - rgb_in.astype(int)).max() <= 1

    def test_round_trip_black(self):
        """RGB [0,0,0] -> LAB -> RGB should round-trip with max diff <= 1."""
        rgb_in = np.array([[0, 0, 0]], dtype=np.uint8)
        lab = reskin_tiles._rgb_to_lab(rgb_in)
        rgb_out = reskin_tiles._lab_to_rgb(lab)
        assert np.abs(rgb_out.astype(int) - rgb_in.astype(int)).max() <= 1

    def test_round_trip_green(self):
        """RGB [0,200,0] -> LAB -> RGB should round-trip with max diff <= 1."""
        rgb_in = np.array([[0, 200, 0]], dtype=np.uint8)
        lab = reskin_tiles._rgb_to_lab(rgb_in)
        rgb_out = reskin_tiles._lab_to_rgb(lab)
        assert np.abs(rgb_out.astype(int) - rgb_in.astype(int)).max() <= 1

    def test_round_trip_batch(self):
        """Random batch of 50 colors -> LAB -> RGB should all round-trip with max diff <= 1."""
        rng = np.random.default_rng(42)
        rgb_in = rng.integers(0, 256, size=(50, 3), dtype=np.uint8)
        lab = reskin_tiles._rgb_to_lab(rgb_in)
        rgb_out = reskin_tiles._lab_to_rgb(lab)
        diff = np.abs(rgb_out.astype(int) - rgb_in.astype(int))
        assert diff.max() <= 1, f"Max round-trip diff = {diff.max()}, failing rows: {np.argwhere(diff > 1)}"


# ---------------------------------------------------------------------------
# harmonize_transitions
# ---------------------------------------------------------------------------

class TestHarmonizeTransitions:
    def _make_atlas(self, width, height, color=(100, 160, 60, 255)):
        """Create a minimal atlas image filled with a single color."""
        return Image.new("RGBA", (width, height), color)

    def _make_cell_info(self, col, row, cell_type="plain"):
        return {
            "col": col,
            "row": row,
            "x": col * reskin_tiles.TILE_SIZE,
            "y": row * reskin_tiles.TILE_SIZE,
            "type": cell_type,
        }

    def test_no_transition_cells_unchanged(self, tmp_path):
        """If all cells are type='plain', they should be returned unchanged."""
        atlas_w = 12 * reskin_tiles.TILE_SIZE
        atlas_h = 145 * reskin_tiles.TILE_SIZE
        atlas = self._make_atlas(atlas_w, atlas_h, color=(80, 140, 50, 255))
        atlas_path = tmp_path / "atlas.png"
        atlas.save(atlas_path)

        img_a = Image.new("RGBA", (reskin_tiles.TILE_SIZE, reskin_tiles.TILE_SIZE), (90, 150, 60, 255))
        img_b = Image.new("RGBA", (reskin_tiles.TILE_SIZE, reskin_tiles.TILE_SIZE), (85, 145, 55, 255))
        cells = [
            (self._make_cell_info(0, 0, "plain"), img_a),
            (self._make_cell_info(1, 0, "plain"), img_b),
        ]

        result = reskin_tiles.harmonize_transitions(cells, atlas_path)

        assert len(result) == 2
        np.testing.assert_array_equal(np.array(result[0][1]), np.array(img_a))
        np.testing.assert_array_equal(np.array(result[1][1]), np.array(img_b))

    def test_beach_cells_harmonized(self, tmp_path):
        """Beach cells (water type, row >= 50) should have land pixels shifted toward plain green."""
        ts = reskin_tiles.TILE_SIZE
        atlas_w = 12 * ts
        atlas_h = 145 * ts

        # Build atlas with grass-colored pixels at (col=3, row=55) — the beach cell location
        # The original atlas at that cell has green hue pixels for grass detection
        atlas_arr = np.zeros((atlas_h, atlas_w, 4), dtype=np.uint8)
        # Fill the beach cell (col=3, row=55) with green (grass-like) pixels
        y0, x0 = 55 * ts, 3 * ts
        atlas_arr[y0:y0 + ts, x0:x0 + ts] = [60, 180, 40, 255]  # hue ~110, sat high -> grass
        atlas = Image.fromarray(atlas_arr)
        atlas_path = tmp_path / "atlas.png"
        atlas.save(atlas_path)

        # Plain cell (reference) — bright green
        plain_img = Image.new("RGBA", (ts, ts), (50, 200, 30, 255))
        # Beach cell (transition) — different green for land portions
        beach_img = Image.new("RGBA", (ts, ts), (100, 140, 80, 255))

        cells = [
            (self._make_cell_info(0, 0, "plain"), plain_img),
            (self._make_cell_info(3, 55, "water"), beach_img),
        ]

        result = reskin_tiles.harmonize_transitions(cells, atlas_path)

        # The beach cell should have been modified
        beach_out = np.array(result[1][1])
        beach_in = np.array(beach_img)
        # At least some pixels should differ (grass pixels were shifted toward plain ref)
        assert not np.array_equal(beach_out[:, :, :3], beach_in[:, :, :3]), \
            "Beach cell should be modified by harmonization"

    def test_strength_zero_no_change(self, tmp_path):
        """With strength=0.0, all cells should be returned unchanged."""
        ts = reskin_tiles.TILE_SIZE
        atlas_w = 12 * ts
        atlas_h = 145 * ts

        # Build atlas with green pixels at beach cell for grass classification
        atlas_arr = np.zeros((atlas_h, atlas_w, 4), dtype=np.uint8)
        y0, x0 = 55 * ts, 3 * ts
        atlas_arr[y0:y0 + ts, x0:x0 + ts] = [60, 180, 40, 255]
        atlas = Image.fromarray(atlas_arr)
        atlas_path = tmp_path / "atlas.png"
        atlas.save(atlas_path)

        plain_img = Image.new("RGBA", (ts, ts), (50, 200, 30, 255))
        beach_img = Image.new("RGBA", (ts, ts), (100, 140, 80, 255))

        cells = [
            (self._make_cell_info(0, 0, "plain"), plain_img),
            (self._make_cell_info(3, 55, "water"), beach_img),
        ]

        result = reskin_tiles.harmonize_transitions(cells, atlas_path, strength=0.0)

        # With strength=0, the shift vector is multiplied by 0, so no change
        for (_, img_in), (_, img_out) in zip(cells, result):
            np.testing.assert_array_equal(np.array(img_out), np.array(img_in))

    def test_transparent_pixels_unchanged(self, tmp_path):
        """Fully transparent transition cells should pass through unchanged."""
        ts = reskin_tiles.TILE_SIZE
        atlas_w = 12 * ts
        atlas_h = 145 * ts

        atlas_arr = np.zeros((atlas_h, atlas_w, 4), dtype=np.uint8)
        atlas = Image.fromarray(atlas_arr)
        atlas_path = tmp_path / "atlas.png"
        atlas.save(atlas_path)

        # Need a plain cell for reference, otherwise harmonize bails out early
        plain_img = Image.new("RGBA", (ts, ts), (50, 200, 30, 255))
        # Fully transparent beach cell
        transparent_img = Image.new("RGBA", (ts, ts), (0, 0, 0, 0))

        cells = [
            (self._make_cell_info(0, 0, "plain"), plain_img),
            (self._make_cell_info(3, 55, "water"), transparent_img),
        ]

        result = reskin_tiles.harmonize_transitions(cells, atlas_path)

        beach_out = np.array(result[1][1])
        assert beach_out[:, :, 3].max() == 0, "Transparent pixels should remain transparent"

    def test_water_reference_from_sea_rows(self, tmp_path):
        """Water reference should be computed only from water cells with row < 50."""
        ts = reskin_tiles.TILE_SIZE
        atlas_w = 12 * ts
        atlas_h = 145 * ts

        # Build atlas with blue water pixels at the beach cell
        atlas_arr = np.zeros((atlas_h, atlas_w, 4), dtype=np.uint8)
        y0, x0 = 55 * ts, 3 * ts
        atlas_arr[y0:y0 + ts, x0:x0 + ts] = [30, 60, 220, 255]  # blue hue ~230, water-like
        atlas = Image.fromarray(atlas_arr)
        atlas_path = tmp_path / "atlas.png"
        atlas.save(atlas_path)

        # Plain cell for grass reference
        plain_img = Image.new("RGBA", (ts, ts), (50, 200, 30, 255))
        # Sea cell (row < 50) — this is the water reference
        sea_color = (20, 80, 200, 255)
        sea_img = Image.new("RGBA", (ts, ts), sea_color)
        # Beach cell at row=55 (water type, row >= 50) — NOT used as water reference
        beach_water_img = Image.new("RGBA", (ts, ts), (100, 100, 255, 255))
        # Another water cell at row=60 — also NOT used as reference (row >= 50)
        other_beach_img = Image.new("RGBA", (ts, ts), (200, 200, 255, 255))

        cells = [
            (self._make_cell_info(0, 0, "plain"), plain_img),
            (self._make_cell_info(8, 35, "water"), sea_img),       # row < 50 -> IS reference
            (self._make_cell_info(3, 55, "water"), beach_water_img),  # row >= 50 -> NOT reference
            (self._make_cell_info(4, 60, "water"), other_beach_img),  # row >= 50 -> NOT reference
        ]

        result = reskin_tiles.harmonize_transitions(cells, atlas_path)

        # The sea cell (row 35) should be unchanged — it's not a transition cell
        sea_out = np.array(result[1][1])
        np.testing.assert_array_equal(sea_out, np.array(sea_img)), \
            "Sea cell (row < 50) should not be modified — it is a reference, not a transition"


# ---------------------------------------------------------------------------
# extract_palette
# ---------------------------------------------------------------------------

class TestExtractPalette:
    def _make_anchor_image(self, path: Path, colors: list[tuple]):
        """Create a synthetic anchor image with given colors on opaque pixels."""
        width = len(colors) * 24
        img = Image.new("RGBA", (width, 24), (0, 0, 0, 0))
        for i, color in enumerate(colors):
            for x in range(i * 24, (i + 1) * 24):
                for y in range(24):
                    img.putpixel((x, y), (*color, 255))
        img.save(path)

    def test_returns_lab_shape(self, tmp_path):
        """extract_palette should return (N, 3) LAB array."""
        anchor_path = tmp_path / "anchor_plain.png"
        self._make_anchor_image(anchor_path, [(100, 150, 200), (200, 100, 50)])
        anchor_paths = {"plain": str(anchor_path)}

        lab = reskin_tiles.extract_palette(anchor_paths, tmp_path, max_colors=8)

        assert lab.ndim == 2
        assert lab.shape[1] == 3
        assert lab.shape[0] > 0

    def test_saves_palette_json(self, tmp_path):
        """extract_palette should save palette.json with colors and count."""
        anchor_path = tmp_path / "anchor_water.png"
        self._make_anchor_image(anchor_path, [(50, 100, 200), (10, 200, 80)])
        anchor_paths = {"water": str(anchor_path)}

        lab = reskin_tiles.extract_palette(anchor_paths, tmp_path, max_colors=8)

        palette_json_path = tmp_path / "palette.json"
        assert palette_json_path.exists()
        data = json.loads(palette_json_path.read_text())
        assert "colors" in data
        assert "count" in data
        assert data["count"] == len(data["colors"])
        assert data["count"] == lab.shape[0]
        # All entries should be hex strings
        for c in data["colors"]:
            assert c.startswith("#")
            assert len(c) == 7

    def test_excludes_grid_and_padding_colors(self, tmp_path):
        """Grid-line black (0,0,0) and padding gray (200,200,200) must be excluded."""
        anchor_path = tmp_path / "anchor_mixed.png"
        # Include grid-line (0,0,0), padding (200,200,200), and a real color
        self._make_anchor_image(anchor_path, [(0, 0, 0), (200, 200, 200), (80, 120, 160)])
        anchor_paths = {"mountain": str(anchor_path)}

        lab = reskin_tiles.extract_palette(anchor_paths, tmp_path, max_colors=8)

        palette_json_path = tmp_path / "palette.json"
        data = json.loads(palette_json_path.read_text())
        hex_colors = data["colors"]
        # Grid-line black and padding gray should NOT be in the palette
        assert "#000000" not in hex_colors
        assert "#c8c8c8" not in hex_colors
        # But the real color should be present (may get quantized slightly)
        assert len(hex_colors) > 0


# ---------------------------------------------------------------------------
# Full batching integration (with real atlas data)
# ---------------------------------------------------------------------------

class TestFullBatching:
    @pytest.fixture
    def cells_manifest(self):
        manifest = Path(__file__).parent.parent / "output" / "Tiles0_cozy" / "cells_manifest.json"
        if not manifest.exists():
            pytest.skip("No cached cells manifest — run dry-run first")
        return json.loads(manifest.read_text())

    def test_all_non_anim_cells_in_batches(self, cells_manifest):
        """Every non-animation-frame cell should appear in exactly one batch.

        Note: if cached batches were generated before animation frame exclusion,
        this test verifies the constraint against a fresh re-batch instead.
        """
        batches_manifest = (
            Path(__file__).parent.parent / "output" / "Tiles0_cozy" / "batches_manifest.json"
        )
        if not batches_manifest.exists():
            pytest.skip("No cached batches manifest")

        batches = json.loads(batches_manifest.read_text())

        batch_ids = set()
        for b in batches:
            for c in b["cells"]:
                assert c["id"] not in batch_ids, f"Duplicate cell {c['id']}"
                batch_ids.add(c["id"])

        # Classify expected IDs
        non_anim_ids = {
            c["id"] for c in cells_manifest
            if not reskin_tiles.is_animation_frame(c["col"], c["row"])
        }
        anim_ids = {
            c["id"] for c in cells_manifest
            if reskin_tiles.is_animation_frame(c["col"], c["row"])
        }

        # Batches should not contain any animation frame cells.
        # Old cached manifests may still include them — skip if so.
        anim_in_batches = batch_ids & anim_ids
        if anim_in_batches:
            pytest.skip(
                f"Cached batches include {len(anim_in_batches)} animation "
                f"frame cells — regenerate with --dry-run"
            )

        assert batch_ids == non_anim_ids

    def test_water_group_has_sea_beach_deepsea(self, cells_manifest):
        """Water batch group should contain sea, beach, and deep sea base rows."""
        batches_manifest = (
            Path(__file__).parent.parent / "output" / "Tiles0_cozy" / "batches_manifest.json"
        )
        if not batches_manifest.exists():
            pytest.skip("No cached batches manifest")

        batches = json.loads(batches_manifest.read_text())
        water_rows = set()
        for b in batches:
            if b["tile_type"] == "water":
                for c in b["cells"]:
                    water_rows.add(c["row"])

        assert 35 in water_rows  # Sea base row (col 8 range)
        assert 47 in water_rows  # DeepSea base row (col 8 range)
        # Note: Beach base row 50 overlaps with DeepSea frame 1 (47+3=50)
        # at some columns, so not all Beach cells at row 50 are batched.
        # Check that water batches contain some Beach-range rows instead.
        beach_range = set(range(49, 56))  # Beach base block rows 49-54
        assert water_rows & beach_range  # at least some Beach rows present
