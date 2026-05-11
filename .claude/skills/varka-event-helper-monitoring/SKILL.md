---
name: varka-event-helper-monitoring
description: Implements ONLY Issue 4 (Gate 5). Builds CLIs to detect event-map entry, safely toggle the helper Play→Pause (never the reverse), parse the timer, raise the <30 s critical alert, and detect the finish dialog or automatic return.
---

# varka-event-helper-monitoring

## Scope
Event-map detection, helper toggle, timer monitoring, finish detection. No multi-character scheduling.

## Required docs to read
- `docs/varka-flow/05-issue-4-event-map-helper-monitoring.md`
- `docs/vision/04-timer-recognition.md`
- `docs/varka-flow/10-varka-error-and-retry-policy.md`
- `docs/automation/05-safe-clicking-rules.md`
- The capability matrix from Gate 2.

## Allowed outputs
- `src/<package>/vision/event_map.py` — multi-signal `EVENT_MAP_READY` (Varka label + timer panel + popups absent + screen stable).
- `src/<package>/vision/helper.py` — Play / Pause icon detection; **never returns "click" if state is Pause**.
- `src/<package>/vision/timer.py` — parses mode (Standby / Time Left / Exit Waiting Time) and `MM:SS(N)` digits via templates (preferred) or OCR.
- `src/<package>/vision/finish.py` — finish dialog detection.
- `src/<package>/automation/helper_toggle.py` — toggles only when icon = Play.
- A throttled critical-alert emitter for "time < 30 s and monsters > 0" (no sound, terminal only, max ~one per few seconds).
- CLI: `python -m <app> test-event-helper --char <name> [--mode foreground|background] [--no-toggle] [--watch <seconds>]`.

## Forbidden outputs
- Clicking the helper when it is already running (Pause icon visible).
- Producing audio alerts or system notifications. Terminal output only.
- Controlling combat or movement.
- Implementing orchestrator-level retry-later — that belongs to the state-machine agent.
- Hard-coded ROI rectangles or thresholds; load from config.

## Required verification command
```
python -m <app> test-event-helper --char <name> --no-toggle --watch 30
python -m <app> test-event-helper --char <name> --watch 60
```
Expected output:
- `--no-toggle`: prints `EVENT_MAP_READY=true|false`, helper state (Play / Pause / Unknown), parsed timer mode + value + monster count, finish dialog state. Watches for `--watch` seconds and prints a sample line each second. Critical alert is logged when condition met. No clicks.
- Without `--no-toggle`: same, plus performs the helper toggle ONLY if Play is detected; verifies the icon flipped to Pause within timeout.

## Stop condition
After the user confirms the helper is started exactly once, the timer parses correctly, the critical alert fires only when expected, and finish detection works (or auto-return is recognised), STOP.
