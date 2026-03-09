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

After capturing screenshots, run both judges **in parallel**. Mechanics must output `"pass": true`. Visual supports two modes:

- default broad audit: catch general visual inconsistencies,
- optional scoped regression mode: narrow failures to the change under test.

### Visual Judge

By default this is a broad visual consistency audit. For change-specific verification, augment the prompt with `CHANGE UNDER TEST`, `SCREENSHOTS UNDER REVIEW`, `FOCUS REGIONS`, and `KNOWN BASELINE DEBT` to switch it into a scoped regression check.

```bash
mkdir -p /tmp/gemini-judge-visual
cp /tmp/step3.png /tmp/gemini-judge-visual/
gemini -p "$(cat .claude/judges/visual-judge.md)

CHANGE UNDER TEST:
[paste 1-3 sentences describing the exact feature or cleanup being verified]

SCREENSHOTS UNDER REVIEW:
- step3.png

FOCUS REGIONS:
- [paste the changed surfaces to inspect]

KNOWN BASELINE DEBT:
- [optional: list visible pre-existing issues that should not fail this run]" \
  -m gemini-3.1-pro-preview \
  --include-directories /tmp/gemini-judge-visual \
  --yolo --output-format text 2>/dev/null \
  > /tmp/verdict-visual.raw

node .agents/scripts/parse-gemini-verdict.mjs /tmp/verdict-visual.raw \
  > /tmp/verdict-visual.json
```

Visual pass/fail semantics:

- Broad audit mode: broad visual inconsistencies are valid failures.
- Scoped regression mode: blocking items are entries in `regressions` and `failures` that are specific, screenshot-grounded, and plausibly introduced by the change under test.
- In scoped regression mode, `pre_existing_issues` and `out_of_scope_observations` are non-blocking.
- If causality is unclear in scoped regression mode, treat the observation as non-blocking.

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
  > /tmp/verdict-mechanics.raw

node .agents/scripts/parse-gemini-verdict.mjs /tmp/verdict-mechanics.raw \
  > /tmp/verdict-mechanics.json
```

### Reading Verdicts

Gemini output is not assumed to be clean JSON. Always normalize the raw output through the parser first, then inspect the parsed verdicts:

```bash
# Check pass/fail programmatically
cat /tmp/verdict-visual.json | python3 -c "import sys,json; v=json.load(sys.stdin); print('VISUAL:', 'PASS' if v['pass'] else 'FAIL'); [print(f'  - {f}') for f in v.get('failures',[])]"
cat /tmp/verdict-mechanics.json | python3 -c "import sys,json; v=json.load(sys.stdin); print('MECHANICS:', 'PASS' if v['pass'] else 'FAIL'); [print(f'  - {f}') for f in v.get('failures',[])]"
```

Mechanics must pass. Interpret the visual result according to the chosen mode. In scoped regression mode, a run passes when no change-introduced regressions are found even if broader inconsistencies are recorded as non-blocking notes.

## Kill Server

```bash
pkill -f "vite preview" 2>/dev/null || true
```
