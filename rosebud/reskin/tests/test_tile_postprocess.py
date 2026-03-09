"""Focused tests extracted from the former monolithic tile pipeline suite."""

from .tile_pipeline_test_support import *

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
# Full batching integration (with real atlas data)
# ---------------------------------------------------------------------------

class TestCompositeFeatureBackgrounds:
    """Tests for the pre-process background compositing (halo fix)."""

    def _make_anchor_image(self, path: Path, color: tuple):
        """Create a synthetic anchor image at 4x scale with the given tile color.

        The anchor is a single-cell grid at 4x scale.  Native layout:
        GRID_LINE_WIDTH border + CELL_PADDING + TILE_SIZE + CELL_PADDING +
        GRID_LINE_WIDTH.  We fill the tile region with *color* and the rest
        with black (grid lines) / gray (padding).
        """
        ts = reskin_tiles.TILE_SIZE  # 24
        pad = reskin_tiles.CELL_PADDING  # 4
        glw = reskin_tiles.GRID_LINE_WIDTH  # 2
        native_w = ts + pad * 2 + glw * 2  # 36
        native_h = native_w

        native_img = Image.new("RGBA", (native_w, native_h), (0, 0, 0, 255))
        # Fill tile region with the desired color
        for y in range(glw + pad, glw + pad + ts):
            for x in range(glw + pad, glw + pad + ts):
                native_img.putpixel((x, y), color)

        # Save at 4x scale
        scaled = native_img.resize((native_w * 4, native_h * 4), Image.NEAREST)
        scaled.save(path)

    def test_plain_cells_unchanged(self, tmp_path):
        """Plain type cells should not be modified by compositing."""
        ts = reskin_tiles.TILE_SIZE
        # Create anchor
        anchor_path = tmp_path / "anchor_plain.png"
        reskinned_color = (80, 200, 60, 255)
        self._make_anchor_image(anchor_path, reskinned_color)

        # Create a minimal atlas with green pixels at (0, 0)
        atlas_arr = np.zeros((3 * ts, 12 * ts, 4), dtype=np.uint8)
        atlas_arr[0:ts, 0:ts] = [80, 180, 50, 255]  # grass-like at plain cell
        atlas = Image.fromarray(atlas_arr)
        atlas_path = tmp_path / "atlas.png"
        atlas.save(atlas_path)

        # Create a plain cell PNG
        plain_color = (100, 160, 70, 255)
        cell_img = Image.new("RGBA", (ts, ts), plain_color)
        cell_path = tmp_path / "r000_c00.png"
        cell_img.save(cell_path)

        cell_info = {
            "id": "r000_c00", "row": 0, "col": 0,
            "x": 0, "y": 0,
            "path": str(cell_path),
            "type": "plain",
            "is_anim_frame": False,
        }

        result = reskin_tiles.composite_feature_backgrounds(
            [cell_info], {"plain": str(anchor_path)}, atlas_path,
        )

        assert result == 0  # nothing composited
        # Verify cell image unchanged
        out_arr = np.array(Image.open(cell_path))
        expected = np.array(cell_img)
        np.testing.assert_array_equal(out_arr, expected)

    def test_forest_cell_background_replaced(self, tmp_path):
        """A forest cell with grass-colored background pixels should have
        those pixels replaced with the reskinned plain tile's pixels."""
        ts = reskin_tiles.TILE_SIZE

        # Reskinned plain anchor — bright cozy green
        anchor_path = tmp_path / "anchor_plain.png"
        reskinned_color = (80, 210, 60, 255)
        self._make_anchor_image(anchor_path, reskinned_color)

        # Original atlas: forest cell at (col=0, row=20) has grass-colored pixels
        atlas_arr = np.zeros((30 * ts, 12 * ts, 4), dtype=np.uint8)
        y0, x0 = 20 * ts, 0
        atlas_arr[y0:y0 + ts, x0:x0 + ts] = [60, 180, 40, 255]  # grass hue ~110
        atlas = Image.fromarray(atlas_arr)
        atlas_path = tmp_path / "atlas.png"
        atlas.save(atlas_path)

        # Forest cell — current (pre-composite) image with different green
        forest_color = (100, 150, 80, 255)
        cell_img = Image.new("RGBA", (ts, ts), forest_color)
        cell_path = tmp_path / "r020_c00.png"
        cell_img.save(cell_path)

        cell_info = {
            "id": "r020_c00", "row": 20, "col": 0,
            "x": 0, "y": 20 * ts,
            "path": str(cell_path),
            "type": "forest",
            "is_anim_frame": False,
        }

        result = reskin_tiles.composite_feature_backgrounds(
            [cell_info], {"plain": str(anchor_path)}, atlas_path,
        )

        assert result == 1  # one cell composited
        # Verify cell image was replaced with reskinned plain tile pixels
        out_arr = np.array(Image.open(cell_path))
        original_arr = np.array(cell_img)
        # The output should differ from the original forest color
        assert not np.array_equal(out_arr[:, :, :3], original_arr[:, :, :3]), \
            "Forest cell pixels should have been replaced by compositing"
        # The replacement color should match the reskinned plain color exactly
        # (NEAREST downscale preserves pixel art values)
        center = ts // 2  # check center pixel to avoid edge artifacts
        np.testing.assert_array_equal(
            out_arr[center, center, :3],
            list(reskinned_color[:3]),
        )

    def test_water_cells_skipped(self, tmp_path):
        """Water type cells should not be composited (they use harmonization)."""
        ts = reskin_tiles.TILE_SIZE

        anchor_path = tmp_path / "anchor_plain.png"
        self._make_anchor_image(anchor_path, (80, 210, 60, 255))

        # Atlas with water-like pixels at (col=0, row=35)
        atlas_arr = np.zeros((40 * ts, 12 * ts, 4), dtype=np.uint8)
        y0, x0 = 35 * ts, 0
        atlas_arr[y0:y0 + ts, x0:x0 + ts] = [30, 80, 200, 255]  # blue water
        atlas = Image.fromarray(atlas_arr)
        atlas_path = tmp_path / "atlas.png"
        atlas.save(atlas_path)

        water_color = (40, 90, 210, 255)
        cell_img = Image.new("RGBA", (ts, ts), water_color)
        cell_path = tmp_path / "r035_c00.png"
        cell_img.save(cell_path)

        cell_info = {
            "id": "r035_c00", "row": 35, "col": 0,
            "x": 0, "y": 35 * ts,
            "path": str(cell_path),
            "type": "water",
            "is_anim_frame": False,
        }

        result = reskin_tiles.composite_feature_backgrounds(
            [cell_info], {"plain": str(anchor_path)}, atlas_path,
        )

        assert result == 0  # water cells skipped
        # Verify cell unchanged
        out_arr = np.array(Image.open(cell_path))
        np.testing.assert_array_equal(out_arr[0, 0], list(water_color))

    def test_transparent_pixels_preserved(self, tmp_path):
        """Transparent pixels in feature tiles should remain transparent
        after compositing."""
        ts = reskin_tiles.TILE_SIZE

        anchor_path = tmp_path / "anchor_plain.png"
        reskinned_color = (80, 210, 60, 255)
        self._make_anchor_image(anchor_path, reskinned_color)

        # Atlas: forest cell at (col=0, row=20) — top half grass, bottom half transparent
        atlas_arr = np.zeros((30 * ts, 12 * ts, 4), dtype=np.uint8)
        y0, x0 = 20 * ts, 0
        atlas_arr[y0:y0 + ts // 2, x0:x0 + ts] = [60, 180, 40, 255]  # top: grass
        # bottom half stays (0,0,0,0) — transparent
        atlas = Image.fromarray(atlas_arr)
        atlas_path = tmp_path / "atlas.png"
        atlas.save(atlas_path)

        # Forest cell: top half has some green, bottom half transparent
        cell_arr = np.zeros((ts, ts, 4), dtype=np.uint8)
        cell_arr[:ts // 2, :] = [100, 150, 80, 255]  # top: opaque green
        cell_arr[ts // 2:, :] = [0, 0, 0, 0]           # bottom: transparent
        cell_img = Image.fromarray(cell_arr)
        cell_path = tmp_path / "r020_c00.png"
        cell_img.save(cell_path)

        cell_info = {
            "id": "r020_c00", "row": 20, "col": 0,
            "x": 0, "y": 20 * ts,
            "path": str(cell_path),
            "type": "forest",
            "is_anim_frame": False,
        }

        reskin_tiles.composite_feature_backgrounds(
            [cell_info], {"plain": str(anchor_path)}, atlas_path,
        )

        out_arr = np.array(Image.open(cell_path))
        # Bottom half should still be transparent
        assert out_arr[ts // 2:, :, 3].max() == 0, \
            "Transparent pixels in bottom half should remain transparent"
        # Top half should have been replaced (grass pixels -> reskinned plain)
        assert out_arr[0, 0, 3] == 255, \
            "Top half opaque pixels should remain opaque"


# ---------------------------------------------------------------------------
# Extended water harmonization
# ---------------------------------------------------------------------------

class TestExtendedWaterHarmonization:
    """Tests for harmonize_transitions() extended to all water cells."""

    def _make_cell_info(self, col, row, cell_type="plain"):
        return {
            "col": col,
            "row": row,
            "x": col * reskin_tiles.TILE_SIZE,
            "y": row * reskin_tiles.TILE_SIZE,
            "type": cell_type,
        }

    def test_all_water_cells_harmonized(self, tmp_path):
        """Non-transition water cells should also have their water pixels
        shifted toward the water reference LAB color."""
        ts = reskin_tiles.TILE_SIZE
        atlas_w = 12 * ts
        atlas_h = 145 * ts

        # Build atlas with blue (water-hue) pixels at a non-transition sea cell
        # col=5, row=40 — interior sea cell, NOT edge column, NOT beach
        atlas_arr = np.zeros((atlas_h, atlas_w, 4), dtype=np.uint8)
        y0, x0 = 40 * ts, 5 * ts
        atlas_arr[y0:y0 + ts, x0:x0 + ts] = [20, 60, 210, 255]  # hue ~228, water-like
        atlas = Image.fromarray(atlas_arr)
        atlas_path = tmp_path / "atlas.png"
        atlas.save(atlas_path)

        # Reference sea cell at row=36 — water reference source
        ref_color = (30, 90, 180, 255)  # different blue
        ref_img = Image.new("RGBA", (ts, ts), ref_color)

        # Non-transition sea cell at row=40, col=5 — should now be harmonized
        target_color = (60, 120, 240, 255)  # lighter blue, differs from reference
        target_img = Image.new("RGBA", (ts, ts), target_color)

        # Also include a plain cell for grass reference
        plain_img = Image.new("RGBA", (ts, ts), (80, 200, 50, 255))

        cells = [
            (self._make_cell_info(0, 0, "plain"), plain_img),
            (self._make_cell_info(5, 36, "water"), ref_img),      # reference (row < 50)
            (self._make_cell_info(5, 40, "water"), target_img),   # non-transition sea
        ]

        result = reskin_tiles.harmonize_transitions(cells, atlas_path)

        # The target cell should have been modified (water pixels shifted)
        target_out = np.array(result[2][1])
        target_in = np.array(target_img)
        assert not np.array_equal(target_out[:, :, :3], target_in[:, :, :3]), \
            "Non-transition water cell should be modified by extended harmonization"

    def test_water_strength_parameter(self, tmp_path):
        """Verify the water_strength parameter controls shift amount for
        non-transition water cells."""
        ts = reskin_tiles.TILE_SIZE
        atlas_w = 12 * ts
        atlas_h = 145 * ts

        # Atlas with water-hue pixels at the target cell
        atlas_arr = np.zeros((atlas_h, atlas_w, 4), dtype=np.uint8)
        y0, x0 = 40 * ts, 5 * ts
        atlas_arr[y0:y0 + ts, x0:x0 + ts] = [20, 60, 210, 255]
        atlas = Image.fromarray(atlas_arr)
        atlas_path = tmp_path / "atlas.png"
        atlas.save(atlas_path)

        ref_img = Image.new("RGBA", (ts, ts), (30, 90, 180, 255))
        target_img = Image.new("RGBA", (ts, ts), (60, 120, 240, 255))
        plain_img = Image.new("RGBA", (ts, ts), (80, 200, 50, 255))

        cells = [
            (self._make_cell_info(0, 0, "plain"), plain_img),
            (self._make_cell_info(5, 36, "water"), ref_img),
            (self._make_cell_info(5, 40, "water"), target_img),
        ]

        # Run with low water_strength
        result_low = reskin_tiles.harmonize_transitions(
            cells, atlas_path, water_strength=0.1,
        )
        # Run with high water_strength
        result_high = reskin_tiles.harmonize_transitions(
            cells, atlas_path, water_strength=0.9,
        )

        out_low = np.array(result_low[2][1])[:, :, :3].astype(np.float64)
        out_high = np.array(result_high[2][1])[:, :, :3].astype(np.float64)
        original = np.array(target_img)[:, :, :3].astype(np.float64)

        # Higher water_strength should move pixels further from original
        diff_low = np.abs(out_low - original).mean()
        diff_high = np.abs(out_high - original).mean()
        assert diff_high > diff_low, \
            f"Higher water_strength should produce larger shift: low={diff_low:.2f}, high={diff_high:.2f}"

    def test_non_water_pixels_in_water_cells_unchanged(self, tmp_path):
        """Non-water-hue pixels in non-transition water cells should not
        be modified."""
        ts = reskin_tiles.TILE_SIZE
        atlas_w = 12 * ts
        atlas_h = 145 * ts

        # Atlas: the target cell has NON-water pixels (red hue ~0)
        atlas_arr = np.zeros((atlas_h, atlas_w, 4), dtype=np.uint8)
        y0, x0 = 40 * ts, 5 * ts
        atlas_arr[y0:y0 + ts, x0:x0 + ts] = [220, 50, 30, 255]  # red, hue ~6
        atlas = Image.fromarray(atlas_arr)
        atlas_path = tmp_path / "atlas.png"
        atlas.save(atlas_path)

        # Reference sea cell
        ref_img = Image.new("RGBA", (ts, ts), (30, 90, 180, 255))

        # Target cell: red pixels (NOT water hue) — should NOT be shifted
        red_color = (200, 60, 40, 255)
        target_img = Image.new("RGBA", (ts, ts), red_color)

        plain_img = Image.new("RGBA", (ts, ts), (80, 200, 50, 255))

        cells = [
            (self._make_cell_info(0, 0, "plain"), plain_img),
            (self._make_cell_info(5, 36, "water"), ref_img),
            (self._make_cell_info(5, 40, "water"), target_img),
        ]

        result = reskin_tiles.harmonize_transitions(cells, atlas_path)

        target_out = np.array(result[2][1])
        target_in = np.array(target_img)
        np.testing.assert_array_equal(target_out, target_in,
            err_msg="Non-water-hue pixels in water cells should not be modified")


# ---------------------------------------------------------------------------
# _rgb_to_hsv_arrays
# ---------------------------------------------------------------------------

class TestRgbToHsvArrays:
    """Tests for the vectorized RGB -> HSV helper."""

    def test_pure_red(self):
        """Pure red (255, 0, 0) should have hue=0, sat=1, val=1."""
        rgb = np.array([[[255, 0, 0]]], dtype=np.uint8)
        hue, sat, val = reskin_tiles._rgb_to_hsv_arrays(rgb)
        np.testing.assert_allclose(hue[0, 0], 0.0, atol=0.5)
        np.testing.assert_allclose(sat[0, 0], 1.0, atol=1e-6)
        np.testing.assert_allclose(val[0, 0], 1.0, atol=1e-6)

    def test_pure_green(self):
        """Pure green (0, 255, 0) should have hue=120, sat=1, val=1."""
        rgb = np.array([[[0, 255, 0]]], dtype=np.uint8)
        hue, sat, val = reskin_tiles._rgb_to_hsv_arrays(rgb)
        np.testing.assert_allclose(hue[0, 0], 120.0, atol=0.5)
        np.testing.assert_allclose(sat[0, 0], 1.0, atol=1e-6)
        np.testing.assert_allclose(val[0, 0], 1.0, atol=1e-6)

    def test_pure_blue(self):
        """Pure blue (0, 0, 255) should have hue=240, sat=1, val=1."""
        rgb = np.array([[[0, 0, 255]]], dtype=np.uint8)
        hue, sat, val = reskin_tiles._rgb_to_hsv_arrays(rgb)
        np.testing.assert_allclose(hue[0, 0], 240.0, atol=0.5)
        np.testing.assert_allclose(sat[0, 0], 1.0, atol=1e-6)
        np.testing.assert_allclose(val[0, 0], 1.0, atol=1e-6)

    def test_black(self):
        """Black (0, 0, 0) should have hue=0, sat=0, val=0."""
        rgb = np.array([[[0, 0, 0]]], dtype=np.uint8)
        hue, sat, val = reskin_tiles._rgb_to_hsv_arrays(rgb)
        assert hue[0, 0] == 0.0
        assert sat[0, 0] == 0.0
        assert val[0, 0] == 0.0

    def test_white(self):
        """White (255, 255, 255) should have hue=0, sat=0, val=1."""
        rgb = np.array([[[255, 255, 255]]], dtype=np.uint8)
        hue, sat, val = reskin_tiles._rgb_to_hsv_arrays(rgb)
        assert hue[0, 0] == 0.0
        assert sat[0, 0] == 0.0
        np.testing.assert_allclose(val[0, 0], 1.0, atol=1e-6)

    def test_uniform_gray(self):
        """A uniform gray (128,128,128) should have delta=0, sat=0."""
        rgb = np.array([[[128, 128, 128]]], dtype=np.uint8)
        hue, sat, val = reskin_tiles._rgb_to_hsv_arrays(rgb)
        assert hue[0, 0] == 0.0
        assert sat[0, 0] == 0.0
        np.testing.assert_allclose(val[0, 0], 128.0 / 255.0, atol=1e-6)

    def test_batch_shape(self):
        """A 2x3 pixel grid should return (2, 3) arrays for hue, sat, val."""
        rgb = np.zeros((2, 3, 3), dtype=np.uint8)
        rgb[0, 0] = [255, 0, 0]    # red
        rgb[0, 1] = [0, 255, 0]    # green
        rgb[0, 2] = [0, 0, 255]    # blue
        rgb[1, 0] = [0, 0, 0]      # black
        rgb[1, 1] = [255, 255, 255] # white
        rgb[1, 2] = [128, 128, 128] # gray
        hue, sat, val = reskin_tiles._rgb_to_hsv_arrays(rgb)
        assert hue.shape == (2, 3)
        assert sat.shape == (2, 3)
        assert val.shape == (2, 3)
        # Verify hues for the primary colors
        np.testing.assert_allclose(hue[0, 0], 0.0, atol=0.5)    # red
        np.testing.assert_allclose(hue[0, 1], 120.0, atol=0.5)  # green
        np.testing.assert_allclose(hue[0, 2], 240.0, atol=0.5)  # blue

    def test_yellow_hue(self):
        """Yellow (255, 255, 0) should have hue=60."""
        rgb = np.array([[[255, 255, 0]]], dtype=np.uint8)
        hue, sat, val = reskin_tiles._rgb_to_hsv_arrays(rgb)
        np.testing.assert_allclose(hue[0, 0], 60.0, atol=0.5)
        np.testing.assert_allclose(sat[0, 0], 1.0, atol=1e-6)
        np.testing.assert_allclose(val[0, 0], 1.0, atol=1e-6)

    def test_cyan_hue(self):
        """Cyan (0, 255, 255) should have hue=180."""
        rgb = np.array([[[0, 255, 255]]], dtype=np.uint8)
        hue, sat, val = reskin_tiles._rgb_to_hsv_arrays(rgb)
        np.testing.assert_allclose(hue[0, 0], 180.0, atol=0.5)


# ---------------------------------------------------------------------------
# _shift_masked_pixels
# ---------------------------------------------------------------------------

class TestShiftMaskedPixels:
    """Tests for the LAB-space pixel shift helper."""

    def test_empty_mask_returns_false(self):
        """An all-False mask should return False and leave arr unchanged."""
        arr = np.full((4, 4, 4), 128, dtype=np.uint8)
        arr[:, :, 3] = 255
        original = arr.copy()
        mask = np.zeros((4, 4), dtype=bool)
        ref_lab = np.array([50.0, 0.0, 0.0])
        result = reskin_tiles._shift_masked_pixels(arr, mask, ref_lab, strength=1.0)
        assert result is False
        np.testing.assert_array_equal(arr, original)

    def test_full_mask_returns_true(self):
        """An all-True mask should return True and modify all RGB pixels."""
        arr = np.full((4, 4, 4), 100, dtype=np.uint8)
        arr[:, :, 3] = 255
        original_rgb = arr[:, :, :3].copy()
        mask = np.ones((4, 4), dtype=bool)
        # A very different target LAB color (bright red in LAB space)
        ref_lab = np.array([53.0, 80.0, 67.0])
        result = reskin_tiles._shift_masked_pixels(arr, mask, ref_lab, strength=1.0)
        assert result is True
        assert not np.array_equal(arr[:, :, :3], original_rgb), \
            "Full-mask shift with strength=1.0 should change all RGB pixels"

    def test_alpha_channel_unchanged(self):
        """The alpha channel should never be modified by _shift_masked_pixels."""
        arr = np.full((4, 4, 4), 100, dtype=np.uint8)
        arr[:, :, 3] = 200  # distinctive alpha value
        alpha_before = arr[:, :, 3].copy()
        mask = np.ones((4, 4), dtype=bool)
        ref_lab = np.array([53.0, 80.0, 67.0])
        reskin_tiles._shift_masked_pixels(arr, mask, ref_lab, strength=1.0)
        np.testing.assert_array_equal(arr[:, :, 3], alpha_before)

    def test_strength_zero_no_change(self):
        """With strength=0.0, pixels should not change (shift is multiplied by 0)."""
        arr = np.full((4, 4, 4), 100, dtype=np.uint8)
        arr[:, :, 3] = 255
        original = arr.copy()
        mask = np.ones((4, 4), dtype=bool)
        ref_lab = np.array([53.0, 80.0, 67.0])
        result = reskin_tiles._shift_masked_pixels(arr, mask, ref_lab, strength=0.0)
        # It returns True (mask had pixels), but no actual change due to zero strength
        assert result is True
        np.testing.assert_array_equal(arr[:, :, :3], original[:, :, :3])

    def test_shift_direction_toward_reference(self):
        """Shifted pixels should be closer to the reference than the original,
        not further away."""
        # Start with green-ish pixels
        arr = np.full((2, 2, 4), 0, dtype=np.uint8)
        arr[:, :, :3] = [80, 160, 60]  # green
        arr[:, :, 3] = 255
        mask = np.ones((2, 2), dtype=bool)

        # Target: bright red in LAB
        ref_lab = np.array([53.0, 80.0, 67.0])

        # Get original LAB distance
        original_rgb = arr[:, :, :3][mask].astype(np.float64)
        original_lab = reskin_tiles._rgb_to_lab(original_rgb)
        dist_before = np.linalg.norm(original_lab - ref_lab[np.newaxis, :], axis=1).mean()

        reskin_tiles._shift_masked_pixels(arr, mask, ref_lab, strength=0.5)

        # Get shifted LAB distance
        shifted_rgb = arr[:, :, :3][mask].astype(np.float64)
        shifted_lab = reskin_tiles._rgb_to_lab(shifted_rgb)
        dist_after = np.linalg.norm(shifted_lab - ref_lab[np.newaxis, :], axis=1).mean()

        assert dist_after < dist_before, \
            f"Shift should move pixels toward reference: before={dist_before:.2f}, after={dist_after:.2f}"

    def test_partial_mask(self):
        """Only masked pixels should be shifted; unmasked stay the same."""
        arr = np.full((4, 4, 4), 100, dtype=np.uint8)
        arr[:, :, 3] = 255
        original = arr.copy()
        mask = np.zeros((4, 4), dtype=bool)
        mask[0, 0] = True
        mask[2, 3] = True
        ref_lab = np.array([53.0, 80.0, 67.0])
        reskin_tiles._shift_masked_pixels(arr, mask, ref_lab, strength=1.0)
        # Unmasked pixels should be unchanged
        unmasked = ~mask
        np.testing.assert_array_equal(
            arr[:, :, :3][unmasked], original[:, :, :3][unmasked])


# ---------------------------------------------------------------------------
# _extract_plain_tile_from_anchor
# ---------------------------------------------------------------------------

class TestExtractPlainTileFromAnchor:
    """Tests for the anchor image tile extraction helper."""

    def _make_anchor_image(self, path, tile_color):
        """Create a synthetic single-cell anchor grid at 4x scale.

        Fills the tile region with tile_color, grid lines with black,
        and padding with gray.
        """
        ts = reskin_tiles.TILE_SIZE  # 24
        pad = reskin_tiles.CELL_PADDING  # 4
        glw = reskin_tiles.GRID_LINE_WIDTH  # 2
        native_w = ts + pad * 2 + glw * 2  # 36
        native_h = native_w

        native_img = Image.new("RGBA", (native_w, native_h), (0, 0, 0, 255))
        # Fill padding area with gray
        for y in range(glw, glw + pad * 2 + ts):
            for x in range(glw, glw + pad * 2 + ts):
                native_img.putpixel((x, y), (200, 200, 200, 255))
        # Fill tile region with tile_color
        for y in range(glw + pad, glw + pad + ts):
            for x in range(glw + pad, glw + pad + ts):
                native_img.putpixel((x, y), tile_color)

        scaled = native_img.resize((native_w * 4, native_h * 4), Image.NEAREST)
        scaled.save(path)

    def test_returns_correct_shape(self, tmp_path):
        """Extracted tile should be (TILE_SIZE, TILE_SIZE, 4)."""
        anchor_path = tmp_path / "anchor_plain.png"
        self._make_anchor_image(anchor_path, (100, 200, 50, 255))
        result = reskin_tiles._extract_plain_tile_from_anchor(str(anchor_path))
        arr = np.array(result)
        ts = reskin_tiles.TILE_SIZE
        assert arr.shape == (ts, ts, 4)

    def test_nearest_resampling_preserves_colors(self, tmp_path):
        """With NEAREST resampling, the exact tile color should be preserved."""
        tile_color = (137, 42, 213, 255)
        anchor_path = tmp_path / "anchor_plain.png"
        self._make_anchor_image(anchor_path, tile_color)
        result = reskin_tiles._extract_plain_tile_from_anchor(str(anchor_path))
        arr = np.array(result)
        # Every pixel in the tile should match exactly
        for c in range(4):
            assert np.all(arr[:, :, c] == tile_color[c]), \
                f"Channel {c}: expected {tile_color[c]} everywhere, got unique values {np.unique(arr[:, :, c])}"

    def test_grid_lines_not_in_tile(self, tmp_path):
        """Grid line pixels (black) should not appear in the extracted tile region."""
        tile_color = (200, 150, 100, 255)
        anchor_path = tmp_path / "anchor_plain.png"
        self._make_anchor_image(anchor_path, tile_color)
        result = reskin_tiles._extract_plain_tile_from_anchor(str(anchor_path))
        arr = np.array(result)
        # No pixel should be black (the grid line color)
        black_mask = (arr[:, :, 0] == 0) & (arr[:, :, 1] == 0) & (arr[:, :, 2] == 0)
        assert not black_mask.any(), "Grid line pixels (black) leaked into tile region"

    def test_padding_not_in_tile(self, tmp_path):
        """Cell padding (gray) should not appear in the extracted tile region."""
        tile_color = (50, 100, 200, 255)
        anchor_path = tmp_path / "anchor_plain.png"
        self._make_anchor_image(anchor_path, tile_color)
        result = reskin_tiles._extract_plain_tile_from_anchor(str(anchor_path))
        arr = np.array(result)
        # No pixel should be gray (200,200,200) — the padding color
        gray_mask = (arr[:, :, 0] == 200) & (arr[:, :, 1] == 200) & (arr[:, :, 2] == 200)
        assert not gray_mask.any(), "Padding pixels (gray) leaked into tile region"


# ---------------------------------------------------------------------------
# composite_feature_backgrounds — edge cases
# ---------------------------------------------------------------------------

class TestCompositeFeatureBackgroundsEdgeCases:
    """Edge-case tests for the background compositing function."""

    def _make_anchor_image(self, path, color):
        """Create a synthetic anchor image at 4x scale (same as TestCompositeFeatureBackgrounds)."""
        ts = reskin_tiles.TILE_SIZE
        pad = reskin_tiles.CELL_PADDING
        glw = reskin_tiles.GRID_LINE_WIDTH
        native_w = ts + pad * 2 + glw * 2
        native_h = native_w

        native_img = Image.new("RGBA", (native_w, native_h), (0, 0, 0, 255))
        for y in range(glw + pad, glw + pad + ts):
            for x in range(glw + pad, glw + pad + ts):
                native_img.putpixel((x, y), color)

        scaled = native_img.resize((native_w * 4, native_h * 4), Image.NEAREST)
        scaled.save(path)

    def test_all_grass_pixels_fully_replaced(self, tmp_path):
        """A cell where ALL original pixels are grass-like should have every
        pixel replaced with the reskinned plain tile."""
        ts = reskin_tiles.TILE_SIZE

        reskinned_color = (90, 220, 70, 255)
        anchor_path = tmp_path / "anchor_plain.png"
        self._make_anchor_image(anchor_path, reskinned_color)

        # Original atlas: forest cell at (col=0, row=20) is ALL grass-colored
        atlas_arr = np.zeros((30 * ts, 12 * ts, 4), dtype=np.uint8)
        y0, x0 = 20 * ts, 0
        atlas_arr[y0:y0 + ts, x0:x0 + ts] = [60, 180, 40, 255]  # hue ~110, sat high
        atlas = Image.fromarray(atlas_arr)
        atlas_path = tmp_path / "atlas.png"
        atlas.save(atlas_path)

        # Forest cell — distinct green to verify replacement
        forest_color = (110, 140, 90, 255)
        cell_img = Image.new("RGBA", (ts, ts), forest_color)
        cell_path = tmp_path / "r020_c00.png"
        cell_img.save(cell_path)

        cell_info = {
            "id": "r020_c00", "row": 20, "col": 0,
            "x": 0, "y": 20 * ts,
            "path": str(cell_path),
            "type": "forest",
            "is_anim_frame": False,
        }

        result = reskin_tiles.composite_feature_backgrounds(
            [cell_info], {"plain": str(anchor_path)}, atlas_path,
        )

        assert result == 1
        out_arr = np.array(Image.open(cell_path))
        # Every pixel should now match the reskinned plain color
        for c in range(3):
            assert np.all(out_arr[:, :, c] == reskinned_color[c]), \
                f"Channel {c}: all grass pixels should be replaced with reskinned plain"

    def test_no_grass_pixels_cell_unchanged(self, tmp_path):
        """A cell with NO grass-like pixels (all blue/water) should be unchanged."""
        ts = reskin_tiles.TILE_SIZE

        reskinned_color = (90, 220, 70, 255)
        anchor_path = tmp_path / "anchor_plain.png"
        self._make_anchor_image(anchor_path, reskinned_color)

        # Original atlas: forest cell at (col=0, row=20) has ALL blue pixels
        atlas_arr = np.zeros((30 * ts, 12 * ts, 4), dtype=np.uint8)
        y0, x0 = 20 * ts, 0
        atlas_arr[y0:y0 + ts, x0:x0 + ts] = [30, 60, 220, 255]  # hue ~228, water-like
        atlas = Image.fromarray(atlas_arr)
        atlas_path = tmp_path / "atlas.png"
        atlas.save(atlas_path)

        # Forest cell with blue pixels
        blue_color = (40, 70, 210, 255)
        cell_img = Image.new("RGBA", (ts, ts), blue_color)
        cell_path = tmp_path / "r020_c00.png"
        cell_img.save(cell_path)

        cell_info = {
            "id": "r020_c00", "row": 20, "col": 0,
            "x": 0, "y": 20 * ts,
            "path": str(cell_path),
            "type": "forest",
            "is_anim_frame": False,
        }

        result = reskin_tiles.composite_feature_backgrounds(
            [cell_info], {"plain": str(anchor_path)}, atlas_path,
        )

        assert result == 0  # no grass pixels found -> nothing composited
        out_arr = np.array(Image.open(cell_path))
        expected = np.array(cell_img)
        np.testing.assert_array_equal(out_arr, expected)

    def test_idempotent_when_already_matching(self, tmp_path):
        """If the cell already has the reskinned plain color, compositing should
        still be idempotent — running it again produces the same output."""
        ts = reskin_tiles.TILE_SIZE

        reskinned_color = (80, 200, 60, 255)
        anchor_path = tmp_path / "anchor_plain.png"
        self._make_anchor_image(anchor_path, reskinned_color)

        # Atlas: forest cell at (col=0, row=20) is grass-colored
        atlas_arr = np.zeros((30 * ts, 12 * ts, 4), dtype=np.uint8)
        y0, x0 = 20 * ts, 0
        atlas_arr[y0:y0 + ts, x0:x0 + ts] = [60, 180, 40, 255]  # grass
        atlas = Image.fromarray(atlas_arr)
        atlas_path = tmp_path / "atlas.png"
        atlas.save(atlas_path)

        # Cell already has the reskinned plain color
        cell_img = Image.new("RGBA", (ts, ts), reskinned_color)
        cell_path = tmp_path / "r020_c00.png"
        cell_img.save(cell_path)

        cell_info = {
            "id": "r020_c00", "row": 20, "col": 0,
            "x": 0, "y": 20 * ts,
            "path": str(cell_path),
            "type": "forest",
            "is_anim_frame": False,
        }

        # First pass
        reskin_tiles.composite_feature_backgrounds(
            [cell_info], {"plain": str(anchor_path)}, atlas_path,
        )
        after_first = np.array(Image.open(cell_path)).copy()

        # Second pass — should produce identical result
        reskin_tiles.composite_feature_backgrounds(
            [cell_info], {"plain": str(anchor_path)}, atlas_path,
        )
        after_second = np.array(Image.open(cell_path))

        np.testing.assert_array_equal(after_first, after_second,
            err_msg="Compositing should be idempotent")

    def test_no_plain_anchor_returns_zero(self, tmp_path):
        """If no plain anchor is provided, compositing should bail out and return 0."""
        ts = reskin_tiles.TILE_SIZE

        atlas_arr = np.zeros((30 * ts, 12 * ts, 4), dtype=np.uint8)
        atlas = Image.fromarray(atlas_arr)
        atlas_path = tmp_path / "atlas.png"
        atlas.save(atlas_path)

        cell_info = {
            "id": "r020_c00", "row": 20, "col": 0,
            "x": 0, "y": 20 * ts,
            "path": str(tmp_path / "r020_c00.png"),
            "type": "forest",
            "is_anim_frame": False,
        }

        # No plain anchor in dict
        result = reskin_tiles.composite_feature_backgrounds(
            [cell_info], {"water": "/fake/anchor_water.png"}, atlas_path,
        )
        assert result == 0

    def test_anim_frame_cells_skipped(self, tmp_path):
        """Animation frame cells should be skipped by compositing."""
        ts = reskin_tiles.TILE_SIZE

        reskinned_color = (90, 220, 70, 255)
        anchor_path = tmp_path / "anchor_plain.png"
        self._make_anchor_image(anchor_path, reskinned_color)

        atlas_arr = np.zeros((30 * ts, 12 * ts, 4), dtype=np.uint8)
        y0, x0 = 20 * ts, 0
        atlas_arr[y0:y0 + ts, x0:x0 + ts] = [60, 180, 40, 255]
        atlas = Image.fromarray(atlas_arr)
        atlas_path = tmp_path / "atlas.png"
        atlas.save(atlas_path)

        forest_color = (110, 140, 90, 255)
        cell_img = Image.new("RGBA", (ts, ts), forest_color)
        cell_path = tmp_path / "r020_c00.png"
        cell_img.save(cell_path)

        cell_info = {
            "id": "r020_c00", "row": 20, "col": 0,
            "x": 0, "y": 20 * ts,
            "path": str(cell_path),
            "type": "forest",
            "is_anim_frame": True,  # animation frame -> should be skipped
        }

        result = reskin_tiles.composite_feature_backgrounds(
            [cell_info], {"plain": str(anchor_path)}, atlas_path,
        )

        assert result == 0
        out_arr = np.array(Image.open(cell_path))
        expected = np.array(cell_img)
        np.testing.assert_array_equal(out_arr, expected)


# ---------------------------------------------------------------------------
# harmonize_transitions — extended edge cases
# ---------------------------------------------------------------------------

class TestHarmonizeTransitionsExtended:
    """Additional edge-case tests for harmonize_transitions with the
    extended water harmonization and refactored _shift_masked_pixels."""

    def _make_cell_info(self, col, row, cell_type="plain"):
        return {
            "col": col,
            "row": row,
            "x": col * reskin_tiles.TILE_SIZE,
            "y": row * reskin_tiles.TILE_SIZE,
            "type": cell_type,
        }

    def test_transition_cells_use_strength_not_water_strength(self, tmp_path):
        """Transition cells should use the `strength` parameter for both
        grass and water pixel shifts, not `water_strength`."""
        ts = reskin_tiles.TILE_SIZE
        atlas_w = 12 * ts
        atlas_h = 145 * ts

        # Atlas with green (grass) pixels at a transition beach cell
        atlas_arr = np.zeros((atlas_h, atlas_w, 4), dtype=np.uint8)
        y0, x0 = 55 * ts, 3 * ts
        atlas_arr[y0:y0 + ts, x0:x0 + ts] = [60, 180, 40, 255]  # grass hue
        atlas = Image.fromarray(atlas_arr)
        atlas_path = tmp_path / "atlas.png"
        atlas.save(atlas_path)

        plain_img = Image.new("RGBA", (ts, ts), (50, 200, 30, 255))
        beach_img = Image.new("RGBA", (ts, ts), (100, 140, 80, 255))

        cells = [
            (self._make_cell_info(0, 0, "plain"), plain_img),
            (self._make_cell_info(3, 55, "water"), beach_img),
        ]

        # Run with high strength, low water_strength
        result_high_str = reskin_tiles.harmonize_transitions(
            cells, atlas_path, strength=0.9, water_strength=0.1,
        )
        # Run with low strength, high water_strength
        result_low_str = reskin_tiles.harmonize_transitions(
            cells, atlas_path, strength=0.1, water_strength=0.9,
        )

        out_high = np.array(result_high_str[1][1])[:, :, :3].astype(np.float64)
        out_low = np.array(result_low_str[1][1])[:, :, :3].astype(np.float64)
        original = np.array(beach_img)[:, :, :3].astype(np.float64)

        # The transition cell should respond to `strength`, not `water_strength`
        diff_high = np.abs(out_high - original).mean()
        diff_low = np.abs(out_low - original).mean()
        assert diff_high > diff_low, (
            f"Transition cells should use 'strength' param: "
            f"high_strength_diff={diff_high:.2f} should be > low_strength_diff={diff_low:.2f}"
        )

    def test_water_strength_zero_leaves_non_transition_water_unchanged(self, tmp_path):
        """With water_strength=0.0, non-transition water cells should be unchanged."""
        ts = reskin_tiles.TILE_SIZE
        atlas_w = 12 * ts
        atlas_h = 145 * ts

        # Atlas with water pixels at a non-transition sea cell (col=5, row=40)
        atlas_arr = np.zeros((atlas_h, atlas_w, 4), dtype=np.uint8)
        y0, x0 = 40 * ts, 5 * ts
        atlas_arr[y0:y0 + ts, x0:x0 + ts] = [20, 60, 210, 255]  # water hue
        atlas = Image.fromarray(atlas_arr)
        atlas_path = tmp_path / "atlas.png"
        atlas.save(atlas_path)

        plain_img = Image.new("RGBA", (ts, ts), (80, 200, 50, 255))
        ref_img = Image.new("RGBA", (ts, ts), (30, 90, 180, 255))
        target_img = Image.new("RGBA", (ts, ts), (60, 120, 240, 255))

        cells = [
            (self._make_cell_info(0, 0, "plain"), plain_img),
            (self._make_cell_info(5, 36, "water"), ref_img),
            (self._make_cell_info(5, 40, "water"), target_img),
        ]

        result = reskin_tiles.harmonize_transitions(
            cells, atlas_path, water_strength=0.0,
        )

        target_out = np.array(result[2][1])
        target_in = np.array(target_img)
        np.testing.assert_array_equal(target_out[:, :, :3], target_in[:, :, :3],
            err_msg="water_strength=0.0 should leave non-transition water cells unchanged")

    def test_edge_column_water_is_transition(self, tmp_path):
        """Water cells in edge columns (0 or 11) should be treated as
        transition cells and use `strength`, not `water_strength`."""
        ts = reskin_tiles.TILE_SIZE
        atlas_w = 12 * ts
        atlas_h = 145 * ts

        # Atlas: water pixels at col=0, row=40 (edge column)
        atlas_arr = np.zeros((atlas_h, atlas_w, 4), dtype=np.uint8)
        y0, x0 = 40 * ts, 0
        atlas_arr[y0:y0 + ts, x0:x0 + ts] = [20, 60, 210, 255]  # water hue
        atlas = Image.fromarray(atlas_arr)
        atlas_path = tmp_path / "atlas.png"
        atlas.save(atlas_path)

        plain_img = Image.new("RGBA", (ts, ts), (80, 200, 50, 255))
        ref_img = Image.new("RGBA", (ts, ts), (30, 90, 180, 255))
        edge_water_img = Image.new("RGBA", (ts, ts), (60, 120, 240, 255))

        cells = [
            (self._make_cell_info(0, 0, "plain"), plain_img),
            (self._make_cell_info(5, 36, "water"), ref_img),
            (self._make_cell_info(0, 40, "water"), edge_water_img),  # edge col=0
        ]

        # With strength=0.8, water_strength=0.0
        # If it's treated as transition, it uses strength -> pixels change
        # If it's treated as non-transition water, it uses water_strength -> no change
        result = reskin_tiles.harmonize_transitions(
            cells, atlas_path, strength=0.8, water_strength=0.0,
        )

        edge_out = np.array(result[2][1])[:, :, :3]
        edge_in = np.array(edge_water_img)[:, :, :3]
        assert not np.array_equal(edge_out, edge_in), \
            "Edge-column water cell should be treated as transition (uses strength, not water_strength)"

    def test_mountain_type_not_harmonized_as_water(self, tmp_path):
        """Non-water, non-transition mountain cells should pass through unchanged."""
        ts = reskin_tiles.TILE_SIZE
        atlas_w = 12 * ts
        atlas_h = 145 * ts

        atlas_arr = np.zeros((atlas_h, atlas_w, 4), dtype=np.uint8)
        atlas = Image.fromarray(atlas_arr)
        atlas_path = tmp_path / "atlas.png"
        atlas.save(atlas_path)

        plain_img = Image.new("RGBA", (ts, ts), (80, 200, 50, 255))
        # Mountain cell at interior column (col=5, row=10) — not a transition
        mountain_color = (150, 130, 110, 255)
        mountain_img = Image.new("RGBA", (ts, ts), mountain_color)

        cells = [
            (self._make_cell_info(0, 0, "plain"), plain_img),
            (self._make_cell_info(5, 10, "mountain"), mountain_img),
        ]

        result = reskin_tiles.harmonize_transitions(cells, atlas_path)

        mountain_out = np.array(result[1][1])
        mountain_in = np.array(mountain_img)
        np.testing.assert_array_equal(mountain_out, mountain_in,
            err_msg="Interior mountain cells should pass through unchanged")


# ---------------------------------------------------------------------------
# TILE_DESCRIPTIONS
# ---------------------------------------------------------------------------
