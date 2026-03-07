# Tile Reskin v2: Anchor + Palette Snap Pipeline

## Context

v1 (style-reference conditioning) failed because Gemini ignores reference images as style anchors. Independent batch calls produced inconsistent art (Stage 2: 2/10 consistency, RGB variance 2042). This v2 uses a 3-layer consistency approach: rigid prompts + per-terrain anchors + deterministic palette snapping.

## Architecture: 3-Layer Consistency

```
Layer 1: Rigid Prompt Template
  Same template for all batches, only {type_name} and {type_hint} vary.
  Athena Crisis-specific structural terms enforce perspective and style.

Layer 2: Per-Terrain Anchor Tiles
  1 anchor tile per terrain type (7-8 calls).
  Included as reference image in each batch call.

Layer 3: Deterministic Palette Snap
  Extract colors from anchors -> build LAB palette.
  Snap every output pixel to nearest palette color.
  GUARANTEES cross-batch color consistency.
```

## Stage 1: Anchor Generation (7-8 API calls)

1. For each terrain type (plain, street, mountain, forest, campsite, pier, water, river), pick 1 representative tile from the original atlas
2. Send each to Gemini with the rigid cozy prompt template (single tile, not a batch grid)
3. Save as `anchor_{type}.png` in output directory
4. Extract all unique non-transparent colors from all anchors -> build the **master palette** in LAB color space
5. Save palette as `palette.json` (hex colors + LAB values)

**Quality gate**: Human reviews anchor tiles. Do they look "cozy"? Is the palette viable?

## Stage 2: Full Reskin (27 API calls + deterministic post-processing)

1. For each batch, identify its terrain type from the batch manifest
2. Send to Gemini with: rigid prompt template + type-specific anchor as reference image
3. **Palette snap**: For every pixel in the output, find nearest color in master palette (Euclidean distance in LAB space), replace. Preserve alpha channel unchanged.
4. Extract reskinned cells from batch grids
5. `copy_base_frames_to_anim_frames()` — fill animation frames from base frames (existing logic, unchanged)
6. Reassemble atlas -> `rosebud/public/reskin/cozy/Tiles0.png`
7. Update `manifest.json` with `"Tiles0": "reskin/cozy/Tiles0.png"`

**Quality gate**: Load in dev server, playtest.

## Prompt Template

```
[Image 1: Anchor tile for this terrain type]
[Image 2: Batch grid to reskin]

"Reskin the tiles in Image 2 to match the visual style of Image 1.

These are {type_name} game tiles, top-down orthogonal perspective,
16-bit modern retro pixel art style, warm and cozy color palette
with soft saturation, flat cartoon shading, clean edges,
storybook illustration aesthetic.

{type_hint}

RULES:
1) Keep the exact same grid layout and tile positions
2) Only change colors and textures -- don't move or resize tiles
3) No text, labels, or watermarks
4) Keep black grid lines and gray padding as-is
5) Match Image 1's palette and shading exactly"
```

## Palette Snap Algorithm

1. Collect all unique non-transparent pixels from all anchor tiles
2. Convert to CIELAB color space
3. Build a KD-tree or flat array for nearest-neighbor lookup
4. For each reskinned tile:
   - For each pixel with alpha > 0:
     - Convert RGB to LAB
     - Find nearest palette color by Euclidean distance
     - Replace RGB with palette color's RGB
     - Preserve original alpha value
5. Return snapped tile

Expected palette size: 40-80 unique colors (enough for shading gradients).

## Anchor Tile Selection

Pick 1 representative tile per terrain type that best represents the type's visual character:

| Type     | Selection criteria                          |
| -------- | ------------------------------------------- |
| plain    | Simple grass tile (avoid edges/transitions) |
| street   | Straight road segment                       |
| mountain | Mid-sized peak (not edge tile)              |
| forest   | Dense tree cluster                          |
| campsite | Base camp tile                              |
| pier     | Wooden dock segment                         |
| water    | Open sea tile (avoid coastline edges)       |
| river    | Straight river segment                      |

## Atlas Details

- Atlas: `Tiles0.png` (288x3480, 12 cols x 145 rows, TileSize=24px)
- 1226 non-empty cells, ~389 are animation frames (excluded from AI batching)
- ~840 base cells in 27 typed batches (6x6 grid each)
- Theme: cozy (warm and cozy color palette, storybook illustration)
- AI model: Gemini 3 Flash Image (Nano Banana 2) via Google GenAI SDK

## Files Modified

- `rosebud/reskin/reskin_tiles.py` — Replace style-reference logic with anchor generation, add palette extraction and snap, update prompt template, update `--stage 1|2` CLI

## Key Differences from v1

| v1 (failed)                         | v2 (this spec)                                          |
| ----------------------------------- | ------------------------------------------------------- |
| Single generic style reference grid | Per-terrain-type anchor tiles                           |
| Vague "match this style" prompt     | Rigid AC-specific template with structural terms        |
| No post-processing                  | Deterministic palette snap (LAB nearest-neighbor)       |
| 3 stages                            | 2 stages (simpler)                                      |
| Theme prompt only                   | Full template: perspective, art style, shading, palette |

## Acceptance Criteria

### Must Have

- [ ] **Stage 1**: Generate 1 anchor tile per terrain type (7-8 types) via Gemini with rigid cozy prompt
- [ ] **Stage 1**: Extract unique colors from all anchors into a master LAB palette and save as `palette.json`
- [ ] **Stage 1 gate**: Anchor tiles and palette are reviewed before Stage 2 runs
- [ ] **Stage 2**: All 27 batches reskinned with per-type anchor as reference image + rigid prompt template
- [ ] **Stage 2**: Every reskinned tile pixel-snapped to master palette (LAB nearest-neighbor, alpha preserved)
- [ ] **Stage 2**: Animation frames filled via `copy_base_frames_to_anim_frames()` (existing logic, unchanged)
- [ ] **Stage 2**: Atlas reassembled and loaded in dev server via manifest.json
- [ ] **Prompt template**: Rigid format with AC-specific terms (top-down orthogonal, 16-bit modern retro, flat cartoon shading, clean edges, storybook illustration)
- [ ] **Prompt template**: Only `{type_name}` and `{type_hint}` vary between batches
- [ ] **CLI**: `--stage 1|2|full` flag controls which stages run

### Nice to Have

- [ ] Palette snap strength parameter (0.0 = no snap, 1.0 = full snap) for tuning
- [ ] Print palette stats after extraction (number of unique colors, color distribution)

### Out of Scope

- Non-Grassland biomes
- Unit sprite reskinning
- ControlNet/LoRA/Stable Diffusion approaches
- Multi-turn conversation approach
- Overlap inpainting approach

## QA Plan

1. **Stage 1**: Run `python3 rosebud/reskin/reskin_tiles.py --atlas Tiles0 --theme cozy --stage 1`
   - Verify 7-8 `anchor_{type}.png` files created in output dir
   - Verify `palette.json` created with 40-80 colors
   - Open anchor tiles — confirm they look "cozy" (warm colors, soft shading, pixel art style)

2. **Stage 2**: Run `python3 rosebud/reskin/reskin_tiles.py --atlas Tiles0 --theme cozy --stage 2`
   - Verify all 27 `batch_*_reskinned.png` files created
   - Open two water batch outputs — confirm they use the same blue tones (palette snap should guarantee this)
   - Verify `rosebud/public/reskin/cozy/Tiles0.png` created
   - Verify `manifest.json` updated: `"Tiles0": "reskin/cozy/Tiles0.png"`

3. **In-game validation**:
   - Start dev server: `pnpm --filter @deities/rosebud dev`
   - Navigate to game -> Play -> Demo 1 -> Grassland -> Start Game
   - Screenshot the map — verify:
     - Water tiles are consistent (same blue tone across entire map)
     - Coastline edges blend smoothly
     - Style is visibly "cozy" / warmer than original
     - No flickering on animated tiles
   - Check console for `[Reskin] Applied 1 tile override(s)` log
