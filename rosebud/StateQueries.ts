import type MapData from '@deities/athena/MapData.tsx';
import vec from '@deities/athena/map/vec.tsx';

type Position = { x: number; y: number };

type UnitResult = {
  fuel: number;
  health: number;
  id: number;
  name: string;
  player: number;
};

type BuildingResult = {
  health: number;
  id: number;
  name: string;
  player: number;
};

type TileResult = {
  cover: number;
  id: number;
  name: string;
};

type UnitWithPosition = UnitResult & {
  position: { x: number; y: number };
};

export function getUnitAt(map: MapData, position: Position): UnitResult | null {
  const unit = map.units.get(vec(position.x, position.y));
  if (!unit) {
    return null;
  }
  return {
    fuel: unit.fuel,
    health: unit.health,
    id: unit.info.id,
    name: unit.info.name,
    player: unit.player,
  };
}

export function getBuildingAt(map: MapData, position: Position): BuildingResult | null {
  const building = map.buildings.get(vec(position.x, position.y));
  if (!building) {
    return null;
  }
  return {
    health: building.health,
    id: building.info.id,
    name: building.info.name,
    player: building.player,
  };
}

export function getTileAt(map: MapData, position: Position): TileResult | null {
  const v = vec(position.x, position.y);
  if (!map.contains(v)) {
    return null;
  }
  const tileInfo = map.getTileInfo(v);
  return {
    cover: tileInfo.configuration.cover,
    id: tileInfo.id,
    name: tileInfo.name,
  };
}

export function getAdjacentUnits(
  map: MapData,
  position: Position,
  playerFilter?: number,
): Array<UnitResult> {
  const results: Array<UnitResult> = [];
  const deltas: ReadonlyArray<[number, number]> = [
    [-1, 0],
    [1, 0],
    [0, -1],
    [0, 1],
  ];

  for (const [dx, dy] of deltas) {
    const adj = vec(position.x + dx, position.y + dy);
    if (!map.contains(adj)) {
      continue;
    }
    const unit = map.units.get(adj);
    if (!unit) {
      continue;
    }
    if (playerFilter != null && unit.player !== playerFilter) {
      continue;
    }
    results.push({
      fuel: unit.fuel,
      health: unit.health,
      id: unit.info.id,
      name: unit.info.name,
      player: unit.player,
    });
  }

  return results;
}

export function getUnitsForPlayer(map: MapData, playerId: number): Array<UnitWithPosition> {
  const results: Array<UnitWithPosition> = [];
  map.units.forEach((unit, position) => {
    if (unit.player === playerId) {
      results.push({
        fuel: unit.fuel,
        health: unit.health,
        id: unit.info.id,
        name: unit.info.name,
        player: unit.player,
        position: { x: position.x, y: position.y },
      });
    }
  });
  return results;
}
