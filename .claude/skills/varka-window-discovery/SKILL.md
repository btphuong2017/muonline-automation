---
name: varka-window-discovery
description: Implements ONLY Issue 1 (Gate 1). Builds a CLI that enumerates Mu Online windows, parses the title (name/level/master/resets), maps to configured characters, and prints a table plus saves a JSON snapshot.
---

# varka-window-discovery

## Scope
Window discovery only. No capture, no input, no flow logic. Output is the discovery table and a JSON snapshot.

## Required docs to read
- `docs/varka-flow/02-issue-1-window-discovery.md`
- `docs/automation/01-window-management.md`
- `docs/architecture/04-config-and-runtime-data.md`

## Allowed outputs
- Module under `src/<package>/windows/` with:
  - `enumerate_game_windows()` — returns a list of `GameWindowInfo` (hwnd, pid, title, parsed name/level/master/resets, rect, visible, minimised).
  - Title parser using a regex sourced from config (default mirrors the doc example: `Asteria MU - Powered by IGCN - Name: [...] Level: [...] Master Level: [...] Resets: [...]`).
- A character-config loader that reads a YAML/JSON file (default path `config/characters.yaml`).
- A matcher that joins enumerated windows to configured characters by display name; logs duplicates and unmatched configs.
- CLI: `python -m <app> scan-windows [--config <path>] [--json <out>]`.

## Forbidden outputs
- Any input sending or screen capture.
- Any persisted window-handle store across sessions.
- OCR on the title bar — Win32 returns the text directly.
- Modifying or focusing any window.

## Required verification command
```
python -m <app> scan-windows
```
Expected output:
- A table with columns: `display_name | level | master_level | resets | hwnd | pid | rect | visible | minimised`.
- One row per discovered Mu Online window.
- A JSON snapshot saved to `.claude/logs/discovered_windows.json`.
- Clear log lines for: parse failures, duplicate matches, configured characters with no window.

## Stop condition
After the user confirms the table shows the correct number of windows and correct character names/levels/etc., STOP. Do not proceed to Gate 2 without explicit user confirmation.
