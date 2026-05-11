## Capture Backends

The bot needs to capture the contents of each game window to run template matching and detect UI elements.  Because multiple windows may be overlapped or not active, it supports more than one capture method.

### MSS screen capture

* The primary backend uses **mss** to capture screen regions.  This method grabs a portion of the desktop at high speed and is sufficient when the target window is in the foreground and unobscured.
* Screen capture is fast and works with hardware overlays such as DirectX, but it cannot capture windows that are behind others or minimised.
* The vision layer defines ROIs based on the window rectangle and crops the captured image to reduce processing time.

### Window capture via Windows API

* To capture overlapped windows, the bot can call the Win32 `PrintWindow` function via **pywin32**.  This captures the contents of a specific window by handle, regardless of whether it is active or obscured.
* Some game clients may return a black image when captured via `PrintWindow` if they use certain DirectX rendering modes.  If this happens, the bot falls back to screen capture and may request that the game window be brought to the foreground.
* The capture backend is selected at runtime based on a capability test (see issue 7).  If `PrintWindow` fails or the frame is stale, the bot uses screen capture.

### Handling minimised windows

* Capturing minimised windows is not supported by most methods.  When a window is minimised, both `PrintWindow` and screen capture generally produce a black frame.
* Therefore the bot requires that windows remain visible (not minimised) while the bot is running.  The scheduler ensures that windows are not minimised.

### ROI management

* For efficiency, capture backends receive only the rectangular region of interest (ROI) relevant to the current detection task: the lobby label, timer panel, helper icon, dialog, etc.
* The ROI coordinates are defined relative to the client area of the game window and are stored in the configuration.  This ensures that detection scales with the window size.
* ROIs can be nested: a high‑level anchor is detected first, then a smaller ROI is extracted for the button or text.

### Switching capture methods

* The orchestrator can switch capture methods on a per‑capability basis.  For example, timer monitoring may run in background with `PrintWindow`, whereas NPC hover detection may require the window to be in the foreground with screen capture.
* The capability test plan (issue 7) determines which capture methods are reliable for each step.
