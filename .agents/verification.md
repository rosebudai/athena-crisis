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

After capturing screenshots, run both judges. Mechanics and visual review are
both human-readable Codex analyses.

Visual supports two modes:

- default broad audit: catch general visual inconsistencies,
- optional scoped regression mode: narrow failures to the change under test.

### Visual Judge

Use Codex directly to review the captured screenshots against [`.agents/judges/visual-judge.md`](/workspace/athena-crisis/.agents/judges/visual-judge.md).

By default this is a broad visual consistency audit. For change-specific verification, provide Codex with `CHANGE UNDER TEST`, `SCREENSHOTS UNDER REVIEW`, `FOCUS REGIONS`, and `KNOWN BASELINE DEBT` to switch it into a scoped regression check.

```bash
# Prepare the screenshots you want Codex to review.
cp /tmp/step3.png /workspace/artifacts/step3.png

# Then ask Codex to inspect the screenshots using:
# - .agents/judges/visual-judge.md
# - CHANGE UNDER TEST
# - SCREENSHOTS UNDER REVIEW
# - FOCUS REGIONS
# - KNOWN BASELINE DEBT (optional)
```

Visual pass/fail semantics:

- Broad audit mode: broad visual inconsistencies are valid failures.
- Scoped regression mode: blocking items are the specific regressions Codex identifies as screenshot-grounded and plausibly introduced by the change under test.
- In scoped regression mode, `pre_existing_issues` and `out_of_scope_observations` are non-blocking.
- If causality is unclear in scoped regression mode, treat the observation as non-blocking.

### Mechanics Judge

Evaluates screenshot sequences against the QA Plan for state correctness, transitions, and data accuracy.

```bash
# Prepare the screenshots you want Codex to review.
cp /tmp/step*.png /workspace/artifacts/

# Then ask Codex to inspect the screenshots using:
# - .agents/judges/mechanics-judge.md
# - QA PLAN STEPS
# - SCREENSHOTS UNDER REVIEW
# - CHANGE UNDER TEST (optional)
```

### Reading Verdicts

Mechanics review should be read directly from Codex's human-readable output.
Visual review should also be read directly.

Mechanics must pass. Interpret the visual result according to the chosen mode
described in `.agents/judges/visual-judge.md`. In scoped regression mode, a run
passes when Codex finds no change-introduced regressions even if broader
inconsistencies are recorded as non-blocking notes.

## Kill Server

```bash
pkill -f "vite preview" 2>/dev/null || true
```
