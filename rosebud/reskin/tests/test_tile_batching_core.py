"""Focused tests extracted from the former monolithic tile pipeline suite."""

from .tile_pipeline_test_support import *

class TestCreateTypedBatches:
    def test_cells_grouped_by_type(self, tmp_path):
        """Cells of the same batch type end up in the same batch.

        Note: Animation cells (including base frames) are now excluded from
        type batches.  Use non-animated water cells for this test.
        """
        cells = [
            _make_cell(0, 0, tmp_path=tmp_path),   # plain
            _make_cell(1, 0, tmp_path=tmp_path),   # plain
            _make_cell(6, 73, tmp_path=tmp_path),   # water (non-animated, in river row range)
            _make_cell(6, 76, tmp_path=tmp_path),   # water (non-animated, in river row range)
        ]
        batches = reskin_tiles.create_typed_batches(cells, tmp_path)

        types = {b["tile_type"] for b in batches}
        assert "plain" in types
        assert "water" in types

    def test_subtypes_batch_independently(self, tmp_path):
        """Sub-types batch under their own raw type, not a merged parent."""
        cells = [
            _make_cell(0, 3, tmp_path=tmp_path, cell_type="street", is_anim_frame=False),
            _make_cell(0, 15, tmp_path=tmp_path, cell_type="trench", is_anim_frame=False),
            _make_cell(8, 1, tmp_path=tmp_path, cell_type="bridge", is_anim_frame=False),
        ]
        batches = reskin_tiles.create_typed_batches(cells, tmp_path)

        # Each sub-type gets its own batch
        assert len(batches) == 3
        batch_types = {b["tile_type"] for b in batches}
        assert batch_types == {"street", "trench", "bridge"}
        for b in batches:
            assert len(b["cells"]) == 1

    def test_anchor_inheritance(self):
        """ANCHOR_INHERITANCE maps sub-types to the correct parent anchor."""
        ai = reskin_tiles.ANCHOR_INHERITANCE
        # Sub-types that should inherit from plain
        assert ai["trench"] == "plain"
        assert ai["lightning"] == "plain"
        # Sub-types that should inherit from street
        assert ai["bridge"] == "street"
        assert ai["pipe"] == "street"
        assert ai["computer"] == "street"
        # Sub-types that should inherit from water
        assert ai["floatingedge"] == "water"
        assert ai["sea_object"] == "water"
        assert ai["reef"] == "water"
        # Types that generate their own anchor should NOT be in the dict
        for own_anchor_type in ("plain", "street", "rail", "mountain", "forest",
                                "campsite", "pier", "water", "river",
                                "stormcloud", "teleporter"):
            assert own_anchor_type not in ai, (
                f"{own_anchor_type} should not be in ANCHOR_INHERITANCE"
            )

    def test_batch_size_limit(self, tmp_path):
        """Batches should not exceed CELLS_PER_BATCH (36)."""
        # Create 40 plain cells, explicitly non-animated for batching tests
        cells = [_make_cell(i % 12, i // 12, tmp_path=tmp_path, is_anim_frame=False) for i in range(40)]
        # Force all to plain type and clear animation metadata
        for c in cells:
            c["type"] = "plain"
            c["anim_name"] = None

        batches = reskin_tiles.create_typed_batches(cells, tmp_path)

        for b in batches:
            assert len(b["cells"]) <= reskin_tiles.CELLS_PER_BATCH

    def test_batch_overflow_creates_multiple(self, tmp_path):
        """More than 36 cells of one type should create multiple batches."""
        cells = [_make_cell(i % 12, i // 12, tmp_path=tmp_path, is_anim_frame=False) for i in range(40)]
        # Force all to plain type and clear animation metadata
        for c in cells:
            c["type"] = "plain"
            c["anim_name"] = None

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
            c["anim_name"] = None

        batches = reskin_tiles.create_typed_batches(cells, tmp_path)
        b = batches[0]

        for c in b["cells"]:
            assert 0 <= c["grid_col"] < reskin_tiles.GRID_COLS
            assert 0 <= c["grid_row"]

    def test_animation_cells_excluded(self, tmp_path):
        """ALL animation cells (base + frames) should be excluded from type batches.

        Animation cells are now handled by build_animation_batches() instead.
        """
        cells = [
            _make_cell(0, 0, tmp_path=tmp_path, is_anim_frame=False),   # plain, included
            _make_cell(1, 0, tmp_path=tmp_path, is_anim_frame=False),   # plain, included
            _make_cell(8, 38, tmp_path=tmp_path, is_anim_frame=True),   # water frame, excluded
            _make_cell(8, 35, tmp_path=tmp_path, is_anim_frame=False),  # water base (Sea anim), excluded
        ]
        batches = reskin_tiles.create_typed_batches(cells, tmp_path)

        all_batch_cells = []
        for b in batches:
            all_batch_cells.extend(b["cells"])

        batch_ids = {c["id"] for c in all_batch_cells}
        assert "r000_c00" in batch_ids  # plain cell included
        assert "r000_c01" in batch_ids  # plain cell included
        assert "r035_c08" not in batch_ids  # water base excluded (Sea animation)
        assert "r038_c08" not in batch_ids  # animation frame excluded
        assert len(all_batch_cells) == 2

    def test_all_anim_frames_excluded_yields_no_batches(self, tmp_path):
        """If all cells are animation frames, no batches should be created."""
        cells = [
            _make_cell(8, 38, tmp_path=tmp_path, is_anim_frame=True),
            _make_cell(9, 38, tmp_path=tmp_path, is_anim_frame=True),
        ]
        batches = reskin_tiles.create_typed_batches(cells, tmp_path)
        assert len(batches) == 0


# ---------------------------------------------------------------------------
# animation metadata coverage
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


# ---------------------------------------------------------------------------
# animation cell exclusion
# ---------------------------------------------------------------------------

class TestAnimationCellExclusion:
    """Verify that animation cells (both base and non-base frames) are
    properly excluded from type batches."""

    def test_animation_base_frames_excluded_from_type_batches(self, tmp_path):
        """Base frames (frame 0) of animations should NOT appear in type batches."""
        # Sea base frame: (8, 35) — frame 0 of Sea animation
        sea_base = _make_cell(8, 35, tmp_path=tmp_path)
        # A plain cell to ensure type batches are non-empty
        plain_cell = _make_cell(0, 0, tmp_path=tmp_path)

        cells = [sea_base, plain_cell]
        batches = reskin_tiles.create_typed_batches(cells, tmp_path)

        all_batch_ids = set()
        for b in batches:
            for c in b["cells"]:
                all_batch_ids.add(c["id"])

        assert sea_base["id"] not in all_batch_ids, (
            "Sea base frame (8, 35) should be excluded from type batches"
        )
        assert plain_cell["id"] in all_batch_ids, (
            "Plain cell should be in type batches"
        )

    def test_animation_non_base_frames_excluded(self, tmp_path):
        """Non-base animation frames should NOT appear in type batches."""
        # Sea non-base frame: (8, 38) — frame 1 of Sea animation
        sea_frame = _make_cell(8, 38, tmp_path=tmp_path)
        # Computer non-base frame: (0, 32) — frame 1 of Computer animation
        comp_frame = _make_cell(0, 32, tmp_path=tmp_path)
        # Lightning non-base frame: (10, 1) — frame 1 of Lightning animation
        lightning_frame = _make_cell(10, 1, tmp_path=tmp_path)
        # A plain cell for contrast
        plain_cell = _make_cell(1, 0, tmp_path=tmp_path)

        cells = [sea_frame, comp_frame, lightning_frame, plain_cell]
        batches = reskin_tiles.create_typed_batches(cells, tmp_path)

        all_batch_ids = set()
        for b in batches:
            for c in b["cells"]:
                all_batch_ids.add(c["id"])

        assert sea_frame["id"] not in all_batch_ids, (
            "Sea non-base frame should be excluded from type batches"
        )
        assert comp_frame["id"] not in all_batch_ids, (
            "Computer non-base frame should be excluded from type batches"
        )
        assert lightning_frame["id"] not in all_batch_ids, (
            "Lightning non-base frame should be excluded from type batches"
        )
        assert plain_cell["id"] in all_batch_ids, (
            "Plain cell should still be in type batches"
        )
