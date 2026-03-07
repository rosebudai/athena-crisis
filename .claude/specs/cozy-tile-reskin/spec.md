# Cozy Tile Reskin

## Goal

Extend the Athena Crisis reskin system to support terrain tile overrides, then reskin the Grassland biome (Tiles0) with the cozy theme.

## Architecture

1. **Extend `manifest.json`** — add a `tiles` map alongside existing `sprites` array:

```json
{
  "basePath": "reskin/cozy",
  "sprites": [],
  "tiles": {
    "Tiles0": "reskin/cozy/Tiles0.png"
  }
}
```

2. **Patch `hera/render/Images.tsx`** — after the manifest loads, swap `Tiles0.src` to the local override URL before the game renders. The existing `Tiles0` export is an `HTMLImageElement` — changing `.src` triggers a reload.

3. **Download + reskin `Tiles0.png`** — fetch the original from CDN, run through nano_banana with the cozy theme, output to `rosebud/public/reskin/cozy/Tiles0.png`.

4. **Wire manifest loading into tile path** — the manifest is already fetched in `art/Sprites.tsx`. Expose the tile overrides so `hera/render/Images.tsx` can consume them (either re-fetch manifest there, or export the parsed data).

## Data Flow

```
manifest.json (tiles field)
  → hera/render/Images.tsx reads tile overrides
  → swaps Tiles0.src to local PNG before first render
  → hera/Tiles.tsx picks up the swapped HTMLImageElement as usual
```

## Key Files

- `rosebud/public/reskin/manifest.json` — manifest with tiles field
- `hera/render/Images.tsx` — tile image loading (Tiles0-Tiles6 HTMLImageElements)
- `art/Sprites.tsx` — existing reskin manifest loading (pattern to follow)
- `hera/Tiles.tsx` — biome→atlas mapping
- `rosebud/reskin/themes/cozy.json` — cozy theme config
- `rosebud/reskin/reskin.py` — pipeline CLI

## Acceptance Criteria

### Must Have

- [ ] `manifest.json` supports a `tiles` field mapping tile names to override paths
- [ ] Runtime loads tile overrides and swaps `HTMLImageElement.src` before first render
- [ ] Grassland biome (Tiles0) displays the cozy-reskinned atlas in-game
- [ ] Empty `tiles` field (or missing) falls back to CDN originals with no errors
- [ ] Reskinned `Tiles0.png` exists at `rosebud/public/reskin/cozy/Tiles0.png`

### Out of Scope

- Other biomes (Tiles1-Tiles6)
- Unit/building sprite reskins for cozy theme
- Per-faction theming runtime support

## QA Plan

1. Start dev server: `pnpm --filter @deities/rosebud dev --host 0.0.0.0`
2. Open http://localhost:5173/
3. Start a game on a Grassland map
4. Verify terrain tiles show cozy-reskinned art (not default pixel art)
5. Check browser console for `[Reskin]` log confirming tile override loaded
6. Remove `tiles` from manifest → verify game falls back to default tiles
