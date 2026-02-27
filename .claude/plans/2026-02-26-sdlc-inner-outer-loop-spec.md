# Subagent-Driven Development: Inner/Outer Loop Redesign

**Goal:** Redesign the subagent-driven-development skill to use an inner/outer loop model based on SDLC best practices.

## Design

### Inner Loop (Per Task)

1. Implement (subagent) — write code, run tests, self-verify, commit
2. Spec Review (subagent/codex) — verify code matches task spec, loop on failure (max 3)

### Outer Loop (After All Tasks)

1. VALIDATE: Functional review against all acceptance criteria (playwright for visual)
2. POLISH: Code review of full diff
3. POLISH: Refactor based on review findings
4. RE-VERIFY: Full test suite + functional re-check
5. HARDEN: Write critical tests for untested paths/edge cases
6. GATE: Lint, type checks, full test suite
7. SHIP: finishing-a-development-branch

Outer loop restarts from ① on any failure, max 3 iterations. Escalate to user if unresolved.

## Acceptance Criteria

### Must Have

- [ ] Inner loop: implement → test → spec review → commit (retry on spec failure)
- [ ] Outer loop: validate → polish → re-verify → harden → gate → ship
- [ ] Functional review uses playwright for visual work, follows .claude/verification.md
- [ ] Code review sees full implementation diff
- [ ] Refactoring triggers re-verification
- [ ] Critical tests written as distinct hardening step
- [ ] Quality gate is final automated check
- [ ] Outer loop restarts from ① on failure, max 3 iterations
- [ ] Escalation after 3 failed iterations
- [ ] Fully autonomous — no human interaction

### Out of Scope

- Changing brainstorming or writing-plans skills
- Modifying implementer/spec-reviewer subagent prompts
