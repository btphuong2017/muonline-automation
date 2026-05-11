## High‑level architecture

The automation system is composed of several loosely coupled components.  Each component has a clear responsibility and communicates with others through well‑defined interfaces.  This separation allows individual parts to be improved or replaced without rewriting the whole system.

### Window discovery

The discovery module enumerates all top‑level Windows GUI windows, filters those belonging to Mu Online, and extracts character metadata from the window title.  It produces a list of `GameWindowInfo` objects containing the window handle, process ID, title, position and parsed character fields (display name, level, master level and resets).  The discovery module runs at start‑up and on demand if windows change.

### Vision layer

The vision layer captures screen or window images and performs image recognition.  It handles:

- Defining regions of interest (ROIs) such as lobby labels, NPC icons, dialogs, helper icons, timer panels and finish pop‑ups.
- Performing template matching within an ROI to locate UI elements.
- Parsing digits or text in the timer panel using either OCR or digit templates.
- Providing multi‑signal detection (combining several signals to determine states such as `LOBBY_READY` or `EVENT_MAP_READY`).

### Input layer

The input layer sends mouse and keyboard events.  It abstracts foreground versus background interactions and supports different back‑ends (e.g. pyautogui for foreground, Win32 messages for background).  It also manages key modifiers (such as Alt) and ensures that clicks are only performed after verifying the presence of expected UI elements.

### Flow/state machine layer

Each high‑level action (e.g. Varka event) is implemented as a state machine.  States represent discrete steps in the process (e.g. `CHECK_LOBBY`, `FIND_NPC`, `HANDLE_POPUP_1`, `WAIT_EVENT_MAP_LOADING`, `START_HELPER`, `MONITOR_EVENT`, `RETURN_LOBBY`).  Transitions between states depend on vision signals, timers and retries.  Each state returns a result indicating success, need to retry, skip, or terminal outcome (done by limit or fatal error).

### Orchestrator

The orchestrator manages multiple characters and coordinates the state machines.  It maintains a runtime record for each character (current state, run count, retry counts, next check time).  The orchestrator operates in a cooperative manner: it iterates over characters, performs only the next needed step for each, and leverages idle time (e.g. when a character is auto‑running) to work on other characters.  It stops when all characters have finished or when a fatal condition (e.g. game crash) is detected.

### Configuration and assets

The system is configured by YAML/JSON files containing character definitions (display name, enabled flag and optional level), ROI definitions, template paths and thresholds, retry limits and timeouts.  Template image assets are stored in a dedicated folder and referenced by the vision layer.  Runtime caches (e.g. candidate points for NPC clicks) are kept in memory for the session.

### Logging and debugging

Logging is critical for diagnosing automation behaviour.  Each state transition, retry, error and success is recorded with timestamps.  Per‑character logs capture actions and decisions.  Screenshots are saved when errors occur.  A summary of each session’s outcomes is reported at the end.