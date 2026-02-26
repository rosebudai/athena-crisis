import { SizeVector } from '../MapData.tsx';

export const AnimationSpeed = 180;

export const AnimationConfig = {
  AnimationDuration: AnimationSpeed * 2,
  ExplosionStep: AnimationSpeed / 2,
  Instant: false,
  MessageSpeed: AnimationSpeed * 2,
  UnitAnimationStep: (AnimationSpeed * 2) / 3,
  UnitMoveDuration: AnimationSpeed as number,
} as const;

export type AnimationConfig = Omit<typeof AnimationConfig, 'Instant'> &
  Readonly<{ Instant: boolean }>;

export const FastAnimationConfig: AnimationConfig = {
  AnimationDuration: AnimationConfig.AnimationDuration / 4,
  ExplosionStep: AnimationConfig.ExplosionStep / 4,
  Instant: false,
  MessageSpeed: AnimationConfig.AnimationDuration / 2,
  UnitAnimationStep: AnimationConfig.UnitAnimationStep / 4,
  UnitMoveDuration: AnimationConfig.UnitMoveDuration / 2,
};

export const InstantAnimationConfig: AnimationConfig = {
  AnimationDuration: 0,
  ExplosionStep: 0,
  Instant: true,
  MessageSpeed: 0,
  UnitAnimationStep: 0,
  UnitMoveDuration: 0,
};

export const getDecoratorLimit = (size: SizeVector) =>
  (size.width * size.height * DecoratorsPerSide) / 2;

export const DecoratorsPerSide = 4;
export const TileSize = 24;
export const DoubleSize = TileSize * 2;
export let MaxHealth = 100;
export let MinDamage = 5;
export let HealAmount = 50;
export let BuildingCover = 10;
export const MinSize = 5;
export const MaxSize = 40;
export const MaxMessageLength = 512;
export let LeaderStatusEffect = 0.05;
export let MoraleStatusEffect = 0.1;
export let CounterAttack = 0.75;
export let RaisedCounterAttack = 0.9;
export let CreateTracksCost = 50;
export let Charge = 1500;
export let MaxCharges = 10;
export let AllowedMisses = 2;
export const DefaultMapSkillSlots = [1, 2];
export let PoisonDamage = 20;
export let PowerStationMultiplier = 0.3;

export function patchGameConfig(overrides: Record<string, number>) {
  for (const [key, value] of Object.entries(overrides)) {
    switch (key) {
      case 'MaxHealth':
        MaxHealth = value;
        break;
      case 'MinDamage':
        MinDamage = value;
        break;
      case 'HealAmount':
        HealAmount = value;
        break;
      case 'BuildingCover':
        BuildingCover = value;
        break;
      case 'CounterAttack':
        CounterAttack = value;
        break;
      case 'RaisedCounterAttack':
        RaisedCounterAttack = value;
        break;
      case 'Charge':
        Charge = value;
        break;
      case 'MaxCharges':
        MaxCharges = value;
        break;
      case 'PoisonDamage':
        PoisonDamage = value;
        break;
      case 'PowerStationMultiplier':
        PowerStationMultiplier = value;
        break;
      case 'LeaderStatusEffect':
        LeaderStatusEffect = value;
        break;
      case 'MoraleStatusEffect':
        MoraleStatusEffect = value;
        break;
      case 'AllowedMisses':
        AllowedMisses = value;
        break;
      case 'CreateTracksCost':
        CreateTracksCost = value;
        break;
    }
  }
}
