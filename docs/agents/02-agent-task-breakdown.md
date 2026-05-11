# Agent Task Breakdown

This document breaks down the implementation tasks for agents into discrete, manageable units.  Each task corresponds to one of the issues described in the Varka flow documentation.

## Issue 1 – Window Discovery

- Enumerate all top‑level windows on the system using the Win32 API.
- Filter windows by the game title prefix.
- Parse character name, level, master level and resets from the window title.
- Create `GameWindowInfo` objects and match them to configured characters.
- Expose a `scan-windows` command that prints the discovery results and writes a JSON file for debugging.

## Issue 2 – Lobby Detection and NPC Click

- Implement lobby detection using multi‑signal confirmation: lobby label template, absence of event timer and finish dialog, and screen stability.
- Create candidate search routines for the NPC: load last successful points, run partial template matching and grid search.
- Implement hover indicator detection by holding ALT and capturing the indicator region.
- Send ALT + left click when a candidate passes hover verification.
- Verify that the NPC dialog opens and handle retries.

## Issue 3 – NPC Popups

- Detect the NPC dialog (popup 1) and locate the “Enter Varka” button using ROI and templates.
- Click the button and wait for the second popup.
- Detect the second popup and click the “Enter” button.
- Handle daily limit dialogs by recognising the specific template, clicking OK and marking the character as done.
- Implement anchor‑based clicking offsets as a fallback if button templates fail.

## Issue 4 – Event Map and Helper Monitoring

- Detect that the character has entered the event map using map labels and timer panel signals.
- Wait briefly for UI render before interacting with the helper.
- Detect the helper’s play/pause icon; click only when in the OFF/Play state.
- Verify that the helper is running and do not click again when in the ON/Pause state.
- Monitor the timer mode and parse countdown and monster counts.  Trigger terminal alerts when time < 30 seconds and monsters remain.
- Detect event completion via finish dialogs or map transitions back to the lobby and click Exit where necessary.

## Issue 5 – Enter Lobby Flow

- Detect characters outside the lobby or event map.
- Send Ctrl + T to open the event window (foreground or background based on capability matrix).
- Detect the event window and select the “Imperial Guardian” entry.
- Click the Enter button and wait for the lobby to load, handling retries.
- Detect crashes or disconnections during the transition and report NEED_USER_LOGIN.

## Issue 6 – Varka Orchestrator

- Create runtime data structures for characters (state, run counts, retries, timestamps).
- Implement a cooperative scheduler that interleaves states across characters, according to the character loop strategy.
- Use a priority queue or rotating index to schedule active characters and skip or delay those waiting.
- Enforce max runs (10) and detect daily limit dialogs to mark characters as done.
- Handle retry counts per state; when exceeding 3, move the character to a retry‑later state with cooldown or mark as skipped.
- Update the terminal dashboard and logs after each state change.
- Detect global interrupts (e.g. window loss) and stop the session when needed.

## Issue 7 – Execution Capability Tests

- Build a test harness to perform the capability tests listed in `02-capability-test-checklist.md`.
- Implement tests for capture, input, hover and UI interactions in foreground, background and minimised modes.
- Collect evidence (screenshots, logs) and produce a capability matrix that maps each capability to pass/partial/fail status.
- Use the matrix to set flags in the configuration for the automation modules.

## Additional Tasks

- Write unit tests and integration tests for the vision and state machine functions.
- Create a logging system that writes structured logs per character and per session.
- Develop the terminal status dashboard according to the specification in `03-terminal-status-dashboard.md`.
- Document all configurations, templates and ROI definitions for future maintenance.