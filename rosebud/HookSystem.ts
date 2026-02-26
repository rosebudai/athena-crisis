import type MapData from '@deities/athena/MapData.tsx';
import { type ActionResponse } from '@deities/apollo/ActionResponse.tsx';
import { type PlayerID } from '@deities/athena/map/Player.tsx';

export type HookEvent =
  | 'turnStart'
  | 'turnEnd'
  | 'afterAttack'
  | 'afterCapture'
  | 'unitCreated'
  | 'unitDestroyed'
  | 'moveComplete';

export type HookAction = { type: string; [key: string]: unknown };

export type HookEntityInfo = {
  position: { x: number; y: number };
  info: { id: number; name: string };
  health: number;
  player: number;
};

export type HookContext = {
  map: MapData;
  activePlayer: PlayerID;
  actionResponse: ActionResponse;
  source?: HookEntityInfo;
  target?: HookEntityInfo;
  position?: { x: number; y: number };
};

export type HookCallback = (ctx: HookContext) => Array<HookAction> | void;

export class HookSystem {
  private hooks: Map<HookEvent, Array<HookCallback>> = new Map();

  on(event: HookEvent, callback: HookCallback): () => void {
    let list = this.hooks.get(event);
    if (!list) {
      list = [];
      this.hooks.set(event, list);
    }
    list.push(callback);

    return () => {
      const current = this.hooks.get(event);
      if (current) {
        const index = current.indexOf(callback);
        if (index !== -1) {
          current.splice(index, 1);
        }
      }
    };
  }

  emit(event: HookEvent, ctx: HookContext): Array<HookAction> {
    const list = this.hooks.get(event);
    if (!list) {
      return [];
    }

    const actions: Array<HookAction> = [];

    for (const callback of list) {
      try {
        const result = callback(ctx);
        if (result) {
          actions.push(...result);
        }
      } catch (error) {
        console.error('[HookSystem] Hook error:', error);
      }
    }

    return actions;
  }

  clear(): void {
    this.hooks.clear();
  }
}

export const hookSystem = new HookSystem();
