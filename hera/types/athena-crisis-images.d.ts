declare module 'athena-crisis:images' {
  export const AttackSprites: Record<AttackSprite, string>;
  export const Crystals: HTMLImageElement;
  export const PortraitSilhouettes: HTMLImageElement;
  export const Tiles0: HTMLImageElement;
  export const Tiles1: HTMLImageElement;
  export const Tiles2: HTMLImageElement;
  export const Tiles3: HTMLImageElement;
  export const Tiles4: HTMLImageElement;
  export const Tiles5: HTMLImageElement;
  export const Tiles6: HTMLImageElement;
  export const Sprites: {
    Crane: string;
    Cursor: string;
    Damage: string;
    Delete: string;
    Explosion: string;
    Fireworks: string;
    GamepadPlaystation: string;
    GamepadSwitch: string;
    GamepadXbox: string;
    Heal: string;
    MessageShadow: string;
    Noise: string;
    Poison: string;
    Sabotage: string;
    Shield: string;
    Structures: string;
    TileDecorators: string;
    UnitIcons: string;
    Upgrade: string;
  };
  export const ShadowImages: ReadonlyMap<string, string>;
  export function applyDirectSpriteOverrides(overrides: ReadonlyMap<string, string>): void;
  export function applyTileOverrides(overrides: ReadonlyMap<string, string>): void;

  const Images: ReadonlyArray<string>;
  export default Images;
}
