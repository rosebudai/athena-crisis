"""Focused tests for the remaining non-repair postprocess helpers."""

from .tile_pipeline_test_support import *


class TestExtractFromReskinned:
    def test_extracts_tile_from_scaled_grid(self, tmp_path):
        ts = reskin_tiles.TILE_SIZE
        pad = reskin_tiles.CELL_PADDING
        glw = reskin_tiles.GRID_LINE_WIDTH
        cell_w = ts + pad * 2
        cell_h = cell_w
        canvas_w = cell_w + glw * 2
        canvas_h = cell_h + glw * 2
        scale_factor = 4

        original = Image.new("RGBA", (ts, ts), (10, 20, 30, 255))
        original_path = tmp_path / "cell.png"
        original.save(original_path)

        native = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 255))
        tile_color = (200, 150, 100, 255)
        for y in range(glw + pad, glw + pad + ts):
            for x in range(glw + pad, glw + pad + ts):
                native.putpixel((x, y), tile_color)

        reskinned_img = native.resize(
            (canvas_w * scale_factor, canvas_h * scale_factor),
            Image.NEAREST,
        )

        batch_meta = {
            "scale_factor": scale_factor,
            "cell_w": cell_w,
            "cell_h": cell_h,
            "canvas_w": canvas_w,
            "canvas_h": canvas_h,
            "cells": [{
                "grid_row": 0,
                "grid_col": 0,
                "path": str(original_path),
            }],
        }

        extracted = reskin_tiles.extract_from_reskinned(reskinned_img, batch_meta)

        assert len(extracted) == 1
        _, img = extracted[0]
        arr = np.array(img)
        np.testing.assert_array_equal(arr[ts // 2, ts // 2, :3], tile_color[:3])
        assert arr[:, :, 3].min() == 255

    def test_restores_original_alpha_mask(self, tmp_path):
        ts = reskin_tiles.TILE_SIZE
        pad = reskin_tiles.CELL_PADDING
        glw = reskin_tiles.GRID_LINE_WIDTH
        cell_w = ts + pad * 2
        cell_h = cell_w
        canvas_w = cell_w + glw * 2
        canvas_h = cell_h + glw * 2
        scale_factor = 4

        original_arr = np.zeros((ts, ts, 4), dtype=np.uint8)
        original_arr[: ts // 2, :] = [0, 0, 0, 255]
        original = Image.fromarray(original_arr)
        original_path = tmp_path / "cell.png"
        original.save(original_path)

        native = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 255))
        tile_color = (120, 180, 220, 255)
        for y in range(glw + pad, glw + pad + ts):
            for x in range(glw + pad, glw + pad + ts):
                native.putpixel((x, y), tile_color)

        reskinned_img = native.resize(
            (canvas_w * scale_factor, canvas_h * scale_factor),
            Image.NEAREST,
        )

        batch_meta = {
            "scale_factor": scale_factor,
            "cell_w": cell_w,
            "cell_h": cell_h,
            "canvas_w": canvas_w,
            "canvas_h": canvas_h,
            "cells": [{
                "grid_row": 0,
                "grid_col": 0,
                "path": str(original_path),
            }],
        }

        extracted = reskin_tiles.extract_from_reskinned(reskinned_img, batch_meta)

        _, img = extracted[0]
        arr = np.array(img)
        assert arr[: ts // 2, :, 3].min() == 255
        assert arr[ts // 2 :, :, 3].max() == 0


class TestExtractPlainTileFromAnchor:
    def _make_anchor_image(self, path: Path, color: tuple[int, int, int, int]):
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

    def test_extracts_expected_tile_size(self, tmp_path):
        anchor_path = tmp_path / "anchor_plain.png"
        self._make_anchor_image(anchor_path, (200, 150, 100, 255))

        result = reskin_tiles._extract_plain_tile_from_anchor(str(anchor_path))

        assert result.size == (reskin_tiles.TILE_SIZE, reskin_tiles.TILE_SIZE)

    def test_extracts_tile_color_without_grid_or_padding_leak(self, tmp_path):
        tile_color = (50, 100, 200, 255)
        anchor_path = tmp_path / "anchor_plain.png"
        self._make_anchor_image(anchor_path, tile_color)

        result = reskin_tiles._extract_plain_tile_from_anchor(str(anchor_path))
        arr = np.array(result)

        np.testing.assert_array_equal(arr[reskin_tiles.TILE_SIZE // 2, reskin_tiles.TILE_SIZE // 2], tile_color)
        black_mask = (arr[:, :, 0] == 0) & (arr[:, :, 1] == 0) & (arr[:, :, 2] == 0)
        gray_mask = (arr[:, :, 0] == 200) & (arr[:, :, 1] == 200) & (arr[:, :, 2] == 200)
        assert not black_mask.any()
        assert not gray_mask.any()
