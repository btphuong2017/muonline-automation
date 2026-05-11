---
name: varka-enter-lobby
description: Implements ONLY Issue 5 (Gate 6). Builds a CLI that, when the character is outside the lobby, opens the Event Window (Ctrl+T), selects Imperial Guardian, clicks Enter, and waits for lobby load with crash/disconnect handling.
---

# varka-enter-lobby

## Scope
Outside-lobby → lobby flow only. Preconditions: character is not in lobby and not in event map and no popups open. Stops once `LOBBY_READY` is confirmed.

## Required docs to read
- `docs/varka-flow/06-issue-5-enter-lobby-flow.md`
- `docs/varka-flow/03-issue-2-lobby-and-npc-click.md` (for the lobby-ready signal reuse)
- `docs/varka-flow/10-varka-error-and-retry-policy.md`
- `docs/automation/05-safe-clicking-rules.md`
- The capability matrix from Gate 2.

## Allowed outputs
- `src/<package>/vision/event_window.py` — detects Events Info header, Imperial Guardian list entry, Enter button (enabled / disabled).
- `src/<package>/automation/event_window.py` — sends Ctrl+T (foreground if matrix says background hotkey FAIL), scrolls the list if needed, clicks the Imperial Guardian entry and the Enter button.
- A loading-screen waiter using the existing lobby-ready multi-signal detection with a generous timeout (15–20 s, sourced from config).
- Crash detection: if the game window vanishes or capture fails repeatedly → return `NEED_USER_LOGIN` sentinel.
- Disabled-Enter handling: return `EVENT_ENTER_NOT_AVAILABLE` sentinel.
- CLI: `python -m <app> test-enter-lobby --char <name> [--mode foreground|background] [--dry-run]`.

## Forbidden outputs
- Calling NPC click, popup handling, or helper toggling.
- Restarting the game or attempting to re-authenticate.
- Persisting state across sessions.
- Persisting Ctrl+T retries beyond the configured limit (default 3).

## Required verification command
```
python -m <app> test-enter-lobby --char <name> --dry-run
python -m <app> test-enter-lobby --char <name>
```
Expected output:
- `--dry-run`: prints location detection (`outside_lobby=true|false`), what the next action would be, and the Event Window detection without sending input.
- Without `--dry-run`: opens the Event Window, selects Imperial Guardian, clicks Enter, polls until `LOBBY_READY=true` or timeout. Reports each step, retry count, and final status (`LOBBY_READY`, `EVENT_ENTER_NOT_AVAILABLE`, `IMPERIAL_GUARDIAN_NOT_FOUND`, `NEED_USER_LOGIN`, or timeout).

## Stop condition
After the user confirms the character reaches the lobby and crash handling is correct (e.g. closing the client raises `NEED_USER_LOGIN` cleanly), STOP.
