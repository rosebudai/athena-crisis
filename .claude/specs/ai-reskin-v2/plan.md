# AI Reskin Pipeline v2 Implementation Plan

> **For Claude:** Execute this plan using subagent-driven-development. This plan was auto-generated and does not require user approval.

**Goal:** Get AI-reskinned Portraits and Buildings rendering in-game as a proof of concept.

**Spec:** `.claude/specs/ai-reskin-v2/spec.md`

**Architecture:** Reuse existing `utils/reskin/` pipeline, fix Sprites.tsx bypass, run pipeline for portrait+building categories, playtest.

**Tech Stack:** Python 3 (existing pipeline), TypeScript (Sprites.tsx fix), FAL.ai Gemini

---

### Task 1: Clean up reskin output and run AI pipeline for portraits and buildings

**What to do:**

1. Remove previous unit-sprite output: `rm -rf utils/reskin/output/cyberpunk/` and `rm -rf rosebud/public/reskin/`
2. Run the pipeline in standard mode (NOT batch mode) for portraits:
   ```bash
   FAL_KEY="51533afa-0b00-4690-9516-bcf32827af65:4d92a7c9d60561a283d13dc108b4be21" \
     python utils/reskin/reskin.py --theme cyberpunk --category portrait --provider fal_gemini --output-dir utils/reskin/output
   ```
3. Run for buildings:
   ```bash
   FAL_KEY="51533afa-0b00-4690-9516-bcf32827af65:4d92a7c9d60561a283d13dc108b4be21" \
     python utils/reskin/reskin.py --theme cyberpunk --category building --provider fal_gemini --output-dir utils/reskin/output --force
   ```
4. Verify output directory has exactly 3 PNGs: `Portraits.png`, `Buildings.png`, `Building-Create.png`

**Important:** The `--force` flag is needed on the second run to overwrite the manifest from the first run. Alternatively, the manifest may be additive — check which behavior occurs.

**Note on standard vs batch mode:** Standard mode (`process_asset()`) sends each image individually through `ai_reskin()` which calls `provider.transform()`. This is appropriate for these 3 large images — no need for grid batching.

**Verify:**

```bash
ls -la utils/reskin/output/cyberpunk/*.png
# Should show 3 files: Buildings.png, Building-Create.png, Portraits.png
```

---

### Task 2: Deploy reskinned assets and rebuild Rosebud

**What to do:**

1. Create the reskin directory in Rosebud's public folder:

   ```bash
   mkdir -p rosebud/public/reskin/cyberpunk
   ```

2. Copy the 3 reskinned PNGs:

   ```bash
   cp utils/reskin/output/cyberpunk/Portraits.png rosebud/public/reskin/cyberpunk/
   cp utils/reskin/output/cyberpunk/Buildings.png rosebud/public/reskin/cyberpunk/
   cp utils/reskin/output/cyberpunk/Building-Create.png rosebud/public/reskin/cyberpunk/
   ```

3. Write the runtime manifest at `rosebud/public/reskin/manifest.json`:

   ```json
   {
     "basePath": "reskin/cyberpunk",
     "sprites": ["Portraits", "Buildings", "Building-Create"]
   }
   ```

4. Verify `art/Sprites.tsx` has the reskin bypass code (the `if (reskinSource) { ... continue; }` block and the `createCanvasFromImage` helper). These were added in the v1 session — read the file to confirm they exist.

5. Rebuild Rosebud:
   ```bash
   pnpm vite build -c ./rosebud/vite.config.ts ./rosebud/
   ```

**Verify:**

- Build succeeds without errors
- `dist/rosebud/reskin/manifest.json` exists in the build output
- `dist/rosebud/reskin/cyberpunk/` has the 3 PNG files

---

### Task 3: Playtest — verify reskinned assets render in-game

**What to do:**

1. Start the preview server:

   ```bash
   pkill -f "vite.*preview" 2>/dev/null
   pnpm vite preview --host 0.0.0.0 --port 5173 -c ./rosebud/vite.config.ts ./rosebud/ &
   ```

2. Write a Playwright script that:
   - Navigates to `http://localhost:5173/`
   - Waits for the page to fully load
   - Clicks "Play" button
   - On the map selection screen, clicks "Start Game"
   - Waits 8 seconds for sprites to load
   - Takes a screenshot of the gameplay
   - Captures all console logs (look for `[Reskin] Loaded 3 sprite overrides`)
   - Captures any console errors

   The Playwright script must be a `.cjs` file (CommonJS), run with `NODE_PATH=/usr/local/share/npm-global/lib/node_modules node script.cjs`.

3. Use the visual-analysis skill (Gemini CLI) to analyze the gameplay screenshot:
   - Are buildings visually different from the standard game?
   - Are portraits visually different?
   - Any broken/missing sprites or error dialogs?
   - Is the game playable?

4. Check console output:
   - Must contain `[Reskin] Loaded 3 sprite overrides`
   - Must NOT contain palette-swap errors (like "Missing '#XXXXXX'")
   - Must NOT have any crash errors

**If the "Start Game" button is not clickable:** The map selection screen requires selecting a map first. Try clicking on a map name (e.g., text containing "Demo") before clicking "Start Game".

**If the game crashes with "FAILED TO LOAD":** The Sprites.tsx bypass isn't working. Check if the `createCanvasFromImage` function is defined and if the `continue` statement is reached for reskinned sprites. Debug by checking console errors.

**Verify:**

- Screenshot shows a game map with buildings visible
- Console shows `[Reskin] Loaded 3 sprite overrides`
- No palette-swap errors in console
- No "FAILED TO LOAD" error dialog

---

### Task 4: Commit all changes

**What to do:**

Commit the working state. The changes include:

- `art/Sprites.tsx` — reskin bypass (from v1, now verified working)
- `utils/reskin/discovery.py` — URL fix (already committed)
- `rosebud/public/reskin/` — reskinned assets + manifest (gitignore these? or include for PoC?)

For the PoC, include the reskinned assets in the commit so others can see the result.

**Verify:**

```bash
git status
git log --oneline -5
```
