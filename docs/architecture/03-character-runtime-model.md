## Character runtime model

Each configured character has an associated runtime record created at the start of the session.  This record stores the dynamic state of the character during automation.

### Character configuration

Static configuration fields are defined in a YAML/JSON file:

- **`display_name`** – The name appearing in the Mu Online window title.  Used to match the configuration to a window.
- **`enabled`** – A boolean flag.  Disabled characters are ignored for the session.
- **`level`** – Optional; provides context but does not affect automation logic.

### Runtime fields

At runtime the bot maintains a structure such as:

- `window` – The handle and metadata of the current game window assigned to this character.
- `current_state` – The state of the Varka FSM (e.g. `CHECK_LOBBY`, `MONITOR_EVENT`).
- `run_id` – The current run index (1 to 10).
- `completed_count` – Number of successful runs completed.
- `max_runs` – Usually 10; may be set to zero when the daily limit is detected.
- `state_retry_count` – Counter of how many times the current state has been retried.
- `next_check_at` – Timestamp when the orchestrator should check this character again (used for wait states).
- `helper_status` – `OFF`, `ON` or `UNKNOWN` based on icon detection.
- `timer_status` – Parsed timer information (mode, seconds left, monsters remaining) if in event map.
- `retry_later_until` – Timestamp for when to retry a failed state (cool‑down between attempts).
- `last_error` – Last error message or code.
- `need_user_login` – Flag set when the game window disappears (crash/disconnect); the orchestrator stops and waits for the user.

The orchestrator updates these fields whenever a state returns a result.  They are not persisted across sessions.