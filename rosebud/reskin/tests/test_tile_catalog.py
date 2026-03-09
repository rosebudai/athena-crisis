"""Focused tests extracted from the former monolithic tile pipeline suite."""

from .tile_pipeline_test_support import *

class TestClassifyCell:
    """Tests for per-cell classification via TILE_CELL_MAP lookup."""

    def test_plain_cells(self):
        assert reskin_tiles.classify_cell(0, 0) == "plain"
        assert reskin_tiles.classify_cell(2, 2) == "plain"
        assert reskin_tiles.classify_cell(4, 1) == "plain"

    def test_street_cells(self):
        assert reskin_tiles.classify_cell(3, 3) == "street"
        assert reskin_tiles.classify_cell(0, 5) == "street"

    def test_mountain_cells(self):
        assert reskin_tiles.classify_cell(3, 7) == "mountain"
        assert reskin_tiles.classify_cell(0, 12) == "mountain"

    def test_forest_cells(self):
        assert reskin_tiles.classify_cell(0, 19) == "forest"
        assert reskin_tiles.classify_cell(4, 25) == "forest"

    def test_campsite_cells(self):
        assert reskin_tiles.classify_cell(0, 28) == "campsite"
        assert reskin_tiles.classify_cell(2, 28) == "campsite"

    def test_pier_cells(self):
        assert reskin_tiles.classify_cell(0, 29) == "pier"
        assert reskin_tiles.classify_cell(0, 34) == "pier"

    def test_water_cells_include_sea_and_beach(self):
        """Water type covers sea (rows 34-58 cols 7-11) and beach (rows 49-72)."""
        assert reskin_tiles.classify_cell(7, 34) == "water"
        assert reskin_tiles.classify_cell(0, 50) == "water"
        assert reskin_tiles.classify_cell(0, 62) == "water"
        assert reskin_tiles.classify_cell(0, 68) == "water"
        assert reskin_tiles.classify_cell(0, 72) == "water"

    def test_river_cells(self):
        assert reskin_tiles.classify_cell(0, 73) == "river"
        assert reskin_tiles.classify_cell(0, 100) == "river"
        assert reskin_tiles.classify_cell(0, 144) == "river"

    def test_stormcloud_cells(self):
        """StormCloud cells (cols 5-8, rows 6-17) classified as stormcloud, NOT mountain."""
        assert reskin_tiles.classify_cell(5, 7) == "stormcloud"
        assert reskin_tiles.classify_cell(6, 7) == "stormcloud"
        assert reskin_tiles.classify_cell(8, 10) == "stormcloud"

    def test_reef_cells(self):
        """Reef cells classified as reef, NOT forest."""
        assert reskin_tiles.classify_cell(5, 18) == "reef"
        assert reskin_tiles.classify_cell(6, 19) == "reef"
        assert reskin_tiles.classify_cell(8, 21) == "reef"

    def test_sea_object_cells(self):
        """Iceberg/Weeds/Island/GasBubbles classified as sea_object, NOT forest."""
        assert reskin_tiles.classify_cell(5, 22) == "sea_object"
        assert reskin_tiles.classify_cell(6, 23) == "sea_object"
        assert reskin_tiles.classify_cell(5, 26) == "sea_object"

    def test_trench_cells(self):
        """Trench cells classified as trench, NOT mountain."""
        assert reskin_tiles.classify_cell(0, 15) == "trench"
        assert reskin_tiles.classify_cell(1, 16) == "trench"

    def test_bridge_cells(self):
        assert reskin_tiles.classify_cell(8, 1) == "bridge"
        assert reskin_tiles.classify_cell(8, 4) == "bridge"

    def test_rail_cells(self):
        assert reskin_tiles.classify_cell(5, 0) == "rail"
        assert reskin_tiles.classify_cell(10, 28) == "rail"

    def test_teleporter_cells(self):
        assert reskin_tiles.classify_cell(0, 26) == "teleporter"
        assert reskin_tiles.classify_cell(3, 26) == "teleporter"

    def test_computer_cells(self):
        assert reskin_tiles.classify_cell(0, 31) == "computer"
        assert reskin_tiles.classify_cell(1, 31) == "computer"

    def test_lightning_cells(self):
        assert reskin_tiles.classify_cell(10, 0) == "lightning"
        assert reskin_tiles.classify_cell(10, 6) == "lightning"

    def test_pipe_cells(self):
        assert reskin_tiles.classify_cell(0, 27) == "pipe"
        assert reskin_tiles.classify_cell(3, 28) == "pipe"

    def test_floatingedge_cells(self):
        assert reskin_tiles.classify_cell(9, 12) == "floatingedge"
        assert reskin_tiles.classify_cell(10, 20) == "floatingedge"

    def test_unmapped_returns_none(self):
        """Cells not in the map return None."""
        assert reskin_tiles.classify_cell(99, 99) is None
        assert reskin_tiles.classify_cell(4, 0) is None  # c4 r0 is not occupied
        assert reskin_tiles.classify_cell(0, 145) is None  # beyond atlas rows

    def test_tile_cell_map_completeness(self):
        """TILE_CELL_MAP should have 1226 entries matching all Tiles0 occupied cells."""
        assert len(reskin_tiles.TILE_CELL_MAP) == 1226


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

class TestTileDescriptionsExistForStreetSubtypes:
    """Verify TILE_DESCRIPTIONS has entries for all street sub-type groups."""

    def _cells_of_type(self, tile_type):
        """Return all (col, row) pairs in TILE_CELL_MAP with the given type."""
        return [
            pos for pos, t in reskin_tiles.TILE_CELL_MAP.items()
            if t == tile_type
        ]

    def test_street_cells_have_descriptions(self):
        """At least some street cells should have TILE_DESCRIPTIONS entries."""
        street_cells = self._cells_of_type("street")
        assert len(street_cells) > 0, "No street cells found in TILE_CELL_MAP"
        described = [
            pos for pos in street_cells
            if pos in reskin_tiles.TILE_DESCRIPTIONS
        ]
        assert len(described) > 0, "No street cells have TILE_DESCRIPTIONS"
        # All street cells should be covered
        assert len(described) == len(street_cells), (
            f"Missing descriptions for street cells: "
            f"{set(street_cells) - set(described)}"
        )

    def test_rail_cells_have_descriptions(self):
        """At least some rail cells should have TILE_DESCRIPTIONS entries."""
        rail_cells = self._cells_of_type("rail")
        assert len(rail_cells) > 0, "No rail cells found in TILE_CELL_MAP"
        described = [
            pos for pos in rail_cells
            if pos in reskin_tiles.TILE_DESCRIPTIONS
        ]
        assert len(described) > 0, "No rail cells have TILE_DESCRIPTIONS"

    def test_trench_cells_have_descriptions(self):
        """At least some trench cells should have TILE_DESCRIPTIONS entries."""
        trench_cells = self._cells_of_type("trench")
        assert len(trench_cells) > 0, "No trench cells found in TILE_CELL_MAP"
        described = [
            pos for pos in trench_cells
            if pos in reskin_tiles.TILE_DESCRIPTIONS
        ]
        assert len(described) > 0, "No trench cells have TILE_DESCRIPTIONS"
        assert len(described) == len(trench_cells), (
            f"Missing descriptions for trench cells: "
            f"{set(trench_cells) - set(described)}"
        )

    def test_bridge_cells_have_descriptions(self):
        """At least some bridge cells should have TILE_DESCRIPTIONS entries."""
        bridge_cells = self._cells_of_type("bridge")
        assert len(bridge_cells) > 0, "No bridge cells found in TILE_CELL_MAP"
        described = [
            pos for pos in bridge_cells
            if pos in reskin_tiles.TILE_DESCRIPTIONS
        ]
        assert len(described) > 0, "No bridge cells have TILE_DESCRIPTIONS"
        assert len(described) == len(bridge_cells), (
            f"Missing descriptions for bridge cells: "
            f"{set(bridge_cells) - set(described)}"
        )

    def test_pipe_cells_have_descriptions(self):
        """At least some pipe cells should have TILE_DESCRIPTIONS entries."""
        pipe_cells = self._cells_of_type("pipe")
        assert len(pipe_cells) > 0, "No pipe cells found in TILE_CELL_MAP"
        described = [
            pos for pos in pipe_cells
            if pos in reskin_tiles.TILE_DESCRIPTIONS
        ]
        assert len(described) > 0, "No pipe cells have TILE_DESCRIPTIONS"
        assert len(described) == len(pipe_cells), (
            f"Missing descriptions for pipe cells: "
            f"{set(pipe_cells) - set(described)}"
        )

    def test_computer_cells_have_descriptions(self):
        """At least some computer cells should have TILE_DESCRIPTIONS entries."""
        computer_cells = self._cells_of_type("computer")
        assert len(computer_cells) > 0, "No computer cells found in TILE_CELL_MAP"
        described = [
            pos for pos in computer_cells
            if pos in reskin_tiles.TILE_DESCRIPTIONS
        ]
        assert len(described) > 0, "No computer cells have TILE_DESCRIPTIONS"
        assert len(described) == len(computer_cells), (
            f"Missing descriptions for computer cells: "
            f"{set(computer_cells) - set(described)}"
        )

    def test_descriptions_are_nonempty_strings(self):
        """All TILE_DESCRIPTIONS values must be non-empty strings."""
        for key, desc in reskin_tiles.TILE_DESCRIPTIONS.items():
            assert isinstance(desc, str), f"Description for {key} is not a string"
            assert len(desc.strip()) > 0, f"Description for {key} is empty"

    def test_all_described_positions_are_in_tile_cell_map(self):
        """Every position in TILE_DESCRIPTIONS must also exist in TILE_CELL_MAP."""
        for pos in reskin_tiles.TILE_DESCRIPTIONS:
            assert pos in reskin_tiles.TILE_CELL_MAP, (
                f"TILE_DESCRIPTIONS has position {pos} not in TILE_CELL_MAP"
            )


# ---------------------------------------------------------------------------
# build_cell_legend
# ---------------------------------------------------------------------------
