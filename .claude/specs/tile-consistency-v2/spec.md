# Tile Consistency V2: Animation-Aware Batching

## Problem

The current tile reskin pipeline (`rosebud/reskin/reskin_tiles.py`) groups atlas cells by row range → tile type, then batches them into 6x6 grids for AI reskinning. This causes two critical issues:

1. **Animation frame flickering**: Animated tiles (Sea, Beach, River, Pier) have multiple frames spaced `offset` rows apart in the atlas. Frames of the same tile land in different AI batches, producing different art styles → visible flickering during animation.
2. **Sea-land boundary mismatch**: Beach and Sea transition tiles span multiple batches, so coastline edges look inconsistent.

## Solution: Animation-Aware Batching + Parallel Generation

### 1. Tile Identity Mapping

Build a mapping from the animation definitions in `athena/info/Tile.tsx`:

| Tile       | Base Position | Frames | Offset | Direction  | Frame Rows           |
| ---------- | ------------- | ------ | ------ | ---------- | -------------------- |
| Sea        | (8, 35)       | 4      | 3      | vertical   | 35, 38, 41, 44       |
| DeepSea    | (8, 47)       | 4      | 3      | vertical   | 47, 50, 53, 56       |
| Beach      | (3, 50)       | 4      | 6      | vertical   | 50, 56, 62, 68       |
| River      | (1, 73)       | 24     | 3      | vertical   | 73, 76, 79, ..., 142 |
| Pier       | (0, 29)       | 4      | 5      | vertical   | 29, 34, 39, 44       |
| Campsite   | (0, 28)       | 4      | 1      | horizontal | N/A (cols shift)     |
| StormCloud | (6, 7)        | 4      | 3      | vertical   | 7, 10, 13, 16        |
| Reef       | (5, 18)       | 4      | 1      | horizontal | N/A (cols shift)     |

For each cell in the atlas, determine which logical tile it belongs to and which animation frame index it is. Cells at the same (col, base_row) with different frame offsets are part of the same logical tile.

### 2. Animation-Grouped Batching

Group cells by **logical tile identity** (same column, same base row modulo animation offset), not just by type. All animation frames of a logical tile must be in the same batch.

**Filmstrip layout**: Within each batch grid, arrange frames of the same logical tile in the same row:

```
[Sea-tile-A-f0] [Sea-tile-A-f1] [Sea-tile-A-f2] [Sea-tile-A-f3]
[Sea-tile-B-f0] [Sea-tile-B-f1] [Sea-tile-B-f2] [Sea-tile-B-f3]
...
```

For River (24 frames), use a 6×4 filmstrip sub-layout:

```
[River-A-f0]  [River-A-f1]  [River-A-f2]  [River-A-f3]
[River-A-f4]  [River-A-f5]  [River-A-f6]  [River-A-f7]
...
[River-A-f20] [River-A-f21] [River-A-f22] [River-A-f23]
```

### 3. Sea-Land Boundary Grouping

Beach and Sea tiles go in the **same batch group** so the AI sees coastline transitions alongside open water. This maintains visual continuity at sea-land boundaries.

### 4. Type-Specific Animation Prompts

Extend the prompt to tell the AI about animation frames:

- "Each row shows animation frames of the SAME tile. Frame 0 is the base state. Keep colors and textures IDENTICAL across all frames — only the wave/ripple position should differ."

### 5. Parallel Batch Generation

Use `concurrent.futures.ThreadPoolExecutor` to send batch requests to Gemini in parallel:

- Default `--workers 8`
- Thread-safe progress output using a lock
- No per-worker sleep needed — the API handles its own rate limiting
- Failed batches are retried (existing retry logic in `reskin_batch_gemini`)

### 6. Color Normalization (kept)

After extraction, 50% color normalization per type remains as a safety net for batch-to-batch drift.

## Files to Modify

- `rosebud/reskin/reskin_tiles.py` — Rewrite batching logic, add parallel execution

## Acceptance Criteria

### Must Have

- [ ] All animation frames of a single tile are in the same AI batch
- [ ] Animation frames are arranged as filmstrips (same row) in the batch grid
- [ ] Sea and Beach tiles are in the same batch group for boundary consistency
- [ ] Reskinned atlas plays animations without visible flickering between frames
- [ ] Sea-land coastline transitions look cohesive
- [ ] Batch generation uses `ThreadPoolExecutor` with configurable `--workers` (default 8)
- [ ] Progress output is thread-safe (no interleaved lines)
- [ ] Color normalization post-processing still applies
- [ ] Pipeline supports `--dry-run` to verify batching without API calls
- [ ] Cached reskinned batches are invalidated when batching logic changes
- [ ] `--fresh` flag clears cache for regeneration

### Nice to Have

- [ ] `--type-only` filter still works for iterating on specific tile types
- [ ] Frame-specific prompt hints

### Out of Scope

- Reskinning non-Grassland biomes (Tiles1-6)
- Unit sprite reskinning
- Building sprite reskinning

## QA Plan

1. Run `python3 rosebud/reskin/reskin_tiles.py --atlas Tiles0 --theme cozy --dry-run` and verify:
   - Batch grouping output shows animation frames together (e.g., "batch_005_sea: 36 cells, 9 logical tiles × 4 frames")
   - Sea and Beach tiles appear in the same batch group
   - Total batch count is ~25 or fewer
2. Run full pipeline: `python3 rosebud/reskin/reskin_tiles.py --atlas Tiles0 --theme cozy --fresh`
   - Verify parallel execution (multiple "Sending to Gemini" messages appear close together)
   - Verify all batches complete successfully
3. Start dev server: `pnpm --filter @deities/rosebud dev --host 0.0.0.0`
4. Navigate to http://localhost:5173/ → Play → Demo 1 → Grassland → Start Game
5. Observe water tiles — animation should play without color flickering between frames
6. Observe coastline (beach/sea boundary) — transition tiles should match ocean color
7. Observe river — flow animation should be consistent
8. Take screenshot with Playwright and run Gemini analysis comparing to v4
9. Verify `--type-only sea` and `--fresh` flags work for iterative re-runs
