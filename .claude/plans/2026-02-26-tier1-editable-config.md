# Tier 1 Editable Config System — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use subagent-driven-development to implement this plan task-by-task.

**Goal:** Extract 5 categories of hardcoded game data into JSON config files that can be edited at runtime without rebuilding.

**Architecture:** Defaults stay compiled in TypeScript classes. At boot, the engine fetches JSON override files from `config/` and patches live registries before rendering. Missing/invalid files are silently ignored.

**Tech Stack:** TypeScript, Vite, React (existing stack — no new deps)

---

### Task 1: Make Configuration.tsx constants mutable

**What to do:**

In `athena/map/Configuration.tsx`, the gameplay constants (`MaxHealth`, `MinDamage`, `HealAmount`, `BuildingCover`, `CounterAttack`, `RaisedCounterAttack`, `Charge`, `MaxCharges`, `PoisonDamage`, `PowerStationMultiplier`, `LeaderStatusEffect`, `MoraleStatusEffect`, `AllowedMisses`, `CreateTracksCost`) are `export const`. These are used at runtime in damage calculations, healing, etc. — they need to become mutable so we can patch them after config load.

Change these from `const` to `let`. Do NOT change structural/UI constants (`AnimationSpeed`, `AnimationConfig`, `TileSize`, `DoubleSize`, `MinSize`, `MaxSize`, `MaxMessageLength`, `DecoratorsPerSide`, `DefaultMapSkillSlots`) — these are either animation/layout constants or not gameplay-relevant.

Add at the bottom of the file:

```ts
export function patchGameConfig(overrides: Record<string, number>) {
  for (const [key, value] of Object.entries(overrides)) {
    switch (key) {
      case 'MaxHealth':
        MaxHealth = value;
        break;
      case 'MinDamage':
        MinDamage = value;
        break;
      case 'HealAmount':
        HealAmount = value;
        break;
      case 'BuildingCover':
        BuildingCover = value;
        break;
      case 'CounterAttack':
        CounterAttack = value;
        break;
      case 'RaisedCounterAttack':
        RaisedCounterAttack = value;
        break;
      case 'Charge':
        Charge = value;
        break;
      case 'MaxCharges':
        MaxCharges = value;
        break;
      case 'PoisonDamage':
        PoisonDamage = value;
        break;
      case 'PowerStationMultiplier':
        PowerStationMultiplier = value;
        break;
      case 'LeaderStatusEffect':
        LeaderStatusEffect = value;
        break;
      case 'MoraleStatusEffect':
        MoraleStatusEffect = value;
        break;
      case 'AllowedMisses':
        AllowedMisses = value;
        break;
      case 'CreateTracksCost':
        CreateTracksCost = value;
        break;
    }
  }
}
```

The explicit switch ensures only known keys are patched and gives us live ES module binding updates.

**Verify:**

- `pnpm build:rosebud` — should succeed with no type errors
- Game should still run identically (no behavior change yet)

**Commit** when verified.

---

### Task 2: ConfigLoader + boot sequence wiring

**What to do:**

Create `rosebud/ConfigLoader.ts` — the central config loading module. It should:

1. Define the 5 config file paths (relative to app root): `config/game-config.json`, `config/unit-stats.json`, `config/damage-tables.json`, `config/tiles.json`, `config/buildings.json`
2. Export an async `loadAndApplyConfigs()` function that:
   - Fetches all 5 JSON files in parallel using `Promise.allSettled`
   - For each fulfilled result, calls the corresponding patcher
   - Silently ignores rejected fetches (file doesn't exist) and JSON parse errors
   - Logs warnings to console for parse errors (helpful for debugging bad AI edits)

For now, only wire up `game-config.json` patching (call `patchGameConfig` from Configuration.tsx). The other 4 patchers will be added in subsequent tasks — just leave commented placeholder calls.

Modify `rosebud/main.tsx` boot sequence:

- The current synchronous boot is: `initializeCSSVariables()` → `initializeCSS()` → `prepareSprites()` → `AudioPlayer.resume()` → `createRoot().render(<App />)`
- Change to: wrap the `createRoot().render()` call in an async IIFE that awaits `loadAndApplyConfigs()` first
- Keep CSS/sprite/audio initialization synchronous (before the await) since they don't depend on configs
- Pattern: `loadAndApplyConfigs().then(() => { createRoot(...).render(<App />) })`

**Verify:**

- `pnpm build:rosebud` — should succeed
- Game boots normally with no `config/` directory present (no errors in console)
- Create `rosebud/public/config/game-config.json` with `{"HealAmount": 99}` and verify no crash (actual value verification comes after full wiring)

**Commit** when verified.

---

### Task 3: Unit stats + damage tables patching

**What to do:**

Add two patcher functions in `rosebud/ConfigLoader.ts` (or a separate `rosebud/configPatchers.ts` if ConfigLoader gets long):

**Unit stats patcher:**

- Import `getUnitInfo` from `athena/info/Unit.tsx` and the `Units` array (it's not exported — you'll need to add an export or use `getUnitInfoOrThrow` with known IDs, or import the individual named unit exports). Actually, the simplest approach: import `filterUnits` and use it to find units by name.
- JSON shape: `{ "Infantry": { "cost": 100, "fuel": 50, "vision": 3, "radius": 4, "defense": 10 }, ... }`
- For each unit name in the JSON, find the matching `UnitInfo` by name using `filterUnits(u => u.name === name)[0]`
- Patch numeric properties. The tricky part: `cost` and `radius` are private fields. Use `(unitInfo as any).cost = value` to bypass TypeScript's private access — this is fine since it's a Rosebud-only runtime patch, not modifying the core engine types.
- For `configuration` sub-properties (fuel, vision): patch them on the `configuration` object directly: `(unitInfo.configuration as any).fuel = value`
- Do NOT patch sprite data, abilities, or entity types — only numeric stats.

**Damage tables patcher:**

- Import `Weapons` from `athena/info/Unit.tsx`
- JSON shape: `{ "SoldierMG": { "Soldier": 60, "Ground": 15 }, ... }`
- For each weapon name, find matching weapon in `Weapons` object by key
- For each target type → damage entry, resolve EntityType by name (create a `entityTypeByName` lookup map from `EntityType` enum) and call `(weapon.damage as Map<EntityType, number>).set(entityType, damage)`
- `ReadonlyMap` is just a TS type — at runtime it's a mutable `Map`

Wire both into `loadAndApplyConfigs()`.

**Verify:**

- `pnpm build:rosebud` succeeds
- Create `rosebud/public/config/unit-stats.json` with `{"Infantry": {"cost": 999}}` — build, open game, check Infantry cost in build menu shows 999
- Create `rosebud/public/config/damage-tables.json` with a test override — verify no crash

**Commit** when verified.

---

### Task 4: Tiles + buildings patching

**What to do:**

**Tiles patcher:**

- Import `getTileInfo` from `athena/info/Tile.tsx`. The `Tiles` array isn't exported, but individual tiles are (Plain, Forest, Mountain, etc.). Use a name-based lookup: collect all exported TileInfo instances.
- Actually, simpler: import `getTileInfo` and iterate IDs 1..43 to build a name→TileInfo map.
- JSON shape: `{ "Forest": { "cover": 25, "movement": { "Soldier": 1, "Tires": 3 }, "vision": 2 }, ... }`
- For each tile name, find matching `TileInfo` and patch:
  - `(tileInfo.configuration as any).cover = value`
  - For movement costs: resolve `MovementType` by name from `MovementTypes` and call `(tileInfo.configuration.movement as Map<MovementType, number>).set(type, cost)`
  - `(tileInfo.configuration as any).vision = value`

**Buildings patcher:**

- Import `getBuildingInfo` from `athena/info/Building.tsx`, iterate IDs 1..22 for name lookup
- JSON shape: `{ "Factory": { "defense": 20, "funds": 200, "cost": 500 }, ... }`
- Patch numeric properties: `(buildingInfo as any).defense = value`, `(buildingInfo.configuration as any).funds = value`, `(buildingInfo as any).cost = value`
- Defer production list editing (unitTypes/restrictedUnits) to a future iteration — it requires Set manipulation and cross-referencing unit names, which is complex and error-prone

Wire both into `loadAndApplyConfigs()`.

**Verify:**

- `pnpm build:rosebud` succeeds
- Create test `config/tiles.json` and `config/buildings.json` with simple numeric overrides — verify no crash
- Spot-check: override Forest cover to 50, verify in-game tooltip (if visible) or via console

**Commit** when verified.

---

### Task 5: Config generator script

**What to do:**

Create `rosebud/scripts/generate-configs.ts` — a Node script (run with `tsx`) that imports the game registries and dumps full default values to JSON.

The script should:

1. Import all unit, tile, building, weapon info and Configuration constants
2. Generate 5 JSON files in `rosebud/public/config/`:
   - `game-config.json` — all patchable constants from Configuration.tsx
   - `unit-stats.json` — all 56 units with their editable numeric properties
   - `damage-tables.json` — all weapons with their damage maps (EntityType names as keys)
   - `tiles.json` — all 43 tiles with cover, movement costs, vision
   - `buildings.json` — all 22 buildings with defense, funds, cost
3. Pretty-print with 2-space indent for readability

Add a script to `rosebud/package.json`: `"generate-configs": "tsx scripts/generate-configs.ts"`

**Verify:**

- Run `cd rosebud && pnpm generate-configs`
- All 5 JSON files are created in `rosebud/public/config/`
- Files are valid JSON and contain expected data (spot-check Infantry cost=200, Forest cover=20, MaxHealth=100)

**Commit** when verified.

---

### Task 6: End-to-end verification

**What to do:**

Create a sample set of config overrides in `rosebud/public/config/` that make visible gameplay changes:

1. `game-config.json`: `{ "HealAmount": 75 }` (units heal more on buildings)
2. `unit-stats.json`: `{ "Infantry": { "cost": 50 } }` (cheap infantry)
3. `damage-tables.json`: pick one weapon, double a damage value
4. `tiles.json`: `{ "Forest": { "cover": 40 } }` (forests give more cover)
5. `buildings.json`: `{ "Factory": { "defense": 30 } }` (tougher factories)

Build and run the game. Verify:

- Game boots without errors
- At least one override is visibly confirmed (Infantry cost in build menu)
- No console errors related to config loading
- Remove all config files — game still boots fine with defaults

After verification, remove the test overrides (don't ship modified defaults). The generated reference files from Task 5 can stay.

**Verify:**

- `pnpm build:rosebud` succeeds
- `pnpm --filter rosebud preview` — game loads, overrides visible
- Delete config files — game loads with defaults

**Commit** when verified (clean state with generator output only).
