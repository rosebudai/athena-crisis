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
        // case 'tiles':
        //   patchTiles(data);
        //   break;
        // case 'buildings':
        //   patchBuildings(data);
        //   break;
      }
    } catch (error) {
      console.warn(`[ConfigLoader] Failed to apply ${CONFIG_PATHS[key]}:`, error);
    }
  }
}
