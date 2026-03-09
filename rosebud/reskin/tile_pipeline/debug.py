from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .catalog import ATLAS_COLS, TILE_SIZE, TYPE_ABBREV

def _draw_outlined_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font,
    fill: str = "white",
    outline: str = "black",
    anchor: str | None = None,
) -> None:
    """Draw text with a 1px black outline for readability on any background."""
    x, y = xy
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), text, font=font, fill=outline, anchor=anchor)
    draw.text((x, y), text, font=font, fill=fill, anchor=anchor)


def generate_debug_atlas(
    atlas_path: Path,
    cells: list[dict],
    output_path: Path,
) -> Path:
    """Generate a labeled overlay PNG of the atlas for visual debugging.

    Each non-empty cell gets three text labels:
      - Top: row number (e.g. "r7")
      - Center: type abbreviation from TYPE_ABBREV
      - Bottom: col number (e.g. "c3")

    Animation frame cells use yellow text; static cells use white text.
    Text has a 1px black outline for visibility against any tile art.

    Parameters
    ----------
    atlas_path : Path
        Path to the atlas PNG to annotate.
    cells : list[dict]
        Cells manifest (list of dicts with row, col, type, is_anim_frame keys).
    output_path : Path
        Where to save the debug atlas PNG.

    Returns
    -------
    Path
        The output_path where the debug atlas was saved.
    """
    img = Image.open(atlas_path).convert("RGBA")

    # Build lookup: (row, col) -> cell info
    cell_lookup: dict[tuple[int, int], dict] = {}
    for cell in cells:
        cell_lookup[(cell["row"], cell["col"])] = cell

    # Set up fonts — use default PIL font (tiny but readable when zoomed)
    try:
        font_tiny = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 7
        )
    except Exception:
        font_tiny = ImageFont.load_default()

    try:
        font_type = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 7
        )
    except Exception:
        font_type = font_tiny

    # Create transparent overlay so annotations don't destroy original pixels
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    rows = img.size[1] // TILE_SIZE
    for row in range(rows):
        for col in range(ATLAS_COLS):
            cell = cell_lookup.get((row, col))
            if cell is None:
                continue

            x0 = col * TILE_SIZE
            y0 = row * TILE_SIZE
            cx = x0 + TILE_SIZE // 2
            cy = y0 + TILE_SIZE // 2

            is_anim = cell.get("is_anim_frame", False)
            text_color = "#ffff00" if is_anim else "white"

            # Row label at top-center
            _draw_outlined_text(
                draw, (cx, y0 + 1), f"r{row}",
                font_tiny, fill=text_color, anchor="mt",
            )

            # Terrain type abbreviation at center
            abbrev = TYPE_ABBREV.get(cell["type"], cell["type"][:3])
            _draw_outlined_text(
                draw, (cx, cy), abbrev,
                font_type, fill=text_color, anchor="mm",
            )

            # Column label at bottom-center
            _draw_outlined_text(
                draw, (cx, y0 + TILE_SIZE - 2), f"c{col}",
                font_tiny, fill=text_color, anchor="mb",
            )

    # Composite overlay onto atlas and save
    result = Image.alpha_composite(img, overlay)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path)
    print(f"  Debug atlas saved: {output_path}  ({result.size[0]}x{result.size[1]})")
    return output_path
