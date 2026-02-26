#!/usr/bin/env -S npx tsx
// generate-music-batch.ts — Generate multiple music tracks via ElevenLabs music.compose.
//
// Usage: ELEVENLABS_API_KEY=... npx tsx generate-music-batch.ts
//
// Edit the `tracks` array below with your track definitions.
// Skips existing files (idempotent). Concurrency-limited to avoid rate limits.

import { ElevenLabsClient } from '@elevenlabs/elevenlabs-js';
import { createWriteStream, existsSync, mkdirSync } from 'fs';
import { stat } from 'fs/promises';
import { join, resolve } from 'path';
import { Readable } from 'stream';
import { pipeline } from 'stream/promises';

const CONCURRENCY = 2;
const outputDir = resolve(import.meta.dirname, 'output');

interface MusicTrack {
  name: string;
  prompt: string;
  durationMs: number;
  file: string;
}

// ── Define your tracks here ─────────────────────────────────
const tracks: MusicTrack[] = [
  // Example:
  // {
  //   name: 'battle-theme',
  //   prompt: 'Looping instrumental music for battlefield strategy game. Heroic strings, military snare, adventurous brass. Bold and tactical. ~115 BPM. Seamless loop.',
  //   durationMs: 30000,
  //   file: 'battle-theme.mp3',
  // },
];

async function pooled<T>(
  items: T[],
  concurrency: number,
  fn: (item: T) => Promise<void>,
): Promise<void> {
  const queue = [...items];
  const workers = Array.from({ length: concurrency }, async () => {
    while (queue.length > 0) {
      const item = queue.shift()!;
      await fn(item);
    }
  });
  await Promise.all(workers);
}

async function main() {
  const apiKey = process.env.ELEVENLABS_API_KEY;
  if (!apiKey) {
    console.error('ELEVENLABS_API_KEY required');
    process.exit(1);
  }

  if (tracks.length === 0) {
    console.error('No tracks defined. Edit the tracks array in this script.');
    process.exit(1);
  }

  mkdirSync(outputDir, { recursive: true });
  const client = new ElevenLabsClient({ apiKey });

  console.log(`Generating ${tracks.length} music tracks (concurrency: ${CONCURRENCY})...`);

  await pooled(tracks, CONCURRENCY, async (track) => {
    const outputPath = join(outputDir, track.file);
    if (existsSync(outputPath)) {
      const size = (await stat(outputPath)).size;
      if (size > 0) {
        console.log(`  ✓ ${track.name} (exists, ${(size / 1024).toFixed(0)} KB)`);
        return;
      }
    }

    try {
      console.log(`  ⏳ ${track.name}...`);
      const audio = await client.music.compose({
        prompt: track.prompt,
        musicLengthMs: track.durationMs,
        forceInstrumental: true,
        outputFormat: 'mp3_44100_128',
      });
      await pipeline(Readable.from(audio), createWriteStream(outputPath));
      const sizeMB = ((await stat(outputPath)).size / 1024 / 1024).toFixed(2);
      console.log(`  ✓ ${track.name} (${sizeMB} MB)`);
    } catch (err: any) {
      console.error(`  ✗ ${track.name}: ${err.message}`);
    }
  });

  console.log('\nDone!');
}

main().catch((err) => {
  console.error('Music generation failed:', err.message);
  process.exit(1);
});
