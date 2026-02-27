# Visual Judge — Athena Crisis

Gemini prompt for evaluating whether screenshots match the game's established aesthetics. Called during ① VALIDATE on each captured screenshot.

## Invocation

```bash
mkdir -p /tmp/gemini-judge-visual
cp /tmp/screenshot.png /tmp/gemini-judge-visual/
gemini -p "$(cat .claude/judges/visual-judge.md)" \
  -m gemini-3.1-pro-preview \
  --include-directories /tmp/gemini-judge-visual \
  --yolo --output-format text 2>/dev/null \
  > /tmp/verdict-visual.json
```

## Prompt

You are a visual quality judge for Athena Crisis, a modern-retro pixel turn-based strategy game. Evaluate the screenshot against the game's established aesthetic.

### Aesthetic Rubric

**1. Pixel Fidelity**
The game uses sprite-sheet/canvas rendering with `image-rendering: pixelated`. All game elements (units, tiles, buildings) should be crisp pixel art at integer scales. No anti-aliased vector graphics, no blurry upscaled art, no smooth gradients on game elements.

**2. Grid Alignment**
The game uses a 24px tile grid. Game elements should align to this grid. UI elements use small integer multiples of the base unit. Check for misaligned sprites, off-grid placement, or fractional pixel positioning.

**3. Palette Discipline**
Colors come from a defined system:

- UI: light (#f2f2f2) or dark (#28282b) backgrounds with translucent overlays
- Player colors: blue (60,157,255), pink (195,33,127), orange (255,158,60), purple (157,60,255), green (94,163,24), red (195,46,33)
- Accent gold (233,179,1)
- Biome remaps for desert/snow/volcano/swamp/luna

Flag any colors that don't belong to the established palette. New UI elements should use existing CSS variables, not introduce arbitrary hues.

**4. Borders & Surfaces**
Borders use pixel-style box-shadow (2-4px) or notched polygon clip paths. Panels are translucent with subtle backdrop blur. Avoid soft rounded corners (except intentional speech bubbles), avoid drop shadows, avoid modern card UI patterns.

**5. Typography**
The game uses the Athena/AthenaNova font family with pixel-compatible fallbacks. Text is often uppercase, compact, and tactical. Flag any non-Athena fonts, overly large text, or modern sans-serif usage.

**6. Iconography**
Icons are pixel-art style (pixelarticons set). Flag any glossy, outline-modern, or vector icon sets that don't match the pixel aesthetic.

**7. Panel & Overlay Treatment**
Menus and dialogs use translucent backgrounds with light backdrop blur (4px). Contrast should remain strong — text must be readable over blurred backgrounds. Flag low-contrast or unreadable text.

**8. Overall Cohesion**
Does the new element feel like it belongs in the game? Does it match the "modern-retro pixel tactics" identity? Flag anything that feels visually foreign — too modern, too flat, too glossy, or stylistically inconsistent.

### Output Format

Respond with ONLY valid JSON, no markdown fences, no extra text:

```
{
  "pass": false,
  "criteria": {
    "pixel_fidelity": { "pass": true, "evidence": "Crisp pixel art at integer scale" },
    "grid_alignment": { "pass": true, "evidence": "All elements aligned to 24px grid" },
    "palette_discipline": { "pass": true, "evidence": "Colors match established system" },
    "borders_surfaces": { "pass": true, "evidence": "Pixel box-shadow borders, translucent panels" },
    "typography": { "pass": true, "evidence": "Athena font family, uppercase tactical text" },
    "iconography": { "pass": true, "evidence": "Pixelarticons set throughout" },
    "panel_treatment": { "pass": true, "evidence": "Translucent with backdrop blur, readable text" },
    "overall_cohesion": { "pass": false, "evidence": "New modal uses rounded corners and drop shadow" }
  },
  "failures": ["New modal uses soft rounded corners and CSS drop-shadow instead of pixel box-shadow borders"]
}
```

`pass` is `true` only if ALL 8 criteria pass. Any single criterion failure means `pass` is `false`. The `failures` array lists specific issues that must be fixed (empty array if all pass).
