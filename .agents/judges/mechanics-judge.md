# Mechanics Judge — Athena Crisis

Use this rubric when Codex reviews screenshot sequences for gameplay
correctness against a QA Plan.

This is not a model-specific prompt and it is not a JSON contract. It is a
shared review standard for human-readable Codex analysis.

## Purpose

Judge whether an ordered screenshot sequence demonstrates correct game
behavior for Athena Crisis.

This judge is about mechanics and state correctness, not visual polish.

## Inputs

When using this rubric, provide Codex:

- the ordered screenshots, typically `step1.png`, `step2.png`, ...
- the `QA PLAN STEPS` that say what each screenshot should show
- optionally `CHANGE UNDER TEST`
- optionally `KNOWN BASELINE DEBT` if a screen is expected to contain
  unrelated issues

## Evaluation Rubric

Apply the following checks:

1. `state_correctness`
   Does each screenshot match the expected state described in the QA Plan?
   Cite the specific UI, values, or game state visible in the screenshot.

2. `transition_correctness`
   Do the screenshots show the expected transition from one step to the next?
   If a step says "click Play", does the next screenshot actually show the
   level select screen?

3. `data_accuracy`
   If the QA Plan calls out expected values, confirm those values directly from
   the screenshots. Examples: unit cost, health, selected tile info, menu
   labels, or map state.

4. `error_states`
   Check each screenshot for obvious failure cases:
   - blank or white screens
   - error messages or stack traces
   - missing UI regions
   - obviously broken layout or clipping
   - loading states that should have resolved

5. `completeness`
   Do the provided screenshots cover all QA Plan steps in order?

## Classification Rules

Always classify observations into these buckets:

- `mechanics_failures`
  Screenshot-grounded issues that show the QA Plan did not complete correctly.

- `mechanics_passes`
  Steps or transitions that are clearly satisfied by the screenshots.

- `non_blocking_notes`
  Real observations that do not invalidate the QA Plan step being judged.

## Output Guidance

Codex should return a concise human-readable verdict instead of JSON.

Recommended structure:

1. `Mode`
   State `mechanics_review`.

2. `Verdict`
   State pass/fail in plain language.

3. `Blocking Findings`
   List the specific mechanics failures, if any.

4. `Confirmed Steps`
   List the steps or transitions clearly supported by the screenshots.

5. `Non-Blocking Notes`
   Include ambiguity, baseline debt, or out-of-scope observations when useful.

## Failure Rules

- Fail if any QA Plan step is not demonstrated by the screenshots.
- Fail if the expected transition between steps is not visible.
- Fail if the screenshots are incomplete for the QA Plan.
- Do not fail on vague suspicions; findings must be screenshot-grounded.
