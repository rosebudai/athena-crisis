# AI Reskin Pipeline v2 — Large Assets Only

## Overview

Proof-of-concept that reskins Portraits and Buildings via AI (FAL.ai Gemini) and renders them in-game, bypassing the palette-swap system entirely. Unit sprites keep original art since AI can't handle tiny sprite sheet frames.

## Architecture

Reuse the existing `utils/reskin/` pipeline with targeted changes:

1. **Pipeline:** Send Buildings, Building-Create, and Portraits sheets directly to FAL.ai Gemini (no 4x4 grid batching — each sheet is already one image).
2. **Runtime (`art/Sprites.tsx`):** When a reskin override exists, bypass `@nkzw/palette-swap` entirely and use the reskinned image for all player variants (0-7).
3. **Output:** 3 reskinned PNGs + `manifest.json` in `rosebud/public/reskin/<theme>/`.

## What Exists (from v1)

- `utils/reskin/` Python package: config, discovery, manifest, providers (echo + fal_gemini), transforms, CLI
- `art/Sprites.tsx` reskin override loading (`reskinSources` map, `loadReskinSources()`)
- Discovery downloads from CDN using `-0` variant suffix
- 34 passing unit tests

## Changes Needed

### 1. Fix Sprites.tsx palette-swap bypass

The `if (reskinSource) { ... continue; }` bypass block was added but not verified working. It needs:

- `createCanvasFromImage()` helper (already added)
- The bypass uses the reskinned image directly for all variants, skipping `swap()`
- Verify it produces no console errors and the game loads

### 2. Add single-image AI transform mode

Current pipeline has two modes: single-image (`ai_reskin.py`) and batch grid (`grid_batch.py`). For large assets, use single-image mode directly — no grid batching needed. The `reskin.py` CLI standard mode (without `--batch`) already does this.

### 3. Run pipeline for portrait + building categories

```bash
FAL_KEY="..." python utils/reskin/reskin.py \
  --theme cyberpunk --category portrait --provider fal_gemini
FAL_KEY="..." python utils/reskin/reskin.py \
  --theme cyberpunk --category building --provider fal_gemini
```

### 4. Copy output and rebuild

Copy reskinned PNGs to `rosebud/public/reskin/cyberpunk/`, write manifest listing only these 3 sprites, rebuild Rosebud.

## Acceptance Criteria

### Must Have

- [ ] Pipeline reskins Portraits, Buildings, and Building-Create via FAL.ai Gemini
- [ ] Reskinned sprites are placed in `rosebud/public/reskin/<theme>/`
- [ ] `manifest.json` lists only the 3 reskinned sprites
- [ ] `Sprites.tsx` loads reskin overrides and bypasses palette-swap (no console errors)
- [ ] Game loads and renders to gameplay screen without crashing
- [ ] Reskinned buildings and portraits are visually different from originals in-game

### Out of Scope

- Unit sprite reskinning
- Team color differentiation for reskinned sprites
- Multiple theme support
- Production quality output

## QA Plan

1. Run `pnpm vite build -c ./rosebud/vite.config.ts ./rosebud/` — build succeeds
2. Run `pnpm vite preview --host 0.0.0.0 --port 5173 -c ./rosebud/vite.config.ts ./rosebud/`
3. Playwright: navigate to `http://localhost:5173/`, click Play → Start Game
4. Screenshot gameplay map — buildings and portraits should look visually different
5. Check browser console — `[Reskin] Loaded 3 sprite overrides` message, no palette-swap errors
6. No "FAILED TO LOAD" error dialog
