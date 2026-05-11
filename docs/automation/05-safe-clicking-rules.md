## Safe Clicking Rules

Performing mouse clicks in a game client carries risk: mis‑clicks can cause the character to move unexpectedly, close a dialog or toggle an option off.  The bot follows these guidelines to minimise mistakes:

### Verify before clicking

* **Detect anchors first:** before clicking a button, link or icon, the bot detects an anchor (e.g. a dialog title, panel border or helper label) to locate the correct region.  Clicks are expressed as offsets relative to that anchor rather than absolute coordinates.
* **Template matching:** whenever possible, the bot confirms the presence of the target via template matching within the ROI.  The match must exceed a threshold; if it fails, the click is skipped.
* **Hover verification:** for NPCs, the bot must see the hover indicator before clicking.  No candidate is clicked blindly.
* **State check:** for toggle buttons like the helper, the bot checks the current state (play vs pause).  It clicks only when the desired state is OFF.

### Limit retries

* Each state is retried up to three times.  Between retries, the bot refreshes the screen capture and re‑detects the UI elements.
* If a click fails repeatedly (e.g. the button is not found), the bot logs the error and moves to the next character or marks the character as retry‑later.  It never spams clicks.

### Control modifiers precisely

* Modifier keys (`ALT`, `CTRL`, etc.) are pressed and released at specific times.  For `ALT + click`, the bot presses `ALT`, moves the mouse, clicks, then releases `ALT` immediately.  It never leaves a modifier key pressed between steps.

### Click relative to client area

* All click coordinates are calculated relative to the client area of the game window.  This avoids issues with different window positions or screen resolutions.
* The bot does not rely on global screen coordinates, which could be wrong if the window is moved or the desktop resolution changes.

### Avoid clicking when uncertain

* If the bot cannot detect the UI element with sufficient confidence or if the state is ambiguous, it does not click.  Instead, it logs the situation and either retries later or asks the user to intervene.
* In states such as **loading/transition**, the UI may still be appearing; clicks are postponed until the screen is stable.

### Special cases

* **Dialog dismissal:** finishing dialogs and daily limit dialogs have dedicated exit buttons.  These are clicked only when the dialog is detected.  If the dialog disappears or the game returns to the lobby automatically, the click is skipped.
* **Emergency stop:** the user can interrupt the bot at any time (e.g. via a hotkey).  The input backends handle this gracefully, stopping clicks immediately.
