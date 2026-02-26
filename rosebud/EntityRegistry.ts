import { BuildingInfo, filterBuildings, registerCustomBuilding } from '../athena/info/Building.tsx';
import { getAllTiles, registerCustomTile, TileInfo } from '../athena/info/Tile.tsx';
import { filterUnits, registerCustomUnit, UnitInfo } from '../athena/info/Unit.tsx';

type UnitOverrides = {
  cost?: number;
  defense?: number;
  fuel?: number;
  name?: string;
  radius?: number;
  vision?: number;
};

type BuildingOverrides = {
  cost?: number;
  defense?: number;
  name?: string;
};

type TileOverrides = {
  cover?: number;
  name?: string;
  vision?: number;
};

export function registerUnit(config: {
  base: string;
  name: string;
  overrides?: Omit<UnitOverrides, 'name'>;
}): number {
  const baseUnit = filterUnits((u) => u.name === config.base)[0];
  if (!baseUnit) {
    throw new Error(`registerUnit: Could not find base unit '${config.base}'.`);
  }
  const cloned = baseUnit.clone(0 as UnitInfo['id'], {
    ...config.overrides,
    name: config.name,
  });
  return registerCustomUnit(cloned);
}

export function registerBuilding(config: {
  base: string;
  name: string;
  overrides?: Omit<BuildingOverrides, 'name'>;
}): number {
  const baseBuilding = filterBuildings((b) => b.name === config.base)[0];
  if (!baseBuilding) {
    throw new Error(`registerBuilding: Could not find base building '${config.base}'.`);
  }
  const cloned = baseBuilding.clone(0 as BuildingInfo['id'], {
    ...config.overrides,
    name: config.name,
  });
  return registerCustomBuilding(cloned);
}

export function registerTile(config: {
  base: string;
  name: string;
  overrides?: Omit<TileOverrides, 'name'>;
}): number {
  const baseTile = getAllTiles().find((t) => t.name === config.base);
  if (!baseTile) {
    throw new Error(`registerTile: Could not find base tile '${config.base}'.`);
  }
  const cloned = baseTile.clone(0 as TileInfo['id'], {
    ...config.overrides,
    name: config.name,
  });
  return registerCustomTile(cloned);
}
