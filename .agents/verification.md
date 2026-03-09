# Verification: Athena Crisis (Rosebud)

Project-level testing context. Consumed by the outer loop's ① VALIDATE step alongside the feature-specific QA Plan in the approved spec, typically `.specs/<feature>.md`.

## Serve

```bash
pnpm build:rosebud && pnpm --filter @deities/rosebud preview --host 0.0.0.0 --port 4173
```

Wait for "Local: http://localhost:4173/" before proceeding.

## Capture: Evaluator Phase

Use `playwright-playtesting` to navigate and capture screenshots. This is the **evaluator** — it collects evidence, it does not judge.

### Project Smoke Test

Minimum screenshots for any change (run before feature-specific QA Plan):

1. **Title screen** — navigate to `http://localhost:4173/`, screenshot after load → `/tmp/step1.png`
2. **Level select** — click "Play", screenshot the map selection screen → `/tmp/step2.png`
3. **In-game** — select a map, start a game, screenshot the game map with units visible → `/tmp/step3.png`

### Config override verification (when applicable)

If testing config changes (unit stats, damage tables, tiles, buildings, game config):

4. **Build menu** — start a game on a map with a Factory, click the Factory, screenshot the build menu showing unit costs → `/tmp/step4.png`
5. **Compare** — verify overridden values (e.g., modified unit cost) appear correctly vs. defaults → `/tmp/step5.png`

### Console Check

Capture browser console output during the smoke test. Look for:

- `[ConfigLoader]` messages — confirms configs were loaded/applied
- No JavaScript errors or unhandled promise rejections

## Judge: Analysis Phase

After capturing screenshots, run both judges **in parallel**. Both must output `"pass": true`.

### Visual Judge

Evaluates screenshots against the game's pixel-art aesthetic rubric. Run on each screenshot showing new or modified UI elements.

```bash
mkdir -p /tmp/gemini-judge-visual
cp /tmp/step*.png /tmp/gemini-judge-visual/
gemini -p "$(cat .claude/judges/visual-judge.md)" \
  -m gemini-3.1-pro-preview \
  --include-directories /tmp/gemini-judge-visual \
  --yolo --output-format text 2>/dev/null \
  > /tmp/verdict-visual.json
```

### Mechanics Judge

Evaluates screenshot sequences against the QA Plan for state correctness, transitions, and data accuracy.

```bash
mkdir -p /tmp/gemini-judge-mechanics
cp /tmp/step*.png /tmp/gemini-judge-mechanics/
gemini -p "$(cat .claude/judges/mechanics-judge.md)

QA PLAN STEPS:
[paste QA Plan steps from the approved spec here, mapping each to stepN.png]" \
  -m gemini-3.1-pro-preview \
  --include-directories /tmp/gemini-judge-mechanics \
  --yolo --output-format text 2>/dev/null \
  > /tmp/verdict-mechanics.json
```

### Reading Verdicts

Both judges output JSON. Parse and check:

```bash
# Check pass/fail programmatically
cat /tmp/verdict-visual.json | python3 -c "import sys,json; v=json.load(sys.stdin); print('VISUAL:', 'PASS' if v['pass'] else 'FAIL'); [print(f'  - {f}') for f in v.get('failures',[])]"
cat /tmp/verdict-mechanics.json | python3 -c "import sys,json; v=json.load(sys.stdin); print('MECHANICS:', 'PASS' if v['pass'] else 'FAIL'); [print(f'  - {f}') for f in v.get('failures',[])]"
```

Both must pass. If either fails, the `failures` array contains specific issues to fix.

## Kill Server

```bash
pkill -f "vite preview" 2>/dev/null || true
```
