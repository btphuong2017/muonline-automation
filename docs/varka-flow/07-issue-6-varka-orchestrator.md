## Issue 6 — Varka Orchestrator and Multi‑Character Scheduling

Having defined how to perform each step of the Varka run for a single character, the next challenge is to coordinate up to five characters concurrently.  Rather than running one character to completion before starting the next, the bot should interleave steps so that idle time in one character is used to advance others.  This file describes the design of the Varka orchestrator.

### Objectives

1. **Round‑robin scheduling:**  At the user’s request, the bot must run all selected characters in a cycle.  For example, after a character has entered the event and enabled the helper, the scheduler should switch to the next character instead of waiting for the event to complete.
2. **Run limit:**  Each character can complete a maximum of ten successful Varka runs in a session.  Additionally, if the game displays a daily limit dialog (see Issue 3 and Issue 6), mark the character as done immediately.
3. **Retry policy:**  Each state may retry up to three times before reporting a failure.  When a state fails after three retries, the character is not permanently skipped; instead, it is placed into a retry‑later state and revisited after a cooldown.
4. **Interruptions:**  If any character encounters a `NEED_USER_LOGIN` condition (game crash or disconnect), the entire bot session must stop so the user can log back in.  Do not continue processing other characters.
5. **Session scope:**  Completed counts and state are stored only in memory for the current session.  They are reset when the bot restarts; daily limits reset every day.

### Character‑level state

Each character maintains its own runtime state object with fields such as:

- **current_state:**  The state in the Varka state machine being executed (e.g., `CHECK_LOBBY`, `HANDLE_POPUP_1`).
- **completed_count:**  Number of successful runs completed in the current session.
- **retry_count:**  Number of retries remaining for the current state (initially three).  This count is reset when transitioning to a new state.
- **status:**  One of `PENDING`, `RUNNING`, `RETRY_LATER`, `DONE_MAX_RUNS`, `DONE_BY_GAME_LIMIT`, `SKIPPED_ERROR`, `NEED_USER_LOGIN`, or `DISABLED`.
- **next_check_at:**  A timestamp indicating when this character’s next action should be performed.  Waiting states set this to a future time so that the scheduler does not block.
- **last_error:**  Most recent error message for debugging and display.

### Scheduler loop

The orchestrator runs a continuous loop.  At each tick it does the following:

1. **Select characters:**  Filter the list of characters to those whose `status` is `RUNNING` or `RETRY_LATER` and whose `next_check_at` is in the past.  Order them round‑robin so that each active character gets a chance.
2. **Process one step:**  For the selected character, call the Varka state machine to execute a single step or a small sequence of closely related steps.  For example, a tick might process the `CLICK_NPC` state entirely, but waiting for the timer in `EVENT_MONITORING` should not block a full tick.
3. **Update state:**  Based on the step’s result, update the character’s `current_state`, `status`, `completed_count`, `retry_count`, `next_check_at` and `last_error`.  If the step finished a run, increment `completed_count`.  If the step returns `DONE_BY_GAME_LIMIT`, set `completed_count` to 10.
4. **Log events:**  Write structured logs with timestamps and character names for each state transition, error and completion.
5. **Check global interrupts:**  If a step results in `NEED_USER_LOGIN` or a user stop command, break out of the loop and stop all processing.

### Handling retries and cooldowns

For each state, the bot may retry up to three times.  On each retry failure, decrement `retry_count`.  When `retry_count` reaches zero, set `status` to `RETRY_LATER` and assign `next_check_at` to some time in the future (e.g. 30 seconds later).  When the scheduler next checks this character after the cooldown, reset `retry_count` and re‑evaluate the character’s environment (e.g. re‑detect location and state) before deciding which state to re‑enter.

Some errors should not be retried at all:

- **DONE_BY_GAME_LIMIT:**  When the daily limit dialog appears, set `status` to `DONE_BY_GAME_LIMIT`, set `completed_count` to 10 and remove the character from active rotation.
- **NEED_USER_LOGIN:**  Indicates a disconnection or crash.  Stop all processing and alert the user.
- **DISABLED:**  Characters marked as disabled in configuration should never be scheduled.

### Completion conditions

- **Run success:**  When a run finishes via finish dialog or automatic return to lobby, increment `completed_count`.  If `completed_count` reaches ten, set `status` to `DONE_MAX_RUNS` and remove the character from the rotation.
- **Daily limit:**  When the game shows the daily limit dialog during NPC interaction, set `status` to `DONE_BY_GAME_LIMIT`, set `completed_count` to ten and remove the character.

### Terminal status and logging

The orchestrator should update a terminal dashboard regularly with the status of all characters.  Key fields include the character name, current state, run count, retry count, last error and any critical alerts (e.g. timer under 30 seconds).  Logs should record every state transition, retry, error and completion to aid debugging.

### Summary of orchestrator responsibilities

1. Discover and initialise runtime state for each enabled character.
2. Cycle through active characters in a fair round‑robin order.
3. Execute one state step per character per tick and update the runtime state.
4. Enforce per‑state retry limits, including cool‑down and retry‑later logic.
5. Detect and handle terminal conditions: run completion, daily limit reached and user login needed.
6. Provide a live terminal dashboard and persistent logs for transparency and debugging.
7. Stop all processing gracefully when the user requests or when a fatal error occurs.