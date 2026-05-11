## Cooperative Scheduler Overview

The Varka bot controls up to five characters concurrently.  A naïve approach would run each character to completion before moving on to the next, but this wastes time when characters are waiting (e.g. running the helper).  Instead, the bot uses a **cooperative scheduler** that interleaves small steps from each character.

### Goals

* **Maximise throughput:** while one character is auto‑fighting with the helper, the scheduler can process another character’s NPC interaction or popup handling.
* **Responsive error handling:** if a character encounters an error or needs user intervention, the scheduler can switch away quickly and continue with others.
* **Fairness:** each character gets time slices; no character monopolises the CPU.

### Operation

* At startup, the scheduler loads the configured characters, discovers their windows and initialises a runtime state for each (current state, completed count, retry counters, etc.).
* The scheduler enters a loop.  On each iteration it selects the next character that is not done and whose `next_check_at` time has passed.
* For the chosen character, it calls the **state machine** to execute a single step.  The state machine may perform detection, send input and update the character’s runtime state.  It then returns a result indicating whether the step succeeded, should be retried later, or produced a terminal state (done or error).
* The scheduler updates the character’s runtime (`current_state`, `completed_count`, `state_retry_count`, `last_error`, `next_check_at`, etc.) and logs the outcome.  If the character reaches a terminal state (DONE by max runs, DONE by game limit, or SKIPPED error), it is removed from scheduling.
* The loop repeats until all characters are done or a global stop (e.g. need user login or user interrupt) occurs.

### Ticks and pacing

* The scheduler runs at a configurable tick rate (e.g. 50–100 ms), ensuring that state checks and actions are interleaved smoothly.
* Characters in waiting states (e.g. loading, event monitoring) schedule their `next_check_at` several seconds in the future.  This prevents the scheduler from polling them too often.

### Global interrupts

The scheduler monitors flags that can stop all activity:

* **NEED_USER_LOGIN:** the game window was lost (crash or disconnect).  The bot stops all characters and informs the user.
* **User stop:** the user sends a stop command or hotkey.  The scheduler exits gracefully.

### Logging and dashboard integration

Each time a step completes, the scheduler logs the result and updates the **terminal dashboard**.  The dashboard reflects the latest state, retry counts and runtime for all characters.
