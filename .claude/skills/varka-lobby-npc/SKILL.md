---
name: varka-lobby-npc
description: Implements ONLY Issue 2 (Gate 3). Builds a CLI to test lobby detection, NPC candidate detection, hover indicator verification, and ALT + left-click. Stops at the moment the first popup is opened — popup handling belongs to varka-popups.
---

# varka-lobby-npc

## Scope
Lobby detection + NPC interaction up to (and including) the ALT-click that opens Popup 1. No popup handling here.

## Required docs to read
- `docs/varka-flow/03-issue-2-lobby-and-npc-click.md`
- `docs/vision/05-hover-indicator-and-npc-detection.md`
- `docs/vision/02-roi-and-template-guidelines.md`
- `docs/automation/05-safe-clicking-rules.md`
- `docs/automation/04-background-vs-foreground-strategy.md`
- The capability matrix from Gate 2.

## Allowed outputs
- `src/<package>/vision/lobby.py` — multi-signal lobby detection (map label + timer panel absence + finish dialog absence + screen stability).
- `src/<package>/vision/npc.py` — candidate generation (cache → partial templates → grid search), hover indicator verification.
- `src/<package>/automation/npc_click.py` — `alt_left_click(window, point)` that respects the capability matrix (foreground if background NPC click is FAIL).
- A per-character candidate cache stored in memory only (no disk persistence).
- CLI: `python -m <app> test-lobby-npc --char <name> [--mode foreground|background] [--no-click]`.

## Forbidden outputs
- Clicking popup buttons.
- Modifying the helper.
- Sending input without first verifying hover indicator (rule 3 of `docs/agents/01-agent-implementation-rules.md`).
- Hard-coded ROIs or thresholds — load from config.
- Wandering the character or sending movement commands.

## Required verification command
```
python -m <app> test-lobby-npc --char <name> --no-click
python -m <app> test-lobby-npc --char <name>
```
Expected output:
- `--no-click`: prints `LOBBY_READY=true|false`, lists candidate points with confidence, prints whether hover indicator was detected at each, saves a debug overlay to `.claude/logs/lobby_npc_<char>.png`. No click is sent.
- Without `--no-click`: same, then performs the verified ALT-click and reports whether Popup 1 became visible within timeout.

## Stop condition
After the user confirms lobby detection works and the NPC dialog opens reliably, STOP. Popup handling is the next gate.
