import { MaxHealth } from '@deities/athena/map/Configuration.tsx';
import vec from '@deities/athena/map/vec.tsx';
import MapData from '@deities/athena/MapData.tsx';
import type { HookAction } from './HookSystem.ts';

/**
 * Applies hook-emitted actions to the game map.
 *
 * Supported action types:
 * - HealUnit: { position: {x, y}, amount: number } — heal unit at position
 * - DamageUnit: { position: {x, y}, amount: number } — damage unit at position
 * - DestroyUnit: { position: {x, y} } — remove unit from map
 * - ModifyUnitFuel: { position: {x, y}, amount: number } — change fuel (+/-)
 *
 * Returns a new MapData if any actions were applied, or the original map if none.
 * Invalid or unrecognized actions are silently skipped with a console.warn.
 */
export function applyHookActions(map: MapData, actions: ReadonlyArray<HookAction>): MapData {
  let current = map;

  for (const action of actions) {
    try {
      current = applySingleAction(current, action);
    } catch (error) {
      console.warn('[HookActionApplicator] Failed to apply action:', action, error);
    }
  }

  return current;
}

function applySingleAction(map: MapData, action: HookAction): MapData {
  const pos = action.position as { x: number; y: number } | undefined;

  switch (action.type) {
    case 'HealUnit': {
      if (!pos || typeof action.amount !== 'number') {
        console.warn('[HookActionApplicator] HealUnit requires position and amount');
        return map;
      }
      const v = vec(pos.x, pos.y);
      const unit = map.units.get(v);
      if (!unit) {
        console.warn('[HookActionApplicator] No unit at position', pos);
        return map;
      }
      const newHealth = Math.min(unit.health + action.amount, MaxHealth);
      if (newHealth === unit.health) {
        return map;
      }
      return map.copy({ units: map.units.set(v, unit.setHealth(newHealth)) });
    }

    case 'DamageUnit': {
      if (!pos || typeof action.amount !== 'number') {
        console.warn('[HookActionApplicator] DamageUnit requires position and amount');
        return map;
      }
      const v = vec(pos.x, pos.y);
      const unit = map.units.get(v);
      if (!unit) {
        console.warn('[HookActionApplicator] No unit at position', pos);
        return map;
      }
      const newHealth = Math.max(0, unit.health - action.amount);
      if (newHealth <= 0) {
        return map.copy({ units: map.units.delete(v) });
      }
      return map.copy({ units: map.units.set(v, unit.setHealth(newHealth)) });
    }

    case 'DestroyUnit': {
      if (!pos) {
        console.warn('[HookActionApplicator] DestroyUnit requires position');
        return map;
      }
      const v = vec(pos.x, pos.y);
      if (!map.units.has(v)) {
        return map;
      }
      return map.copy({ units: map.units.delete(v) });
    }

    case 'ModifyUnitFuel': {
      if (!pos || typeof action.amount !== 'number') {
        console.warn('[HookActionApplicator] ModifyUnitFuel requires position and amount');
        return map;
      }
      const v = vec(pos.x, pos.y);
      const unit = map.units.get(v);
      if (!unit) {
        return map;
      }
      const newFuel = Math.max(0, unit.fuel + action.amount);
      return map.copy({ units: map.units.set(v, unit.setFuel(newFuel)) });
    }

    default:
      console.warn(`[HookActionApplicator] Unknown action type: "${action.type}"`);
      return map;
  }
}
