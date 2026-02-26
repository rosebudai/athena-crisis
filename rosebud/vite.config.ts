import babelPluginEmotion from '@emotion/babel-plugin';
import react from '@vitejs/plugin-react';
import { resolve } from 'node:path';
import { defineConfig } from 'vite';
import presets from '../infra/babelPresets.tsx';
import createResolver from '../infra/createResolver.tsx';

const root = resolve(__dirname, '..');

export default defineConfig({
  root: __dirname,
  base: './',
  publicDir: resolve(__dirname, 'public'),
  build: {
    outDir: resolve(__dirname, 'dist'),
    target: 'esnext',
    emptyOutDir: true,
    assetsDir: 'static',
    // Inline all audio files as data URIs so the game is fully self-contained
    // (Rosebud Universal mode cannot serve binary assets locally)
    assetsInlineLimit: 600 * 1024, // 600KB covers all audio files
  },
  define: {
    'process.env.NODE_ENV': JSON.stringify('production'),
    'process.env.IS_DEMO': JSON.stringify('1'),
    'process.env.IS_LANDING_PAGE': JSON.stringify(''),
  },
  resolve: {
    alias: [
      createResolver(),
      // Map workspace packages to their source directories
      { find: /^@deities\/apollo\/(.*)$/, replacement: resolve(root, 'apollo/$1') },
      { find: /^@deities\/art\/(.*)$/, replacement: resolve(root, 'art/$1') },
      { find: /^@deities\/athena\/(.*)$/, replacement: resolve(root, 'athena/$1') },
      { find: /^@deities\/dionysus\/(.*)$/, replacement: resolve(root, 'dionysus/$1') },
      { find: /^@deities\/hera\/(.*)$/, replacement: resolve(root, 'hera/$1') },
      { find: /^@deities\/hermes\/(.*)$/, replacement: resolve(root, 'hermes/$1') },
      { find: /^@deities\/i18n\/(.*)$/, replacement: resolve(root, 'i18n/$1') },
      { find: /^@deities\/ui\/(.*)$/, replacement: resolve(root, 'ui/$1') },
    ],
  },
  plugins: [
    react({
      babel: {
        plugins: [babelPluginEmotion],
        presets,
      },
    }),
  ],
  worker: {
    format: 'es',
    plugins: () => [
      react({
        babel: {
          plugins: [babelPluginEmotion],
          presets,
        },
      }),
    ],
  },
  assetsInclude: ['**/*.aac', '**/*.ogg'],
});
