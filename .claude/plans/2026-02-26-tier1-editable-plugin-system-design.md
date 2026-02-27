# Athena Crisis: Tier 1 Editable Game + Plugin System

**Linear:** ENG-3896 — Port Athena Crisis to Rosebud
**Date:** 2026-02-26

## Goal

Make Athena Crisis a "Tier 1 Editable" game on Rosebud: users (via AI agent or manual editing) can customize game balance, add new units/buildings, and attach scripted behaviors — all without rebuilding the engine.

## Architecture

Pre-built Vite engine bundle (`main.js`) is immutable. All customization happens via:

- **JSON config files** — override stats, constants, damage tables (Tier 1)
- **JS mod files** — register new entities and lifecycle hooks (Level 2)

### Boot Sequence

```
index.html → main.js (pre-built engine)
  → expose window.AthenaEngine API
  → fetch + apply JSON configs (game-config, unit-stats, damage-tables, tiles, buildings)
  → fetch mods.json → load each mod file
     → mods call AthenaEngine.registerUnit(), .on(), etc.
  → fetch map.json or use built-in catalog
  → prepareSprites() → render game
```

### Project File Structure

```
project/
├── index.html              ← loads engine bundle
├── main.js                 ← pre-built engine (never edited)
├── game-config.json        ← global constants (heal, counter-attack, poison, etc.)
├── unit-stats.json         ← stat overrides for existing 56 units
├── damage-tables.json      ← weapon effectiveness overrides
├── tiles.json              ← terrain movement/cover/vision overrides
├── buildings.json          ← building production/defense overrides
├── mods.json               ← manifest listing active mod files
├── mods/
│   ├── medic-infantry.js   ← example: new unit + heal-on-attack hook
│   └── weather-system.js   ← example: turn-based weather affecting terrain
├── styles.css              ← visual customization
└── assets/                 ← custom sprites (future)
```

## Engine API (`window.AthenaEngine`)

### Entity Registration

- `registerUnit(config)` → numeric ID (appends to Units array)
- `registerBuilding(config)` → numeric ID
- `registerTile(config)` → numeric ID

New entities use `base` field to inherit from existing types, with `overrides` for changed stats.

### Stat Overrides (Tier 1)

- `patchUnit(idOrName, overrides)`
- `patchBuilding(idOrName, overrides)`
- `patchTile(idOrName, overrides)`
- `patchDamageTable(weaponName, overrides)`
- `patchGameConfig(overrides)` — already partially exists in Configuration.tsx

### Lifecycle Hooks (emit-only)

Callbacks return `Action[]` that feed back into the action dispatcher:

- `on('turnStart', ctx => Action[])`
- `on('turnEnd', ctx => Action[])`
- `on('afterAttack', ctx => Action[])`
- `on('afterCapture', ctx => Action[])`
- `on('unitCreated', ctx => Action[])`
- `on('unitDestroyed', ctx => Action[])`
- `on('moveComplete', ctx => Action[])`

### Hook Context (`ctx`)

- `ctx.map` — current MapData snapshot (read-only)
- `ctx.activePlayer` — current player
- `ctx.source` / `ctx.target` — involved entities
- `ctx.position` — event location
- `ctx.actionResponse` — original ActionResponse

### State Queries (for use in hooks)

- `getUnitAt(position)`, `getBuildingAt(position)`, `getTileAt(position)`
- `getAdjacentUnits(position, playerFilter?)`
- `getUnitsForPlayer(playerId)`
- `getUnitInfo(idOrName)`, `getBuildingInfo(idOrName)`
- `getAllUnits()`, `getAllBuildings()`

## Mod File Format

Plain JS (no imports, no JSX, no build step). Uses global `AthenaEngine` API.

```js
// mods/medic-infantry.js
const medicId = AthenaEngine.registerUnit({
  base: 'Infantry',
  name: 'Medic',
  overrides: { cost: 250, vision: 3 },
});

AthenaEngine.on('afterAttack', (ctx) => {
  if (ctx.source?.info.id !== medicId) return;
  const allies = AthenaEngine.getAdjacentUnits(ctx.source.position, ctx.activePlayer).filter(
    (u) => u.health < 100,
  );
  return allies.map((u) => ({ type: 'Heal', unit: u.id, amount: 20 }));
});
```

### Conventions

- One mod per file, named descriptively
- Mods execute top-to-bottom at boot (before first game frame)
- Mods can hold local state via closures
- Hook ordering: manifest order, then registration order within a mod
- Emitted actions validated — invalid actions dropped with console.warn

## Error Handling

**Principle:** The game always boots. Bad configs or broken mods degrade gracefully.

| Scenario                  | Behavior                                |
| ------------------------- | --------------------------------------- |
| Config file: valid JSON   | Apply overrides                         |
| Config file: invalid JSON | console.warn, use compiled defaults     |
| Config file: 404/missing  | Silently use defaults                   |
| Mod file: runs cleanly    | Registered                              |
| Mod file: throws error    | console.error, skip mod, game continues |
| Mod file: 404/missing     | console.warn, skip mod                  |
| mods.json: missing        | No mods loaded, vanilla game            |
| Hook emits invalid action | console.warn, action dropped            |

## Engine Changes Required

1. **Config loader** — new module that fetches all JSON configs at boot, applies via patch functions
2. **Patch functions** — extend existing `patchGameConfig()` pattern to units, buildings, tiles, damage tables
3. **Entity registration** — safe append to Units/Buildings/Tiles arrays with new IDs
4. **Hook system** — event emitter integrated into action dispatch pipeline (applyActionResponse.tsx, applyEndTurnActionResponse.tsx)
5. **Mod loader** — fetch mods.json, load each mod via fetch+Function, error handling
6. **AthenaEngine global** — assemble and expose the API object before mod loading
7. **State query helpers** — thin wrappers around existing MapData methods for mod use
8. **Boot sequence refactor** — make rosebud/main.tsx async-aware, load configs+mods before game render

## Out of Scope

- Custom sprites/assets for new units
- `before*` middleware hooks (modify actions pre-execution)
- AI config extraction (deeply embedded heuristics)
- New action types defined by mods
- Mod dependency management or versioning
- JS sandboxing for mod execution
