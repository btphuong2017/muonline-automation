# Capability Test Checklist

This checklist summarises the capability tests described in Issue 7.  Each test determines whether a particular feature can operate in background, minimised or requires the window to be active.  Testers should record results and evidence (screenshots/logs) for each capability and populate a capability matrix.

## Test List

1. **Window Discovery Baseline** – Verify enumeration and parsing of game windows.
2. **Foreground Capture** – Confirm that capturing the active game window yields the correct image.
3. **Background Capture** – Test capturing overlapped windows; record whether frames are real time or stale.
4. **Minimised Capture** – Test capturing windows that are minimised; note if this is unsupported.
5. **Foreground Hotkey** – Ensure hotkeys (e.g. Ctrl+T) work when the window is focused.
6. **Background Hotkey** – Test sending hotkeys to non‑active windows; verify responses.
7. **Foreground UI Click** – Click UI elements (event tabs, buttons) when the window is active and confirm actions.
8. **Background UI Click** – Attempt to click UI elements in non‑active windows and observe behaviour.
9. **Foreground NPC Hover Indicator** – Hold ALT and hover NPC to confirm indicator detection when focused.
10. **Background NPC Hover Indicator** – Check whether the hover indicator appears when the window is not active.
11. **Foreground ALT + Left Click NPC** – Verify that ALT + click opens NPC dialog when focused.
12. **Background ALT + Left Click NPC** – Attempt NPC interaction without focusing the window.
13. **Popup Handling Background** – Test clicking pop‑up buttons (Enter Varka, Enter dungeon) in non‑active windows.
14. **Helper Toggle Background** – Determine whether Varka Helper can be toggled without focus.
15. **Timer Monitoring Background** – Verify that the timer panel updates and can be parsed in background.
16. **Finish Dialog Background** – Test detection and Exit button clicks for the finish dialog without focus.
17. **Multi‑Window Safety** – Ensure that input and capture operations target the correct window; check for cross‑window interference.
18. **Foreground Focus‑Switch Stability** – Rapidly switch focus among windows and perform actions to confirm stability.

## Recording Results

For each test, testers should record:

- **Mode**: background, minimised, foreground.
- **Result**: pass, partial, fail.
- **Evidence**: path to screenshot or log demonstrating the outcome.
- **Notes**: observations (e.g. input lag, stale images, mis‑targeted clicks).

Populate the capability matrix once all tests are complete.  The matrix guides the selection of background or foreground execution modes for each step of the Varka flow.