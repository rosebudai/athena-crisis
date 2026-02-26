import { ActionResponse } from '@deities/apollo/ActionResponse.tsx';
import { decodeEffects, Effects, encodeEffects, EncodedEffects } from '@deities/apollo/Effects.tsx';
import {
  decodeActionResponse,
  encodeActionResponse,
  EncodedActionResponse,
} from '@deities/apollo/EncodedActions.tsx';
import { MapMetadata } from '@deities/apollo/MapMetadata.tsx';
import { prepareSprites } from '@deities/art/Sprites.tsx';
import {
  generateBuildings,
  generateRandomMap,
  generateSea,
} from '@deities/athena/generator/MapGenerator.tsx';
import convertBiome from '@deities/athena/lib/convertBiome.tsx';
import { Biome } from '@deities/athena/map/Biome.tsx';
import { PlainMap } from '@deities/athena/map/PlainMap.tsx';
import MapData, { SizeVector } from '@deities/athena/MapData.tsx';
import { biomeToSong } from '@deities/hera/audio/Music.tsx';
import GameMap from '@deities/hera/GameMap.tsx';
import useClientGame from '@deities/hera/hooks/useClientGame.tsx';
import useClientGameAction from '@deities/hera/hooks/useClientGameAction.tsx';
import useClientGamePlayerDetails from '@deities/hera/hooks/useClientGamePlayerDetails.tsx';
import LocaleContext from '@deities/hera/i18n/LocaleContext.tsx';
import GameActions from '@deities/hera/ui/GameActions.tsx';
import DemoViewer from '@deities/hera/ui/lib/DemoViewer.tsx';
import MapInfo from '@deities/hera/ui/MapInfo.tsx';
import { ClientGame } from '@deities/hermes/game/toClientGame.tsx';
import undo from '@deities/hermes/game/undo.tsx';
import { UndoType } from '@deities/hermes/game/undo.tsx';
import demo1, { metadata as metadata1 } from '@deities/hermes/map-fixtures/demo-1.tsx';
import demo2, { metadata as metadata2 } from '@deities/hermes/map-fixtures/demo-2.tsx';
import demo3, { metadata as metadata3 } from '@deities/hermes/map-fixtures/demo-3.tsx';
import shrine, { metadata as metadataShrine } from '@deities/hermes/map-fixtures/shrine.tsx';
import theyAreCloseToHome, {
  metadata as metadataTheyAreCloseToHome,
} from '@deities/hermes/map-fixtures/they-are-close-to-home.tsx';
import AudioPlayer from '@deities/ui/AudioPlayer.tsx';
import initializeCSS from '@deities/ui/CSS.tsx';
import { initializeCSSVariables } from '@deities/ui/cssVar.tsx';
import { AlertContext } from '@deities/ui/hooks/useAlert.tsx';
import useScale, { ScaleContext } from '@deities/ui/hooks/useScale.tsx';
import { css } from '@emotion/css';
import { VisibilityStateContext } from '@nkzw/use-visibility-state';
import { Component, ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';

// Initialize global CSS (variables, global styles)
initializeCSSVariables();
initializeCSS();

// Prepare sprite CSS classes (async, loads from CDN)
prepareSprites();

// Enable audio - sound files are generated via ElevenLabs
AudioPlayer.resume();
AudioPlayer.preload();

const startAction = { type: 'Start' } as const;

// --- Save/Load ---

const SAVE_VERSION = 1;
const SAVE_KEYS = ['athena-save-1', 'athena-save-2', 'athena-save-3'] as const;
const AUTOSAVE_KEY = 'athena-autosave';

type SaveData = {
  version: number;
  timestamp: number;
  mapId: string;
  mapName: string;
  biome: number;
  mapState: PlainMap;
  effects: EncodedEffects;
  lastAction: EncodedActionResponse | null;
  ended: boolean;
};

function serializeGame(
  game: {
    state: MapData;
    effects: Effects;
    lastAction: ActionResponse | null;
    ended: boolean;
  },
  mapId: string,
  mapName: string,
  biome: Biome,
): SaveData {
  return {
    version: SAVE_VERSION,
    timestamp: Date.now(),
    mapId,
    mapName,
    biome,
    mapState: game.state.toJSON(),
    effects: encodeEffects(game.effects),
    lastAction: game.lastAction ? encodeActionResponse(game.lastAction) : null,
    ended: game.ended,
  };
}

function writeSave(key: string, data: SaveData): boolean {
  try {
    localStorage.setItem(key, JSON.stringify(data));
    return true;
  } catch {
    return false;
  }
}

function readSave(key: string): SaveData | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (data?.version !== SAVE_VERSION) return null;
    return data as SaveData;
  } catch {
    return null;
  }
}

function readAllSaves(): Record<string, SaveData | null> {
  const saves: Record<string, SaveData | null> = {};
  for (const key of SAVE_KEYS) {
    saves[key] = readSave(key);
  }
  saves[AUTOSAVE_KEY] = readSave(AUTOSAVE_KEY);
  return saves;
}

function deleteSave(key: string): void {
  localStorage.removeItem(key);
}

function exportSave(data: SaveData): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `athena-crisis-save-${new Date(data.timestamp).toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

function importSaveFromFile(): Promise<SaveData | null> {
  return new Promise((resolve) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = () => {
      const file = input.files?.[0];
      if (!file) {
        resolve(null);
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        try {
          const data = JSON.parse(reader.result as string);
          if (data?.version !== SAVE_VERSION) {
            resolve(null);
            return;
          }
          resolve(data as SaveData);
        } catch {
          resolve(null);
        }
      };
      reader.onerror = () => resolve(null);
      reader.readAsText(file);
    };
    input.oncancel = () => resolve(null);
    input.click();
  });
}

function formatTimestamp(ts: number): string {
  const d = new Date(ts);
  const now = Date.now();
  const diff = now - ts;
  if (diff < 60_000) return 'Just now';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  return d.toLocaleDateString();
}

// --- Map catalog ---

type MapEntry = {
  id: string;
  name: string;
  map: MapData;
  metadata: MapMetadata;
  size: string;
  tags: ReadonlyArray<string>;
};

const mapCatalog: ReadonlyArray<MapEntry> = [
  {
    id: 'demo-1',
    name: metadata1.name || 'Demo 1',
    map: demo1,
    metadata: metadata1,
    size: '15x10',
    tags: ['beginner'],
  },
  {
    id: 'demo-2',
    name: metadata2.name || 'Demo 2',
    map: demo2,
    metadata: metadata2,
    size: '15x10',
    tags: ['beginner'],
  },
  {
    id: 'demo-3',
    name: metadata3.name || 'Demo 3',
    map: demo3,
    metadata: metadata3,
    size: '17x11',
    tags: ['intermediate'],
  },
  {
    id: 'shrine',
    name: metadataShrine.name || 'Shrine',
    map: shrine,
    metadata: metadataShrine,
    size: '12x10',
    tags: ['story', 'reward'],
  },
  {
    id: 'they-are-close-to-home',
    name: metadataTheyAreCloseToHome.name || 'They are Close to Home',
    map: theyAreCloseToHome,
    metadata: metadataTheyAreCloseToHome,
    size: '22x10',
    tags: ['hard', 'story'],
  },
];

const biomeOptions: ReadonlyArray<{ biome: Biome; label: string }> = [
  { biome: Biome.Grassland, label: 'Grassland' },
  { biome: Biome.Desert, label: 'Desert' },
  { biome: Biome.Snow, label: 'Snow' },
  { biome: Biome.Swamp, label: 'Swamp' },
  { biome: Biome.Volcano, label: 'Volcano' },
];

const biomeNames: Record<number, string> = {
  [Biome.Grassland]: 'Grassland',
  [Biome.Desert]: 'Desert',
  [Biome.Snow]: 'Snow',
  [Biome.Swamp]: 'Swamp',
  [Biome.Volcano]: 'Volcano',
  [Biome.Spaceship]: 'Spaceship',
  [Biome.Luna]: 'Luna',
};

// --- Emotion styles ---

const containerStyle = css`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: #1b1b23;
  color: #e0e0e0;
  font-family: Athena, sans-serif;
  padding: 20px;
  box-sizing: border-box;
`;

const titleStyle = css`
  font-size: 48px;
  font-weight: bold;
  color: #ff6b6b;
  text-transform: uppercase;
  letter-spacing: 6px;
  margin-bottom: 8px;
  text-align: center;
`;

const subtitleStyle = css`
  font-size: 16px;
  color: #888;
  letter-spacing: 3px;
  text-transform: uppercase;
  margin-bottom: 48px;
  text-align: center;
`;

const buttonStyle = css`
  font-family: Athena, sans-serif;
  font-size: 20px;
  font-weight: bold;
  color: #1b1b23;
  background: #ff6b6b;
  border: none;
  padding: 14px 48px;
  cursor: pointer;
  text-transform: uppercase;
  letter-spacing: 3px;
  transition: background 0.15s;

  &:hover {
    background: #ff8787;
  }

  &:active {
    background: #e05555;
  }
`;

const secondaryButtonStyle = css`
  font-family: Athena, sans-serif;
  font-size: 14px;
  font-weight: bold;
  color: #ccc;
  background: #2a2a36;
  border: 1px solid #444;
  padding: 10px 24px;
  cursor: pointer;
  text-transform: uppercase;
  letter-spacing: 2px;
  transition: background 0.15s;

  &:hover {
    background: #3a3a4a;
  }

  &:active {
    background: #222230;
  }
`;

const selectHeadingStyle = css`
  font-size: 28px;
  font-weight: bold;
  color: #ff6b6b;
  text-transform: uppercase;
  letter-spacing: 4px;
  margin-bottom: 24px;
  text-align: center;
`;

const mapGridStyle = css`
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
  width: 100%;
  max-width: 720px;
  margin-bottom: 24px;
`;

const mapCardStyle = css`
  background: #2a2a36;
  border: 2px solid #444;
  padding: 16px;
  cursor: pointer;
  transition:
    border-color 0.15s,
    background 0.15s;

  &:hover {
    border-color: #ff6b6b;
    background: #32323e;
  }
`;

const mapCardSelectedStyle = css`
  background: #32323e;
  border: 2px solid #ff6b6b;
  padding: 16px;
  cursor: pointer;
`;

const mapCardNameStyle = css`
  font-size: 16px;
  font-weight: bold;
  color: #e0e0e0;
  margin-bottom: 4px;
`;

const mapCardDetailStyle = css`
  font-size: 12px;
  color: #888;
`;

const tagStyle = css`
  display: inline-block;
  font-size: 10px;
  color: #ffcc00;
  background: #3a3522;
  padding: 2px 6px;
  margin-top: 6px;
  margin-right: 4px;
  text-transform: uppercase;
  letter-spacing: 1px;
`;

const sectionLabelStyle = css`
  font-size: 14px;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 2px;
  margin-bottom: 10px;
  text-align: center;
`;

const biomeRowStyle = css`
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
  margin-bottom: 24px;
`;

const biomeChipStyle = css`
  font-family: Athena, sans-serif;
  font-size: 12px;
  font-weight: bold;
  color: #ccc;
  background: #2a2a36;
  border: 1px solid #444;
  padding: 8px 16px;
  cursor: pointer;
  text-transform: uppercase;
  letter-spacing: 1px;
  transition:
    border-color 0.15s,
    background 0.15s;

  &:hover {
    border-color: #ff6b6b;
    background: #32323e;
  }
`;

const biomeChipSelectedStyle = css`
  font-family: Athena, sans-serif;
  font-size: 12px;
  font-weight: bold;
  color: #fff;
  background: #ff6b6b;
  border: 1px solid #ff6b6b;
  padding: 8px 16px;
  cursor: pointer;
  text-transform: uppercase;
  letter-spacing: 1px;
`;

const actionRowStyle = css`
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
`;

const overlayStyle = css`
  position: fixed;
  inset: 0;
  background: rgba(20, 20, 28, 0.85);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 10000;
`;

const overlayTitleStyle = css`
  font-size: 40px;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 6px;
  margin-bottom: 32px;
  text-align: center;
`;

const overlayVictoryColor = css`
  color: #4ecdc4;
`;

const overlayDefeatColor = css`
  color: #ff6b6b;
`;

const overlayButtonRow = css`
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  justify-content: center;
`;

const gameMapWrapperStyle = css`
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  width: 100%;
  background: #1b1b23;
  overflow: hidden;
`;

const howToContainerStyle = css`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: #1b1b23;
  color: #e0e0e0;
  font-family: Athena, sans-serif;
  padding: 40px 20px;
  box-sizing: border-box;
`;

const howToHeadingStyle = css`
  font-size: 32px;
  font-weight: bold;
  color: #ff6b6b;
  text-transform: uppercase;
  letter-spacing: 4px;
  margin-bottom: 32px;
  text-align: center;
`;

const howToListStyle = css`
  list-style: none;
  padding: 0;
  margin: 0 0 36px 0;
  max-width: 480px;
  width: 100%;
`;

const howToItemStyle = css`
  margin-bottom: 16px;
  font-size: 15px;
  line-height: 1.5;
  color: #e0e0e0;
`;

const howToLabelStyle = css`
  font-weight: bold;
  color: #ff6b6b;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-right: 8px;
`;

const slotGridStyle = css`
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  max-width: 400px;
  margin-bottom: 24px;
`;

const slotCardStyle = css`
  background: #2a2a36;
  border: 2px solid #444;
  padding: 14px 18px;
  cursor: pointer;
  transition:
    border-color 0.15s,
    background 0.15s;
  display: flex;
  justify-content: space-between;
  align-items: center;

  &:hover {
    border-color: #ff6b6b;
    background: #32323e;
  }
`;

const slotCardEmptyStyle = css`
  background: #2a2a36;
  border: 2px solid #333;
  padding: 14px 18px;
  cursor: pointer;
  color: #555;
  transition: border-color 0.15s;

  &:hover {
    border-color: #666;
  }
`;

const slotCardDisabledStyle = css`
  background: #222230;
  border: 2px solid #333;
  padding: 14px 18px;
  color: #555;
  cursor: default;
`;

const slotNameStyle = css`
  font-size: 14px;
  font-weight: bold;
  color: #e0e0e0;
`;

const slotDetailStyle = css`
  font-size: 11px;
  color: #888;
  margin-top: 2px;
`;

const slotTimeStyle = css`
  font-size: 11px;
  color: #666;
  text-align: right;
  white-space: nowrap;
`;

const pauseButtonStyle = css`
  position: fixed;
  top: 12px;
  left: 12px;
  z-index: 9999;
  width: 40px;
  height: 40px;
  background: rgba(27, 27, 35, 0.8);
  border: 1px solid #555;
  color: #ccc;
  font-size: 20px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;

  &:hover {
    background: rgba(58, 58, 74, 0.9);
  }
`;

const feedbackStyle = css`
  color: #4ecdc4;
  font-size: 14px;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 2px;
  margin-bottom: 16px;
  min-height: 20px;
`;

const errorFeedbackStyle = css`
  color: #ff6b6b;
  font-size: 14px;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 2px;
  margin-bottom: 16px;
  min-height: 20px;
`;

// --- Error boundary ---

class GameErrorBoundary extends Component<
  { children: ReactNode; onReset: () => void },
  { error: Error | null }
> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error) {
    console.error('[GameErrorBoundary]', error);
  }

  render() {
    if (this.state.error) {
      return (
        <div className={containerStyle}>
          <h2 className={titleStyle} style={{ fontSize: 28 }}>
            Something went wrong
          </h2>
          <p style={{ color: '#aaa', marginBottom: 24, textAlign: 'center' }}>
            {this.state.error.message}
          </p>
          <button
            className={buttonStyle}
            onClick={() => {
              this.setState({ error: null });
              this.props.onReset();
            }}
          >
            Back to Menu
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// --- Screen types ---

type Screen = 'title' | 'select' | 'playing' | 'howto' | 'title-load';

// --- Loaded game state passed from App to PlaygroundGame ---

type LoadedGameState = {
  effects: Effects;
  lastAction: ActionResponse | null;
  ended: boolean;
};

// --- Components ---

function TitleScreen({
  onPlay,
  onHowToPlay,
  onContinue,
  onLoadGame,
  hasAutoSave,
}: {
  onPlay: () => void;
  onHowToPlay: () => void;
  onContinue: () => void;
  onLoadGame: () => void;
  hasAutoSave: boolean;
}) {
  return (
    <div className={containerStyle}>
      <h1 className={titleStyle}>Athena Crisis</h1>
      <p className={subtitleStyle}>Turn-Based Strategy</p>
      {hasAutoSave && (
        <button className={buttonStyle} onClick={onContinue} style={{ marginBottom: 12 }}>
          Continue
        </button>
      )}
      <button
        className={hasAutoSave ? secondaryButtonStyle : buttonStyle}
        onClick={onPlay}
        style={hasAutoSave ? { marginBottom: 12 } : undefined}
      >
        {hasAutoSave ? 'New Game' : 'Play'}
      </button>
      <button className={secondaryButtonStyle} onClick={onLoadGame} style={{ marginTop: 4 }}>
        Load Game
      </button>
      <button className={secondaryButtonStyle} onClick={onHowToPlay} style={{ marginTop: 4 }}>
        How to Play
      </button>
    </div>
  );
}

function HowToPlay({ onBack }: { onBack: () => void }) {
  return (
    <div className={howToContainerStyle}>
      <h2 className={howToHeadingStyle}>How to Play</h2>
      <ul className={howToListStyle}>
        <li className={howToItemStyle}>
          <span className={howToLabelStyle}>Select:</span>
          Tap/click a unit to select it.
        </li>
        <li className={howToItemStyle}>
          <span className={howToLabelStyle}>Move:</span>
          Tap a highlighted blue tile to move.
        </li>
        <li className={howToItemStyle}>
          <span className={howToLabelStyle}>Attack:</span>
          Tap a highlighted red tile to attack.
        </li>
        <li className={howToItemStyle}>
          <span className={howToLabelStyle}>End Turn:</span>
          Press the arrow button (bottom right) to end your turn.
        </li>
        <li className={howToItemStyle}>
          <span className={howToLabelStyle}>Undo:</span>
          Press the undo button to take back a move.
        </li>
        <li className={howToItemStyle}>
          <span className={howToLabelStyle}>Info:</span>
          Press the info button (&#8505;) to see objectives.
        </li>
        <li className={howToItemStyle}>
          <span className={howToLabelStyle}>Buildings:</span>
          Move infantry onto enemy buildings to capture them.
        </li>
      </ul>
      <button className={secondaryButtonStyle} onClick={onBack}>
        Back
      </button>
    </div>
  );
}

function SlotPicker({
  mode,
  onSelect,
  onCancel,
}: {
  mode: 'save' | 'load';
  onSelect: (key: string) => void;
  onCancel: () => void;
}) {
  const saves = useMemo(() => readAllSaves(), []);

  const slots = mode === 'save' ? SAVE_KEYS : [...SAVE_KEYS, AUTOSAVE_KEY];

  return (
    <div className={overlayStyle}>
      <h2 className={selectHeadingStyle}>{mode === 'save' ? 'Save Game' : 'Load Game'}</h2>
      <div className={slotGridStyle}>
        {slots.map((key) => {
          const save = saves[key];
          const label = key === AUTOSAVE_KEY ? 'Auto-Save' : `Slot ${key.slice(-1)}`;

          if (!save) {
            if (mode === 'load') {
              return (
                <div key={key} className={slotCardDisabledStyle}>
                  <span>{label} -- Empty</span>
                </div>
              );
            }
            return (
              <div key={key} className={slotCardEmptyStyle} onClick={() => onSelect(key)}>
                <span>{label} -- Empty</span>
              </div>
            );
          }

          return (
            <div key={key} className={slotCardStyle} onClick={() => onSelect(key)}>
              <div>
                <div className={slotNameStyle}>
                  {label}: {save.mapName || save.mapId}
                </div>
                <div className={slotDetailStyle}>
                  {biomeNames[save.biome] || 'Unknown'} -- {save.ended ? 'Ended' : 'In Progress'}
                </div>
              </div>
              <div className={slotTimeStyle}>{formatTimestamp(save.timestamp)}</div>
            </div>
          );
        })}
      </div>
      <button className={secondaryButtonStyle} onClick={onCancel}>
        Cancel
      </button>
    </div>
  );
}

type PauseView = 'menu' | 'save' | 'load' | 'confirm-exit';

function PauseMenu({
  onResume,
  onSave,
  onLoad,
  onExportSave,
  onImportSave,
  onExit,
}: {
  onResume: () => void;
  onSave: (key: string) => void;
  onLoad: (key: string) => void;
  onExportSave: () => void;
  onImportSave: () => void;
  onExit: () => void;
}) {
  const [view, setView] = useState<PauseView>('menu');
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const feedbackTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(
    () => () => {
      clearTimeout(feedbackTimer.current);
    },
    [],
  );

  const clearFeedback = useCallback(() => {
    setFeedback(null);
    setError(null);
  }, []);

  const handleSave = useCallback(
    (key: string) => {
      onSave(key);
      setFeedback('Saved!');
      setView('menu');
      clearTimeout(feedbackTimer.current);
      feedbackTimer.current = setTimeout(clearFeedback, 2000);
    },
    [onSave, clearFeedback],
  );

  const handleLoad = useCallback(
    (key: string) => {
      onLoad(key);
    },
    [onLoad],
  );

  const handleImport = useCallback(async () => {
    clearFeedback();
    onImportSave();
  }, [onImportSave, clearFeedback]);

  if (view === 'save') {
    return <SlotPicker mode="save" onSelect={handleSave} onCancel={() => setView('menu')} />;
  }

  if (view === 'load') {
    return <SlotPicker mode="load" onSelect={handleLoad} onCancel={() => setView('menu')} />;
  }

  if (view === 'confirm-exit') {
    return (
      <div className={overlayStyle}>
        <h2 className={selectHeadingStyle}>Exit to Menu?</h2>
        <p style={{ color: '#aaa', marginBottom: 24, textAlign: 'center', maxWidth: 360 }}>
          Unsaved progress will be lost.
        </p>
        <div className={overlayButtonRow}>
          <button className={buttonStyle} onClick={onExit}>
            Exit
          </button>
          <button className={secondaryButtonStyle} onClick={() => setView('menu')}>
            Cancel
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={overlayStyle}>
      <h2 className={selectHeadingStyle}>Paused</h2>
      {feedback && <div className={feedbackStyle}>{feedback}</div>}
      {error && <div className={errorFeedbackStyle}>{error}</div>}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, width: 220 }}>
        <button className={buttonStyle} onClick={onResume}>
          Resume
        </button>
        <button
          className={secondaryButtonStyle}
          onClick={() => {
            clearFeedback();
            setView('save');
          }}
        >
          Save Game
        </button>
        <button
          className={secondaryButtonStyle}
          onClick={() => {
            clearFeedback();
            setView('load');
          }}
        >
          Load Game
        </button>
        <button className={secondaryButtonStyle} onClick={onExportSave}>
          Export Save
        </button>
        <button className={secondaryButtonStyle} onClick={handleImport}>
          Import Save
        </button>
        <button className={secondaryButtonStyle} onClick={() => setView('confirm-exit')}>
          Exit to Menu
        </button>
      </div>
    </div>
  );
}

function LevelSelect({
  onBack,
  onStart,
}: {
  onBack: () => void;
  onStart: (map: MapData, metadata: MapMetadata | undefined, mapId: string, biome: Biome) => void;
}) {
  const [selectedMapId, setSelectedMapId] = useState<string | null>(null);
  const [selectedBiome, setSelectedBiome] = useState<Biome>(Biome.Grassland);

  const handleStart = useCallback(() => {
    if (selectedMapId === 'random') {
      const randomBase = generateSea(generateBuildings(generateRandomMap(new SizeVector(15, 10))));
      const map = convertBiome(randomBase, selectedBiome);
      onStart(map, undefined, 'random', selectedBiome);
      return;
    }

    const entry = mapCatalog.find((e) => e.id === selectedMapId);
    if (!entry) return;

    const map = convertBiome(entry.map, selectedBiome);
    onStart(map, entry.metadata, entry.id, selectedBiome);
  }, [selectedMapId, selectedBiome, onStart]);

  return (
    <div className={containerStyle}>
      <h2 className={selectHeadingStyle}>Select Map</h2>

      <div className={mapGridStyle}>
        {mapCatalog.map((entry) => (
          <div
            key={entry.id}
            className={selectedMapId === entry.id ? mapCardSelectedStyle : mapCardStyle}
            onClick={() => setSelectedMapId(entry.id)}
          >
            <div className={mapCardNameStyle}>{entry.name}</div>
            <div className={mapCardDetailStyle}>{entry.size}</div>
            {entry.tags.map((tag) => (
              <span key={tag} className={tagStyle}>
                {tag}
              </span>
            ))}
          </div>
        ))}

        <div
          className={selectedMapId === 'random' ? mapCardSelectedStyle : mapCardStyle}
          onClick={() => setSelectedMapId('random')}
        >
          <div className={mapCardNameStyle}>Random Map</div>
          <div className={mapCardDetailStyle}>15x10, generated</div>
          <span className={tagStyle}>random</span>
        </div>
      </div>

      <div className={sectionLabelStyle}>Biome</div>
      <div className={biomeRowStyle}>
        {biomeOptions.map(({ biome, label }) => (
          <button
            key={biome}
            className={selectedBiome === biome ? biomeChipSelectedStyle : biomeChipStyle}
            onClick={() => setSelectedBiome(biome)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className={actionRowStyle}>
        <button className={secondaryButtonStyle} onClick={onBack}>
          Back
        </button>
        <button
          className={buttonStyle}
          disabled={selectedMapId === null}
          onClick={handleStart}
          style={selectedMapId === null ? { opacity: 0.4, cursor: 'default' } : undefined}
        >
          Start Game
        </button>
      </div>
    </div>
  );
}

function GameOverOverlay({
  isVictory,
  onPlayAgain,
  onBackToMenu,
}: {
  isVictory: boolean;
  onPlayAgain: () => void;
  onBackToMenu: () => void;
}) {
  return (
    <div className={overlayStyle}>
      <h2
        className={`${overlayTitleStyle} ${isVictory ? overlayVictoryColor : overlayDefeatColor}`}
      >
        {isVictory ? 'Victory' : 'Defeat'}
      </h2>
      <div className={overlayButtonRow}>
        <button className={buttonStyle} onClick={onPlayAgain}>
          Play Again
        </button>
        <button className={secondaryButtonStyle} onClick={onBackToMenu}>
          Back to Menu
        </button>
      </div>
    </div>
  );
}

// Custom hook: like useClientGame but for loaded saves (bypasses startGame)
function useLoadedClientGame(
  map: MapData,
  loadedGame: LoadedGameState,
): [game: ClientGame, setGame: (game: ClientGame) => void, undo: (type: UndoType) => void] {
  const [game, setGame] = useState<ClientGame>(() => ({
    effects: loadedGame.effects,
    ended: loadedGame.ended,
    lastAction: loadedGame.lastAction,
    state: map,
    turnState: [map, loadedGame.lastAction, loadedGame.effects, []],
  }));

  return [game, setGame, useCallback((type: UndoType) => setGame(undo(game, type)), [game])];
}

// Wrapper component for a newly started game (uses useClientGame which calls startGame)
function NewPlaygroundGame(
  props: PlaygroundGameInnerProps & { map: MapData; metadata?: MapMetadata },
) {
  const [game, setGame, undoFn] = useClientGame(
    props.map,
    DemoViewer.id,
    props.metadata?.effects || new Map(),
    startAction,
  );
  return <PlaygroundGameInner {...props} game={game} setGame={setGame} undoFn={undoFn} />;
}

// Wrapper component for a loaded game (bypasses startGame to preserve saved state)
function LoadedPlaygroundGame(
  props: PlaygroundGameInnerProps & { map: MapData; loadedGame: LoadedGameState },
) {
  const [game, setGame, undoFn] = useLoadedClientGame(props.map, props.loadedGame);
  return <PlaygroundGameInner {...props} game={game} setGame={setGame} undoFn={undoFn} />;
}

function PlaygroundGame({
  biome,
  map,
  metadata,
  mapId,
  loadedGame,
  onPlayAgain,
  onBackToMenu,
  onSave,
  onLoad,
  onImportSave,
}: {
  biome: Biome;
  map: MapData;
  metadata?: MapMetadata;
  mapId: string;
  loadedGame?: LoadedGameState;
  onPlayAgain: () => void;
  onBackToMenu: () => void;
  onSave: (key: string) => void;
  onLoad: (key: string) => void;
  onImportSave: () => void;
}) {
  const innerProps: PlaygroundGameInnerProps = {
    biome,
    metadata,
    mapId,
    onPlayAgain,
    onBackToMenu,
    onSave,
    onLoad,
    onImportSave,
  };

  if (loadedGame) {
    return <LoadedPlaygroundGame {...innerProps} map={map} loadedGame={loadedGame} />;
  }
  return <NewPlaygroundGame {...innerProps} map={map} metadata={metadata} />;
}

type PlaygroundGameInnerProps = {
  biome: Biome;
  metadata?: MapMetadata;
  mapId: string;
  onPlayAgain: () => void;
  onBackToMenu: () => void;
  onSave: (key: string) => void;
  onLoad: (key: string) => void;
  onImportSave: () => void;
};

function PlaygroundGameInner({
  biome,
  metadata,
  mapId,
  onPlayAgain,
  onBackToMenu,
  onSave,
  onLoad,
  onImportSave,
  game,
  setGame,
  undoFn,
}: PlaygroundGameInnerProps & {
  game: ClientGame;
  setGame: (game: ClientGame) => void;
  undoFn: (type: UndoType) => void;
}) {
  const [renderKey, setRenderKey] = useState(0);
  const [paused, setPaused] = useState(false);
  const zoom = useScale();

  // Music is managed at App level to avoid stop/play race on load

  // Auto-save after each action
  const wrappedSetGame = useCallback(
    (newGame: ClientGame) => {
      setGame(newGame);
      if (!newGame.ended) {
        const mapName = metadata?.name || mapId;
        const saveData = serializeGame(newGame, mapId, mapName, biome);
        writeSave(AUTOSAVE_KEY, saveData);
      }
    },
    [setGame, mapId, metadata?.name, biome],
  );

  const onGameError = useCallback((error: Error) => {
    console.error('[GameAction]', error);
  }, []);
  const onAction = useClientGameAction(game, wrappedSetGame, null, onGameError);

  // Save current game to a slot
  const handleSave = useCallback(
    (key: string) => {
      const mapName = metadata?.name || mapId;
      const saveData = serializeGame(game, mapId, mapName, biome);
      writeSave(key, saveData);
      onSave(key);
    },
    [game, mapId, metadata?.name, biome, onSave],
  );

  // Export current game
  const handleExport = useCallback(() => {
    const mapName = metadata?.name || mapId;
    const saveData = serializeGame(game, mapId, mapName, biome);
    exportSave(saveData);
  }, [game, mapId, metadata?.name, biome]);

  const playerDetails = useClientGamePlayerDetails(game.state, DemoViewer);
  const onUndo = useCallback(
    (type: UndoType) => {
      undoFn(type);
      setRenderKey((k) => k + 1);
    },
    [undoFn],
  );
  const fade = renderKey === 0;

  return (
    <div className={gameMapWrapperStyle}>
      <button className={pauseButtonStyle} onClick={() => setPaused(true)} title="Menu">
        &#9776;
      </button>
      {paused && (
        <PauseMenu
          onResume={() => setPaused(false)}
          onSave={(key) => {
            handleSave(key);
          }}
          onLoad={(key) => {
            setPaused(false);
            onLoad(key);
          }}
          onExportSave={handleExport}
          onImportSave={() => {
            setPaused(false);
            onImportSave();
          }}
          onExit={() => {
            setPaused(false);
            onBackToMenu();
          }}
        />
      )}
      <GameMap
        autoPanning
        currentUserId={DemoViewer.id}
        fogStyle="soft"
        key={`play-demo-map-${renderKey}`}
        lastActionResponse={game.lastAction}
        map={game.state}
        margin="minimal"
        onAction={onAction}
        onError={onGameError}
        pan
        paused={paused}
        playerDetails={playerDetails}
        scale={zoom}
        scroll={false}
        style="floating"
        tilted
      >
        {(props, actions) => {
          const gameEnd = props.lastActionResponse?.type === 'GameEnd';
          const isVictory =
            gameEnd &&
            props.lastActionResponse != null &&
            'toPlayer' in props.lastActionResponse &&
            props.lastActionResponse.toPlayer === 1;

          return (
            <>
              <MapInfo hide={gameEnd} {...props} />
              <GameActions
                actions={actions}
                canUndoAction
                fade={fade}
                hide={gameEnd}
                state={props}
                undo={onUndo}
                zoom={zoom}
              />
              {gameEnd && (
                <GameOverOverlay
                  isVictory={!!isVictory}
                  onPlayAgain={onPlayAgain}
                  onBackToMenu={onBackToMenu}
                />
              )}
            </>
          );
        }}
      </GameMap>
    </div>
  );
}

function App() {
  const [screen, setScreen] = useState<Screen>('title');
  const [gameConfig, setGameConfig] = useState<{
    map: MapData;
    metadata?: MapMetadata;
    mapId: string;
    biome: Biome;
    loadedGame?: LoadedGameState;
  } | null>(null);

  // Key to force re-mount of PlaygroundGame on play-again
  const [gameKey, setGameKey] = useState(0);

  const handlePlay = useCallback(() => {
    setScreen('select');
  }, []);

  const handleHowToPlay = useCallback(() => {
    setScreen('howto');
  }, []);

  const handleBack = useCallback(() => {
    setScreen('title');
  }, []);

  const handleStart = useCallback(
    (map: MapData, metadata: MapMetadata | undefined, mapId: string, biome: Biome) => {
      setGameConfig({ map, metadata, mapId, biome });
      setGameKey((k) => k + 1);
      setScreen('playing');
    },
    [],
  );

  const handlePlayAgain = useCallback(() => {
    if (!gameConfig) return;

    if (gameConfig.mapId === 'random') {
      // Generate a new random map for play-again
      const randomBase = generateSea(generateBuildings(generateRandomMap(new SizeVector(15, 10))));
      const map = convertBiome(randomBase, gameConfig.biome);
      setGameConfig((prev) => (prev ? { ...prev, map, loadedGame: undefined } : prev));
    } else {
      // Restore original catalog map for a fresh start (in case we loaded a save)
      const catalogEntry = mapCatalog.find((e) => e.id === gameConfig.mapId);
      if (catalogEntry) {
        const map = convertBiome(catalogEntry.map, gameConfig.biome);
        setGameConfig((prev) =>
          prev ? { ...prev, map, metadata: catalogEntry.metadata, loadedGame: undefined } : prev,
        );
      } else {
        setGameConfig((prev) => (prev ? { ...prev, loadedGame: undefined } : prev));
      }
    }
    setGameKey((k) => k + 1);
  }, [gameConfig]);

  const handleBackToMenu = useCallback(() => {
    setScreen('select');
  }, []);

  // Load a save from SaveData directly
  const loadFromSave = useCallback((data: SaveData) => {
    try {
      const mapState = MapData.fromObject(data.mapState);
      const effects = decodeEffects(data.effects);
      const lastAction = data.lastAction ? decodeActionResponse(data.lastAction) : null;

      // Find metadata from catalog if it's a known map
      const catalogEntry = mapCatalog.find((e) => e.id === data.mapId);

      setGameConfig({
        map: mapState,
        metadata: catalogEntry?.metadata,
        mapId: data.mapId,
        biome: data.biome as Biome,
        loadedGame: { effects, lastAction, ended: data.ended },
      });
      setGameKey((k) => k + 1);
      setScreen('playing');
    } catch (error) {
      console.error('[LoadSave] Corrupt save data:', error);
    }
  }, []);

  const handleLoadSlot = useCallback(
    (key: string) => {
      const data = readSave(key);
      if (data) loadFromSave(data);
    },
    [loadFromSave],
  );

  const handleImportSave = useCallback(async () => {
    const data = await importSaveFromFile();
    if (data) loadFromSave(data);
  }, [loadFromSave]);

  // No-op for save confirmation (save happens in PlaygroundGame)
  const handleSaveConfirm = useCallback(() => {}, []);

  // Check for auto-save existence (re-evaluated when screen changes)
  const hasAutoSave = screen === 'title' && readSave(AUTOSAVE_KEY) !== null;

  const handleContinue = useCallback(() => {
    const data = readSave(AUTOSAVE_KEY);
    if (data) loadFromSave(data);
  }, [loadFromSave]);

  const handleTitleLoad = useCallback(() => {
    setScreen('title-load');
  }, []);

  // Manage music at App level to survive PlaygroundGame remounts (load game)
  const currentSong =
    screen === 'playing' && gameConfig
      ? biomeToSong(gameConfig.biome, gameConfig.metadata?.tags)
      : null;
  useEffect(() => {
    if (currentSong) {
      AudioPlayer.play(currentSong);
    } else {
      AudioPlayer.stopCurrentSong();
    }
  }, [currentSong]);

  // Memoize the game rendering to avoid unnecessary work
  const gameElement = useMemo(() => {
    if (screen !== 'playing' || !gameConfig) return null;
    return (
      <PlaygroundGame
        biome={gameConfig.biome}
        key={gameKey}
        map={gameConfig.map}
        mapId={gameConfig.mapId}
        metadata={gameConfig.metadata}
        loadedGame={gameConfig.loadedGame}
        onPlayAgain={handlePlayAgain}
        onBackToMenu={handleBackToMenu}
        onSave={handleSaveConfirm}
        onLoad={handleLoadSlot}
        onImportSave={handleImportSave}
      />
    );
  }, [
    screen,
    gameConfig,
    gameKey,
    handlePlayAgain,
    handleBackToMenu,
    handleSaveConfirm,
    handleLoadSlot,
    handleImportSave,
  ]);

  return (
    <MemoryRouter>
      <LocaleContext>
        <ScaleContext>
          <VisibilityStateContext>
            <AlertContext>
              {screen === 'title' && (
                <TitleScreen
                  onPlay={handlePlay}
                  onHowToPlay={handleHowToPlay}
                  onContinue={handleContinue}
                  onLoadGame={handleTitleLoad}
                  hasAutoSave={hasAutoSave}
                />
              )}
              {screen === 'howto' && <HowToPlay onBack={handleBack} />}
              {screen === 'title-load' && (
                <SlotPicker mode="load" onSelect={handleLoadSlot} onCancel={handleBack} />
              )}
              {screen === 'select' && <LevelSelect onBack={handleBack} onStart={handleStart} />}
              {screen === 'playing' && (
                <GameErrorBoundary onReset={handleBackToMenu}>{gameElement}</GameErrorBoundary>
              )}
            </AlertContext>
          </VisibilityStateContext>
        </ScaleContext>
      </LocaleContext>
    </MemoryRouter>
  );
}

const root = createRoot(document.getElementById('root')!);
root.render(<App />);
