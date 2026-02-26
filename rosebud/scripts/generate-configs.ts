/**
 * Config generator script — run with `tsx` from the rosebud package.
 *
 * Imports the game registries from @deities/athena and dumps full default
 * values to JSON files under rosebud/public/config/.
 *
 * Usage:
 *   pnpm --filter @deities/rosebud generate-configs
 *   # or directly:
 *   npx tsx rosebud/scripts/generate-configs.ts
 */

// ---------------------------------------------------------------------------
// Buildings
// ---------------------------------------------------------------------------
import { getAllBuildings } from '@deities/athena/info/Building.tsx';
// ---------------------------------------------------------------------------
// Movement types (for reverse-mapping)
// ---------------------------------------------------------------------------
import { MovementTypes } from '@deities/athena/info/MovementType.tsx';
// ---------------------------------------------------------------------------
// Tiles
// ---------------------------------------------------------------------------
import { getAllTiles } from '@deities/athena/info/Tile.tsx';
// ---------------------------------------------------------------------------
// Units, Weapons
// ---------------------------------------------------------------------------
import { mapUnits, Weapons } from '@deities/athena/info/Unit.tsx';
// ---------------------------------------------------------------------------
// Game Configuration constants (the patchable ones)
// ---------------------------------------------------------------------------
import {
  AllowedMisses,
  BuildingCover,
  Charge,
  CounterAttack,
  CreateTracksCost,
  HealAmount,
  LeaderStatusEffect,
  MaxCharges,
  MaxHealth,
  MinDamage,
  MoraleStatusEffect,
  PoisonDamage,
  PowerStationMultiplier,
  RaisedCounterAttack,
} from '@deities/athena/map/Configuration.tsx';
// ---------------------------------------------------------------------------
// Entity types (for reverse-mapping numeric enum → name)
// ---------------------------------------------------------------------------
import { EntityType } from '@deities/athena/map/Entity.tsx';
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const outDir = resolve(__dirname, '..', 'public', 'config');

/** Build a reverse lookup from the EntityType enum: numeric value → name. */
function entityTypeNameMap(): Map<number, string> {
  const map = new Map<number, string>();
  for (const [key, value] of Object.entries(EntityType)) {
    // TypeScript numeric enums produce both string→number and number→string entries.
    // We want the string keys only.
    if (typeof value === 'number') {
      map.set(value, key);
    }
  }
  return map;
}

/** Build a reverse lookup from MovementTypes: MovementType instance → key name. */
function movementTypeNameMap(): Map<unknown, string> {
  const map = new Map<unknown, string>();
  for (const [key, value] of Object.entries(MovementTypes)) {
    map.set(value, key);
  }
  return map;
}

function writeJSON(filename: string, data: unknown) {
  const filepath = resolve(outDir, filename);
  writeFileSync(filepath, JSON.stringify(data, null, 2) + '\n', 'utf-8');
  console.log(`  wrote ${filepath}`);
}

// ---------------------------------------------------------------------------
// 1. game-config.json
// ---------------------------------------------------------------------------

function generateGameConfig() {
  const config: Record<string, number> = {
    AllowedMisses,
    BuildingCover,
    Charge,
    CounterAttack,
    CreateTracksCost,
    HealAmount,
    LeaderStatusEffect,
    MaxCharges,
    MaxHealth,
    MinDamage,
    MoraleStatusEffect,
    PoisonDamage,
    PowerStationMultiplier,
    RaisedCounterAttack,
  };
  writeJSON('game-config.json', config);
}

// ---------------------------------------------------------------------------
// 2. unit-stats.json
// ---------------------------------------------------------------------------

function generateUnitStats() {
  const units: Record<string, Record<string, number>> = {};
  mapUnits((unit) => {
    units[unit.name] = {
      cost: unit.getCostFor(null),
      fuel: unit.configuration.fuel,
      radius: unit.getRadiusFor(null),
      vision: unit.configuration.vision,
      defense: unit.defense,
    };
  });
  writeJSON('unit-stats.json', units);
}

// ---------------------------------------------------------------------------
// 3. damage-tables.json
// ---------------------------------------------------------------------------

function generateDamageTables() {
  const etNames = entityTypeNameMap();

  const tables: Record<string, Record<string, number>> = {};

  for (const [weaponKey, weapon] of Object.entries(Weapons)) {
    const damageObj: Record<string, number> = {};
    for (const [entityType, dmg] of weapon.damage) {
      const name = etNames.get(entityType as number) ?? String(entityType);
      damageObj[name] = dmg;
    }
    tables[weaponKey] = damageObj;
  }

  writeJSON('damage-tables.json', tables);
}

// ---------------------------------------------------------------------------
// 4. tiles.json
// ---------------------------------------------------------------------------

function generateTiles() {
  const mtNames = movementTypeNameMap();
  const tiles: Record<string, { cover: number; vision: number; movement: Record<string, number> }> =
    {};

  for (const tile of getAllTiles()) {
    if (tiles[tile.name]) continue; // skip duplicate names (Forest variants share config)
    const movement: Record<string, number> = {};
    for (const [mt, cost] of tile.configuration.movement) {
      const name = mtNames.get(mt) ?? String(mt);
      movement[name] = cost;
    }
    tiles[tile.name] = {
      cover: tile.configuration.cover,
      vision: tile.configuration.vision,
      movement,
    };
  }

  writeJSON('tiles.json', tiles);
}

// ---------------------------------------------------------------------------
// 5. buildings.json
// ---------------------------------------------------------------------------

function generateBuildings() {
  const buildings: Record<string, Record<string, number>> = {};
  for (const building of getAllBuildings()) {
    buildings[building.name] = {
      defense: building.defense,
      funds: building.configuration.funds,
      cost: building.getCostFor(null),
    };
  }
  writeJSON('buildings.json', buildings);
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main() {
  mkdirSync(outDir, { recursive: true });
  console.log('Generating config JSON files...\n');

  generateGameConfig();
  generateUnitStats();
  generateDamageTables();
  generateTiles();
  generateBuildings();

  console.log('\nDone.');
}

main();
