# Plugin System — QA Testing Instructions

## Prerequisites

```bash
cd /workspace/athena-crisis
npm run build:rosebud
# Serve from dist: npx serve dist/rosebud -l 5173
# OR use dev server: cd rosebud && npx vite --host 0.0.0.0 --port 5173
```

Open browser at `http://localhost:5173`. Open DevTools console to monitor logs.

---

## UC-1: Game boots cleanly without any config/mod files

**Setup:** Remove or rename `config/` directory and `mods.json` from the served directory.

**Steps:**

1. Load the app in browser
2. Observe the console output

**Expected:**

- Console shows `[ModLoader] No mods.json found, skipping mods` (or similar)
- No errors in console related to config loading
- Game loads to title screen normally
- All menus work, can start a new game
- All 56 built-in units are available at their default stats

---

## UC-2: JSON config overrides (Tier 1)

### UC-2a: game-config.json

**Setup:** Create `config/game-config.json`:

```json
{
  "MaxHealth": 50,
  "HealAmount": 25,
  "CounterAttack": 0.5
}
```

**Steps:**

1. Load app, start a new game
2. Create a unit and check its max health
3. Place a unit on a healing building and end turn

**Expected:**

- Units spawn with 50 HP (not 100)
- Healing restores 25 HP (not 50)
- Counter-attack damage is reduced (50% vs default 75%)

### UC-2b: unit-stats.json

**Setup:** Create `config/unit-stats.json`:

```json
{
  "Infantry": { "cost": 50, "vision": 5 },
  "SmallTank": { "defense": 30 }
}
```

**Steps:**

1. Load app, start game, open build menu at a Factory
2. Check Infantry cost and SmallTank defense

**Expected:**

- Infantry costs 50 (default: 150)
- Infantry vision is 5 (default: 2)
- SmallTank defense is 30 (default: 15)
- Other units unchanged

### UC-2c: Invalid config graceful degradation

**Setup:** Create `config/unit-stats.json` with invalid JSON:

```
{ this is not valid json
```

**Steps:**

1. Load app, observe console

**Expected:**

- Console shows a warning about failed config parsing
- Game boots normally with all default values
- No blank screen or crash

### UC-2d: Unknown unit/tile/building names in configs

**Setup:** Create `config/unit-stats.json`:

```json
{
  "FakeUnit": { "cost": 999 },
  "Infantry": { "cost": 100 }
}
```

**Steps:**

1. Load app, observe console

**Expected:**

- Console warns: `[ConfigLoader] patchUnitStats: unknown unit "FakeUnit"`
- Infantry cost IS applied (100)
- Game boots normally

---

## UC-3: Mod loading system

### UC-3a: Mods load in manifest order

**Setup:** Use the default `mods.json` with all 3 example mods.

**Steps:**

1. Load app, observe console

**Expected (in order):**

- `[Mod] Infantry stats overridden: cost=100, vision=4`
- `[Mod] Registered Heavy Infantry with ID: 57`
- `[Mod] Heal-on-attack enabled: units heal 20 HP after attacking`
- `[ModLoader] Loaded 3 mod(s)`

### UC-3b: Broken mod doesn't block other mods

**Setup:** Create `mods/broken.js`:

```js
throw new Error("I'm broken!");
```

Update `mods.json`:

```json
{
  "mods": ["mods/broken.js", "mods/stat-override.js"]
}
```

**Steps:**

1. Load app, observe console

**Expected:**

- Console shows `[ModLoader] Error executing mod: mods/broken.js` with the error
- `stat-override.js` still loads successfully
- Game boots normally

### UC-3c: Missing mod file

**Setup:** Reference a non-existent file in `mods.json`:

```json
{
  "mods": ["mods/does-not-exist.js", "mods/stat-override.js"]
}
```

**Steps:**

1. Load app, observe console

**Expected:**

- Console warns about failed fetch for `does-not-exist.js`
- `stat-override.js` still loads
- Game boots normally

### UC-3d: Empty mods array

**Setup:** `mods.json`:

```json
{ "mods": [] }
```

**Steps:**

1. Load app

**Expected:**

- No mod-related warnings
- Game boots with all default values

---

## UC-4: Entity registration (custom units)

### UC-4a: Register a new unit via mod

**Setup:** Use `mods/custom-unit.js` (registers "Heavy Infantry" based on Infantry).

**Steps:**

1. Load app, start new game
2. Build a Factory, open build menu
3. Look for "Heavy Infantry" in the unit list

**Expected:**

- "Heavy Infantry" appears in the build menu
- Cost is 300 (vs Infantry's 150)
- Defense is 20 (vs Infantry's 5)
- Vision is 2 (vs Infantry's default)
- It reuses Infantry's sprite
- It has all Infantry abilities (capture, etc.)

### UC-4b: Registered unit persists through gameplay

**Steps:**

1. Build a Heavy Infantry unit
2. Move it, attack with it, capture a building with it
3. End multiple turns

**Expected:**

- Unit functions identically to Infantry except for stat differences
- No errors in console during any action
- Unit persists across turns

---

## UC-5: Stat patching via AthenaEngine API

### UC-5a: patchUnit by name

**Setup:** `mods/stat-override.js` patches Infantry (cost=100, vision=4).

**Steps:**

1. Load app, start game, check Infantry in build menu

**Expected:**

- Infantry cost is 100
- Infantry vision is 4
- Other stats unchanged

### UC-5b: patchUnit by ID (console test)

**Steps:**

1. Open browser console
2. Run: `AthenaEngine.patchUnit(1, { cost: 50 })`
3. Check Infantry cost in build menu

**Expected:**

- Infantry cost changes to 50

### UC-5c: getUnitInfo introspection

**Steps:**

1. Open browser console during a game
2. Run: `AthenaEngine.getUnitInfo('Infantry')`
3. Run: `AthenaEngine.getUnitInfo(1)`
4. Run: `AthenaEngine.getAllUnits()`

**Expected:**

- Both calls return the Infantry UnitInfo object
- `getAllUnits()` returns array of all units including any registered custom units

---

## UC-6: Lifecycle hooks

### UC-6a: afterAttack hook fires

**Setup:** Use `mods/heal-on-attack.js`.

**Steps:**

1. Start a game with two opposing players (or play vs AI)
2. Position an Infantry unit adjacent to an enemy
3. Attack the enemy

**Expected:**

- Attack resolves normally
- Attacking unit heals 20 HP after the attack (visible in unit health)
- Console shows no errors
- If attacker was at 80 HP before attack, it may take counter-attack damage then heal 20

### UC-6b: Hook with custom mod (turnStart)

**Setup:** Create `mods/turn-logger.js`:

```js
AthenaEngine.on('turnStart', function (ctx) {
  console.log('[TurnLogger] Turn started for player', ctx.activePlayer);
  return [];
});
```

Add to `mods.json`.

**Steps:**

1. Start game, end your turn, observe console

**Expected:**

- `[TurnLogger] Turn started for player 2` appears when AI turn starts
- `[TurnLogger] Turn started for player 1` appears when your turn starts again

### UC-6c: Hook error doesn't crash game

**Setup:** Create `mods/bad-hook.js`:

```js
AthenaEngine.on('afterAttack', function (ctx) {
  throw new Error('Hook exploded!');
});
```

Add to `mods.json` BEFORE `heal-on-attack.js`.

**Steps:**

1. Start game, attack an enemy

**Expected:**

- Console shows `[HookSystem] Hook error: Error: Hook exploded!`
- Heal-on-attack hook still fires (later in registration order)
- Game continues normally

### UC-6d: unitDestroyed hook fires

**Setup:** Create `mods/destroy-logger.js`:

```js
AthenaEngine.on('unitDestroyed', function (ctx) {
  console.log('[DestroyLogger] Unit destroyed at', ctx.position);
  return [];
});
```

**Steps:**

1. Attack and kill an enemy unit

**Expected:**

- `[DestroyLogger] Unit destroyed at {x: N, y: N}` appears in console
- `afterAttack` also fires for the same action

### UC-6e: moveComplete hook fires

**Setup:** Create `mods/move-logger.js`:

```js
AthenaEngine.on('moveComplete', function (ctx) {
  console.log('[MoveLogger] Unit moved to', ctx.position, 'info:', ctx.source?.info?.name);
  return [];
});
```

**Steps:**

1. Move any unit during gameplay

**Expected:**

- Console logs the destination position and unit name

---

## UC-7: Hook action emission

### UC-7a: HealUnit action

**Setup:** `mods/heal-on-attack.js` (included by default).

**Steps:**

1. Start game, damage your own unit (let enemy attack it)
2. Attack an enemy with the damaged unit

**Expected:**

- After the attack, the unit heals 20 HP
- Health change is reflected in the game UI immediately
- If unit was at 60 HP and took 10 counter-attack damage, final HP = 50 + 20 = 70

### UC-7b: DamageUnit action

**Setup:** Create `mods/revenge-damage.js`:

```js
AthenaEngine.on('afterAttack', function (ctx) {
  if (!ctx.target || ctx.target.health <= 0) return;
  var adjacent = AthenaEngine.getAdjacentUnits(ctx.target.position);
  return adjacent
    .filter(function (u) {
      return u.player === ctx.target.player;
    })
    .map(function (u) {
      return { type: 'DamageUnit', position: u.position, amount: 10 };
    });
});
```

**Steps:**

1. Attack a unit that has adjacent friendly units
2. Check health of the adjacent allies

**Expected:**

- Adjacent allies of the attacked unit each lose 10 HP
- If an adjacent ally had <= 10 HP, it is removed from the map

### UC-7c: DestroyUnit action

**Setup:** Create `mods/instant-kill-zone.js`:

```js
AthenaEngine.on('moveComplete', function (ctx) {
  if (ctx.position && ctx.position.x === 5 && ctx.position.y === 5) {
    return [{ type: 'DestroyUnit', position: ctx.position }];
  }
});
```

**Steps:**

1. Move a unit to position (5,5)

**Expected:**

- Unit is removed from the map upon reaching that tile
- Console shows no errors

### UC-7d: Invalid hook action is ignored

**Setup:** Create mod:

```js
AthenaEngine.on('afterAttack', function (ctx) {
  return [{ type: 'FakeAction', foo: 'bar' }];
});
```

**Steps:**

1. Attack an enemy

**Expected:**

- Console shows `[HookActionApplicator] Unknown action type: "FakeAction"`
- Game continues normally, no crash

### UC-7e: Recursion depth cap

**Setup:** Create mod that heals on every afterAttack (including recursion):

```js
AthenaEngine.on('afterAttack', function (ctx) {
  if (ctx.source) {
    return [{ type: 'HealUnit', position: ctx.source.position, amount: 5 }];
  }
});
```

**Steps:**

1. Attack an enemy
2. Observe console and unit health

**Expected:**

- Hook fires at most 3 times (MAX_HOOK_DEPTH cap)
- Unit heals at most 15 HP (5 x 3), not infinite
- No stack overflow or infinite loop

---

## UC-8: State query functions

### UC-8a: Queries work in hooks

**Setup:** Create `mods/query-test.js`:

```js
AthenaEngine.on('afterAttack', function (ctx) {
  var unit = AthenaEngine.getUnitAt(ctx.source.position);
  var adj = AthenaEngine.getAdjacentUnits(ctx.source.position);
  var tile = AthenaEngine.getTileAt(ctx.source.position);
  console.log('[QueryTest] Unit:', unit, 'Adjacent:', adj.length, 'Tile:', tile);
  return [];
});
```

**Steps:**

1. Attack an enemy, check console

**Expected:**

- `unit` is an object with `{id, name, health, player, fuel}`
- `adj` is an array of similar objects (may be empty)
- `tile` is an object with `{id, name, cover}`
- No errors

### UC-8b: Queries throw before game starts

**Steps:**

1. Open console on the title screen (before starting a game)
2. Run: `AthenaEngine.getUnitAt({x: 1, y: 1})`

**Expected:**

- Throws error: "No active map" or similar descriptive message

### UC-8c: getAdjacentUnits with player filter

**Setup:** Create mod that logs filtered adjacent units:

```js
AthenaEngine.on('afterAttack', function (ctx) {
  var friendlies = AthenaEngine.getAdjacentUnits(ctx.source.position, ctx.activePlayer);
  var enemies = AthenaEngine.getAdjacentUnits(ctx.source.position);
  console.log(
    '[FilterTest] Friendly adjacent:',
    friendlies.length,
    'All adjacent:',
    enemies.length,
  );
  return [];
});
```

**Steps:**

1. Position units from both teams near each other
2. Attack, check console

**Expected:**

- Friendly count <= All count
- Filter correctly excludes enemy units

---

## UC-9: Save/Load with mods active

### UC-9a: Save game with modded units

**Steps:**

1. Load with mods enabled (including custom-unit.js)
2. Build a Heavy Infantry, play several turns
3. Save the game

**Expected:**

- Save completes without errors
- Heavy Infantry unit data is persisted

### UC-9b: Load saved game with mods

**Steps:**

1. Save a game with mods active
2. Reload the page (mods reload at boot)
3. Load the saved game

**Expected:**

- Game loads with modded unit stats intact
- Heavy Infantry appears correctly
- No duplicate hook firing on load

---

## UC-10: Edge cases and stress tests

### UC-10a: Multiple mods registering units with same name

**Setup:** Two mods both call `registerUnit({base: 'Infantry', name: 'Clone'})`.

**Expected:**

- Both register successfully with different IDs
- Both appear in build menu (may be confusing UX but no crash)

### UC-10b: Mod patching then registering based on patched unit

**Setup:** Mod 1 patches Infantry cost to 50. Mod 2 registers based on Infantry.

**Expected:**

- Registered unit inherits the PATCHED cost (50), since mods run sequentially

### UC-10c: Large number of hooks on same event

**Setup:** Register 100 hooks on `afterAttack` (in a loop in a mod).

**Expected:**

- All fire without performance degradation for normal gameplay
- No stack overflow

### UC-10d: Build succeeds

```bash
npm run build:rosebud
```

**Expected:**

- Build completes with no errors
- `dist/rosebud/mods.json` and `dist/rosebud/mods/*.js` present in output
