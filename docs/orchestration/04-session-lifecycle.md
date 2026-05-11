# Session Lifecycle

This document describes the lifecycle of a Varka automation session.  A session begins when the user starts the bot and ends when all characters have completed their runs or a global interruption (such as a login failure) occurs.  The orchestrator coordinates the following phases:

## 1. Initialization

At the start of a session, the bot:

- Loads configuration files for characters and templates.
- Enumerates game windows and matches them to configured characters using the window discovery routine (Issue 1).
- Instantiates runtime state for each enabled character, including current state, run count, retry counters and timestamps.
- Initializes capture and input backends (foreground, background or hybrid) according to the capability matrix.
- Creates a terminal status dashboard and logger for the session.

If discovery fails for any character, that character is marked as `missing_window` and skipped.  If no windows are found, the session stops with an error.

## 2. Main Loop

The orchestrator runs a cooperative scheduler loop (see `02-character-loop-strategy.md`) that interleaves states across characters.  Each tick of the loop:

1. **Selects the next character**: Characters are ordered such that those with pending active states are processed before those waiting or done.  Characters marked for retry‐later are skipped until their cooldown expires.
2. **Processes one state step**: The scheduler calls the Varka state machine to execute a small unit of work for the selected character.  This may involve checking the current map, interacting with the NPC or monitoring the timer.  Each state has its own retry counter; if it fails three times, the character is moved to the retry‑later queue or marked as skipped.
3. **Updates runtime state**: After the step completes, the character’s state, run count, retry counters and timestamps are updated.  The terminal dashboard is refreshed and events are logged.
4. **Checks global interrupts**: Between steps, the scheduler checks for fatal conditions such as window loss or NEED_USER_LOGIN.  If such a condition is detected, the session terminates and the user is alerted.

The loop continues until all characters have been marked as `DONE_MAX_RUNS` or `DONE_BY_GAME_LIMIT`, or a fatal interruption stops the session.

## 3. Completion

When a character completes a run successfully, its `completed_count` is incremented.  If the count reaches 10 or the game displays a daily limit dialog, the character is marked `DONE_MAX_RUNS` or `DONE_BY_GAME_LIMIT`.  A summary entry is logged.

If a character returns to the lobby without a cleared popup, it still counts as one success (Issue 6).  The orchestrator ensures that helper and timer monitoring have finished before marking success.

## 4. Termination

The session ends when:

- All characters are done; or
- A fatal error occurs (e.g. user needs to log in again, game windows lost); or
- The user stops the bot manually.

On termination, the bot:

- Writes a final summary to the log, including per‑character run counts and errors.
- Closes any open captures or input handles.
- Restores the user’s environment if needed (e.g. bringing the original window to the foreground).

This session lifecycle ensures consistent startup, cooperative execution and safe shutdown.  It ties together the lower‑level behaviours defined in the other Varka flow documents.