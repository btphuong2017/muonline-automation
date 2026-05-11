---
name: docs-review
description: Use BEFORE any implementation task. Reads the relevant docs, summarises verified facts, lists assumptions, surfaces risks, and asks only the questions that the docs cannot answer. Stops without writing code.
---

# docs-review

## Scope
Read-only doc reconnaissance for one task. Output: a short briefing the user can sanity-check in under a minute.

## Required docs to read (always)
- `docs/00-overview.md`
- `docs/01-requirements.md`
- `docs/03-system-boundaries.md`
- `docs/agents/01-agent-implementation-rules.md`

## Required docs to read (per task type)
| Task type | Add these |
|---|---|
| Window discovery (Issue 1) | `docs/varka-flow/02-issue-1-window-discovery.md`, `docs/automation/01-window-management.md` |
| Capability test (Issue 7) | `docs/varka-flow/08-issue-7-execution-capability-test-plan.md`, `docs/testing/02-capability-test-checklist.md`, `docs/automation/02-capture-backends.md`, `docs/automation/03-input-backends.md`, `docs/automation/04-background-vs-foreground-strategy.md` |
| Lobby + NPC (Issue 2) | `docs/varka-flow/03-issue-2-lobby-and-npc-click.md`, `docs/vision/05-hover-indicator-and-npc-detection.md` |
| Popups (Issue 3) | `docs/varka-flow/04-issue-3-npc-popups.md` |
| Event map + helper (Issue 4) | `docs/varka-flow/05-issue-4-event-map-helper-monitoring.md`, `docs/vision/04-timer-recognition.md` |
| Enter lobby (Issue 5) | `docs/varka-flow/06-issue-5-enter-lobby-flow.md` |
| Orchestrator (Issue 6) | `docs/varka-flow/07-issue-6-varka-orchestrator.md`, `docs/varka-flow/09-varka-state-reference.md`, `docs/varka-flow/10-varka-error-and-retry-policy.md`, `docs/orchestration/01-cooperative-scheduler.md` |

## Allowed outputs
A single Markdown briefing with:
1. **Task** — one sentence.
2. **Verified facts** — bullets, each with `docs/...` reference.
3. **Assumptions** — bullets marked `confirmed` / `assumed` / `needs user confirmation`.
4. **Risks / unknowns** — 2–5 bullets.
5. **Open questions for the user** — only those that the docs cannot answer.
6. **Suggested next skill** — name of one of the implementation skills.

## Forbidden outputs
- Writing or editing any file outside `.claude/workflow/open-questions.md` (and only to add a new question).
- Implementing code or running game-side commands.
- Inventing UI behaviour, ROIs, hotkeys, thresholds, or template names not present in `docs/`.

## Required verification command
None — this skill is pre-implementation reconnaissance. Output is the verification.

## Stop condition
Stop after delivering the briefing. Wait for the user to confirm scope before invoking an implementation skill.
