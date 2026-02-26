# Athena Crisis — Modding Guide

Athena Crisis is a pixel-art turn-based strategy game. Players build units from buildings, move them on a tile map, and attack enemies. The game engine is pre-compiled — you modify game behavior through **JSON config files** and **JavaScript mod scripts**, not by editing the engine source.

## Project Structure

```
/index.html              ← Entry point (do not edit)
/config/game-config.json ← Global gameplay constants
/config/unit-stats.json  ← Per-unit stat overrides
/config/damage-tables.json ← Weapon damage multipliers
/config/tiles.json       ← Tile properties (cover, vision)
/config/buildings.json   ← Building properties (defense, funds)
/mods.json               ← Mod manifest (load order)
/mods/*.js               ← JavaScript mod scripts
```

Static assets (`/static/*.js`, `/static/*.css`, `/fonts/*`) are compiled engine bundles. **Never edit or delete them.**

---

## Quick Start: Change Unit Stats

Edit `/config/unit-stats.json`. Every unit is keyed by name:

```json
{
  "Infantry": { "cost": 100, "fuel": 60, "vision": 3, "defense": 10 },
  "Small Tank": { "cost": 400, "defense": 20 }
}
```

Only include fields you want to override. Omitted fields keep their defaults.

**Patchable unit fields:** `cost`, `fuel`, `radius` (movement range), `vision`, `defense`

## Quick Start: Change Game Rules

Edit `/config/game-config.json`:

```json
{
  "MaxHealth": 100,
  "HealAmount": 50,
  "CounterAttack": 0.75,
  "MinDamage": 5,
  "BuildingCover": 10,
  "PoisonDamage": 20,
  "MaxCharges": 10
}
```

**All patchable constants:** MaxHealth, MinDamage, HealAmount, BuildingCover, CounterAttack, RaisedCounterAttack, Charge, MaxCharges, PoisonDamage, PowerStationMultiplier, LeaderStatusEffect, MoraleStatusEffect, AllowedMisses, CreateTracksCost

---

## Mod System

Mods are plain JavaScript files executed at boot via `window.AthenaEngine`. They can patch stats, register new units, and hook into game events.

### Loading Mods

List mods in `/mods.json`. They execute **in order** — earlier mods run first:

```json
{
  "mods": ["mods/stat-override.js", "mods/custom-unit.js", "mods/heal-on-attack.js"]
}
```

Create each mod as a separate `.js` file under `/mods/`.

### Writing Mods

Mods are vanilla JavaScript (no imports, no modules). Use `var` instead of `const`/`let` to avoid scoping issues between mods. The global `AthenaEngine` object is your API.

---

## AthenaEngine API Reference

### Stat Patching

```js
// Patch a unit by name
AthenaEngine.patchUnit('Infantry', { cost: 100, vision: 4 });

// Patch a building
AthenaEngine.patchBuilding('Factory', { defense: 20 });

// Patch a tile
AthenaEngine.patchTile('Forest', { cover: 5, vision: 2 });

// Patch a weapon's damage table
AthenaEngine.patchDamageTable('MG', { Ground: 60, Artillery: 40 });

// Patch global game config
AthenaEngine.patchGameConfig({ MaxHealth: 50, HealAmount: 25 });
```

### Registering Custom Units

Create a new unit based on an existing one:

```js
var id = AthenaEngine.registerUnit({
  base: 'Infantry', // existing unit to clone from
  name: 'Heavy Infantry', // display name for the new unit
  overrides: {
    // stat overrides (all optional)
    cost: 300,
    defense: 20,
    vision: 2,
    fuel: 40,
    radius: 2,
  },
});
```

The new unit inherits the base unit's sprite, abilities, movement type, and weapon. It automatically appears in the build menu of any building that can produce the base unit's type.

You can also register buildings and tiles:

```js
AthenaEngine.registerBuilding({
  base: 'Factory',
  name: 'Mega Factory',
  overrides: { defense: 30 },
});
AthenaEngine.registerTile({ base: 'Forest', name: 'Dense Forest', overrides: { cover: 8 } });
```

### Lifecycle Hooks

Subscribe to game events. Hooks can **observe** events or **emit actions** that modify the game state.

```js
AthenaEngine.on('eventName', function (ctx) {
  // ctx contains event-specific data
  // Return an array of actions, or nothing
  return [{ type: 'HealUnit', position: ctx.source.position, amount: 20 }];
});
```

**Available events:**

| Event           | Fires when             | ctx fields                         |
| --------------- | ---------------------- | ---------------------------------- |
| `afterAttack`   | A unit attacks another | `source`, `target`, `activePlayer` |
| `afterCapture`  | A building is captured | `source`, `target`, `position`     |
| `unitCreated`   | A unit is built        | `source`, `position`               |
| `unitDestroyed` | A unit is destroyed    | `target`, `position`               |
| `moveComplete`  | A unit finishes moving | `source`, `position`               |
| `turnStart`     | A player's turn begins | `activePlayer`                     |
| `turnEnd`       | A player's turn ends   | `activePlayer`                     |

**ctx shape:**

```
ctx.activePlayer  — player ID (number)
ctx.source        — { position: {x, y}, info: {id, name}, health, player }
ctx.target        — same shape as source (may be null)
ctx.position      — {x, y}
```

### Hook Actions

Hooks return arrays of actions. These are the supported action types:

```js
// Heal a unit (capped at MaxHealth)
{ type: 'HealUnit', position: {x, y}, amount: 20 }

// Damage a unit (removes it if health reaches 0)
{ type: 'DamageUnit', position: {x, y}, amount: 30 }

// Instantly destroy a unit
{ type: 'DestroyUnit', position: {x, y} }

// Add or remove fuel
{ type: 'ModifyUnitFuel', position: {x, y}, amount: -10 }
```

Hook actions trigger at most **3 levels deep** to prevent infinite loops.

### State Queries

Read game state from within hooks or the browser console:

```js
AthenaEngine.getUnitAt({ x: 3, y: 5 });
// → { id, name, health, player, fuel } or null

AthenaEngine.getBuildingAt({ x: 3, y: 5 });
// → { id, name, player } or null

AthenaEngine.getTileAt({ x: 3, y: 5 });
// → { id, name, cover } or null

AthenaEngine.getAdjacentUnits({ x: 3, y: 5 });
// → array of unit objects in 4 cardinal directions

AthenaEngine.getAdjacentUnits({ x: 3, y: 5 }, playerId);
// → filtered to only that player's units

AthenaEngine.getUnitsForPlayer(1);
// → all units belonging to player 1
```

### Introspection

```js
AthenaEngine.getUnitInfo('Infantry'); // by name
AthenaEngine.getUnitInfo(2); // by ID
AthenaEngine.getAllUnits(); // array of all unit definitions
AthenaEngine.getBuildingInfo('Factory');
AthenaEngine.getAllBuildings();
```

---

## Mod Examples

### Stat Override

```js
// /mods/stat-override.js
AthenaEngine.patchUnit('Infantry', { cost: 100, vision: 4 });
```

### Custom Unit

```js
// /mods/custom-unit.js
var id = AthenaEngine.registerUnit({
  base: 'Infantry',
  name: 'Heavy Infantry',
  overrides: { cost: 300, defense: 20 },
});
```

### Heal on Attack

```js
// /mods/heal-on-attack.js
AthenaEngine.on('afterAttack', function (ctx) {
  if (!ctx.source || ctx.source.health <= 0) return;
  return [{ type: 'HealUnit', position: ctx.source.position, amount: 20 }];
});
```

### Splash Damage

```js
// /mods/splash-damage.js — damage adjacent allies when a unit is hit
AthenaEngine.on('afterAttack', function (ctx) {
  if (!ctx.target || ctx.target.health <= 0) return;
  var adjacent = AthenaEngine.getAdjacentUnits(ctx.target.position, ctx.target.player);
  return adjacent.map(function (u) {
    return { type: 'DamageUnit', position: u.position, amount: 10 };
  });
});
```

### Turn Logger

```js
// /mods/turn-logger.js
AthenaEngine.on('turnStart', function (ctx) {
  console.log('Turn started for player', ctx.activePlayer);
});
```

---

## Error Handling

- **Invalid JSON configs** — logged to console, game uses defaults
- **Unknown unit/building/tile names in configs** — logged as warning, skipped
- **Broken mod (throws error)** — logged, other mods still load
- **Missing mod file** — logged, other mods still load
- **Unknown hook action type** — logged as warning, ignored
- **Hook throws error** — logged, other hooks still fire

The game always boots. Errors in configs or mods never prevent loading.

---

## Entity Reference

### Units (56 built-in)

**Ground:** Pioneer, Infantry, Medic, Saboteur, Rocket Launcher, Sniper, Flamethrower, Humvee, Humvee Avenger, Jeep, Truck, Small Tank, Artillery, Heavy Artillery, Artillery Humvee, Anti Air, Heavy Tank, Mammoth, Super Tank, Super APU, APU, Inferno Jetpack, Jetpack

**Air:** Fighter Jet, Bomber, Drone Bomber, Acid Bomber, Helicopter, Transport Chopper, X-Fighter, Recon Drone

**Naval:** Battleship, Corvette, Destroyer, Frigate, Patrol Ship, Sea Patrol, Support Ship, Hovercraft, Lander, Octopus

**Rail:** Supply Train, Transport Train, Cannon

**Special (not normally buildable):** Dinosaur, Bear, Alien, Zombie, Ogre, Brute, Commander, Bazooka Bear, AIU, Scientist, Dragon

### Buildings (20)

HQ, House, Factory, Airbase, Shipyard, Barracks, Repair Shop, Radar Station, Shelter, Power Station, Research Lab, Medbay, Oil Rig, Bar, Spawn Platform, Barrier, Sea Barrier, Crashed Airplane, Destroyed House, Destroyed Super Tank

### Which Buildings Build Which Units

- **Factory** — Ground + Artillery + Rail units
- **Airbase** — Air units
- **Shipyard** — Naval units
- **Barracks** — Infantry-type ground units
- **HQ** — Pioneer only

### Tiles (35)

Plain, Forest, Mountain, Street, Path, Bridge, River, Sea, Deep Sea, Beach, Reef, Weeds, Island, Trench, Ruins, Wall, Construction Site, Shipyard Construction Site, Rail Track, Rail Bridge, Pier, Airfield, Barrel, Box, Campsite, Computer, Gas Bubbles, Iceberg, Lightning Barrier, Pipe, Platform, Space, Storm Cloud, Teleporter, Window
