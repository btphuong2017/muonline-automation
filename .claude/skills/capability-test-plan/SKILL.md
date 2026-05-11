---
name: capability-test-plan
description: Implements ONLY Issue 7 — the capability test harness. Builds a CLI that runs the 18 tests across foreground / background / minimised modes and emits a capability matrix JSON plus a human summary. Does NOT implement any Varka flow logic.
---

# capability-test-plan

## Scope
Just the test harness for Issue 7. Each test targets ONE capability. No combined Varka flow. No NPC interaction beyond the dedicated tests. No real game-side commands the user has not approved.

## Required docs to read
- `docs/varka-flow/08-issue-7-execution-capability-test-plan.md`
- `docs/testing/02-capability-test-checklist.md`
- `docs/automation/02-capture-backends.md`
- `docs/automation/03-input-backends.md`
- `docs/automation/04-background-vs-foreground-strategy.md`
- `docs/03-system-boundaries.md`

## Allowed outputs
- A new module `src/<package>/capability/` with one function per test (T1–T18).
- A CLI: `python -m <app> capability-test [--test N] [--mode foreground|background|minimized] [--char <name>]`.
- Output files in `.claude/logs/capability/`:
  - `capability_matrix.json` (machine-readable, one row per capability × mode).
  - `capability_summary.md` (human-readable table with PASS / PARTIAL / FAIL + notes).
  - Optional debug screenshots, only with explicit user approval.
- A short report listing which tests are wired up vs deferred.

## Forbidden outputs
- Any code that implements lobby detection, NPC click, popup handling, helper toggle, or timer parsing as part of the actual Varka flow. Capability tests may *exercise* those primitives in isolation but must not chain them into a run.
- Running tests that send `ALT + click` to NPCs without explicit user "go" — those have side effects (consume an attempt).
- Storing screenshots that contain account names without user approval.

## Required verification command
```
python -m <app> capability-test --test 1
python -m <app> capability-test
```
Expected output:
- `--test 1` prints discovered windows (hwnd, pid, parsed name, rect, visible/minimised) for each game client.
- Full run produces `capability_matrix.json` and `capability_summary.md` in `.claude/logs/capability/` and prints the summary table.

## Stop condition
After the harness is wired up and `--test 1` has been demonstrated by the user, STOP. Ask the user which subsequent tests are safe to run on their account before executing any test that sends real input.
