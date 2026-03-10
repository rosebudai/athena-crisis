# Athena Crisis Reskin Findings

## Purpose

This document captures the main findings from the tile and sprite reskin
investigation so future work can start from the architectural conclusions
instead of repeating the same experiments.

## Executive Summary

- Terrain reskinning is much harder than it first appeared.
- Units and buildings are the correct first-class reskin target.
- The tile pipeline improved orchestration and cache discipline, but it was
  built around the wrong primitive for many terrain families.
- The sprite pipeline had the right primitive for units and buildings, but the
  quality contract was too weak.
- The current units/buildings pipeline is structurally much better, but visual
  quality is still the main unsolved problem.

## How The Game Actually Renders Art

### Terrain

Terrain is not rendered as simple atlas cells.

The actual runtime model is defined across:

- `athena/info/Tile.tsx`
- `athena/lib/getModifier.tsx`
- `hera/render/renderTile.tsx`

Important consequences:

- many visible tiles depend on neighbor topology,
- some tiles are layered over fallbacks,
- some modifiers are chosen by position-based variant rules,
- and some tiles render as quarters, halves, composites, or overlays.

For terrain, atlas storage is often just a backing representation. It is not
the same thing as the visible semantic tile.

### Units And Buildings

Units and buildings are much closer to a one-asset, one-runtime-unit model.

Relevant runtime path:

- `art/Sprites.tsx`
- `hera/render/Images.tsx`
- `rosebud/reskin/reskin.py`

This is why named sprite sheets are a much better automation target than tile
atlases.

## Tile Pipeline Findings

### What Worked

The tile pipeline produced useful infrastructure:

- modular batch construction,
- stronger cache identity,
- exact-match cache reuse,
- better prompt/version discipline,
- and focused tests around batching and provider behavior.

Relevant files:

- `rosebud/reskin/tile_pipeline/batching.py`
- `rosebud/reskin/tile_pipeline/provider.py`
- `rosebud/reskin/tile_pipeline/prompts.py`

### What Failed

The core assumption was wrong for many terrain families:

- extract one `24x24` atlas cell,
- batch those cells,
- ask the model to repaint them,
- crop one `24x24` cell back out.

This worked only when a storage cell was already close to a meaningful visible
tile.

It broke down for:

- layered terrain,
- animated overlays,
- joinable terrain,
- area/composite terrain,
- and especially `sea_object`.

### Sea Object Research

`sea_object` was the most important diagnostic case.

We first improved batching by introducing explicit semantic families:

- `sea_object_static`
- `sea_object_island_anim`
- `sea_object_iceberg_weeds_anim`
- `sea_object_gas_bubbles_anim`

This improved grouping, but it did not fix the deeper problem.

The deeper problem was that the source unit itself was wrong:

- the extracted cells were visually incoherent,
- they were often storage fragments rather than meaningful objects,
- and even better family splits still fed the model bad inputs.

We also tested preview-aware batching. That proved another key point:

- a better semantic preview image does not solve the problem if the output
  contract is still an atlas-fragment repaint target.

### Final Tile Verdict

The tile pipeline is still useful as research and infrastructure, but terrain
reskinning needs a render-aware pipeline.

For terrain, the real architectural requirement is:

1. a render-aware semantic input,
2. a clear output contract,
3. and an invertible mapping back to valid game assets.

Without that, better batching only improves symptoms.

## Asset Complexity Ranking

The effective ranking from easiest to hardest is:

1. portraits and UI sprites,
2. unit sprite sheets,
3. building sprite sheets,
4. isolated decorative props,
5. animated isolated props,
6. overlay terrain families,
7. joinable / area / composite terrain.

Important implication:

- do not start with terrain if the goal is progress with low engineering risk.

## Sprite And Building Findings

### What The Old Sprite Pipeline Got Right

The old sprite pipeline used the right primitive:

- one named sprite sheet,
- one generated output,
- one runtime override path.

That is fundamentally better than atlas-cell repainting for units/buildings.

### What It Got Wrong

The quality contract was weak.

Failure modes included:

- blurry or painterly pseudo-pixel output,
- weak silhouette preservation,
- frame-to-frame drift,
- flat building shading,
- and outputs that technically loaded but looked worse in game.

The problem was not mainly routing. It was that bad outputs were too easy to
accept.

## Current Units/Buildings Pipeline Direction

The current pipeline direction is:

- named sprite sheets as the default generation unit,
- one sheet per request by default,
- `nano_banana` as the normal AI provider,
- explicit runtime manifest publishing,
- direct image override support for assets like `Structures`,
- stronger prompt contract for sheet preservation,
- separate progress manifest and runtime manifest.

Relevant files:

- `rosebud/reskin/reskin.py`
- `rosebud/reskin/discovery.py`
- `rosebud/reskin/manifest.py`
- `rosebud/reskin/transforms/ai_reskin.py`
- `art/Sprites.tsx`
- `hera/render/Images.tsx`

### Runtime Contract

The runtime manifest now supports:

- `sprites` for standard sprite-sheet overrides,
- `directSprites` for direct image assets,
- `tiles` for tile atlas overrides.

This is important because `Structures` does not fit the normal sprite-variant
override seam.

## What We Kept

From the tile work:

- cache rigor,
- manifest discipline,
- stronger tests,
- and explicit batch metadata.

From the sprite/building work:

- named asset boundaries,
- one-sheet generation,
- runtime manifest integration,
- direct sprite overrides,
- and resumable progress tracking.

## What We Removed Or Deprioritized

- public grid batching from the normal sprite CLI,
- the old `fal_gemini` sprite-provider surface,
- silent resize recovery on provider size mismatch,
- Gemini-specific judge plumbing,
- committed bad reskin outputs from the served tree,
- and temporary tile runtime-preview helper files.

These either added complexity without improving quality or supported
experiments that no longer align with the chosen direction.

## Main Open Problem

The main open problem is now sprite quality, not pipeline wiring.

The current units/buildings pipeline is structurally sound enough to keep
building on, but it still needs better output acceptance.

Likely next steps:

- cohort-aware prompts,
- per-asset comparison artifacts,
- automated quality gates,
- and publish-only-on-pass behavior.

## Recommended Next Direction

Do not restart terrain work yet.

Instead:

1. keep terrain parked,
2. keep units and buildings as the active target,
3. improve quality control before publishing generated assets,
4. return to terrain only after a render-aware terrain design exists.

## Related Specs

These docs capture the main design steps that led to the conclusions above:

- `.specs/family-based-batching.md`
- `.specs/sea-object-render-preview-batching.md`
- `.specs/reskin-asset-roadmap.md`
- `.specs/units-buildings-reskin-v2.md`
- `.specs/sprite-pipeline-simplification.md`
