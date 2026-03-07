# Tile Reskin Staged Experiment: Style-Reference Conditioning

## Context

Previous attempts at full tile atlas reskinning failed due to:

- Cross-batch style drift (11 water batches = 11 different blue tones)
- Animation frame flickering (frames in different batches got different art)
- Full-scale runs launched before validating the approach

This experiment derisks the approach in 3 staged gates before any full-scale run.

## Architecture

### Stage 1 — Style Reference Generation (1 API call)

Pick 8-10 representative tiles spanning all major terrain types (1 grass, 1 water, 1 beach-edge, 1 mountain, 1 forest, 1 road, 1 river, 1 pier). Arrange in a single grid and send to Gemini with the cozy theme prompt. The output becomes the **style reference image** — the visual anchor for all subsequent calls.

**Quality gate**: Human reviews the style reference. If it doesn't look good as standalone art, stop.

### Stage 2 — Consistency Validation (2 API calls)

Take two different water batches (the hardest type from the post-mortem). Send each batch to Gemini with the style reference image included as a second input. Prompt says: "Reskin these tiles to match the exact style, palette, and texture of the reference image."

**Quality gate**: Compare the two water batch outputs. If they have visually different blue tones, wave patterns, or textures, the reference conditioning isn't working — stop.

### Stage 3 — Animation Validation (1 API call)

Take a batch containing base-frame tiles for Sea + Beach + River. Reskin with style reference. Then programmatically copy base frames to all animation frame slots. Load into the game and check: do animated tiles look acceptable as static? Do coastline transitions work?

**Quality gate**: Playtest in dev server. If animations flicker, seams are jarring, or static water looks unacceptable, stop.

## Key Changes from Previous Pipeline

1. **Style reference image** — every batch call includes the reference as a second image input
2. **Only base frames sent to AI** — animation frame rows excluded from batching entirely
3. **Frame copying is mandatory** — not post-processing but a core pipeline step
4. **Staged execution** — `--stage 1|2|3|full` flag, each stage requires human approval before advancing
5. **No full-scale run until stages 1-3 pass**

## Batch Layout

Same 6x6 grid with 4px padding and 4x upscale. Only base-frame cells included in batches (animation frame cells excluded during extraction). After reskinning, `copy_base_frames_to_anim_frames` fills in all animation slots.

## Prompt Structure

```
[Image 1: Style reference grid]
[Image 2: Batch grid to reskin]

"Reskin the tiles in Image 2 to match the exact visual style of Image 1.
Image 1 shows the target style — match its palette, texture quality, and
shading approach exactly.

{type_hint}

RULES:
1) Keep the exact same grid layout and tile positions
2) Only change colors and textures — don't move or resize tiles
3) No text, labels, or watermarks
4) Keep black grid lines and gray padding as-is
5) Match Image 1's style precisely — same color temperature, same brush feel"
```

## Files Modified

- `rosebud/reskin/reskin_tiles.py` — add style-reference logic, stage flags, exclude animation frames from batching

## Atlas Details

- Atlas: `Tiles0.png` (288x3480, 12 cols x 145 rows, TileSize=24px)
- 1226 non-empty cells, ~285 are animation frames (base-frame copy targets)
- Theme: cozy (`cozy cartoon style, warm bright colors, soft shading, friendly cute aesthetic, storybook illustration`)
- AI model: `gemini-3.1-flash-image-preview` via Google GenAI SDK

## Animation Frame Handling

Only base frames are sent to the AI. After reskinning, `copy_base_frames_to_anim_frames` copies base frame art to all other animation frames using alpha-similarity check (threshold 0.85) to avoid cross-type overwrites at shared rows.

Key animated tiles and their base positions:
| Tile | Base (col, row) | Frames | Offset | Direction |
|------|-----------------|--------|--------|-----------|
| Sea | (8, 35) | 4 | 3 | Vertical |
| DeepSea | (8, 47) | 4 | 3 | Vertical |
| Beach | (3, 50) | 4 | 6 | Vertical |
| River | (1, 73) | 24 | 3 | Vertical |
| Pier | (0, 29) | 4 | 5 | Vertical |
| StormCloud | (6, 7) | 4 | 3 | Vertical |
| Campsite | (0, 28) | 4 | 1 | Horizontal |
| Reef | (5, 18) | 4 | 1 | Horizontal |

## Acceptance Criteria

### Must Have

- [ ] **Stage 1**: Pipeline generates a style reference grid from 8-10 representative tiles (1 per terrain type) and saves it as `style_reference.png`
- [ ] **Stage 1 gate**: Style reference is visually reviewed before any further calls
- [ ] **Stage 2**: Two water batches are reskinned with the style reference as conditioning input (2-image prompt)
- [ ] **Stage 2 gate**: Both water batch outputs use the same blue tone and texture pattern (measured by RGB mean variance < threshold, confirmed visually)
- [ ] **Stage 3**: Base-frame tiles for water types are reskinned, frames are copied, atlas is reassembled and loaded in dev server
- [ ] **Stage 3 gate**: Animated tiles render without flickering; coastline transitions are cohesive
- [ ] Animation frame rows are excluded from AI batching — only base frames are sent
- [ ] `copy_base_frames_to_anim_frames` with alpha-similarity check runs after every reskin
- [ ] `--stage 1|2|3|full` CLI flag controls which stages run
- [ ] Each stage exits after completion and prints clear pass/fail guidance

### Nice to Have

- [ ] Automated RGB variance metric printed after Stage 2 (quantitative, not just visual)
- [ ] Stage results cached so re-running a later stage doesn't repeat earlier API calls

### Out of Scope

- Full atlas generation (only after all 3 stages pass in a future run)
- Programmatic animation frame derivation (future enhancement)
- Non-Grassland biomes
- Unit sprite reskinning

## QA Plan

1. **Stage 1**: Run `python3 rosebud/reskin/reskin_tiles.py --atlas Tiles0 --theme cozy --stage 1`
   - Verify `style_reference.png` is created in output dir
   - Open the image — confirm it contains ~8-10 tiles in a clear grid with cozy art style
   - Visual check: does it look like a coherent "cozy" style you'd want applied everywhere?

2. **Stage 2**: Run `python3 rosebud/reskin/reskin_tiles.py --atlas Tiles0 --theme cozy --stage 2`
   - Verify two `*_water_*_reskinned.png` files are created
   - Open both — compare blue tones, wave patterns, and overall texture
   - Check printed RGB variance metric (if implemented)
   - Visual check: could you tell these came from the same artist?

3. **Stage 3**: Run `python3 rosebud/reskin/reskin_tiles.py --atlas Tiles0 --theme cozy --stage 3`
   - Verify `rosebud/public/reskin/cozy/Tiles0.png` is created
   - Verify manifest.json re-enabled: `"Tiles0": "reskin/cozy/Tiles0.png"`
   - Start dev server: `pnpm --filter @deities/rosebud dev`
   - Navigate to game -> Play -> Demo 1 -> Grassland -> Start Game
   - Screenshot the map — verify:
     - Water tiles are static (no flickering between frames)
     - Coastline edges blend smoothly (no jarring seams)
     - Style is visibly "cozy" / different from original
   - Check console for `[Reskin] Applied 1 tile override(s)` log
