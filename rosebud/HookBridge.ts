import { ActionResponse } from '@deities/apollo/ActionResponse.tsx';
import { GameStateEntry } from '@deities/apollo/Types.tsx';
import MapData from '@deities/athena/MapData.tsx';
import {
  hookSystem,
  type HookAction,
  type HookContext,
  type HookEntityInfo,
  type HookEvent,
} from './HookSystem.ts';

const MAX_HOOK_DEPTH = 3;

function buildEntityFromUnit(
  unit: { health: number; info: { id: number; name: string }; player: number },
  position: { x: number; y: number },
): HookEntityInfo {
  return {
    position,
    info: { id: unit.info.id, name: unit.info.name },
    health: unit.health,
    player: unit.player,
  };
}

function buildEntityFromBuilding(
  building: {
    health: number;
    info: { id: number; name: string };
    player: number;
  },
  position: { x: number; y: number },
): HookEntityInfo {
  return {
    position,
    info: { id: building.info.id, name: building.info.name },
    health: building.health,
    player: building.player,
  };
}

function buildBaseContext(map: MapData, actionResponse: ActionResponse): HookContext {
  return {
    map,
    activePlayer: map.getCurrentPlayer().id,
    actionResponse,
  };
}

function emitEvents(
  events: ReadonlyArray<{ event: HookEvent; ctx: HookContext }>,
): Array<HookAction> {
  const actions: Array<HookAction> = [];
  for (const { event, ctx } of events) {
    actions.push(...hookSystem.emit(event, ctx));
  }
  return actions;
}

export function processActionResponse(
  actionResponse: ActionResponse,
  map: MapData,
  _depth: number = 0,
): Array<GameStateEntry> {
  if (_depth >= MAX_HOOK_DEPTH) {
    return [];
  }

  const events: Array<{ event: HookEvent; ctx: HookContext }> = [];

  switch (actionResponse.type) {
    case 'AttackUnit': {
      const { from, to, unitA, unitB, playerA, playerB } = actionResponse;
      const baseCtx = buildBaseContext(map, actionResponse);

      // Build source from the pre-action attacker info.
      // unitA in the response is the post-attack state (may be undefined if destroyed).
      const originalUnitA = map.units.get(from);
      const source: HookEntityInfo | undefined = originalUnitA
        ? buildEntityFromUnit(originalUnitA, { x: from.x, y: from.y })
        : unitA
          ? {
              position: { x: from.x, y: from.y },
              info: { id: 0, name: 'Unknown' },
              health: unitA.health,
              player: playerA,
            }
          : undefined;

      // Build target from the post-attack defender.
      // unitB in the response is the post-attack state; if undefined, defender was destroyed.
      const originalUnitB = map.units.get(to);
      const target: HookEntityInfo | undefined = originalUnitB
        ? buildEntityFromUnit(originalUnitB, { x: to.x, y: to.y })
        : unitB
          ? {
              position: { x: to.x, y: to.y },
              info: { id: 0, name: 'Unknown' },
              health: unitB.health,
              player: playerB,
            }
          : undefined;

      events.push({
        event: 'afterAttack',
        ctx: {
          ...baseCtx,
          source,
          target,
          position: { x: from.x, y: from.y },
        },
      });

      // If unitB is undefined in the response, the defender was destroyed.
      if (!unitB) {
        events.push({
          event: 'unitDestroyed',
          ctx: {
            ...baseCtx,
            source,
            target,
            position: { x: to.x, y: to.y },
          },
        });
      }
      break;
    }

    case 'AttackBuilding': {
      const { from, to } = actionResponse;
      const baseCtx = buildBaseContext(map, actionResponse);

      const sourceUnit = map.units.get(from);
      const source: HookEntityInfo | undefined = sourceUnit
        ? buildEntityFromUnit(sourceUnit, { x: from.x, y: from.y })
        : undefined;

      const targetBuilding = map.buildings.get(to);
      const target: HookEntityInfo | undefined = targetBuilding
        ? buildEntityFromBuilding(targetBuilding, { x: to.x, y: to.y })
        : undefined;

      events.push({
        event: 'afterAttack',
        ctx: {
          ...baseCtx,
          source,
          target,
          position: { x: from.x, y: from.y },
        },
      });
      break;
    }

    case 'Capture': {
      const { from } = actionResponse;
      const baseCtx = buildBaseContext(map, actionResponse);

      events.push({
        event: 'afterCapture',
        ctx: {
          ...baseCtx,
          position: { x: from.x, y: from.y },
        },
      });
      break;
    }

    case 'CreateUnit': {
      const { to } = actionResponse;
      const baseCtx = buildBaseContext(map, actionResponse);

      const unit = map.units.get(to);
      const source: HookEntityInfo | undefined = unit
        ? buildEntityFromUnit(unit, { x: to.x, y: to.y })
        : undefined;

      events.push({
        event: 'unitCreated',
        ctx: {
          ...baseCtx,
          source,
          position: { x: to.x, y: to.y },
        },
      });
      break;
    }

    case 'Move': {
      const { to } = actionResponse;
      const baseCtx = buildBaseContext(map, actionResponse);

      const unit = map.units.get(to);
      const source: HookEntityInfo | undefined = unit
        ? buildEntityFromUnit(unit, { x: to.x, y: to.y })
        : undefined;

      events.push({
        event: 'moveComplete',
        ctx: {
          ...baseCtx,
          source,
          position: { x: to.x, y: to.y },
        },
      });
      break;
    }

    case 'EndTurn': {
      const { current, next } = actionResponse;
      const baseCtx = buildBaseContext(map, actionResponse);

      events.push({
        event: 'turnEnd',
        ctx: {
          ...baseCtx,
          activePlayer: current.player,
          position: undefined,
        },
      });

      events.push({
        event: 'turnStart',
        ctx: {
          ...baseCtx,
          activePlayer: next.player,
          position: undefined,
        },
      });
      break;
    }

    default:
      // No hook events for other action response types.
      break;
  }

  const hookActions = emitEvents(events);

  // For now, hook actions are collected but not converted back into GameStateEntries.
  // Future tasks will handle converting HookActions into executable game actions.
  // The return type supports this future extension.
  void hookActions;

  return [];
}

export function createHookCallback(): (
  actionResponse: ActionResponse,
  map: MapData,
) => Array<GameStateEntry> {
  return (actionResponse: ActionResponse, map: MapData) =>
    processActionResponse(actionResponse, map, 0);
}
