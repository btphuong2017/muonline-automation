## Varka state reference

This document lists the states used in the Varka automation flow and provides a brief explanation of each state.  These states appear in the state machine diagrams, orchestrator logic and per‑character runtime structures.  Grouping them here helps agents ensure consistency across modules.

### Location and environment states

* **UNKNOWN** – The initial state when the system cannot determine where the character is.
* **LOADING_OR_TRANSITION** – The game is transitioning between maps or has just closed/opened a dialog; screen contents are not stable.  The bot should wait until frames stabilise before acting.
* **LOBBY_READY** – The character is in the lobby/waiting room (e.g., *Waiting Room for Imperial Fort*) and the UI is stable.  The NPC may or may not be visible yet.  This state is the entry point for NPC detection.
* **EVENT_MAP_READY** – The character has entered the Varka dungeon; the dungeon timer and map label confirm this.  The helper can be toggled once the UI has rendered.
* **EVENT_FINISHED_DIALOG** – The finish popup has appeared, indicating the event has been completed successfully.  The bot must click Exit.
* **RETURNED_TO_LOBBY** – After finishing or failing the event, the character has returned to the lobby.  The state machine should start over or mark a run as complete.
* **OUTSIDE_VARKA_FLOW** – The character is in an unrelated map (e.g., town) and needs to open the event window and enter the lobby via Issue 5.
* **GAME_WINDOW_LOST** – The game window has closed, crashed or become inaccessible.  This triggers a global stop (`NEED_USER_LOGIN`).

### NPC and lobby interaction states

* **FIND_NPC_CANDIDATE** – The system is searching for points on the screen that may correspond to the NPC (using cached points, partial templates and grid searches).
* **NPC_HOVER_CANDIDATE_FOUND** – A candidate point has passed the hover indicator check.  The bot will attempt an `Alt`‑click.
* **ALT_CLICK_NPC** – The bot is holding `Alt` and clicking the candidate.  The next step is to verify whether the NPC dialog opens.
* **NPC_CLICK_FAILED** – After clicking, no dialog appears.  The bot will try another candidate or retry the state up to the configured limit.
* **NPC_DIALOG_OPEN** – The NPC dialog is open.  The bot will handle Pop‑up 1 and Pop‑up 2.
* **NPC_DIALOG_FAILED** – After exhausting retries for opening the dialog or handling pop‑ups, the state is considered failed.

### Popup handling states (Issue 3)

* **NPC_DIALOG_STEP_1_OPEN** – Pop‑up 1 (Fortress of the Imperial Guard) is open.  The bot must locate and click `Enter Varka`.
* **CLICK_ENTER_VARKA** – The bot is clicking the `Enter Varka` button within Pop‑up 1.
* **WAIT_POPUP_2** – The bot waits briefly for Pop‑up 2 to appear.  If it does not, retries may be attempted.
* **NPC_DIALOG_STEP_2_OPEN** – Pop‑up 2 is open.  The bot must click `Enter` to join the dungeon.
* **CLICK_ENTER_DUNGEON** – The bot is clicking the `Enter` button in Pop‑up 2.
* **NO_VARKA_ATTEMPT_OR_BLOCKED** – A dialog indicating the daily entry limit has been reached appears; the run ends with `DONE_BY_GAME_LIMIT` and no further retries.

### Event map and helper states (Issue 4)

* **WAIT_EVENT_MAP_LOADING** – The bot has clicked to enter the event and is waiting for the dungeon map to load.  It polls for the timer and map label but does not interact.
* **EVENT_MAP_READY_BUT_HELPER_OFF** – The dungeon is loaded but the helper is not yet running; the helper button shows the play icon.
* **START_HELPER** – The bot clicks the helper play icon.  It must verify that the helper switches to the running/pause icon.

  Implementation note: `_activate_helper()` in `automation/event_helper.py` implements
  `WAIT_EVENT_MAP_LOADING` -> `EVENT_MAP_READY_BUT_HELPER_OFF` -> `START_HELPER` as one
  function with two independently-budgeted phases rather than three separate states:
  `_wait_for_helper_visible()` (time-based poll, up to `_HELPER_VISIBLE_TIMEOUT_S`, for the
  icon to render) followed by a count-based click/verify retry loop (`max_retries`). The
  boundary between the three conceptual states above is the moment the poll first sees a
  non-UNKNOWN helper_state.
* **EVENT_RUNNING_WITH_HELPER_ON** – The character is auto‑farming with the helper.  The bot monitors the timer, alerts if the remaining time is short and monsters remain, and looks for the finish dialog.
* **EVENT_MONITORING** – Same as the above but emphasises that the bot is in a monitoring loop rather than performing active actions.
* **EVENT_CRITICAL_ALERT** – A substate triggered when the timer shows less than 30 seconds and remaining monsters are non‑zero.  The bot raises a terminal alert but does not control the character.

### Enter lobby flow states (Issue 5)

* **OPEN_EVENT_WINDOW** – The bot presses `Ctrl+T` to open the event window and checks that the window appears.
* **SELECT_IMPERIAL_GUARDIAN** – It locates the “Imperial Guardian” item in the event list and clicks it.
* **CLICK_EVENT_ENTER** – It clicks the `Enter` button for the Imperial Guardian event to move to the lobby.
* **WAIT_LOBBY_LOADING** – The bot waits 5–10 seconds for the map transition to complete and then confirms `LOBBY_READY`.
* **EVENT_WINDOW_OPEN_FAILED** – The event window did not open after retries; the run fails.
* **IMPERIAL_GUARDIAN_NOT_FOUND** – The event list did not contain the Imperial Guardian entry; the run fails.
* **EVENT_ENTER_NOT_AVAILABLE** – The Enter button is disabled or not available, indicating the event is closed or the daily limit is reached; the run ends.

### Orchestrator and meta‑states (Issue 6)

* **PENDING** – Character has not started running yet.
* **RUNNING** – Character is currently being processed by the scheduler.
* **RETRY_LATER** – The state failed three times; the character is placed on cooldown before being retried.
* **DONE_MAX_RUNS** – The character reached the configured maximum run count (e.g., 10) and is considered done for the session.
* **DONE_BY_GAME_LIMIT** – The game indicated that the daily entrance limit has been reached; the character is done without error.
* **SKIPPED_ERROR** – A state failed after retries and the character is skipped; this may require user intervention.
* **NEED_USER_LOGIN** – A crash or disconnect occurred; the whole bot must stop and await manual login.
* **USER_STOPPED** – The user has manually stopped the bot; all processing halts.
* **FATAL_ERROR** – An unexpected unrecoverable error occurred; the session ends.

### Notes

* States are treated as *conceptual milestones* rather than classes or functions.  They are used to organise the flow, direct logging and implement retry logic.
* Agents should always update the character’s current state in the runtime model; this drives the scheduler and the terminal dashboard.
* Additional sub‑states may exist for testing or implementation purposes, but they should be documented in the relevant module.  The list above covers the shared vocabulary across the Varka flow.
