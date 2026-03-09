from __future__ import annotations

from .catalog import TILE_DESCRIPTIONS

def build_cell_legend(cells: list[dict], type_name: str) -> str:
    """Build a numbered cell legend string from TILE_DESCRIPTIONS.

    Parameters
    ----------
    cells : list[dict]
        Cell info dicts (must contain ``col`` and ``row`` keys).
    type_name : str
        Fallback tile type name used when a cell has no entry in
        TILE_DESCRIPTIONS.

    Returns
    -------
    str
        A formatted legend string, or empty string if no cell in
        *cells* has an entry in TILE_DESCRIPTIONS.
    """
    descriptions: list[str] = []
    has_real_desc = False
    for cell in cells:
        key = (cell["col"], cell["row"])
        desc = TILE_DESCRIPTIONS.get(key)
        if desc:
            has_real_desc = True
            descriptions.append(desc)
        else:
            descriptions.append(f"{type_name} tile")

    if not has_real_desc:
        return ""

    lines = [f'{i + 1}. "{d}"' for i, d in enumerate(descriptions)]
    return (
        "\nThe tiles in the grid are (left-to-right, top-to-bottom):\n"
        + "\n".join(lines)
        + "\n"
    )

# Type-specific prompt hints
TILE_TYPE_HINTS = {
    "plain": (
        "These are GRASS and PLAIN terrain tiles. They are flat ground tiles "
        "that tile seamlessly together. Keep them as simple, flat ground with "
        "subtle texture variation. All tiles in this batch must use the SAME "
        "base green tone so they blend together seamlessly when placed adjacent."
    ),
    "street": (
        "These are ROAD/STREET tiles showing paved paths with various "
        "connections (straight, corners, intersections, dead-ends). "
        "Keep the road width, line markings, and edge style CONSISTENT "
        "across all tiles. Roads must connect seamlessly at tile edges."
    ),
    "mountain": (
        "These are MOUNTAIN terrain tiles showing rocky peaks and elevated "
        "terrain. Keep the rock texture, snow caps, and shading style "
        "CONSISTENT across all tiles. Mountains connect to form ranges. "
        "Mountain tiles form connected ranges — ensure rock textures flow "
        "seamlessly across tile boundaries with no visible seams or "
        "flat-colored rectangular blocks. Snow caps and rock faces should "
        "blend naturally where tiles meet."
    ),
    "forest": (
        "These are FOREST/TREE tiles showing various tree arrangements "
        "(single trees, connected forests, edges). Keep the tree style, "
        "leaf color, and trunk style CONSISTENT. The ground beneath trees "
        "must match the plain grass tone."
    ),
    "campsite": (
        "These are CAMPSITE tiles showing camp structures and fire pits. "
        "Keep the warm, inviting aesthetic consistent."
    ),
    "pier": (
        "These are PIER/DOCK tiles showing wooden structures extending "
        "over water. Keep the wood texture and water style consistent. "
        "Piers connect to form walkways. "
        "Border tiles must transition smoothly into adjacent terrain. "
        "Where borders meet water, match the water style exactly. "
        "Where borders meet grass, match the grass tone exactly."
    ),
    "water": (
        "These are WATER tiles including open ocean (SEA), deep ocean, "
        "and coastline transitions (BEACH). Keep the water color, wave pattern, "
        "and foam style IDENTICAL across ALL tiles — sea, deep sea, and beach "
        "tiles must look like they belong to the same ocean. Beach sand must be "
        "a consistent warm tone. Coastline edges must blend seamlessly between "
        "sand and water."
    ),
    "river": (
        "These are RIVER tiles showing flowing water with banks. Keep the "
        "water color and flow pattern IDENTICAL to the sea tiles. River "
        "banks must match the plain grass tone. All river tiles must blend "
        "seamlessly when connected."
    ),
    "stormcloud": (
        "These are atmospheric STORM CLOUD and WEATHER EFFECT tiles. They should "
        "look like dramatic clouds with lightning, rain, or storm effects. Use "
        "cool grays, dark blues, and white highlights."
    ),
    "teleporter": (
        "These are TELEPORTER PAD tiles. They are sci-fi/magical portal platforms. "
        "Maintain their distinctive glow and energy effects."
    ),
}

# Prompt templates for anchor generation and batch reskinning (v2 pipeline).
ANCHOR_PROMPT_TEMPLATE = (
    "{style_sheet_instruction}"
    "Reskin this {type_name} game tile to a completely different visual theme. "
    "Target style: {theme_prompt}. "
    "Top-down orthogonal perspective. "
    "{type_hint} "
    "RULES: "
    "1) Keep the exact same grid layout and tile position. "
    "2) Only change colors and textures — don't move or resize the tile. "
    "3) No text, labels, or watermarks. "
    "4) Keep black grid lines and gray padding as-is. "
    "5) Make the style change DRAMATIC and obvious — this must look like a completely different theme."
)

BATCH_PROMPT_TEMPLATE = (
    "{style_sheet_instruction}"
    "Reskin the tiles in the last image to match the visual style of the anchor tile. "
    "These are {type_name} game tiles, top-down orthogonal perspective. "
    "Target style: {theme_prompt}. "
    "{type_hint} "
    "{cell_legend}"
    "RULES: "
    "1) Keep the exact same grid layout and tile positions. "
    "2) Only change colors and textures — don't move or resize tiles. "
    "3) No text, labels, or watermarks. "
    "4) Keep black grid lines and gray padding as-is. "
    "5) Match the anchor tile's palette and shading exactly."
)

MULTI_ANCHOR_BATCH_PROMPT_TEMPLATE = (
    "{style_sheet_instruction}"
    "Reskin the tiles in the last image to match the visual style of the reference images. "
    "The main reference shows the target style for {type_name} tiles. "
    "Additional references show context colors — match water portions to any water "
    "reference and grass/land portions to any grass reference exactly. "
    "These are {type_name} game tiles, top-down orthogonal perspective. "
    "Target style: {theme_prompt}. "
    "{type_hint} "
    "{cell_legend}"
    "RULES: "
    "1) Keep the exact same grid layout and tile positions. "
    "2) Only change colors and textures — don't move or resize tiles. "
    "3) No text, labels, or watermarks. "
    "4) Keep black grid lines and gray padding as-is. "
    "5) Match the reference images' palettes and shading exactly. "
    "6) Use the reference grass/land colors for any land portions."
)

ANIM_BATCH_PROMPT_TEMPLATE = (
    "{style_sheet_instruction}"
    "Reskin the animation frames in the last image to match the visual style of the anchor tile. "
    "Each column in the grid represents the next frame of a looping animation. "
    "CRITICAL: Preserve the motion differences between frames — each frame should have the same "
    "reskinned style but maintain its unique position/shape changes that create the animation. "
    "Rules:\n"
    "1) Each column is one animation frame. Reskin all frames identically in style.\n"
    "2) Preserve frame-to-frame differences (position shifts, shape changes, opacity variations).\n"
    "3) Maintain exact transparency — do not fill transparent areas.\n"
    "4) Match the anchor tile's palette and shading.\n"
    "5) Keep the same grid layout — same number of rows and columns.\n"
    "{cell_legend}"
)
