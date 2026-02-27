# AI Reskin Pipeline for Athena Crisis

## Overview

Port the Wesnoth `utils/reskin/` pipeline to Athena Crisis, enabling AI-powered reskinning of all game sprites via a theme-driven CLI tool. The pipeline uses batch 4x4 grid compositing to minimize API calls, FAL.ai Gemini for image generation, and integrates with the existing palette-swap sprite loading system via local file overrides.

## Architecture

```
utils/reskin/                     (Python CLI — offline build tool)
├── reskin.py                     CLI entry point
├── config.py                     Theme loading + validation
├── discovery.py                  Athena Crisis asset discovery
├── manifest.py                   Resumable progress tracking
├── providers/
│   ├── base.py                   Abstract ReskinProvider
│   ├── echo.py                   Dry-run (returns original image)
│   └── fal_gemini.py             FAL.ai Gemini 3 Pro img-edit
├── transforms/
│   ├── ai_reskin.py              Single-image AI transform
│   ├── grid_batch.py             4x4 grid compositing + extraction
│   └── palette_swap.py           Algorithmic color-family swap
├── themes/
│   └── cyberpunk.json            Example theme
├── tests/                        Unit tests
└── output/                       Generated assets (gitignored)
```

```
art/Sprites.tsx                   (Runtime integration — ~10 lines added)
  └── Before palette-swap, check for local override PNGs
```

## Data Flow

```
1. DISCOVER
   Read SpriteVariant names from athena/info/SpriteVariants.tsx
   Download source images from art.athenacrisis.com/v19/<name>.png
   Classify: unit-sprite | building | portrait | icon | effect

2. BATCH
   Group sprites by pixel dimensions (64px bucket step)
   Compose 4x4 grids (2048x2048 canvas, gray bg, black grid lines)
   Write grid PNGs + manifest.json with cell coordinates

3. RESTYLE
   For each grid: build per-cell prompt from theme + sprite metadata
   Send grid image + prompt to FAL.ai Gemini edit API
   Save restyled grid PNGs

4. EXTRACT
   Crop individual sprites from restyled grids using manifest coordinates
   Restore original alpha masks (RGB from AI, alpha from original)
   Validate: check sprite actually changed (mean pixel diff > 3)
   Write individual PNGs to output/<theme>/<name>.png

5. INTEGRATE (runtime)
   Copy output/<theme>/ to rosebud/public/reskin/<theme>/
   At boot, Sprites.tsx checks for local files before fetching from CDN
   Palette-swap runs on the reskinned source images → team colors work automatically
```

## Components

### 1. Asset Discovery (`discovery.py`)

Unlike Wesnoth's faction-directory structure, Athena Crisis sprites are identified by `SpriteVariant` names. Discovery:

- Parses `athena/info/SpriteVariants.tsx` to extract all sprite type names
- Downloads source images from `art.athenacrisis.com/v19/<name>.png`
- Caches downloaded originals in `output/.cache/`
- Classifies sprites into categories:
  - `unit-sprite`: Names starting with `Units-` (e.g., `Units-Infantry`)
  - `building`: `Buildings`, `Building-Create`
  - `portrait`: `Portraits`
  - `icon`: `Label`, `Medal`, `Message`
  - `effect`: `Capture`, `Rescue`, `Spawn`, `NavalExplosion`, etc.
  - `shadow`: `BuildingsShadow`, `StructuresShadow`
  - `decorator`: `Decorators`
- Shadows and decorators are excluded from AI reskin by default (palette-swap only)

Asset count: ~90 sprite types total. After excluding shadows/decorators, ~80 go through AI reskin.

### 2. Grid Batching (`transforms/grid_batch.py`)

Ported from Wesnoth with minimal changes:

- Groups sprites by similar dimensions (64px bucket step)
- Renders 4x4 grids on 2048x2048 canvas with gray background + black grid lines
- Each cell has 16px padding around the sprite
- Scale factor computed to fill canvas efficiently
- Manifest tracks exact pixel coordinates for extraction

With ~80 sprites, this produces ~5 grid images (5 API calls instead of 80).

### 3. Prompt Building

Per-grid prompts follow the Wesnoth format:

```
This is a 4x4 grid of game sprites on gray background, separated by black grid lines.

Each cell contains:
  Row A Col 1: unit-sprite — Infantry
  Row A Col 2: unit-sprite — Heavy Tank
  ...

Restyle every sprite to: <theme.prompt>

You MUST keep the exact same silhouette, shape, size, and proportions of every object.
Only change colors and textures. No text, no labels, no new objects.
Keep grid lines and gray backgrounds.
```

### 4. Extraction + Alpha Restoration (`transforms/grid_batch.py`)

- Reverse the grid composition using manifest coordinates
- Crop each sprite at its original dimensions
- **Alpha restoration**: Take RGB channels from AI output, alpha channel from original source — preserves exact silhouettes
- **Validation**: Compare restyled vs original (mean pixel diff must be > 3 to confirm actual restyling)

### 5. Theme Configuration (`config.py`)

Theme JSON format (same as Wesnoth):

```json
{
  "name": "cyberpunk",
  "description": "Neon-lit sci-fi warriors with glowing circuits",
  "prompt": "cyberpunk neon sci-fi style, glowing circuits, chrome metal",
  "palette": {
    "reds": "#ff0044",
    "greens": "#00ff88",
    "blues": "#ff6600",
    "silvers": "#c0c0ff"
  }
}
```

The `prompt` drives AI reskin. The `palette` drives algorithmic color-family swap for icons/shadows that skip AI.

### 6. Runtime Integration (`art/Sprites.tsx`)

Minimal change to the existing sprite loading pipeline:

In `Sprites.tsx`, the `Variants` map entries have a `source` URL pointing to `art.athenacrisis.com`. Before palette-swap runs, we check if a local override exists at a configurable path (e.g., `reskin/<name>.png`). If found, use the local URL instead.

This is wired through the existing `ConfigLoader` pattern — a `config/reskin.json` file maps theme name to the directory containing reskinned PNGs:

```json
{
  "theme": "cyberpunk",
  "basePath": "reskin/cyberpunk"
}
```

The palette-swap system then runs on the reskinned source images, automatically generating team-colored variants. Zero changes needed to the rendering pipeline.

### 7. Providers

**EchoProvider**: Returns original image unchanged. For dry-run pipeline testing.

**FalGeminiProvider**: Calls `fal-ai/gemini-3-pro-image-preview/edit` with uploaded grid images. ~$0.008 per grid. Supports both single-image and grid transform modes. Retries with exponential backoff. Validates output dimensions (must be >= 1024px).

### 8. Manifest (`manifest.py`)

JSON manifest tracks:

- Theme, provider, timestamp
- Per-asset status (completed/failed), source hash, output path
- Enables resumable runs — skip already-completed assets on re-run
- `--force` flag reprocesses everything

## CLI Interface

```bash
# Dry run — validate pipeline without API calls
python utils/reskin/reskin.py \
  --theme cyberpunk \
  --batch \
  --dry-run

# Full AI reskin
python utils/reskin/reskin.py \
  --theme cyberpunk \
  --batch \
  --provider fal_gemini

# Reskin only units
python utils/reskin/reskin.py \
  --theme cyberpunk \
  --batch \
  --category unit-sprite \
  --provider fal_gemini

# Palette-swap only (no AI, just recolor)
python utils/reskin/reskin.py \
  --theme cyberpunk \
  --palette-only

# Force reprocess everything
python utils/reskin/reskin.py \
  --theme cyberpunk \
  --batch \
  --provider fal_gemini \
  --force
```

## Acceptance Criteria

### Must Have

- [ ] `discovery.py` parses SpriteVariants.tsx and downloads all ~90 source images from art.athenacrisis.com
- [ ] `grid_batch.py` composes sprites into 4x4 grids and writes manifest with cell coordinates
- [ ] Grid extraction correctly recovers individual sprites at original dimensions
- [ ] Alpha mask restoration preserves exact original silhouettes on restyled sprites
- [ ] `EchoProvider` passes dry-run end-to-end (discover → batch → extract → output PNGs)
- [ ] `FalGeminiProvider` sends grid images to FAL.ai and saves restyled output
- [ ] Theme JSON loading with validation of required fields (name, prompt, palette)
- [ ] Manifest enables resumable runs — re-running skips completed assets
- [ ] `palette_swap.py` recolors icons/shadows by color family
- [ ] Runtime integration: `Sprites.tsx` loads local override PNGs when `config/reskin.json` is present
- [ ] Palette-swap runs on reskinned source images, producing correct team-colored variants
- [ ] Unit tests for discovery, grid batching, extraction, palette swap, manifest, config loading

### Nice to Have

- [ ] `--category` flag to reskin only unit-sprites, buildings, portraits, etc.
- [ ] Sprite validation (mean pixel diff check) warns on unchanged outputs
- [ ] Progress bar / percentage during batch processing

### Out of Scope

- Nano Banana provider (stub only in Wesnoth, not implemented)
- CDN distribution of themes
- In-game theme picker UI
- Reskinning of non-palette-swapped assets (attack effects, tile sprites, cursor, etc.)
- Web build patching (Wesnoth's `patch_web_build.py` — not needed since AC loads assets via URL)

## QA Plan

1. Run `python utils/reskin/reskin.py --theme cyberpunk --batch --dry-run` — should complete without errors, output PNGs identical to originals in `output/cyberpunk/`
2. Verify `output/cyberpunk/grids/manifest.json` contains correct batch metadata with cell coordinates
3. Verify individual sprite PNGs in `output/cyberpunk/` match original dimensions
4. Verify alpha channels are preserved (compare original vs output alpha masks)
5. Copy `output/cyberpunk/` to `rosebud/public/reskin/cyberpunk/`
6. Add `config/reskin.json` pointing to the theme
7. Run the Rosebud dev server (`cd rosebud && npx vite`)
8. Verify sprites render with reskinned art in the game view
9. Verify team colors (palette-swap) still work correctly on reskinned sprites
10. Run unit tests: `cd utils/reskin && python -m pytest tests/`
