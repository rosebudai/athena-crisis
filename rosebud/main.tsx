import { MapMetadata } from '@deities/apollo/MapMetadata.tsx';
import { prepareSprites } from '@deities/art/Sprites.tsx';
import {
  generateBuildings,
  generateRandomMap,
  generateSea,
} from '@deities/athena/generator/MapGenerator.tsx';
import convertBiome from '@deities/athena/lib/convertBiome.tsx';
import { Biome } from '@deities/athena/map/Biome.tsx';
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
import { useCallback, useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';

// Initialize global CSS (variables, global styles)
initializeCSSVariables();
initializeCSS();

// Prepare sprite CSS classes (async, loads from CDN)
prepareSprites();

// Enable audio - sound files are generated via ElevenLabs
AudioPlayer.resume();
AudioPlayer.preload();

const startAction = { type: 'Start' } as const;

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

// --- Screen types ---

type Screen = 'title' | 'select' | 'playing' | 'howto';

// --- Components ---

function TitleScreen({ onPlay, onHowToPlay }: { onPlay: () => void; onHowToPlay: () => void }) {
  return (
    <div className={containerStyle}>
      <h1 className={titleStyle}>Athena Crisis</h1>
      <p className={subtitleStyle}>Turn-Based Strategy</p>
      <button className={buttonStyle} onClick={onPlay}>
        Play
      </button>
      <button className={secondaryButtonStyle} onClick={onHowToPlay} style={{ marginTop: 16 }}>
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

function PlaygroundGame({
  biome,
  map,
  metadata,
  onPlayAgain,
  onBackToMenu,
}: {
  biome: Biome;
  map: MapData;
  metadata?: MapMetadata;
  onPlayAgain: () => void;
  onBackToMenu: () => void;
}) {
  const [renderKey, setRenderKey] = useState(0);
  const zoom = useScale();

  // Play biome-appropriate music when game starts or biome changes
  const song = biomeToSong(biome, metadata?.tags);
  useEffect(() => {
    AudioPlayer.play(song);
    return () => {
      AudioPlayer.stopCurrentSong();
    };
  }, [song]);

  const [game, setGame, undo] = useClientGame(
    map,
    DemoViewer.id,
    metadata?.effects || new Map(),
    startAction,
  );
  const onAction = useClientGameAction(game, setGame);
  const playerDetails = useClientGamePlayerDetails(game.state, DemoViewer);
  const onUndo = useCallback(
    (type: UndoType) => {
      undo(type);
      setRenderKey((k) => k + 1);
    },
    [undo],
  );
  const fade = renderKey === 0;

  return (
    <div className={gameMapWrapperStyle}>
      <GameMap
        autoPanning
        currentUserId={DemoViewer.id}
        fogStyle="soft"
        key={`play-demo-map-${renderKey}`}
        lastActionResponse={game.lastAction}
        map={game.state}
        margin="minimal"
        onAction={onAction}
        pan
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
      setGameConfig((prev) => (prev ? { ...prev, map } : prev));
    }
    setGameKey((k) => k + 1);
  }, [gameConfig]);

  const handleBackToMenu = useCallback(() => {
    setScreen('select');
  }, []);

  // Memoize the game rendering to avoid unnecessary work
  const gameElement = useMemo(() => {
    if (screen !== 'playing' || !gameConfig) return null;
    return (
      <PlaygroundGame
        biome={gameConfig.biome}
        key={gameKey}
        map={gameConfig.map}
        metadata={gameConfig.metadata}
        onPlayAgain={handlePlayAgain}
        onBackToMenu={handleBackToMenu}
      />
    );
  }, [screen, gameConfig, gameKey, handlePlayAgain, handleBackToMenu]);

  return (
    <LocaleContext>
      <ScaleContext>
        <VisibilityStateContext>
          <AlertContext>
            {screen === 'title' && (
              <TitleScreen onPlay={handlePlay} onHowToPlay={handleHowToPlay} />
            )}
            {screen === 'howto' && <HowToPlay onBack={handleBack} />}
            {screen === 'select' && <LevelSelect onBack={handleBack} onStart={handleStart} />}
            {screen === 'playing' && gameElement}
          </AlertContext>
        </VisibilityStateContext>
      </ScaleContext>
    </LocaleContext>
  );
}

const root = createRoot(document.getElementById('root')!);
root.render(<App />);
