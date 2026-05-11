## Issue 4 — Event Map Detection, Helper Activation and Monitoring

When the bot has clicked through both NPC pop‑ups and requests entry to the Varka event, it must recognise that the character has actually zoned into the event map, enable the in‑game helper immediately, and then monitor the event timer until completion.  This document summarises the steps and safeguards for these tasks.

### Detecting entry into the event map

After clicking **Enter** on Pop‑up 2, the game performs a transition into the event map.  The bot should poll for the following signals to determine when the character is inside the dungeon:

- **Map label:**  The top‑left label should change from “Waiting Room for Imperial Fort” to a Varka map label (for example “Varka” or similar).  A template of this label is used to detect the transition.  Detection is considered reliable after several consecutive frames show the Varka label.
- **Timer panel:**  A new timer panel appears in the bottom‑right corner.  Its title has the form `Round X (Zone Y)` with `X` varying by round and `Y` typically between 1 and 4.  Detecting this panel via an anchor template is another strong signal that the event map is ready.
- **Dialog/popup absence:**  All NPC pop‑ups should be closed.  If the original pop‑ups remain, or if a finish dialog is already present, the state machine should handle those cases separately.
- **Screen stability:**  Do not assume the event map is ready as soon as the black fade begins.  Wait until successive captures show the scene has stabilised (no rapid visual changes) before proceeding.

If these signals are satisfied within a reasonable timeout (for example 5–8 seconds), set the state to `EVENT_MAP_READY`.  Otherwise log a failure and let the orchestrator decide whether to retry.

### Opening the Varka Helper

Immediately after entering the event map, the in‑game Varka Helper must be activated so that the character will fight automatically.  This helper behaves as a **toggle**: a play icon indicates it is off, and a pause icon indicates it is running.  Clicking the icon while it is in pause state will stop the helper, so the bot must detect the current state before clicking.

The recommended procedure is:

1. **Wait briefly:**  Even after the event map is ready, wait 0.5–1 second for the helper UI to render.  Do not click immediately.
2. **Detect helper icon:**  Crop the helper area (usually top‑left) and run template matching for the play and pause icons.  If the play icon (helper off) is found, proceed to click; if the pause icon (helper running) is found, skip the click.
3. **Click when off:**  If the helper is off, click the play icon to start it.  Wait briefly, then verify that the icon changed to pause.  If it does not change, log a retryable error.
4. **Do nothing when on:**  If the helper is already running, avoid clicking again to prevent pausing it.  Proceed to monitoring.

If the helper state cannot be determined, do not guess; log the issue and handle via the orchestrator’s retry logic.

### Monitoring the event timer

During the event the bot does **not** control the character beyond enabling the helper.  However, it must monitor the timer panel to provide alerts and to determine when the run is complete:

1. **Standby phase:**  Before the combat begins, the timer shows a **Standby** or **Standing by** state.  No action is required during this phase.
2. **Time Left (Remaining Monsters):**  When combat is active, the timer displays a countdown and the number of remaining monsters in parentheses, e.g. `02:34(12)`.  Use either OCR or digit‑template recognition within the timer ROI to parse the minutes, seconds and monster count.  If the countdown drops below 30 seconds and the monster count is still greater than zero, raise a **critical alert** on the terminal so the user can intervene manually.  To avoid spamming alerts, emit the alert no more often than every few seconds.
3. **Exit Waiting Time:**  After the combat round ends, the timer switches to “Exit Waiting Time,” indicating that the dungeon is about to end.  No critical alert is necessary in this phase.  Wait for a finish dialog or automatic return to the lobby.
4. **Timer disappearance:**  When the timer panel disappears, the character is either loading between maps or returning to the lobby.  The state machine should switch to event‑completion handling.

### Event completion and finishing

An event run can end in two ways:

1. **Finish dialog:**  A dialog appears announcing that the map has been cleared.  This dialog includes an **Exit** button.  The bot should detect this dialog by template, click **Exit** and then wait for the game to return to the lobby.  After returning to the lobby, increment the character’s completed run count.
2. **Automatic return:**  Sometimes the game returns to the lobby without displaying a finish dialog, for example after a timeout or failure.  If the lobby label reappears and no dialog is present, treat this as a completed run as well.  Log whether the run ended with a finish dialog or an automatic return.

If the event does not finish within a long timeout or the timer stalls, log a failure and let the orchestrator decide whether to retry or skip the character.

### Key points

- Use multiple signals (map label, timer panel, absence of pop‑ups) to detect entry into the event map.  Do not rely on any single indicator.
- The helper icon is a toggle; always detect its state before clicking.  Never click the pause icon.
- Monitor the timer panel in the background using ROI cropping and template or OCR parsing.  Raise a critical alert when the time left is under 30 seconds and monsters remain.  Do not produce sound; the alert should only appear in the terminal.
- Treat both finish dialog and automatic return as successful completions.  If the run ends due to the daily limit dialog, handle that as per Issue 6.