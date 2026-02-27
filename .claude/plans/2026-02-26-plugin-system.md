# Plugin/Mod System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use subagent-driven-development to implement this plan task-by-task.

**Goal:** Add a runtime plugin system so Rosebud users can register new units/buildings, override stats, and attach emit-only lifecycle hooks — all without rebuilding the engine.

**Architecture:** A `window.AthenaEngine` global API is exposed at boot. A mod loader reads `mods.json`, fetches each listed JS file, and evals it. Mods call `AthenaEngine.registerUnit()`, `.on()`, etc. Hooks fire after action responses and emit new actions back into the dispatcher. Tier 1 config loading (JSON overrides) is already implemented in `rosebud/ConfigLoader.ts`.

**Tech Stack:** TypeScript (engine internals), plain JS (mod files), existing Athena Crisis action/entity system

---

### Task 1: Create the hook event emitter

**What to do:**
Create `rosebud/HookSystem.ts` — a typed event emitter that stores hook callbacks by event name and fires them with context.

Supported events: `turnStart`, `turnEnd`, `afterAttack`, `afterCapture`, `unitCreated`, `unitDestroyed`, `moveComplete`.

The `on(event, callback)` method registers a callback. The `emit(event, ctx)` method fires all registered callbacks for that event, collects returned action arrays, flattens them, and returns the combined list.

The context object (`HookContext`) passed to callbacks should contain:

- `map`: current MapData (read-only reference)
- `activePlayer`: PlayerID
- `actionResponse`: the ActionResponse that triggered this hook
- Plus event-specific fields extracted from the actionResponse (e.g., `source`/`target` positions for attack events)

Key decision: callbacks return `Array<{type: string, [key: string]: unknown}>` (plain objects, not typed ActionResponse). The engine validates and converts them before dispatch. This keeps mod code simple (users write plain objects, not typed TS).

**Verify:**

- `npx tsc --noEmit` passes
- Unit test: instantiate HookSystem, register a hook, emit an event, verify returned actions

**Commit** when verified.

---

### Task 2: Create entity registration functions

**What to do:**
Create `rosebud/EntityRegistry.ts` with functions to register new units, buildings, and tiles at runtime.

`registerUnit(config)`:

- `config.base` (string) — name of existing unit to inherit from (looked up via `filterUnits`)
- `config.name` (string) — name for the new unit
- `config.overrides` (object) — stat overrides: `cost`, `fuel`, `vision`, `radius`, `defense`
- Creates a new `UnitInfo` instance by cloning the base unit's constructor args with overrides applied
- Appends to the `Units` array (the array in `athena/info/Unit.tsx` currently isn't exported as mutable). Solution: export a `registerCustomUnit(info: UnitInfo)` function from `Unit.tsx` that pushes to the array and returns the new ID.
- Returns the new numeric ID

`registerBuilding(config)` and `registerTile(config)` follow the same pattern. Each needs a corresponding `registerCustomX` function exported from the info module.

Key decision: the `Units` array comment says "order must not be changed" — this applies to existing entries. Appending new entries at the end is safe since existing IDs (1-based index) are preserved. New units get IDs 57+.

Key challenge: `UnitInfo` constructor takes ~14 positional args including complex types (sprites, weapons, abilities). For the base-clone approach, the simplest path is to add a `clone(overrides)` method to `UnitInfo` that creates a new instance with the same args but overridden stats and a new ID. Same for `BuildingInfo` and `TileInfo`.

**Verify:**

- `npx tsc --noEmit` passes
- Unit test: register a unit based on Infantry, verify it gets ID 57, verify `getUnitInfo(57)` returns it with overridden stats

**Commit** when verified.

---

### Task 3: Create state query helpers

**What to do:**
Create `rosebud/StateQueries.ts` with read-only query functions that mods use inside hook callbacks. These are thin wrappers around MapData methods, designed to work with a MapData reference that the hook system provides.

Functions (all take `map: MapData` as first arg):

- `getUnitAt(map, position)` → unit info + health + player, or null
- `getBuildingAt(map, position)` → building info + player, or null
- `getTileAt(map, position)` → tile info
- `getAdjacentUnits(map, position, playerFilter?)` → array of unit summaries at adjacent positions
- `getUnitsForPlayer(map, playerId)` → array of all units for that player

Return plain objects (not class instances) so mods get simple data. Use `map.units.get(vec)`, `map.buildings.get(vec)`, `map.getTileInfo(vec)` internally.

The adjacency helper uses `map.contains(adjacent)` to bounds-check and iterates the 4 cardinal directions.

**Verify:**

- `npx tsc --noEmit` passes

**Commit** when verified.

---

### Task 4: Assemble and expose `window.AthenaEngine`

**What to do:**
Create `rosebud/AthenaEngine.ts` that assembles the public API from the hook system, entity registry, state queries, and existing config patchers.

```ts
window.AthenaEngine = {
  // Entity registration (from Task 2)
  registerUnit,
  registerBuilding,
  registerTile,
  // Stat overrides (existing from ConfigLoader + new wrappers)
  patchUnit,
  patchBuilding,
  patchTile,
  patchDamageTable,
  patchGameConfig,
  // Hooks (from Task 1)
  on: hookSystem.on,
  // Queries (from Task 3, bound to current map)
  getUnitAt,
  getBuildingAt,
  getTileAt,
  getAdjacentUnits,
  getUnitsForPlayer,
  // Introspection
  getUnitInfo,
  getBuildingInfo,
  getAllUnits,
  getAllBuildings,
};
```

The `patchUnit`, `patchBuilding`, `patchTile`, `patchDamageTable` functions are extracted from `ConfigLoader.ts` into reusable exports (they already exist as `patchUnitStats` etc. — just re-export with cleaner names and single-entity signatures).

For query functions: they need access to the current MapData. Use a setter `AthenaEngine._setMap(map)` called by the game loop whenever state changes. The public query functions call through to `StateQueries` with the current map.

Also add TypeScript declarations for `window.AthenaEngine` so the engine code can reference it without errors.

**Verify:**

- `npx tsc --noEmit` passes
- `window.AthenaEngine` is available in browser console after boot

**Commit** when verified.

---

### Task 5: Create the mod loader

**What to do:**
Create `rosebud/ModLoader.ts` with an async `loadMods()` function.

Flow:

1. `fetch('mods.json')` — if 404 or invalid JSON, return silently (no mods)
2. Validate the manifest: expect `{ mods: string[] }`
3. For each mod path in `mods` array:
   a. `fetch(modPath)` to get the JS source text
   b. Wrap in try/catch and execute via `new Function(source)()`
   c. On error: `console.error('[ModLoader] Failed to load mod:', path, error)`, continue to next mod
4. Log loaded mod count to console

Key decision: use `new Function(source)()` rather than `eval()` or dynamic `import()`. `Function` creates a new scope (mod can't access engine internals except through the global `AthenaEngine`). Dynamic `import()` won't work because Rosebud serves raw JS files, not ES modules.

**Verify:**

- `npx tsc --noEmit` passes
- Manual test: create a test `mods.json` and a simple mod file, verify mod code runs at boot

**Commit** when verified.

---

### Task 6: Integrate hook firing into the action pipeline

**What to do:**
Wire the HookSystem's `emit()` calls into the engine's action response processing so hooks actually fire at the right moments.

The main integration point is `apollo/actions/executeGameAction.tsx`. After `applyConditions` returns the gameState, iterate through the action responses and fire hooks:

- `AttackUnit` / `AttackBuilding` → fire `afterAttack`
- `Capture` → fire `afterCapture`
- `CreateUnit` → fire `unitCreated`
- `EndTurn` → fire `turnEnd` (for ending player) + `turnStart` (for next player)
- `Move` → fire `moveComplete`
- When a unit's health reaches 0 in AttackUnit → fire `unitDestroyed`

For each hook event, build the context from the actionResponse and current map state.

The tricky part: hooks return new action objects that need to be dispatched. These should be validated, then applied via `applyActionResponse` and appended to the gameState array. This creates a mini-loop: hook actions can themselves trigger hooks (but cap recursion at depth 3 to prevent infinite loops).

Key decision: Hook integration should be behind a feature flag / optional import so the core `apollo` module doesn't hard-depend on rosebud code. Approach: `executeGameAction` accepts an optional `onActionResponse` callback parameter. Rosebud passes the hook system's emit function as this callback. This keeps `apollo` clean.

**Verify:**

- `npx tsc --noEmit` passes
- Integration test: register a hook for `afterAttack` that emits a Heal action, verify the heal appears in the gameState after an attack

**Commit** when verified.

---

### Task 7: Update boot sequence to load mods

**What to do:**
Update `rosebud/main.tsx` boot sequence to:

1. Call `initAthenaEngine()` (from Task 4) — exposes `window.AthenaEngine`
2. Call `loadAndApplyConfigs()` (existing) — applies JSON config overrides
3. Call `loadMods()` (from Task 5) — runs mod files that call AthenaEngine APIs
4. Then render `<App />`

Current boot is:

```ts
loadAndApplyConfigs().then(() => {
  const root = createRoot(document.getElementById('root')!);
  root.render(<App />);
});
```

Change to:

```ts
initAthenaEngine();
loadAndApplyConfigs()
  .then(() => loadMods())
  .then(() => {
    const root = createRoot(document.getElementById('root')!);
    root.render(<App />);
  });
```

Also wire the `AthenaEngine._setMap(map)` call into the game components so queries work with current state. The right place is in `useClientGame` or wherever the game state updates — pass the map to the engine on each state change.

Wire the hook callback into the action execution path — pass the hook system's emit function as the `onActionResponse` callback to `executeGameAction` (via the worker or directly depending on how actions are dispatched in Rosebud).

**Verify:**

- `npm run build:rosebud` succeeds
- Game boots normally without any mods.json (graceful fallback)
- Game boots normally with empty `mods.json`: `{"mods": []}`

**Commit** when verified.

---

### Task 8: Write example mods and test end-to-end

**What to do:**
Create example mod files to validate the full pipeline:

1. `rosebud/examples/mods.json` — manifest listing the example mods
2. `rosebud/examples/mods/stat-override.js` — simple mod that patches Infantry to cost 100 and have 5 vision (validates `patchUnit` works from mod context)
3. `rosebud/examples/mods/custom-unit.js` — registers a "Heavy Infantry" unit based on Infantry with higher defense and cost (validates `registerUnit`)
4. `rosebud/examples/mods/heal-on-attack.js` — registers an `afterAttack` hook that heals the attacker by 10 HP if they survived (validates hook system end-to-end)

**Verify:**

- Copy example files to the rosebud build output
- Boot the game, start a match
- Verify Infantry costs 100 (stat override mod)
- Verify Heavy Infantry appears in unit build list (custom unit mod)
- Attack with a unit and verify it heals afterwards (hook mod)
- Use **playwright-playtesting** to screenshot the build menu showing the modded units
- Use **visual-analysis** to confirm the custom unit appears

**Commit** when verified.
