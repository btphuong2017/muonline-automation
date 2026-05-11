## Character Loop Strategy

This document describes how the cooperative scheduler loops through all
configured characters when executing the Varka automation.  The goal is
to maximise efficiency by interleaving small units of work across
characters rather than running one character from start‑to‑finish
before moving on to the next.  The scheduler treats each character as
an independent state machine and steps each one through its current
state in turn.

### Key principles

* **Interleaving states:**  The orchestrator does not fully complete
  the Varka flow for one character before switching.  Instead it
  executes a short action for the current state of character A,
  updates its runtime state, then switches to character B, and so on.
  This allows the bot to make progress on all characters while
  another character is waiting for a timer, map transition or helper
  auto run.

* **Round‑robin fairness:**  Characters are scheduled in a simple
  round‑robin order.  Once the scheduler processes a step for one
  character it moves the cursor to the next enabled character.  This
  ensures no character starves if another character enters a long
  waiting state.  The order may be adjusted to prioritise urgent
  conditions such as critical timer alerts or global interrupts.

* **Run count tracking:**  Each runtime character record tracks
  `completed_count` and `max_runs`.  When `completed_count` reaches
  `max_runs` (default 10) the orchestrator marks the character as
  `DONE_MAX_RUNS`.  A special state `DONE_BY_GAME_LIMIT` is used when
  the game displays the daily limit dialog; in this case the
  orchestrator also sets `completed_count` to `max_runs` and removes
  the character from the active pool.

* **Retry and retry‑later:**  Each state has an internal retry
  counter.  If a state fails up to three times the orchestrator logs
  the error, captures a screenshot and moves the character into
  `RETRY_LATER` with a cooldown.  After the cooldown expires the
  scheduler will reattempt the state.  Fatal errors such as
  `NEED_USER_LOGIN` stop the entire session.

* **Skipping finished characters:**  Characters that reach
  `DONE_MAX_RUNS` or `DONE_BY_GAME_LIMIT` are removed from the
  scheduling queue.  Disabled characters are skipped entirely.

### Scheduler loop pseudo code

The scheduler maintains a list of runtime character objects.  Each
iteration (called a *tick*) performs the following steps:

1. **Select next character.**  Choose the next enabled character that
   is not in a terminal state (`DONE_*`, `NEED_USER_LOGIN`, or
   `SKIPPED_ERROR`).  If no characters remain, stop the session.
2. **Check global interrupts.**  Before running the step, check if
   there is a global stop request or if any character requires
   immediate attention (e.g. `NEED_USER_LOGIN`).  If so, handle it and
   break out.
3. **Process one step.**  Call the state handler for the character’s
   current state.  Handlers return a new state and may update
   `completed_count`, schedule a retry or mark the character as
   finished.  State handlers must be short and non‑blocking; long
   waits (e.g. waiting for a map load) should set a future
   `next_check_at` so the scheduler knows when to revisit the
   character.
4. **Update dashboard and log.**  After the step completes, update
   the terminal status dashboard and append structured log entries.
5. **Advance cursor.**  Move to the next character in the list and
   repeat.

### Retry later and cooldowns

When a character hits the retry limit for a state the scheduler does
not immediately drop the character.  Instead it records a
`retry_later_until` timestamp and a `retry_later_reason`.  The
character is skipped during scheduling until the current time is
greater than `retry_later_until`.  This allows transient issues (e.g.
momentary lag or NPC crowding) to clear before attempting the step
again.  The cooldown durations may be configured per state.

### Handling concurrent wait states

Many states, such as `WAIT_EVENT_MAP_LOADING` or
`EVENT_MONITORING`, involve waiting for external conditions.  The
scheduler does not block the entire loop during these waits.  When
entering such a state the handler sets a `next_check_at` time on the
character.  The scheduler will skip that character on subsequent
ticks until the time has expired, allowing other characters to
progress.  This mechanism is critical to achieve cooperative
multitasking.

### Summary

The character loop strategy ensures that all characters progress
towards their maximum run count efficiently while respecting retry
limits and avoiding long blocking waits.  By interleaving work across
characters, the bot can manage up to five game windows in a single
session and make the best use of idle time while helpers run events
in the background.