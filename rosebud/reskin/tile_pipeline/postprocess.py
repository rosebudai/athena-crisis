from __future__ import annotations

from PIL import Image

from .catalog import CELL_PADDING, GRID_LINE_WIDTH, TILE_SIZE


def extract_from_reskinned(
    reskinned_img: Image.Image,
    batch_meta: dict,
) -> list[tuple[dict, Image.Image]]:
    """Extract individual reskinned cells from the AI output grid.

    Uses proportional coordinate scaling to map expected grid positions
    to the AI output resolution, while restoring the original alpha masks.
    """
    scale_factor = batch_meta["scale_factor"]
    cell_w = batch_meta["cell_w"]
    cell_h = batch_meta["cell_h"]
    canvas_w = batch_meta["canvas_w"]
    canvas_h = batch_meta["canvas_h"]

    img_w, img_h = reskinned_img.size
    x_ratio = img_w / (canvas_w * scale_factor)
    y_ratio = img_h / (canvas_h * scale_factor)

    results: list[tuple[dict, Image.Image]] = []
    for cell_info in batch_meta["cells"]:
        row = cell_info["grid_row"]
        col = cell_info["grid_col"]

        cx = GRID_LINE_WIDTH + col * (cell_w + GRID_LINE_WIDTH)
        cy = GRID_LINE_WIDTH + row * (cell_h + GRID_LINE_WIDTH)
        tile_x = cx + CELL_PADDING
        tile_y = cy + CELL_PADDING

        sx = tile_x * scale_factor * x_ratio
        sy = tile_y * scale_factor * y_ratio
        sw = TILE_SIZE * scale_factor * x_ratio
        sh = TILE_SIZE * scale_factor * y_ratio

        tile_crop = reskinned_img.crop((
            int(round(sx)),
            int(round(sy)),
            int(round(sx + sw)),
            int(round(sy + sh)),
        ))
        tile_crop = tile_crop.resize((TILE_SIZE, TILE_SIZE), Image.NEAREST)

        original = Image.open(cell_info["path"]).convert("RGBA")
        r, g, b, _ = tile_crop.split()
        _, _, _, orig_alpha = original.split()
        tile_final = Image.merge("RGBA", (r, g, b, orig_alpha))

        results.append((cell_info, tile_final))

    return results
