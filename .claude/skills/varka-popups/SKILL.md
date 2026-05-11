---
name: varka-popups
description: Implements ONLY Issue 3 (Gate 4). Builds a CLI to detect Popup 1 ("Fortress of the Imperial Guard"), click "Enter Varka", detect Popup 2, click "Enter", and recognise the daily-limit dialog. No event-map logic.
---

# varka-popups

## Scope
Popup 1 + Popup 2 + daily-limit dialog detection and clicks. Stops when the event-map transition begins.

## Required docs to read
- `docs/varka-flow/04-issue-3-npc-popups.md`
- `docs/varka-flow/10-varka-error-and-retry-policy.md`
- `docs/vision/02-roi-and-template-guidelines.md`
- `docs/automation/05-safe-clicking-rules.md`
- The capability matrix from Gate 2.

## Allowed outputs
- `src/<package>/vision/popups.py` — ROI-based detection of Popup 1 title, Popup 2 anchor, daily-limit dialog.
- `src/<package>/automation/popup_click.py` — clicks the verified button centre (or anchor-based offset). Verifies the click by checking that the source dialog closed.
- Daily-limit handling: returns a `DONE_BY_GAME_LIMIT` sentinel — **does not** itself mutate orchestrator state. The orchestrator owns terminal status.
- CLI: `python -m <app> test-varka-popups --char <name> [--mode foreground|background] [--no-click]`.

## Forbidden outputs
- Implementing event-map detection or helper toggling.
- Clicking "Leave Varka" or "Close" in Popup 1 — those are context-only.
- Reading or clicking the Monster Element / Varka Level fields in Popup 2.
- Blocking polls; use the timeouts and retry counts from `docs/varka-flow/10-varka-error-and-retry-policy.md`.

## Required verification command
```
python -m <app> test-varka-popups --char <name> --no-click
python -m <app> test-varka-popups --char <name>
```
Expected output:
- `--no-click`: prints which dialogs are detected, the resolved button click points, and confidence; saves debug overlays. No clicks.
- Without `--no-click`: prerequisite is Popup 1 already open (run `test-lobby-npc` first). Reports each click result, retry counts, and whether the event-map transition began. If daily-limit dialog appears, prints `DONE_BY_GAME_LIMIT` and stops.

## Stop condition
After the user confirms both popups are clicked correctly and the daily-limit dialog is recognised without false positives, STOP.
