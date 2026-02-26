#!/usr/bin/env -S npx tsx
// generate-audio.ts — Generate music + SFX from an audio-manifest.json via ElevenLabs.
//
// Usage: ELEVENLABS_API_KEY=... npx tsx generate-audio.ts <output-dir> [--manifest <path>]
//
// Reads audio-manifest.json, calls ElevenLabs APIs, writes mp3 files.
// Skips existing files (idempotent). Updates manifest `generated` flags in-place.

import { ElevenLabsClient } from '@elevenlabs/elevenlabs-js';
import { readFileSync, writeFileSync, createWriteStream, existsSync, mkdirSync } from 'fs';
import { stat } from 'fs/promises';
import { join, resolve } from 'path';
import { Readable } from 'stream';
import { pipeline } from 'stream/promises';

const SFX_CONCURRENCY = 3;

interface MusicEntry {
  prompt: string;
  durationMs: number;
  file: string;
  generated: boolean;
  error?: string;
}

interface SfxEntry {
  name: string;
  prompt: string;
  durationSeconds: number;
  file: string;
  generated: boolean;
  error?: string;
}

interface AudioManifest {
  gameTitle: string;
  music: MusicEntry;
  sfx: SfxEntry[];
}

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
  const args = process.argv.slice(2);
  const manifestIdx = args.indexOf('--manifest');
  let manifestPath: string | undefined;
  if (manifestIdx !== -1 && args[manifestIdx + 1]) {
    manifestPath = resolve(args[manifestIdx + 1]);
    args.splice(manifestIdx, 2);
  }
  const dir = args.find((a) => !a.startsWith('--'));
  if (!dir) {
    console.error('Usage: npx tsx generate-audio.ts <output-dir> [--manifest <path>]');
    process.exit(1);
  }

  if (!manifestPath) {
    manifestPath = join(dir, 'audio-manifest.json');
  }
  if (!existsSync(manifestPath)) {
    console.error(`audio-manifest.json not found at ${manifestPath}`);
    process.exit(1);
  }

  const apiKey = process.env.ELEVENLABS_API_KEY;
  if (!apiKey) {
    console.error('ELEVENLABS_API_KEY is required but not set.');
    process.exit(1);
  }

  const manifest: AudioManifest = JSON.parse(readFileSync(manifestPath, 'utf-8'));
  const client = new ElevenLabsClient({ apiKey });

  // ── Generate background music ───────────────────────────
  const bgmPath = join(dir, manifest.music.file);
  mkdirSync(join(bgmPath, '..'), { recursive: true });
  if (existsSync(bgmPath)) {
    console.log(`Music already exists — skipping.`);
    manifest.music.generated = true;
  } else {
    console.log(`Generating background music...`);
    console.log(`  Prompt: ${manifest.music.prompt}`);
    console.log(`  Duration: ${manifest.music.durationMs}ms`);
    try {
      const audio = await client.music.compose({
        prompt: manifest.music.prompt,
        musicLengthMs: manifest.music.durationMs,
        forceInstrumental: true,
        outputFormat: 'mp3_44100_128',
      });
      await pipeline(Readable.from(audio), createWriteStream(bgmPath));
      const sizeMB = ((await stat(bgmPath)).size / 1024 / 1024).toFixed(2);
      console.log(`  Saved ${sizeMB} MB → ${bgmPath}`);
      manifest.music.generated = true;
    } catch (err: any) {
      console.error(`  Music generation failed: ${err.message}`);
      manifest.music.generated = false;
      manifest.music.error = err.message;
    }
  }

  // ── Generate sound effects ──────────────────────────────
  const sfxDir = join(dir, 'sfx');
  mkdirSync(sfxDir, { recursive: true });

  console.log(
    `Generating ${manifest.sfx.length} sound effects (concurrency: ${SFX_CONCURRENCY})...`,
  );

  await pooled(manifest.sfx, SFX_CONCURRENCY, async (entry) => {
    const outputPath = join(dir, entry.file);
    if (existsSync(outputPath)) {
      console.log(`  ✓ ${entry.name} (exists)`);
      entry.generated = true;
      return;
    }

    try {
      const audio = await client.textToSoundEffects.convert({
        text: entry.prompt,
        durationSeconds: entry.durationSeconds,
        promptInfluence: 0.5,
        outputFormat: 'mp3_44100_128',
      });
      await pipeline(Readable.from(audio), createWriteStream(outputPath));
      const size = (await stat(outputPath)).size;
      console.log(`  ✓ ${entry.name} (${(size / 1024).toFixed(0)} KB)`);
      entry.generated = true;
    } catch (err: any) {
      console.error(`  ✗ ${entry.name}: ${err.message}`);
      entry.generated = false;
      entry.error = err.message;
    }
  });

  // ── Update manifest in-place ────────────────────────────
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n');

  const generated = manifest.sfx.filter((e) => e.generated).length;
  const total = manifest.sfx.length;
  const musicStatus = manifest.music.generated ? '✓' : '✗';
  console.log(`\nDone: music ${musicStatus}, SFX ${generated}/${total}`);
}

main().catch((err) => {
  console.error('Audio generation failed:', err.message);
  process.exit(1);
});
