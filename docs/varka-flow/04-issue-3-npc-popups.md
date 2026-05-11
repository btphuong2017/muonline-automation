## Issue 3 — Handling NPC Pop‑ups

After the bot locates and clicks the Varka event NPC, two sequential pop‑ups must be processed.  This file summarises how to recognise and handle those pop‑ups safely using template matching rather than OCR or blind clicking.

### Purpose of the pop‑ups

1. **Popup 1:** This is the dialog titled “Fortress of the Imperial Guard.”  It presents up to three buttons: **Enter Varka**, **Leave Varka** and **Close**.  When the player still has Varka attempts, clicking **Enter Varka** should open the second dialog.  If the character has reached its daily limit the game shows a different dialog (see Issue 6) and the bot should mark the character as done.
2. **Popup 2:** After a successful click on **Enter Varka**, a second dialog appears.  It prompts the player to select a monster element and Varka level, but for our automation both of these are irrelevant.  The bot should always click the **Enter** button on this second dialog to enter the event map.

### Detection and interaction strategy

- **ROI‑based detection:**  Both dialogs appear in fixed positions relative to the game window.  The bot should crop a small region of interest (ROI) around the dialog area and run template matching on the title bar (“Fortress of the Imperial Guard”) or other anchor elements to detect that the dialog has opened.  Using ROI prevents false positives from other UI elements and speeds up matching.
- **Button templates:**  Within the detected dialog ROI, locate the **Enter Varka** button using a template or anchor‑based offset.  Do not rely on text recognition for the button label; use an image template or pre‑defined offset relative to the dialog anchor.  The **Leave Varka** and **Close** buttons should only be used for context to avoid accidental clicks.
- **Clicking Pop‑up 1:**  Once the **Enter Varka** button is found, move the mouse to its centre and click.  Record the click in logs.  After clicking, switch to a state waiting for Pop‑up 2.
- **Waiting for Pop‑up 2:**  The second dialog may take up to a few seconds to appear.  The bot should poll the same fixed ROI for the second dialog.  If Pop‑up 2 does not appear within a timeout (for example 5 seconds), assume either the character reached its daily limit (Issue 6) or an error occurred.  In case of failure, log an error and retry up to the configured number of times.
- **Clicking Pop‑up 2:**  Detect the **Enter** button inside Pop‑up 2 using a template or relative position.  As with Pop‑up 1, click the centre of the button.  Ignore fields labelled “Monster Element” or “Varka Level” entirely.  After clicking **Enter**, transition to a state that waits for the event map to load.
- **Verification:**  Successful processing of both pop‑ups should lead to a loading/transition screen and then to the event map.  The bot must check that the dialogs have closed and that no error messages appeared.  If nothing changes after clicking, assume the click failed and retry within the allowed retry count.

### Error handling

- **Missing buttons:**  If either the **Enter Varka** button or the **Enter** button cannot be detected within a reasonable number of frames, the bot should log a recoverable error and retry the current step up to the state’s retry limit.  After the retry limit is exceeded, mark the state as failed and hand control back to the orchestrator.
- **Dialog not opening:**  If Pop‑up 1 does not appear after clicking the NPC or Pop‑up 2 does not appear after clicking **Enter Varka**, the bot should also treat this as a failure.  Potential causes include mis‑clicked NPC, lag or a daily limit dialog.  Retry within the state’s limit; otherwise report to the orchestrator.
- **Daily limit dialog:**  A special dialog saying the daily limit has been exceeded should be handled at the orchestrator level (Issue 6).  It is detected by its own template and sets the character state to `DONE_BY_GAME_LIMIT` immediately.

### Key takeaways

- Always use template matching in small ROIs to detect dialogs and buttons; do not rely on full‑screen OCR.
- Use anchor‑based offsets for clicking if button templates prove unreliable.  This reduces the chance of clicking the wrong area when other players overlap the UI.
- Wait for Pop‑up 2 to appear before clicking; use timeouts to avoid indefinite waits.
- Log each step and error.  Limit retries per state to avoid endless loops.  Escalate to the orchestrator after repeated failures.