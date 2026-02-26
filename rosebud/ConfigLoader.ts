import { patchGameConfig } from '@deities/athena/map/Configuration.tsx';

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
        // case 'unitStats':
        //   patchUnitStats(data);
        //   break;
        // case 'damageTables':
        //   patchDamageTables(data);
        //   break;
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
