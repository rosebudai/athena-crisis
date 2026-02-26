import { getBuildingInfo } from '@deities/athena/info/Building.tsx';
import { MovementType, MovementTypes } from '@deities/athena/info/MovementType.tsx';
import { getAllTiles } from '@deities/athena/info/Tile.tsx';
import { filterUnits, Weapons } from '@deities/athena/info/Unit.tsx';
import { patchGameConfig } from '@deities/athena/map/Configuration.tsx';
import { EntityType } from '@deities/athena/map/Entity.tsx';

/**
 * Config file paths relative to the app root.
 * These JSON files are optional — if any are missing, the game
 * boots with its built-in defaults.
 */
const CONFIG_PATHS = {
  gameConfig: 'config/game-config.json',
  unitStats: 'config/unit-stats.json',
  damageTables: 'config/damage-tables.json',
  tiles: 'config/tiles.json',
  buildings: 'config/buildings.json',
} as const;

async function fetchJSON(path: string): Promise<unknown> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

const UNIT_STAT_FIELDS = new Set(['cost', 'fuel', 'radius', 'vision', 'defense']);
const CONFIGURATION_FIELDS = new Set(['fuel', 'vision']);

function patchUnitStats(data: unknown): void {
  const entries = data as Record<string, Record<string, number>>;
  for (const [name, stats] of Object.entries(entries)) {
    const unitInfo = filterUnits((u) => u.name === name)[0];
    if (!unitInfo) {
      console.warn(`[ConfigLoader] patchUnitStats: unknown unit "${name}"`);
      continue;
    }
    for (const [field, value] of Object.entries(stats)) {
      if (!UNIT_STAT_FIELDS.has(field) || typeof value !== 'number') {
        continue;
      }
      if (CONFIGURATION_FIELDS.has(field)) {
        (unitInfo.configuration as any)[field] = value;
      }
      // cost and radius are private top-level fields; defense is public top-level.
      if (!CONFIGURATION_FIELDS.has(field)) {
        (unitInfo as any)[field] = value;
      }
    }
  }
}

// Build a reverse map from EntityType enum name → numeric value.
const entityTypeByName: ReadonlyMap<string, EntityType> = new Map(
  (Object.keys(EntityType) as Array<string>)
    .filter((key) => isNaN(Number(key)))
    .map((key) => [key, EntityType[key as keyof typeof EntityType]]),
);

function patchDamageTables(data: unknown): void {
  const entries = data as Record<string, Record<string, number>>;
  for (const [weaponKey, damageEntries] of Object.entries(entries)) {
    const weapon = (Weapons as Record<string, unknown>)[weaponKey];
    if (!weapon || typeof weapon !== 'object' || !('damage' in (weapon as any))) {
      console.warn(`[ConfigLoader] patchDamageTables: unknown weapon "${weaponKey}"`);
      continue;
    }
    const damageMap = (weapon as any).damage as Map<EntityType, number>;
    for (const [targetName, damage] of Object.entries(damageEntries)) {
      const entityType = entityTypeByName.get(targetName);
      if (entityType === undefined) {
        console.warn(`[ConfigLoader] patchDamageTables: unknown EntityType "${targetName}"`);
        continue;
      }
      if (typeof damage === 'number') {
        damageMap.set(entityType, damage);
      }
    }
  }
}

// Build a name→MovementType lookup from the MovementTypes object keys.
const movementTypeByName: ReadonlyMap<string, MovementType> = new Map(
  Object.entries(MovementTypes).map(([key, mt]) => [key, mt]),
);

function patchTiles(data: unknown): void {
  const entries = data as Record<
    string,
    {
      cover?: number;
      movement?: Record<string, number>;
      vision?: number;
    }
  >;

  // Build a name→TileInfo lookup. For duplicate names (e.g. Forest variants)
  // only the first is stored — they share configuration anyway.
  const tileByName = new Map<string, ReturnType<typeof getAllTiles>[number]>();
  for (const tile of getAllTiles()) {
    if (!tileByName.has(tile.name)) {
      tileByName.set(tile.name, tile);
    }
  }

  for (const [name, overrides] of Object.entries(entries)) {
    const tileInfo = tileByName.get(name);
    if (!tileInfo) {
      console.warn(`[ConfigLoader] patchTiles: unknown tile "${name}"`);
      continue;
    }

    if (typeof overrides.cover === 'number') {
      (tileInfo.configuration as any).cover = overrides.cover;
    }
    if (typeof overrides.vision === 'number') {
      (tileInfo.configuration as any).vision = overrides.vision;
    }
    if (overrides.movement) {
      const movementMap = tileInfo.configuration.movement as Map<MovementType, number>;
      for (const [mtName, cost] of Object.entries(overrides.movement)) {
        const movementType = movementTypeByName.get(mtName);
        if (!movementType) {
          console.warn(
            `[ConfigLoader] patchTiles: unknown MovementType "${mtName}" for tile "${name}"`,
          );
          continue;
        }
        if (typeof cost === 'number') {
          movementMap.set(movementType, cost);
        }
      }
    }
  }
}

function patchBuildings(data: unknown): void {
  const entries = data as Record<string, { cost?: number; defense?: number; funds?: number }>;

  // Build a name→BuildingInfo lookup by iterating known IDs.
  const buildingByName = new Map<string, NonNullable<ReturnType<typeof getBuildingInfo>>>();
  for (let id = 1; ; id++) {
    const building = getBuildingInfo(id);
    if (!building) {
      break;
    }
    if (!buildingByName.has(building.name)) {
      buildingByName.set(building.name, building);
    }
  }

  for (const [name, overrides] of Object.entries(entries)) {
    const buildingInfo = buildingByName.get(name);
    if (!buildingInfo) {
      console.warn(`[ConfigLoader] patchBuildings: unknown building "${name}"`);
      continue;
    }

    if (typeof overrides.defense === 'number') {
      (buildingInfo as any).defense = overrides.defense;
    }
    if (typeof overrides.funds === 'number') {
      (buildingInfo.configuration as any).funds = overrides.funds;
    }
    if (typeof overrides.cost === 'number') {
      (buildingInfo as any).cost = overrides.cost;
    }
  }
}

/**
 * Fetch all config JSON files in parallel and apply any overrides
 * found. Missing files and parse errors are silently ignored so the
 * game always boots with sensible defaults.
 */
export async function loadAndApplyConfigs(): Promise<void> {
  const keys = Object.keys(CONFIG_PATHS) as Array<keyof typeof CONFIG_PATHS>;
  const results = await Promise.allSettled(keys.map((key) => fetchJSON(CONFIG_PATHS[key])));

  for (let i = 0; i < keys.length; i++) {
    const key = keys[i];
    const result = results[i];

    if (result.status !== 'fulfilled') {
      // File does not exist or network error — skip silently.
      continue;
    }

    try {
      const data = result.value;

      switch (key) {
        case 'gameConfig':
          patchGameConfig(data as Record<string, number>);
          break;
        case 'unitStats':
          patchUnitStats(data);
          break;
        case 'damageTables':
          patchDamageTables(data);
          break;
        case 'tiles':
          patchTiles(data);
          break;
        case 'buildings':
          patchBuildings(data);
          break;
      }
    } catch (error) {
      console.warn(`[ConfigLoader] Failed to apply ${CONFIG_PATHS[key]}:`, error);
    }
  }
}
