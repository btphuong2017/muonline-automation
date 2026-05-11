## State machine overview

Each high‑level action is implemented as a finite state machine (FSM).  A state machine defines discrete states, transitions between states and retry rules.  States are responsible for performing small, atomic steps and returning a result to the orchestrator.

### General pattern

1. **Enter state.**  A state receives the current character context and global settings.  It may capture the screen, perform template matching, send input events or wait for timers.
2. **Evaluate outcome.**  A state returns one of several outcomes:
   - `SUCCESS` – the state completed and the next state should be entered immediately.
   - `WAIT` – the state has initiated an action (e.g. map change) and should be checked later; the orchestrator schedules a future time for the next check.
   - `RETRY` – the state failed but can retry.  The orchestrator increments the retry count and reenters the state until the retry limit is reached.
   - `FAIL` – the state failed irrecoverably.  The orchestrator logs the error and moves the character to `SKIPPED_ERROR`.
   - `DONE` – the action is complete for this character (e.g. limit reached); the orchestrator stops further processing for this character.
3. **Update runtime.**  The orchestrator updates the character’s runtime record with the new state, retry counters and scheduled next check time.  It then proceeds to service other characters.

### Varka flow example

The Varka action uses a state machine with states such as:

- `CHECK_LOCATION` – Determine whether the character is in the lobby, the event map or somewhere else.
- `ENTER_LOBBY` – If outside, open the Event window, select Imperial Guardian and click Enter.
- `CHECK_LOBBY` – Ensure the character is in the lobby and the screen is stable.
- `FIND_NPC` – Locate the Varka NPC via candidate search and hover indicator.
- `CLICK_NPC` – Hover and Alt + click the NPC; wait for the first popup.
- `HANDLE_POPUP_1` – Click “Enter Varka” in the first popup.  Detect limit dialog to end early.
- `HANDLE_POPUP_2` – Click “Enter” in the second popup to enter the event.
- `WAIT_EVENT_MAP` – Poll until the event map is loaded.
- `START_HELPER` – Detect helper state and click Play if needed.
- `MONITOR_EVENT` – Monitor the timer; alert on critical time; detect finish.
- `HANDLE_FINISH_DIALOG` – If event cleared popup appears, click Exit.
- `RETURN_LOBBY` – Wait for transition back to lobby and increment the run count.
- `DONE_BY_LIMIT` / `DONE_MAX_RUNS` – Terminal states when the character has reached the daily limit or completed the configured number of runs.

Each state includes its own retry limit.  If a state reaches its retry limit, the state returns `FAIL` and the character is skipped for the session.