## Issue 5 — Entering the Lobby from Outside

When the bot discovers that a character is not already in the Varka lobby and not currently in the event map, it must automatically navigate the game’s event interface to enter the lobby.  This file summarises the procedure and error handling for that situation.

### Detecting that the character is outside the lobby

Before triggering the lobby entry flow, ensure the character is not already in a Varka state:

- **Lobby not detected:**  The `Waiting Room for Imperial Fort` label and other lobby indicators are absent.
- **Event map not detected:**  The event timer panel and Varka map label are absent.
- **No pop‑ups open:**  There is no NPC dialog or finish dialog visible.

If all of these conditions hold, assume the character is in a regular map or town.  Proceed to open the Event Window.

### Opening the Event Window

- **Use a hotkey:**  Press **Ctrl + T** to open the game’s Event Window.  Always send this hotkey to the game window after bringing it into focus (if running in foreground mode).  If running in background mode, test whether the hotkey works without focus (see Issue 7).
- **Detect Event Window:**  After sending the hotkey, poll a small ROI where the Event Window header normally appears.  Use a template of the “Events Info” header to detect whether the window has opened.  If it fails to open, retry the hotkey up to the configured number of attempts (for example three times).  If the window still does not appear, log an error and hand control back to the orchestrator.

### Selecting the Imperial Guardian event

Inside the Event Window, the left‑hand list contains various events.  The bot must find and select **Imperial Guardian**:

- **Locate list item:**  Use template matching to find the Imperial Guardian entry within the left panel of the Event Window.  Avoid fixed coordinates because the list may scroll.  If necessary, scroll within the list and attempt detection again.
- **Click selection:**  Once found, click on the centre of the Imperial Guardian entry.  Verify the selection by detecting a change in the main content area—for example, the appearance of the Imperial Guardian title or image in the main panel.
- **Failure handling:**  If the item cannot be found after a few scroll attempts, log `IMPERIAL_GUARDIAN_NOT_FOUND`, capture a screenshot and skip the character or alert the user.

### Entering the lobby via the Enter button

- **Locate the Enter button:**  In the Event Window’s right‑hand panel, find the **Enter** button associated with Imperial Guardian.  This button may be disabled if the event is not currently available or the character has no remaining entries for the day.  Use a template to detect both enabled and disabled states.
- **Click if enabled:**  If the button is enabled, click on it.  Record the click and transition to a state waiting for the lobby to load.  If the button is disabled, log `EVENT_ENTER_NOT_AVAILABLE` and skip the character for this session.

### Waiting for the lobby to load

Entering the lobby often triggers a loading screen.  The game may remain on a black screen for 5–10 seconds.  Use a loop that polls every few hundred milliseconds to detect when the lobby has loaded:

- **Timeout:**  Allow a generous timeout (e.g., 15–20 seconds).  If the lobby does not appear within this time, capture a screenshot, log a timeout and skip or retry depending on the orchestrator’s policy.
- **Detect lobby ready:**  Use the same multi‑signal lobby detection described in Issue 2 (lobby label, absence of timer/event panels, screen stability).  Once confirmed, hand control back to the lobby/NPC flow.
- **Crash or disconnect:**  Occasionally the game may crash during map transitions.  If the game window disappears or capturing fails repeatedly, mark `NEED_USER_LOGIN` and stop the entire bot session so that the user can restart the game.

### Summary of rules

- Only initiate the lobby entry flow when the character is neither in the lobby nor in the event map and there are no open dialogs.
- Use **Ctrl + T** to open the Event Window, detect it via a header template and retry if necessary.
- Locate and select **Imperial Guardian** from the event list using template matching; verify the selection by content change.
- Detect whether the **Enter** button is enabled; click it only when enabled; treat disabled states as a normal condition rather than an error.
- Wait for the lobby to load using multi‑signal detection and a generous timeout.  Log and skip characters on repeated failure.