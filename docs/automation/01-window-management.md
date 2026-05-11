## Window Management

Correctly identifying and interacting with the game windows is fundamental to the bot.  Multiple characters are controlled simultaneously, so the bot must enumerate, focus and send input to each window independently.

### Enumerating game windows

* The bot uses Windows API calls (e.g. through **pywin32** or **pywinauto**) to enumerate all top‑level windows.
* It filters windows whose titles contain the server prefix (e.g. `Asteria MU – Powered by IGCN`) and match the format `Name: [char] Level: [lv] Master Level: [ml] Resets: [n]`.  A regular expression extracts the character name, level, master level and reset count from the title.
* Each window is stored in a `GameWindowInfo` object containing the handle (`hwnd`), process ID, title, rectangle coordinates, visibility and minimised status.  This information is discovered on each run; **window handles are never persisted**.

### Matching windows to characters

* The configuration file lists the display names of the characters to be automated.  After discovery, windows are matched to these names.
* If multiple windows share a name or a configured name is missing, the bot logs a warning and skips ambiguous windows.
* Characters can be enabled or disabled in configuration.  Disabled characters are ignored during scheduling.

### Focusing and switching windows

* To send human‑like input (mouse movement, clicks, keyboard presses) reliably, the bot can bring a window to the foreground using `SetForegroundWindow` or by sending an Alt+Tab sequence.  Focusing ensures that the game receives input and that the hover indicator appears.
* When running in background mode for certain steps, focusing is not required.  However, the bot always ensures that the window is visible (not minimised), as some capture methods fail on minimised windows.
* The scheduler keeps track of which window is currently focused to avoid unnecessary switching.

### Keyboard shortcuts and window control

* Opening the **Event Window** is done by sending **Ctrl + T** to the game window.  This is used in the “enter lobby” flow when the character is not in the lobby or event map.
* Other global shortcuts can be added to configuration if needed.  All hotkey sending is abstracted through an input backend to support foreground and background methods.
* The bot never resizes or moves game windows.  Windows remain in their positions; overlapping windows are handled by selecting the correct `hwnd` for capture and input.

### Window health checks

* The runtime periodically verifies that the window still exists and that the process is alive.  If the window is lost (e.g. due to a game crash), the bot stops all activity and notifies the user to log in again.
* Minimised windows can cause capture to return black frames; the bot either prevents minimising windows or detects this and uses fallback strategies.
