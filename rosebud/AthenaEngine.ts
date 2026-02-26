import type MapData from '@deities/athena/MapData.tsx';
import {
  filterBuildings,
  getAllBuildings,
  getBuildingInfo,
} from '@deities/athena/info/Building.tsx';
import { getAllTiles } from '@deities/athena/info/Tile.tsx';
import { filterUnits, getAllUnits, getUnitInfo, Weapons } from '@deities/athena/info/Unit.tsx';
import { patchGameConfig } from '@deities/athena/map/Configuration.tsx';
import { EntityType } from '@deities/athena/map/Entity.tsx';
import type { HookCallback, HookEvent } from './HookSystem.ts';
import { registerBuilding, registerTile, registerUnit } from './EntityRegistry.ts';
import { hookSystem } from './HookSystem.ts';
import {
  getAdjacentUnits,
  getBuildingAt,
  getTileAt,
  getUnitAt,
  getUnitsForPlayer,
} from './StateQueries.ts';

// ---------------------------------------------------------------------------
// Map state – set by the game loop, read by query wrappers.
// ---------------------------------------------------------------------------

let currentMap: MapData | null = null;

export function setCurrentMap(map: MapData): void {
  currentMap = map;
}

function requireMap(): MapData {
  if (!currentMap) {
    throw new Error(
      '[AthenaEngine] No active map. Query functions can only be called during a game.',
    );
  }
  return currentMap;
}

// ---------------------------------------------------------------------------
// Helpers shared by the single-entity patch wrappers.
// ---------------------------------------------------------------------------

const UNIT_STAT_FIELDS = new Set(['cost', 'fuel', 'radius', 'vision', 'defense']);
const UNIT_CONFIGURATION_FIELDS = new Set(['fuel', 'vision']);

// Reverse map from EntityType enum name -> numeric value (mirrors ConfigLoader).
const entityTypeByName: ReadonlyMap<string, EntityType> = new Map(
  (Object.keys(EntityType) as Array<string>)
    .filter((key) => isNaN(Number(key)))
    .map((key) => [key, EntityType[key as keyof typeof EntityType]]),
);

// ---------------------------------------------------------------------------
// Single-entity patching functions exposed to mods.
// ---------------------------------------------------------------------------

function patchUnit(nameOrId: string | number, overrides: Record<string, number>): void {
  const unitInfo =
    typeof nameOrId === 'number'
      ? getUnitInfo(nameOrId)
      : (filterUnits((u) => u.name === nameOrId)[0] ?? null);

  if (!unitInfo) {
    console.warn(`[AthenaEngine] patchUnit: unknown unit "${nameOrId}"`);
    return;
  }

  for (const [field, value] of Object.entries(overrides)) {
    if (!UNIT_STAT_FIELDS.has(field) || typeof value !== 'number') {
      continue;
    }
    if (UNIT_CONFIGURATION_FIELDS.has(field)) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (unitInfo.configuration as any)[field] = value;
    }
    if (!UNIT_CONFIGURATION_FIELDS.has(field)) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (unitInfo as any)[field] = value;
    }
  }
}

function patchBuilding(nameOrId: string | number, overrides: Record<string, number>): void {
  let buildingInfo;
  if (typeof nameOrId === 'number') {
    buildingInfo = getBuildingInfo(nameOrId);
  } else {
    buildingInfo = filterBuildings((b) => b.name === nameOrId)[0] ?? null;
  }

  if (!buildingInfo) {
    console.warn(`[AthenaEngine] patchBuilding: unknown building "${nameOrId}"`);
    return;
  }

  for (const [field, value] of Object.entries(overrides)) {
    if (typeof value !== 'number') {
      continue;
    }
    switch (field) {
      case 'defense':
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (buildingInfo as any).defense = value;
        break;
      case 'funds':
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (buildingInfo.configuration as any).funds = value;
        break;
      case 'cost':
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (buildingInfo as any).cost = value;
        break;
    }
  }
}

function patchTile(name: string, overrides: { cover?: number; vision?: number }): void {
  const tileInfo = getAllTiles().find((t) => t.name === name);

  if (!tileInfo) {
    console.warn(`[AthenaEngine] patchTile: unknown tile "${name}"`);
    return;
  }

  if (typeof overrides.cover === 'number') {
    (tileInfo.configuration as Record<string, unknown>).cover = overrides.cover;
  }
  if (typeof overrides.vision === 'number') {
    (tileInfo.configuration as Record<string, unknown>).vision = overrides.vision;
  }
}

function patchDamageTable(weaponName: string, overrides: Record<string, number>): void {
  const weapon = (Weapons as Record<string, unknown>)[weaponName];
  if (!weapon || typeof weapon !== 'object' || !('damage' in (weapon as Record<string, unknown>))) {
    console.warn(`[AthenaEngine] patchDamageTable: unknown weapon "${weaponName}"`);
    return;
  }

  const damageMap = (weapon as { damage: Map<EntityType, number> }).damage;
  for (const [targetName, damage] of Object.entries(overrides)) {
    const entityType = entityTypeByName.get(targetName);
    if (entityType === undefined) {
      console.warn(`[AthenaEngine] patchDamageTable: unknown EntityType "${targetName}"`);
      continue;
    }
    if (typeof damage === 'number') {
      damageMap.set(entityType, damage);
    }
  }
}

// ---------------------------------------------------------------------------
// Introspection helpers.
// ---------------------------------------------------------------------------

function resolveUnitInfo(idOrName: number | string) {
  if (typeof idOrName === 'number') {
    return getUnitInfo(idOrName);
  }
  return filterUnits((u) => u.name === idOrName)[0] ?? null;
}

function resolveBuildingInfo(idOrName: number | string) {
  if (typeof idOrName === 'number') {
    return getBuildingInfo(idOrName);
  }
  return filterBuildings((b) => b.name === idOrName)[0] ?? null;
}

// ---------------------------------------------------------------------------
// The API object attached to window.AthenaEngine.
// ---------------------------------------------------------------------------

function buildAPI() {
  return {
    // Entity registration
    registerUnit,
    registerBuilding,
    registerTile,

    // Single-entity patching
    patchUnit,
    patchBuilding,
    patchTile,
    patchDamageTable,
    patchGameConfig,

    // Hooks
    on: (event: HookEvent, callback: HookCallback) => hookSystem.on(event, callback),

    // Queries (use currentMap)
    getUnitAt: (position: { x: number; y: number }) => getUnitAt(requireMap(), position),
    getBuildingAt: (position: { x: number; y: number }) => getBuildingAt(requireMap(), position),
    getTileAt: (position: { x: number; y: number }) => getTileAt(requireMap(), position),
    getAdjacentUnits: (position: { x: number; y: number }, playerFilter?: number) =>
      getAdjacentUnits(requireMap(), position, playerFilter),
    getUnitsForPlayer: (playerId: number) => getUnitsForPlayer(requireMap(), playerId),

    // Introspection
    getUnitInfo: resolveUnitInfo,
    getBuildingInfo: resolveBuildingInfo,
    getAllUnits: () => getAllUnits(),
    getAllBuildings: () => getAllBuildings(),
  };
}

export type AthenaEngineAPI = ReturnType<typeof buildAPI>;

// ---------------------------------------------------------------------------
// Initialization – call once at startup.
// ---------------------------------------------------------------------------

export function initAthenaEngine(): void {
  (window as unknown as { AthenaEngine: AthenaEngineAPI }).AthenaEngine = buildAPI();
}

// ---------------------------------------------------------------------------
// TypeScript global augmentation so that `window.AthenaEngine` type-checks.
// ---------------------------------------------------------------------------

declare global {
  interface Window {
    AthenaEngine: AthenaEngineAPI;
  }
}
