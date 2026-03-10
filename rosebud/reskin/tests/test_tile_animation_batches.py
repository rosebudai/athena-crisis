"""Focused tests extracted from the former monolithic tile pipeline suite."""

from .tile_pipeline_test_support import *

class TestAnimationBatches:
    """Tests for animation-specific batch creation via build_animation_batches."""

    def _make_all_anim_cells(self, tmp_path):
        """Create cells for ALL positions in the _anim_cell_map (base + non-base)."""
        cells = []
        if reskin_tiles._anim_cell_map is None:
            reskin_tiles._build_anim_cell_map_conservative()
        for (col, row), (anim_name, frame_idx, cell_idx) in reskin_tiles._anim_cell_map.items():
            cells.append(_make_cell(col, row, tmp_path=tmp_path))
        return cells

    def test_build_animation_batches_creates_batches(self, tmp_path):
        """build_animation_batches should create at least one batch."""
        cells = self._make_all_anim_cells(tmp_path)
        batches = reskin_tiles.build_animation_batches(cells, tmp_path)
        assert len(batches) > 0, "Expected at least one animation batch"

    def test_animation_batch_has_correct_metadata(self, tmp_path):
        """Each animation batch should have is_animation_batch, anim_name,
        frame_indices, and cells_per_frame fields."""
        cells = self._make_all_anim_cells(tmp_path)
        batches = reskin_tiles.build_animation_batches(cells, tmp_path)
        for b in batches:
            assert b["is_animation_batch"] is True, (
                f"Batch {b['batch_id']} missing is_animation_batch flag"
            )
            assert "anim_name" in b, f"Batch {b['batch_id']} missing anim_name"
            assert isinstance(b["anim_name"], str)
            assert "frame_indices" in b, f"Batch {b['batch_id']} missing frame_indices"
            assert isinstance(b["frame_indices"], list)
            assert len(b["frame_indices"]) > 0
            assert "cells_per_frame" in b, f"Batch {b['batch_id']} missing cells_per_frame"
            assert b["cells_per_frame"] >= 1
            assert "batch_family" in b, f"Batch {b['batch_id']} missing batch_family"
            assert "layout_strategy" in b, f"Batch {b['batch_id']} missing layout_strategy"
            assert b["layout_strategy"] == "frame_strip"

    def test_frames_as_columns_layout(self, tmp_path):
        """grid_col in batch cells should correspond to the frame index position
        within the sub-batch's frame_indices list."""
        cells = self._make_all_anim_cells(tmp_path)
        batches = reskin_tiles.build_animation_batches(cells, tmp_path)
        for b in batches:
            n_cols = b["cols"]
            assert n_cols == len(b["frame_indices"]), (
                f"Batch {b['batch_id']}: cols ({n_cols}) != "
                f"len(frame_indices) ({len(b['frame_indices'])})"
            )
            for c in b["cells"]:
                assert 0 <= c["grid_col"] < n_cols, (
                    f"Cell grid_col {c['grid_col']} out of range [0, {n_cols})"
                )

    def test_large_animation_sub_batching(self, tmp_path):
        """River (24 frames) should be split into sub-batches of at most 6 frames."""
        cells = self._make_all_anim_cells(tmp_path)
        batches = reskin_tiles.build_animation_batches(cells, tmp_path)
        river_batches = [b for b in batches if b["anim_name"] == "River"]
        assert len(river_batches) > 1, (
            f"River (24 frames) should produce multiple sub-batches, got {len(river_batches)}"
        )
        for b in river_batches:
            assert len(b["frame_indices"]) <= 6, (
                f"Sub-batch {b['batch_id']} has {len(b['frame_indices'])} frames, max is 6"
            )

    def test_sub_batch_includes_frame_zero_reference(self, tmp_path):
        """Each River sub-batch should include frame 0 as a reference column."""
        cells = self._make_all_anim_cells(tmp_path)
        batches = reskin_tiles.build_animation_batches(cells, tmp_path)
        river_batches = [b for b in batches if b["anim_name"] == "River"]
        for b in river_batches:
            assert 0 in b["frame_indices"], (
                f"Sub-batch {b['batch_id']} missing frame 0 reference: {b['frame_indices']}"
            )

    def test_no_overlap_with_type_batches(self, tmp_path):
        """Animation cells should not appear in type batches."""
        cells = self._make_all_anim_cells(tmp_path)
        # Also add some non-animation cells for type batches
        cells.append(_make_cell(0, 0, tmp_path=tmp_path))  # plain
        cells.append(_make_cell(1, 0, tmp_path=tmp_path))  # plain

        anim_batches = reskin_tiles.build_animation_batches(cells, tmp_path)
        type_batches = reskin_tiles.create_typed_batches(cells, tmp_path)

        anim_cell_ids = set()
        for b in anim_batches:
            for c in b["cells"]:
                anim_cell_ids.add(c["id"])

        type_cell_ids = set()
        for b in type_batches:
            for c in b["cells"]:
                type_cell_ids.add(c["id"])

        overlap = anim_cell_ids & type_cell_ids
        assert len(overlap) == 0, (
            f"{len(overlap)} cells appear in both animation and type batches: "
            f"{list(overlap)[:10]}"
        )

    def test_all_cells_covered(self, tmp_path):
        """Type batches + animation batches should cover all TILE_CELL_MAP cells
        that have a corresponding extracted cell."""
        # Build cells for all mapped positions
        all_cells = []
        for (col, row), cell_type in reskin_tiles.TILE_CELL_MAP.items():
            all_cells.append(_make_cell(col, row, tmp_path=tmp_path))

        anim_batches = reskin_tiles.build_animation_batches(all_cells, tmp_path)
        type_batches = reskin_tiles.create_typed_batches(all_cells, tmp_path)

        batched_ids = set()
        for b in anim_batches:
            for c in b["cells"]:
                batched_ids.add(c["id"])
        for b in type_batches:
            for c in b["cells"]:
                batched_ids.add(c["id"])

        all_ids = {c["id"] for c in all_cells}

        missing = all_ids - batched_ids
        assert len(missing) == 0, (
            f"{len(missing)} cells not covered by any batch: {list(missing)[:20]}"
        )

    def test_anim_cell_map_covers_all_animations(self):
        """_build_anim_cell_map_conservative should map entries for every
        animation name in ANIMATED_TILES (except those fully shadowed by
        earlier entries due to cell overlap, e.g. Computer overlaps Pier)."""
        if reskin_tiles._anim_cell_map is None:
            reskin_tiles._build_anim_cell_map_conservative()

        anim_names_in_map = {v[0] for v in reskin_tiles._anim_cell_map.values()}
        anim_names_in_tiles = {entry[0] for entry in reskin_tiles.ANIMATED_TILES}

        # Computer's cells are fully overlapped by Pier (processed earlier),
        # so it won't appear in the map.  This is expected.
        known_shadowed = {"Computer"}
        missing = anim_names_in_tiles - anim_names_in_map - known_shadowed
        assert len(missing) == 0, (
            f"_anim_cell_map is missing animations: {missing}"
        )
        # Verify the map has the majority of animation types
        assert len(anim_names_in_map) >= len(anim_names_in_tiles) - len(known_shadowed)

    def test_anim_prompt_template_has_placeholders(self):
        """ANIM_BATCH_PROMPT_TEMPLATE should contain required placeholders."""
        tmpl = reskin_tiles.ANIM_BATCH_PROMPT_TEMPLATE
        assert "{style_sheet_instruction}" in tmpl, "Missing {style_sheet_instruction}"
        assert "{cell_legend}" in tmpl, "Missing {cell_legend}"

    def test_build_animation_batches_uses_anim_cell_idx_for_rows(self, tmp_path):
        """Animation batch row placement should respect anim_cell_idx values."""
        cells = self._make_all_anim_cells(tmp_path)

        removed = False
        filtered_cells = []
        for cell in cells:
            if (
                cell["anim_name"] == "Sea"
                and cell["anim_frame_idx"] == 1
                and cell["anim_cell_idx"] == 0
                and not removed
            ):
                removed = True
                continue
            filtered_cells.append(cell)

        assert removed, "Expected to remove one Sea frame-1 cell for sparse-row test"

        batches = reskin_tiles.build_animation_batches(filtered_cells, tmp_path)
        sea_batch = next(
            b for b in batches
            if b["anim_name"] == "Sea" and 1 in b["frame_indices"]
        )

        frame_col = sea_batch["frame_indices"].index(1)
        target_cell = next(
            c for c in sea_batch["cells"]
            if c["anim_name"] == "Sea"
            and c["anim_frame_idx"] == 1
            and c["anim_cell_idx"] == 1
        )

        assert target_cell["grid_col"] == frame_col
        assert target_cell["grid_row"] == 1

    def test_build_animation_batches_cleans_stale_anim_outputs(self, tmp_path):
        """Old anim_* artifacts in the work dir should be removed before rebuild."""
        stale_dir = tmp_path / "anim_old_batch"
        stale_dir.mkdir()
        stale_file = tmp_path / "batches" / "anim_old.png"
        stale_file.parent.mkdir()
        stale_file.write_bytes(b"stale")

        cells = self._make_all_anim_cells(tmp_path)
        reskin_tiles.build_animation_batches(cells, tmp_path)

        assert not stale_dir.exists()
        assert not stale_file.exists()

    def test_sea_object_animation_families_get_explicit_batch_families(self, tmp_path):
        """Sea-object animation families should emit dedicated animation batches."""
        cells = [
            _make_cell(5, 22, tmp_path=tmp_path),
            _make_cell(6, 22, tmp_path=tmp_path),
            _make_cell(5, 23, tmp_path=tmp_path),
            _make_cell(6, 23, tmp_path=tmp_path),
            _make_cell(5, 24, tmp_path=tmp_path),
            _make_cell(6, 25, tmp_path=tmp_path),
            _make_cell(6, 27, tmp_path=tmp_path),
            _make_cell(5, 26, tmp_path=tmp_path),
            _make_cell(6, 26, tmp_path=tmp_path),
        ]

        batches = reskin_tiles.build_animation_batches(cells, tmp_path)

        families_by_anim = {b["anim_name"]: b["batch_family"] for b in batches}
        assert families_by_anim["Iceberg/Weeds"] == "sea_object_iceberg_weeds_anim"
        assert families_by_anim["Island"] == "sea_object_island_anim"
        assert families_by_anim["GasBubbles"] == "sea_object_gas_bubbles_anim"

        island_batch = next(b for b in batches if b["anim_name"] == "Island")
        iceberg_batch = next(b for b in batches if b["anim_name"] == "Iceberg/Weeds")
        gas_batch = next(b for b in batches if b["anim_name"] == "GasBubbles")

        assert island_batch["cells_per_frame"] == 2
        assert iceberg_batch["cells_per_frame"] == 2
        assert gas_batch["cells_per_frame"] == 2
