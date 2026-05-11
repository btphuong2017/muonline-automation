## Configuration and runtime data

The bot relies on configuration files and runtime data structures to operate correctly.  This document summarises the key pieces of data.

### Character configuration

A YAML/JSON configuration file defines the list of characters and their properties.  Each entry includes:

* `display_name`: identifies the character window based on the window title.
* `enabled`: determines whether the bot should run this character in the current session.
* `level` (optional): provides contextual information but does not change behaviour.

Only enabled characters are processed; others are skipped.

### Template configuration

Template files are used for image recognition.  They should be stored under a dedicated `assets/templates/` folder.  The configuration lists each template with its path, associated ROI and threshold.  For example:

```yaml
templates:
  lobby_label:
    path: assets/templates/lobby/label.png
    roi: [10, 50, 200, 30]  # x, y, width, height relative to client area
    threshold: 0.85
  npc_hover_icon:
    path: assets/templates/npc/hover_icon.png
    roi_size: [80, 80]
    threshold: 0.80
  enter_varka_button:
    path: assets/templates/popup/enter_varka.png
    roi: [400, 300, 200, 100]
    threshold: 0.90
```

ROIs should be tuned for the game’s window resolution.  Thresholds control how confident the template match must be to be considered present.

### Runtime caches

During a session the bot maintains caches of dynamic information:

* **Candidate click points** – For each character, the bot stores a limited list of previous NPC click points that worked.  These points are tested first on subsequent runs.  Cached points have metadata (success count, fail count, last use) and are verified via hover indicator before being clicked.
* **Success history** – A longer list of successful click locations with timestamps.  Used for analysis and debugging.
* **Retry timers** – Timestamps controlling when a character can retry a state after repeated failures.
* **Critical events** – Timestamps for when to issue alerts (e.g. repeating a time‑critical alert every few seconds).

Runtime data is kept in memory and reset at the start of each session.

### Logging configuration

Logging destinations and levels are configured separately.  The recommended setup is:

- A per‑character log file with details of each state entry, action, result and error.
- A session log summarising high‑level events (e.g. which characters succeeded or failed and why).
- Screenshots saved only on errors to aid troubleshooting.

The logging module should allow toggling verbosity without changing the core logic.