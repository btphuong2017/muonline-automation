## System boundaries

This section describes what the automation bot is allowed to do and what it must not do.  Adhering to these boundaries keeps the project maintainable and compliant with game policies.

### Allowed interactions

The bot interacts with Mu Online only via standard user interfaces:

- Enumerating and inspecting window titles and dimensions via Win32 APIs.
- Capturing screen or window contents to analyse images and text using template matching or OCR.
- Moving the mouse cursor and clicking via system APIs.  Holding keys (e.g. Alt) while clicking is permitted.
- Sending keyboard hotkeys (e.g. Ctrl + T) to open in‑game windows.
- Reading visible dialogs and UI elements to make decisions.
- Waiting and timing to allow the game to update.

### Prohibited interactions

The bot **must not**:

- Inject code or hook into the game process.
- Read or write the game’s memory or network packets.
- Modify game files or circumvent anti‑cheat systems.
- Automate tasks unrelated to the specific Varka event without explicit design.
- Persist sensitive information about the user beyond the session (e.g. storing credentials or session data).

### Error handling boundaries

When the game crashes or disconnects, the bot cannot recover automatically.  It must stop and inform the user to log in again.  The bot does not attempt to restart the game or re‑authenticate.  All state is held only in memory for the current session; daily limits reset at the start of each session.