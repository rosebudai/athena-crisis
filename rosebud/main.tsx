import { MapMetadata } from '@deities/apollo/MapMetadata.tsx';
import { prepareSprites } from '@deities/art/Sprites.tsx';
import convertBiome from '@deities/athena/lib/convertBiome.tsx';
import { Biome } from '@deities/athena/map/Biome.tsx';
import MapData from '@deities/athena/MapData.tsx';
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
import AudioPlayer from '@deities/ui/AudioPlayer.tsx';
import initializeCSS from '@deities/ui/CSS.tsx';
import { initializeCSSVariables } from '@deities/ui/cssVar.tsx';
import { AlertContext } from '@deities/ui/hooks/useAlert.tsx';
import { ScaleContext } from '@deities/ui/hooks/useScale.tsx';
import { VisibilityStateContext } from '@nkzw/use-visibility-state';
import { useCallback, useState } from 'react';
import { createRoot } from 'react-dom/client';

// Initialize global CSS (variables, global styles)
initializeCSSVariables();
initializeCSS();

// Prepare sprite CSS classes (async, loads from CDN)
prepareSprites();

// Pause audio by default for standalone builds
AudioPlayer.pause();

const startAction = { type: 'Start' } as const;

// Build a demo map
const currentDemoMap = convertBiome(demo1, Biome.Grassland);

function PlaygroundGame({ map, metadata }: { map: MapData; metadata?: MapMetadata }) {
  const [renderKey, setRenderKey] = useState(0);
  const zoom = 1;

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
        const hide = props.lastActionResponse?.type === 'GameEnd';
        return (
          <>
            <MapInfo hide={hide} {...props} />
            <GameActions
              actions={actions}
              canUndoAction
              fade={fade}
              hide={hide}
              state={props}
              undo={onUndo}
              zoom={zoom}
            />
          </>
        );
      }}
    </GameMap>
  );
}

function App() {
  return (
    <LocaleContext>
      <ScaleContext>
        <VisibilityStateContext>
          <AlertContext>
            <PlaygroundGame map={currentDemoMap} metadata={metadata1} />
          </AlertContext>
        </VisibilityStateContext>
      </ScaleContext>
    </LocaleContext>
  );
}

const root = createRoot(document.getElementById('root')!);
root.render(<App />);
