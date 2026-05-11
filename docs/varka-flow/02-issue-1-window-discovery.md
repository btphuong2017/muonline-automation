## Issue 1 – Window discovery

This document summarises the solution for discovering Mu Online windows and extracting character information.

### Problem

The bot needs to know which game windows correspond to which configured characters.  There may be up to five game clients open at once, and the windows may overlap.  The discovery task must detect each window, extract the character name and other metadata from the window title, and map it to the configuration.

### Solution

1. **Enumerate windows.**  Use Win32 APIs (`EnumWindows`, `GetWindowText`, `GetWindowThreadProcessId`, `GetWindowRect`) to iterate over all top‑level windows.  Filter those whose titles contain the game prefix (e.g. “Asteria MU – Powered by IGCN”).
2. **Parse the title.**  The game window title contains the character name, level, master level and reset count in a standard format:

   ```
   Asteria MU - Powered by IGCN - Name: [PPMG] Level: [400] Master Level: [1350] Resets: [3]
   ```

   Use a regular expression to extract the values from the title.  Store them in a structure along with the window handle and position.
3. **Match to configuration.**  For each configured character, find a window whose parsed `display_name` matches.  Assign that window to the character’s runtime record.  If multiple windows match the same name, log an error.  If a configured character has no matching window, log a warning and skip the character.
4. **Visibility and state.**  Record whether the window is visible or minimised (`IsWindowVisible`, `IsIconic`).  Minimized windows may not capture properly; the capability test plan (Issue 7) will clarify this.
5. **Discovery command.**  Provide a CLI command to run the discovery in isolation.  It outputs a table of windows and saves a JSON snapshot (e.g. `discovered_windows.json`) for debugging.  This helps ensure that windows are detected before starting the full automation.

### Key points

- Do **not** use OCR on the title bar; the Win32 APIs provide the text directly.
- Do **not** persist window handles across sessions; handles change when clients are restarted.
- The configuration file stores only the character names and flags; all dynamic information is discovered at runtime.
- Log parse errors clearly if the title does not match the expected format, and skip such windows.