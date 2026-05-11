## Varka error and retry policy

This document captures the error categories, retry limits and fallback strategies used throughout the Varka automation flow.  It centralises the rules discussed across the individual issues so that agents implement consistent behaviour.

### Error categories

1. **Recoverable errors** – Temporary failures that may succeed upon retry.  Examples:
   * A template match is not found because of momentary lag or a crowded scene.
   * A click does not register or the NPC dialog does not open on the first attempt.
   * Pop‑up 2 does not appear immediately after Pop‑up 1.
   * Helper state cannot be detected on the first try.
   These errors should be retried up to the configured limit for the state (three attempts by default).  Between retries, the bot should refresh its screenshot and reconsider its candidate list.  The state machine remains in the same step until success or until retries are exhausted.

2. **Non‑retryable conditions** – Situations where retrying will not help.  Examples:
   * The daily entrance limit dialog appears (`Cannot enter as you have exceeded the daily entrance limit.`).  The character is marked `DONE_BY_GAME_LIMIT` and no further action is taken.
   * The event window’s Enter button is disabled or missing (event closed).  The bot logs a message and moves to the next character.
   * The event entry limit has already been reached for the character in the current session (run count ≥ 10).  The character is marked `DONE_MAX_RUNS`.

3. **Fatal or session‑level errors** – Conditions that require stopping the bot entirely:
   * The game window disappears (crash, disconnect, process killed).
   * The capture system fails consistently (no frames or black frames for all windows).
   * User intervention is requested (the operator pressed a stop command or the bot cannot proceed safely).
   In these cases the orchestrator enters `NEED_USER_LOGIN`, `USER_STOPPED` or `FATAL_ERROR` and halts further processing until the user resolves the situation.

### Retry limits and behaviour

* **Per‑state retry limit** – For most states, the bot will retry up to **three** times.  Each retry should take a fresh screenshot, re‑compute candidates and re‑attempt the action.  If all three retries fail, the state returns a `FAILED_RETRY_EXCEEDED` result.

* **Retry and skip policy** – When a state returns `FAILED_RETRY_EXCEEDED`, the orchestrator does *not* give up on the entire character immediately.  Instead, it places the character into a `RETRY_LATER` state with a cool‑down period (e.g., 30 seconds).  After the cooldown, the scheduler re‑evaluates the character from the `CHECK_LOCATION` state.  This avoids repeated rapid failures when the game scene has not stabilised or when other players block the NPC.

* **Retry count reset** – Successfully completing a state resets its retry counter.  Failures in later states do not affect earlier ones.

* **Maximum runs** – Each character is allowed up to **10** successful runs per session.  On the tenth success, the character enters `DONE_MAX_RUNS` and is excluded from further runs.  When the game signals the daily entrance limit, the character is immediately marked `DONE_BY_GAME_LIMIT`, and its run count is set to the maximum to prevent further attempts.

### Handling uncertain outcomes

* **Return to lobby without finish dialog** – If the character returns to the lobby and no finish dialog was detected, the run is still counted as a success.  This simplifies the logic because some servers return the character automatically instead of showing the clear dialog.

* **Unknown state transitions** – If the bot cannot determine whether it is in the lobby, in the event map or elsewhere, it should fall back to `UNKNOWN` and attempt to re‑detect.  Persistent unknowns after retries are treated as failures.

* **Timeouts** – Each waiting state (e.g., waiting for Pop‑up 2 or waiting for the event map to load) should have a timeout (around 5–20 seconds depending on context).  Timeouts count as a failure and increment the retry counter.  Long blocking `sleep` calls should be avoided; instead poll the relevant signals (map label, timer panel, dialog) at short intervals.

### Logging and alerts

Every error or retry should be logged with:

* The character name and run number
* The current state and sub‑state
* Retry count
* A human‑readable description of the error (e.g., “NPC hover indicator not found”)
* A timestamp
* A screenshot of the relevant region (if possible)

When a `FAILED_RETRY_EXCEEDED` occurs, the terminal dashboard should clearly mark the character as `RETRY_LATER` with the reason.  When a critical alert (e.g., `Time Left < 30 s`) occurs, the dashboard should highlight it but **should not** automatically stop the bot.

### Summary

The Varka bot is designed to be robust in the face of transient failures.  It retries states up to three times, cools down before re‑attempting a problematic character, and distinguishes between recoverable, non‑recoverable and fatal conditions.  By following this policy, agents can implement a resilient orchestrator that avoids getting stuck in tight loops while still maximising the chances of completing each character’s daily runs.
