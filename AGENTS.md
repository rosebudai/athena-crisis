# Athena Crisis Repo Instructions

## Verification

Project-specific verification instructions live in [`.agents/verification.md`](/workspace/athena-crisis/.agents/verification.md).

When a workflow or skill asks for repo-local verification guidance, use that file first.

## Shared Agent Assets

- Shared repo-local skills live in [`.agents/skills`](/workspace/athena-crisis/.agents/skills).
- Shared repo-local judges live in [`.agents/judges`](/workspace/athena-crisis/.agents/judges).
- `.claude/skills` and `.claude/verification.md` are symlinked to the shared `.agents` copies so Claude and Codex use the same local assets.
