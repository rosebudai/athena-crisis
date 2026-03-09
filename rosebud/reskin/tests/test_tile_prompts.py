"""Focused tests extracted from the former monolithic tile pipeline suite."""

from .tile_pipeline_test_support import *

class TestCellLegendGeneration:
    """Verify build_cell_legend correctly builds legends from TILE_DESCRIPTIONS."""

    def test_legend_with_described_cells(self):
        """Cells with TILE_DESCRIPTIONS entries produce a numbered legend."""
        cells = [
            {"col": 0, "row": 3},  # street top-left corner
            {"col": 3, "row": 3},  # street horizontal
        ]
        legend = reskin_tiles.build_cell_legend(cells, "street")
        assert "The tiles in the grid are" in legend
        assert '1. "road top-left corner' in legend
        assert '2. "road straight horizontal' in legend

    def test_legend_with_no_descriptions(self):
        """Cells with no TILE_DESCRIPTIONS entries produce empty string."""
        cells = [
            {"col": 99, "row": 99},
            {"col": 98, "row": 98},
        ]
        legend = reskin_tiles.build_cell_legend(cells, "water")
        assert legend == ""

    def test_legend_mixed_described_and_default(self):
        """Mix of described and undescribed cells uses default for unknowns."""
        cells = [
            {"col": 0, "row": 3},   # has description
            {"col": 99, "row": 99},  # no description -> default
        ]
        legend = reskin_tiles.build_cell_legend(cells, "street")
        assert legend != ""
        assert '1. "road top-left corner' in legend
        assert '2. "street tile"' in legend

    def test_legend_single_cell(self):
        """A single described cell should produce a one-line legend."""
        cells = [{"col": 0, "row": 31}]  # computer terminal base
        legend = reskin_tiles.build_cell_legend(cells, "computer")
        assert "The tiles in the grid are" in legend
        assert '1. "computer terminal base' in legend

    def test_legend_empty_cells_list(self):
        """An empty cells list should produce empty string."""
        legend = reskin_tiles.build_cell_legend([], "plain")
        assert legend == ""

    def test_legend_numbering_sequential(self):
        """Legend numbering should be 1-based and sequential."""
        cells = [
            {"col": 0, "row": 3},
            {"col": 1, "row": 3},
            {"col": 2, "row": 3},
        ]
        legend = reskin_tiles.build_cell_legend(cells, "street")
        assert "1. " in legend
        assert "2. " in legend
        assert "3. " in legend


# ---------------------------------------------------------------------------
# generate_style_reference_sheet
# ---------------------------------------------------------------------------

class TestGenerateStyleReferenceSheet:
    """Tests for style reference sheet generation."""

    def _make_anchor(self, path: Path, color: tuple):
        """Create a synthetic anchor image (single-cell grid at 4x scale)."""
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

        scaled = native_img.resize((native_w * 4, native_h * 4), Image.NEAREST)
        scaled.save(path)

    def test_creates_file(self, tmp_path):
        """generate_style_reference_sheet should create the sheet PNG."""
        anchor_paths = {}
        for t in ("plain", "water", "forest"):
            p = tmp_path / f"anchor_{t}.png"
            self._make_anchor(p, (100, 150, 200, 255))
            anchor_paths[t] = str(p)

        sheet_path = reskin_tiles.generate_style_reference_sheet(
            anchor_paths, tmp_path,
        )

        assert sheet_path.exists()
        assert sheet_path.name == "style_reference_sheet.png"

    def test_output_dimensions_reasonable(self, tmp_path):
        """Sheet dimensions should scale with the number of anchors."""
        anchor_paths = {}
        for t in ("plain", "street", "mountain", "forest", "water"):
            p = tmp_path / f"anchor_{t}.png"
            self._make_anchor(p, (80, 120, 160, 255))
            anchor_paths[t] = str(p)

        sheet_path = reskin_tiles.generate_style_reference_sheet(
            anchor_paths, tmp_path,
        )

        img = Image.open(sheet_path)
        # 5 anchors -> 5 cols x 1 row, each cell 120px wide + margin
        # Width should be around 5*120 + 8 = 608
        assert img.width >= 5 * 120
        assert img.height >= 120  # at least one row of tiles + labels

    def test_all_anchor_types_present(self, tmp_path):
        """Sheet should include all provided anchor types."""
        types_to_create = [
            "plain", "street", "mountain", "forest", "campsite",
            "pier", "water", "river", "stormcloud", "teleporter",
        ]
        anchor_paths = {}
        for t in types_to_create:
            p = tmp_path / f"anchor_{t}.png"
            self._make_anchor(p, (60 + hash(t) % 100, 100, 150, 255))
            anchor_paths[t] = str(p)

        sheet_path = reskin_tiles.generate_style_reference_sheet(
            anchor_paths, tmp_path,
        )

        img = Image.open(sheet_path)
        # 10 anchors -> 5 cols x 2 rows
        # Height should accommodate 2 rows
        assert img.height >= 2 * 120

    def test_single_anchor(self, tmp_path):
        """Sheet should work with a single anchor."""
        p = tmp_path / "anchor_plain.png"
        self._make_anchor(p, (100, 200, 50, 255))
        anchor_paths = {"plain": str(p)}

        sheet_path = reskin_tiles.generate_style_reference_sheet(
            anchor_paths, tmp_path,
        )

        assert sheet_path.exists()
        img = Image.open(sheet_path)
        assert img.width > 0
        assert img.height > 0

    def test_empty_anchor_paths_raises(self, tmp_path):
        """Empty anchor_paths should raise ValueError."""
        with pytest.raises(ValueError, match="No anchor paths"):
            reskin_tiles.generate_style_reference_sheet({}, tmp_path)

    def test_includes_rail_when_present(self, tmp_path):
        """Rail anchor should be included in the sheet when available."""
        anchor_paths = {}
        for t in ("plain", "rail"):
            p = tmp_path / f"anchor_{t}.png"
            self._make_anchor(p, (100, 150, 200, 255))
            anchor_paths[t] = str(p)

        sheet_path = reskin_tiles.generate_style_reference_sheet(
            anchor_paths, tmp_path,
        )

        assert sheet_path.exists()
        img = Image.open(sheet_path)
        # 2 anchors -> 2 cols x 1 row
        assert img.width >= 2 * 120


# ---------------------------------------------------------------------------
# style_sheet_instruction in prompt templates
# ---------------------------------------------------------------------------

class TestStyleSheetInstructionInPrompts:
    """Verify {style_sheet_instruction} placeholder exists in all templates."""

    def test_anchor_prompt_has_placeholder(self):
        assert "{style_sheet_instruction}" in reskin_tiles.ANCHOR_PROMPT_TEMPLATE

    def test_batch_prompt_has_placeholder(self):
        assert "{style_sheet_instruction}" in reskin_tiles.BATCH_PROMPT_TEMPLATE

    def test_multi_anchor_batch_prompt_has_placeholder(self):
        assert "{style_sheet_instruction}" in reskin_tiles.MULTI_ANCHOR_BATCH_PROMPT_TEMPLATE

    def test_empty_instruction_produces_clean_prompt(self):
        """When style_sheet_instruction is empty, prompt should not have
        leading whitespace or artifacts."""
        prompt = reskin_tiles.BATCH_PROMPT_TEMPLATE.format(
            style_sheet_instruction="",
            type_name="water",
            type_hint="",
            theme_prompt="cozy autumn",
            cell_legend="",
        )
        assert prompt.startswith("Reskin the tiles")

    def test_instruction_prepended_when_provided(self):
        """When style_sheet_instruction is set, it should appear at the
        start of the prompt."""
        instruction = (
            "The first image is a world style reference showing all terrain "
            "types in this theme. Your output must visually belong in this "
            "world — match the overall color temperature, shading style, "
            "and level of detail. "
        )
        prompt = reskin_tiles.BATCH_PROMPT_TEMPLATE.format(
            style_sheet_instruction=instruction,
            type_name="water",
            type_hint="",
            theme_prompt="cozy autumn",
            cell_legend="",
        )
        assert prompt.startswith("The first image is a world style reference")


# ---------------------------------------------------------------------------
# build_animation_batches
# ---------------------------------------------------------------------------

class TestReskinBatchGemini:
    """Focused tests for prompt routing in reskin_batch_gemini."""

    def test_animation_batches_use_anim_prompt_without_anchors(self, tmp_path, monkeypatch):
        """Animation batches should use the animation prompt even without anchors."""
        batch_path = tmp_path / "batch.png"
        Image.new("RGBA", (24, 24), (10, 20, 30, 255)).save(batch_path)

        seen = {}

        class _FakePart:
            def __init__(self, data=None, mime_type=None):
                self.inline_data = types.SimpleNamespace(data=data, mime_type=mime_type)

            @classmethod
            def from_bytes(cls, data, mime_type):
                return cls(data=data, mime_type=mime_type)

        class _FakeResponse:
            def __init__(self):
                buf = io.BytesIO()
                Image.new("RGBA", (24, 24), (1, 2, 3, 255)).save(buf, format="PNG")
                image_part = types.SimpleNamespace(
                    inline_data=types.SimpleNamespace(data=buf.getvalue(), mime_type="image/png")
                )
                self.candidates = [types.SimpleNamespace(content=types.SimpleNamespace(parts=[image_part]))]

        class _FakeModels:
            def generate_content(self, *, contents, **kwargs):
                seen["contents"] = contents
                return _FakeResponse()

        class _FakeClient:
            def __init__(self, api_key):
                self.models = _FakeModels()

        fake_genai = types.ModuleType("google.genai")
        fake_genai.Client = _FakeClient
        fake_genai.types = types.SimpleNamespace(
            Part=_FakePart,
            GenerateContentConfig=lambda **kwargs: kwargs,
        )
        fake_google = types.ModuleType("google")
        fake_google.genai = fake_genai

        monkeypatch.setitem(sys.modules, "google", fake_google)
        monkeypatch.setitem(sys.modules, "google.genai", fake_genai)
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")

        image = reskin_tiles.reskin_batch_gemini(
            batch_path=str(batch_path),
            theme={"prompt": "cozy"},
            batch_id="anim_test",
            tile_type="water",
            anchor_paths=None,
            is_animation_batch=True,
        )

        assert image is not None
        assert seen["contents"][0] == reskin_tiles.ANIM_BATCH_PROMPT_TEMPLATE.format(
            cell_legend="",
            style_sheet_instruction="",
        )


# ---------------------------------------------------------------------------
# Animation cell exclusion from type batches
# ---------------------------------------------------------------------------
