---
name: varka-orchestrator
description: Implements ONLY Issue 6 (Gate 7). Builds a cooperative scheduler over up to 5 characters with a dry-run / smoke-test mode and a terminal status dashboard. Wires together the gates 1–6 components without changing them.
---

# varka-orchestrator

## Scope
Cooperative scheduling, retry/cooldown, run-limit accounting, terminal dashboard, dry-run mode. Reuses already-verified components from gates 1–6.

## Required docs to read
- `docs/varka-flow/07-issue-6-varka-orchestrator.md`
- `docs/varka-flow/09-varka-state-reference.md`
- `docs/varka-flow/10-varka-error-and-retry-policy.md`
- `docs/orchestration/01-cooperative-scheduler.md`
- `docs/orchestration/02-character-loop-strategy.md`
- `docs/orchestration/03-terminal-status-dashboard.md`
- `docs/orchestration/04-session-lifecycle.md`

## Allowed outputs
- `src/<package>/orchestrator/runtime.py` — `CharacterRuntime` with fields: `current_state`, `completed_count`, `retry_count`, `status`, `next_check_at`, `last_error`.
- `src/<package>/orchestrator/scheduler.py` — round-robin tick loop. One step per character per tick.
- `src/<package>/orchestrator/dashboard.py` — terminal status table refreshed at a sensible cadence.
- A `--dry-run` mode that exercises scheduling and transitions using stubbed action results (no real input to the game). Useful without live windows.
- A `--smoke` mode that runs against live windows but caps after a single successful tick per character.
- Global interrupt handling: `NEED_USER_LOGIN`, user stop, fatal capture failure all halt the loop cleanly.
- CLI: `python -m <app> start-varka [--dry-run | --smoke] [--config <path>]`.

## Forbidden outputs
- Modifying any state-machine step implementation from earlier gates.
- Adding new terminal statuses beyond those in `docs/varka-flow/07-issue-6-varka-orchestrator.md`.
- True multi-threading or asyncio for state actions in the MVP — cooperative only.
- Continuing to process other characters after `NEED_USER_LOGIN`.
- Persisting state to disk between sessions.

## Required verification command
```
python -m <app> start-varka --dry-run
python -m <app> start-varka --smoke
```
Expected output:
- `--dry-run`: prints the dashboard refreshing as each character advances through stubbed states; demonstrates retry-then-cooldown and `DONE_BY_GAME_LIMIT` and `DONE_MAX_RUNS` paths via injected stub results. No real input sent.
- `--smoke`: runs against real windows but stops after one successful tick per character so the user can sanity-check fairness and dashboard accuracy without spending entries.

## Stop condition
After the user confirms the dashboard is readable, fairness is acceptable, retries cool down correctly, and no character continues after `NEED_USER_LOGIN`, STOP. Do **not** start a real full automation run without explicit user approval.
