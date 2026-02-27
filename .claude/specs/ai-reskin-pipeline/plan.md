# AI Reskin Pipeline Implementation Plan

> **For Claude:** Execute this plan using subagent-driven-development. This plan was auto-generated and does not require user approval.

**Goal:** Port the Wesnoth reskin pipeline to Athena Crisis, enabling AI-powered sprite reskinning via a Python CLI with batch grid processing.

**Spec:** `.claude/specs/ai-reskin-pipeline/spec.md`

**Architecture:** Standalone Python CLI in `utils/reskin/` that discovers Athena Crisis sprite assets, composes them into 4x4 grids, sends them to FAL.ai Gemini for AI restyling, extracts individual sprites with alpha restoration, and outputs reskinned PNGs. A thin runtime integration in `art/Sprites.tsx` loads local overrides before the existing palette-swap pipeline.

**Tech Stack:** Python 3, PIL/Pillow, fal-client, pytest; TypeScript (minimal runtime integration in Sprites.tsx)

---

### Task 1: Scaffold the reskin package structure and config/theme system

**What to do:**

Create the `utils/reskin/` directory tree with all `__init__.py` files, `.gitignore` for `output/`, and the config/theme system.

Files to create:

- `utils/reskin/__init__.py` (empty)
- `utils/reskin/.gitignore` — ignore `output/`, `__pycache__/`, `*.pyc`
- `utils/reskin/config.py` — Port directly from Wesnoth's `config.py`. Identical `ThemeConfig` dataclass (name, description, prompt, palette dict). `load_theme()` loads by file path or by name from `themes/` directory. Validate required fields: name, prompt, palette.
- `utils/reskin/themes/cyberpunk.json` — Copy from Wesnoth as-is (already has good defaults).
- `utils/reskin/providers/__init__.py` (empty)
- `utils/reskin/transforms/__init__.py` (empty)
- `utils/reskin/tests/__init__.py` (empty)

Also create `utils/reskin/tests/test_config.py` — Port from Wesnoth's test_config.py, adapt theme path to point to the AC `themes/` dir.

**Verify:**

```bash
cd /workspace/athena-crisis && python -m pytest utils/reskin/tests/test_config.py -v
```

All tests should pass.

**Commit** when verified.

---

### Task 2: Implement asset discovery for Athena Crisis

**What to do:**

Create `utils/reskin/discovery.py`. This is the main component that differs from Wesnoth — instead of scanning filesystem directories by faction, we:

1. Parse `athena/info/SpriteVariants.tsx` with a regex to extract all `SpriteVariant` type union members (the strings like `'Units-Infantry'`, `'Buildings'`, etc.)
2. For each name, build the source URL: `https://art.athenacrisis.com/v19/{name}.png`
3. Download source images to a cache directory (`output/.cache/`) — skip if already cached
4. Classify by name prefix:
   - `Units-*` → `"unit-sprite"`
   - `Buildings`, `Building-Create` → `"building"`
   - `Portraits` → `"portrait"`
   - `Label`, `Medal`, `Message` → `"icon"`
   - `BuildingsShadow`, `StructuresShadow` → `"shadow"`
   - `Decorators` → `"decorator"`
   - Everything else (`Capture`, `Rescue`, `Spawn`, etc.) → `"effect"`

Use a dataclass `AssetInfo` with fields: `name` (str), `source_path` (str — path to cached file), `source_url` (str), `category` (str).

The `discover_assets()` function takes `repo_root` and optional `category` filter, returns `List[AssetInfo]`.

Use `urllib.request.urlretrieve` for downloads (no extra dependencies). Print progress: `[1/90] Downloading Units-Infantry...`

Create `utils/reskin/tests/test_discovery.py`:

- Test that parsing SpriteVariants.tsx finds ~90 names
- Test classification logic for each category
- Test category filter

**Verify:**

```bash
cd /workspace/athena-crisis && python -m pytest utils/reskin/tests/test_discovery.py -v
```

**Commit** when verified.

---

### Task 3: Implement providers (echo + FAL.ai Gemini)

**What to do:**

Create the provider layer — port directly from Wesnoth with minimal changes:

- `utils/reskin/providers/base.py` — Identical to Wesnoth. Abstract `ReskinProvider` with `transform(image_path, prompt, params) -> bytes` and `transform_grid(grid_path, prompt, output_path) -> bool`.

- `utils/reskin/providers/echo.py` — Identical to Wesnoth. Returns original image unchanged. Supports both `transform` and `transform_grid`. **One change**: fix the import path from `utils.reskin.providers.base` to a relative import `.base` since we're not running from the Wesnoth repo root.

- `utils/reskin/providers/fal_gemini.py` — Port from Wesnoth. Same FAL.ai API call to `fal-ai/gemini-3-pro-image-preview/edit`. Same retry logic (3 attempts with exponential backoff). Same output size validation (>= 1024px). Fix import paths to relative.

Create `utils/reskin/tests/test_providers.py`:

- Test EchoProvider.transform returns valid PNG bytes
- Test EchoProvider.transform_grid copies file
- Test FalGeminiProvider raises without FAL_KEY env var

**Verify:**

```bash
cd /workspace/athena-crisis && python -m pytest utils/reskin/tests/test_providers.py -v
```

**Commit** when verified.

---

### Task 4: Implement transforms (palette_swap + ai_reskin + grid_batch)

**What to do:**

Port all three transform modules from Wesnoth:

- `utils/reskin/transforms/palette_swap.py` — Port from Wesnoth identically. HSV-based color-family classification + hue/saturation shifting. No changes needed.

- `utils/reskin/transforms/ai_reskin.py` — Port from Wesnoth. Prompt templates adapted for Athena Crisis categories:
  - `"unit-sprite"`: "Reskin this 2D pixel art game unit sprite. Preserve transparency, silhouette, and animation pose. Style: {style}"
  - `"building"`: "Reskin this 2D pixel art game building sprite. Preserve transparency and structure. Style: {style}"
  - `"portrait"`: "Reskin this character portrait. Preserve face composition and expression. Style: {style}"
  - Default falls back to the unit-sprite template.

- `utils/reskin/transforms/grid_batch.py` — Port from Wesnoth with these adaptations:
  - `group_into_batches()` — same logic, takes `List[AssetInfo]` (our dataclass has `.source_path` and `.name` instead of `.relative_path`)
  - `render_grid()` — same canvas compositing logic
  - `build_grid_prompt()` — same per-cell prompt format, use `asset.category` and `asset.name` for cell descriptions
  - `extract_sprites_from_grid()` — identical inverse extraction
  - `restore_alpha()` — identical (RGB from AI, alpha from original)
  - `validate_sprite()` — identical (mean pixel diff > 3)
  - `extract_and_save()` — adapt output path to use `asset.name` instead of `asset.relative_path`

Create tests:

- `utils/reskin/tests/test_palette_swap.py` — Port from Wesnoth (uses synthetic test images)
- `utils/reskin/tests/test_grid_batch.py` — Test grid compositing + extraction roundtrip with small synthetic sprites. Create 4 tiny 32x32 RGBA PNGs, build a grid, extract, verify dimensions match.

**Verify:**

```bash
cd /workspace/athena-crisis && python -m pytest utils/reskin/tests/test_palette_swap.py utils/reskin/tests/test_grid_batch.py -v
```

**Commit** when verified.

---

### Task 5: Implement manifest and CLI entry point

**What to do:**

- `utils/reskin/manifest.py` — Port from Wesnoth identically. The only change: replace `faction` field with a generic `source` field since Athena Crisis doesn't have factions. Same `is_completed()`, `mark_completed()`, `mark_failed()`, `summary()` methods.

- `utils/reskin/reskin.py` — Main CLI entry point. Adapt from Wesnoth's `reskin.py`:
  - Replace `--faction` arg with Athena Crisis discovery (no faction needed — discovers all sprites)
  - Add `--category` filter (unit-sprite, building, portrait, icon, effect)
  - Add `--repo-root` defaulting to `../../` (two levels up from `utils/reskin/`)
  - Keep `--theme`, `--provider`, `--dry-run`, `--force`, `--palette-only`, `--batch`, `--output-dir`
  - Standard mode: iterate assets, apply AI or palette-swap per category (shadows/decorators always palette-only)
  - Batch mode: call `run_batch()` — same flow as Wesnoth (build grids → send to AI → extract)
  - Fix all import paths to be relative (not `from utils.reskin.X`)

The `sys.path` setup at the top of `reskin.py` should add the script's own directory so relative imports work when run directly.

Create `utils/reskin/tests/test_manifest.py` — Port from Wesnoth, adapt field names.

**Verify:**

```bash
# Unit tests
cd /workspace/athena-crisis && python -m pytest utils/reskin/tests/test_manifest.py -v

# Dry-run CLI (requires network to download sprites — tests the full pipeline)
cd /workspace/athena-crisis && python utils/reskin/reskin.py --theme cyberpunk --category unit-sprite --dry-run --batch
```

The dry-run should:

- Discover unit sprites
- Download source images to cache
- Build 4x4 grids
- "Restyle" with echo provider (copy unchanged)
- Extract sprites
- Print summary with completed count

**Commit** when verified.

---

### Task 6: Runtime integration in Sprites.tsx

**What to do:**

Add reskin override support to `art/Sprites.tsx` so that when local reskinned images are available, they're used instead of the CDN originals.

The integration point is in `_prepareSprites()`. Currently, each sprite's source image comes from `Variants.get(imageName)?.source` which points to `art.athenacrisis.com`. We need to:

1. At the top of `_prepareSprites()`, attempt to fetch `reskin/manifest.json` (relative URL — works in Rosebud's Vite dev server when files are in `public/reskin/`). If it doesn't exist, proceed normally (no reskin).

2. If the manifest exists, it contains `{ "basePath": "reskin/cyberpunk", "sprites": ["Units-Infantry", "Buildings", ...] }`. For each sprite name in the list, override the source URL to `{basePath}/{name}.png`.

3. This override happens before `loadImage()` is called, so the palette-swap system processes the reskinned source image and generates team-colored variants automatically.

The manifest format for the runtime is simpler than the build manifest — just a list of available sprites and the base path. The CLI's final step should generate this `manifest.json` alongside the output PNGs.

Also update `reskin.py` to write this runtime manifest after extraction completes.

**Verify:**

```bash
cd /workspace/athena-crisis && npx tsc --noEmit
```

TypeScript should compile without errors.

**Commit** when verified.

---

### Task 7: End-to-end dry-run test and documentation

**What to do:**

Create an integration test that runs the full pipeline end-to-end with the echo provider:

`utils/reskin/tests/test_integration.py`:

- Run `reskin.py --theme cyberpunk --batch --dry-run --output-dir <tmp>` as a subprocess
- Verify exit code 0
- Verify grid manifest exists with batch metadata
- Verify individual sprite PNGs exist in output dir
- Verify runtime manifest.json was generated
- Verify at least 80 sprites were processed

Also verify the full test suite passes:

```bash
cd /workspace/athena-crisis && python -m pytest utils/reskin/tests/ -v
```

**Verify:**

```bash
cd /workspace/athena-crisis && python -m pytest utils/reskin/tests/test_integration.py -v
```

**Commit** when verified.
