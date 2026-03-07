# Transition Tile Harmonization

## Problem

Transition tiles (beach coastlines, riverbanks, sea edges) contain pixels from two terrain types (e.g., grass + water). These tiles are batched by their primary type ("water" for beach, "river" for rivers), so Gemini reskins land portions with a different green (~139 RGB units away) than actual plain tiles. This creates visible seams at terrain boundaries in-game.

## Design

Two-phase approach in the stage 2 pipeline:

### Phase 1 — Context-Enriched Batching

Modify `create_typed_batches()` to inject "context cells" from adjacent terrain types into transition batches. When building a "water" batch containing beach cells (rows 50-72), include 2-4 reskinned plain cells as visual reference. Same for "river" batches. Context cells are visually labeled in the batch grid (e.g., "REF" marker in padding) so Gemini matches their style. Context cells are stripped from output — input-only.

### Phase 2 — Post-Processing Harmonization

After palette snap, add `harmonize_transitions()` that:

1. Extracts dominant "grass" LAB color from reskinned plain cells (type="plain")
2. Extracts dominant "water" LAB color from reskinned pure-sea cells (rows 35-49)
3. For each transition cell (beach rows 50-72, river rows 73-144, sea-edge rows 34-49):
   - Uses original atlas to build per-pixel "terrain membership" mask via hue classification
   - Shifts "grass-like" pixels (hue 60°-160°, sat > 20%) toward reference grass LAB mean
   - Shifts "water-like" pixels (hue 180°-260°, sat > 20%) toward reference water LAB mean
   - Uses soft blending factor (60% shift strength) to avoid harsh artifacts

### Pipeline Data Flow

```
Stage 2 (current):
  reskin batches → palette snap → copy anim frames → reassemble

Stage 2 (new):
  reskin batches (with context cells) → palette snap → harmonize transitions → copy anim frames → reassemble
```

### Components Modified

1. **`create_typed_batches()`** — Accept optional `context_cells` dict mapping tile_type → list of reference cell images. Inject into batch grids with visual marker.
2. **`_reskin_batches()`** — Strip context cells from output after reskinning.
3. **New: `harmonize_transitions()`** — Post-processing step between palette snap and anim frame copy.
4. **`main()`** — Wire into stage 2 pipeline.

### Transition Type → Reference Types

| Transition tiles                      | Land reference   | Water reference              |
| ------------------------------------- | ---------------- | ---------------------------- |
| Beach (rows 50-72)                    | plain (rows 0-2) | sea (rows 35-49)             |
| River (rows 73-144)                   | plain (rows 0-2) | — (river blue from own type) |
| Sea edges (rows 34-49, boundary cols) | plain (rows 0-2) | sea center (row 35 col 8)    |

### Hue Classification (using original atlas as ground truth)

- **Grass-like**: Original pixel hue 60°-160° (yellow-green to green), saturation > 20%
- **Water-like**: Original pixel hue 180°-260° (cyan to blue), saturation > 20%
- **Neutral/other**: Sand, rock, shadow — left unchanged

## Acceptance Criteria

### Must Have

- [ ] Transition batches (water, river) include 2-4 reskinned plain cells as visual context when sent to Gemini
- [ ] Context cells are stripped from output — they don't end up in the final atlas
- [ ] `harmonize_transitions()` post-processing step shifts land-like pixels in beach/river/sea-edge cells toward the reskinned plain tiles' mean color
- [ ] Water-like pixels in beach cells are shifted toward reskinned sea tiles' mean color
- [ ] The harmonization uses the original atlas to classify pixels as land-like vs water-like (hue-based)
- [ ] All 41 existing tests still pass
- [ ] The reskinned atlas shows visually consistent grass green across plain tiles and beach/river land portions
- [ ] No new flickering introduced — animation frame copy still works correctly

### Nice to Have

- [ ] Harmonization shift strength is configurable (default 60%)
- [ ] `--skip-harmonize` flag to bypass the step for debugging

### Out of Scope

- Forest↔plain and mountain↔plain transitions (Joinable-type, not blended pixel transitions)
- Biome variants (desert, snow, etc.) — only Grassland/cozy theme for now
- Reskinning non-Tiles0 atlases

## QA Plan

Steps the agent follows during end-user testing (references `.claude/verification.md`):

1. Run `python3 rosebud/reskin/reskin_tiles.py --atlas Tiles0 --theme cozy --stage 2` — verify it completes without errors and reports harmonization stats
2. Run `python3 -m pytest rosebud/reskin/tests/test_tile_batching.py -v` — all tests pass
3. Serve: `pnpm build:rosebud && pnpm --filter @deities/rosebud preview --host 0.0.0.0 --port 4173`
4. Navigate to `http://localhost:4173/`, screenshot title screen → `/tmp/step1.png`
5. Click "Play", select "They are Close to Home" (22x10, has coastlines + rivers), click "Start Game"
6. Screenshot the game map → `/tmp/step3.png` — verify:
   - Beach coastline tiles: the grass portions match the green of inland plain tiles
   - River bank tiles: the grass portions match surrounding plain tiles
   - Sea edge tiles: smooth transition, no jarring color boundary
7. Wait 5 seconds, screenshot again → `/tmp/step3b.png` — verify no flickering
8. Compare `/tmp/step3.png` side-by-side with the pre-change screenshot at `/tmp/transitions.png` to confirm improvement
9. Run visual judge per verification.md
10. Both judges must pass
