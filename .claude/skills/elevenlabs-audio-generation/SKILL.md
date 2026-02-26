---
name: elevenlabs-audio-generation
description: Use when generating game audio (music, sound effects, BGM) via ElevenLabs API. Use when adding sound to a game port, replacing missing audio assets, or creating new SFX/music from text prompts.
---

# ElevenLabs Audio Generation

Generate music and SFX using the ElevenLabs API (`@elevenlabs/elevenlabs-js` v2.36+).

## Prerequisites

- `ELEVENLABS_API_KEY` env var
- `npm install @elevenlabs/elevenlabs-js dotenv`

## Scripts (included in this skill)

| Script                    | Purpose                                                           |
| ------------------------- | ----------------------------------------------------------------- |
| `generate-audio.ts`       | Manifest-driven: generates music + SFX from `audio-manifest.json` |
| `generate-music-batch.ts` | Batch music: generates multiple tracks from inline `tracks` array |

### generate-audio.ts (manifest-driven)

Reads an `audio-manifest.json`, generates all music and SFX, writes mp3 files, updates manifest in-place.

```bash
ELEVENLABS_API_KEY=... npx tsx .claude/skills/elevenlabs-audio-generation/generate-audio.ts audio/ --manifest audio/audio-manifest.json
```

### generate-music-batch.ts (batch music)

Edit the `tracks` array in the script, then run:

```bash
ELEVENLABS_API_KEY=... npx tsx .claude/skills/elevenlabs-audio-generation/generate-music-batch.ts
```

Output goes to `output/` next to the script. Change `outputDir` as needed.

## API Quick Reference

### Music — `client.music.compose()`

```typescript
const audio = await client.music.compose({
  prompt:
    'Looping instrumental music for grassland strategy. Heroic strings, military snare. ~115 BPM. Seamless loop.',
  musicLengthMs: 30000,
  forceInstrumental: true,
  outputFormat: 'mp3_44100_128',
});
await pipeline(Readable.from(audio), createWriteStream('track.mp3'));
```

### SFX — `client.textToSoundEffects.convert()`

```typescript
const audio = await client.textToSoundEffects.convert({
  text: 'sharp whistling missile launch into air, combat game sound',
  durationSeconds: 1,
  promptInfluence: 0.5,
  outputFormat: 'mp3_44100_128',
});
await pipeline(Readable.from(audio), createWriteStream('sfx/missile.mp3'));
```

## Manifest Schema

```json
{
  "gameTitle": "Game Name",
  "music": {
    "prompt": "Looping instrumental background music for...",
    "durationMs": 30000,
    "file": "music/track.mp3",
    "generated": false
  },
  "sfx": [
    {
      "name": "attack_cannon",
      "prompt": "single heavy cannon blast, military game sound",
      "durationSeconds": 1,
      "file": "sfx/attack_cannon.mp3",
      "generated": false
    }
  ]
}
```

Script sets `generated: true` after writing each file. Existing files are skipped.

## Prompt Writing

| Do                                                                     | Don't                                  |
| ---------------------------------------------------------------------- | -------------------------------------- |
| Vivid natural language: "deep booming artillery cannon fire, war game" | Technical specs: "sine wave at 400Hz"  |
| Include context: "game sound", "military", "retro", "arcade"           | Abstract descriptions: "an explosion"  |
| Describe mood: "cheerful", "menacing", "satisfying"                    | Overly long prompts (keep < 100 chars) |
| For music: include BPM, "Seamless loop", instrumentation               | Forget "Seamless loop" for BGM         |

## Duration Guidelines

| Type                             | Duration        |
| -------------------------------- | --------------- |
| UI click / chirp / collect       | 0.5s            |
| Attack / jump / hit              | 1-1.5s          |
| Explosion / death / heavy impact | 2s              |
| Victory / fanfare / celebration  | 3s              |
| Background music                 | 30000ms (loops) |

## Concurrency

ElevenLabs rate-limits requests. Use pooled concurrency:

- **Music**: 1-2 concurrent
- **SFX**: 2-3 concurrent
- **Large batches (80+ SFX)**: concurrency of 2

## Common Mistakes

- **Forgetting `forceInstrumental: true`** on music — you'll get vocals
- **Missing `Seamless loop` in music prompts** — track won't loop cleanly
- **SFX too long** — keep short; 0.5-2s covers most game sounds
- **Not streaming to file** — `audio` is async iterable, must use `Readable.from()` + `pipeline()`
- **Rate limits** — if you get 429 errors, reduce concurrency or add retry with backoff
