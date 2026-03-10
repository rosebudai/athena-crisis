# Visual Judge — Athena Crisis

Use this rubric when Codex reviews screenshots for visual quality.

This is not a model-specific prompt and it is not a JSON contract. It is a shared review standard for human-readable Codex analysis.

## Purpose

Judge whether captured screenshots are visually consistent with Athena Crisis.

By default this supports two review modes:

1. `broad_audit`
   Use when no meaningful change-specific context is provided. Broad inconsistencies are valid findings.

2. `scoped_regression`
   Use when the reviewer is given:
   - `CHANGE UNDER TEST`,
   - `SCREENSHOTS UNDER REVIEW`,
   - `FOCUS REGIONS`,
   - and optionally `KNOWN BASELINE DEBT`.

   In this mode, only findings plausibly introduced by the change under test are blocking.

## Inputs

When using this rubric, provide Codex:

- one or more screenshots,
- optionally a short `CHANGE UNDER TEST` description,
- optionally `SCREENSHOTS UNDER REVIEW`,
- optionally `FOCUS REGIONS`,
- optionally `KNOWN BASELINE DEBT`.

## Evaluation Rubric

Apply the following checks in either mode.

1. `pixel_fidelity`
   Crisp pixel art at integer scale for tiles, units, buildings, and pixel-styled UI surfaces. Flag blur, anti-aliased vector intrusion into pixel surfaces, or obvious scaling artifacts.

2. `grid_alignment`
   Game content should sit cleanly on the 24px tile grid. Flag off-grid placement, fractional-looking positioning, or visual misalignment.

3. `palette_discipline`
   Colors should fit the established Athena Crisis palette and biome logic. Flag arbitrary hues or jarring mismatches that break cohesion.

4. `borders_surfaces`
   Panels and surfaces should match the game’s visual language. Pixel box-shadows, notched treatments, translucency, and blur are usually consistent; soft modern card treatments may be inconsistent unless clearly intentional.

5. `typography`
   Text should fit Athena’s established font and tactical UI feel. Flag obviously mismatched fonts, weights, or sizing.

6. `iconography`
   Icons should feel native to the game. Flag icon sets or render styles that look visually foreign.

7. `panel_treatment`
   Menus and overlays should maintain readable, coherent treatment. Flag low-contrast, opaque/heavy surfaces where translucency is expected, or inconsistent overlay styling.

8. `overall_cohesion`
   Does the screen feel visually coherent with Athena Crisis as a whole? Flag anything that feels stylistically off, too modern, too glossy, too flat, or otherwise inconsistent.

## Scoped Regression Checks

In `scoped_regression`, focus especially on the changed surface and nearby side effects:

1. `changed_feature_rendering`
   For tile or rendering work, focus on seams, edge treatment, mismatched transitions, corrupted sprites, missing assets, blur, and rendering artifacts.

2. `change_local_cohesion`
   Look for abrupt mismatches, broken palette transitions, clipping, layout shifts, or obvious rendering discontinuities near the changed region.

3. `unintended_visual_side_effects`
   Look for overlap, clipping, missing text, broken layering, or nearby UI damage introduced by the change.

## Classification Rules

Always classify observations into these buckets:

- `regressions`
  Screenshot-grounded issues likely introduced by the change under test. In scoped regression mode, only these are blocking.

- `pre_existing_issues`
  Visible issues that appear older, unrelated, or are explicitly called out in `KNOWN BASELINE DEBT`. These are non-blocking in scoped regression mode.

- `out_of_scope_observations`
  Real observations outside the requested verification target or focus regions. These are non-blocking in scoped regression mode.

## Output Guidance

Codex should return a concise human-readable verdict instead of JSON.

Recommended structure:

1. `Mode`
   State either `broad_audit` or `scoped_regression`.

2. `Verdict`
   State pass/fail in plain language.

3. `Blocking Findings`
   List only change-linked regressions when in scoped mode.

4. `Non-Blocking Notes`
   Include `pre_existing_issues` and `out_of_scope_observations` when relevant.

5. `Check Summary`
   Briefly summarize the most relevant rubric categories such as `pixel_fidelity`, `grid_alignment`, `palette_discipline`, and `overall_cohesion`.

## Failure Rules

- In `broad_audit`, meaningful visual inconsistencies can fail the review.
- In `scoped_regression`, only specific, screenshot-grounded regressions tied to the change under test should fail the review.
- Do not turn vague taste preferences into blocking findings.
- If causality is unclear in scoped mode, prefer a non-blocking note over a regression.
