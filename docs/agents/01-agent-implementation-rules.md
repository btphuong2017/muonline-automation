# Agent Implementation Rules

These rules provide guidance to developers implementing the automation agents for the Varka bot.  Agents should adhere to these rules to ensure consistency, safety and maintainability.

## 1. Follow the Single‑Responsibility Principle

Each agent should focus on a specific aspect of the automation:

- **Vision agent:** captures images, performs template matching and returns detection results.
- **Input agent:** sends mouse and keyboard commands through the selected backend (foreground/background/hybrid).
- **State machine agent:** evaluates the current state and decides the next action.
- **Scheduler agent:** orchestrates multiple characters, manages retries and logs.

Avoid coupling different concerns in the same module; this allows easier testing and replacement of backends.

## 2. Respect the Capability Matrix

Agents must consult the capability matrix generated from Issue 7 before choosing execution modes.  If a capability is marked as `fail` in background mode, the agent must switch to foreground for that step.  Never send background clicks or hotkeys to a window if the matrix indicates it will not work.

## 3. Always Verify Before Acting

For any detection or click:

- Verify screen stability before reading.
- Verify templates with confidence thresholds.
- Verify hover indicators before clicking NPCs.
- Verify helper state before toggling.
- Verify pop‑ups are present before pressing buttons.

Never click blindly based on stale coordinates.  Use anchor points and ROI detection to compute relative offsets.

## 4. Limit Retries and Log Everything

Each state should have a maximum of three retries.  On each retry, refresh the screen and re‑detect rather than repeating the same action blindly.  When retries exceed the limit, create a detailed log entry and either mark the character for retry‑later or treat it as done according to the error policy.

All actions, detections and errors must be logged with timestamps, character names and context.  Logs should also record the current run count and state for debugging.

## 5. Use Configuration and Templates

Do not hard‑code coordinates or thresholds.  Load ROI definitions and template paths from configuration files or constants defined in the `vision` and `automation` modules.  This allows adjustments without modifying code.

## 6. Handle Interrupts and Fatal Errors

Detect global interrupts (e.g. NEED_USER_LOGIN, window loss) at every safe point in the loop.  If a fatal condition occurs, stop the entire session, clean up resources and notify the user.  Do not continue operating on other characters in an inconsistent state.

## 7. Avoid Race Conditions

When switching focus between windows or sending input concurrently, ensure that operations complete before proceeding.  Use small delays where necessary and check that the active window is correct after focusing.  Do not assume that background operations always succeed; verify results.

## 8. Keep Human Safety in Mind

Bot actions should never harm the user’s system.  Do not move or close windows unrelated to the game.  Provide an emergency stop mechanism (e.g. a global hotkey or a key press in the terminal) so that the user can stop the bot immediately.  Respect user settings and do not modify them without consent.

## 9. Document and Comment

Include docstrings and comments to explain complex logic, assumptions and workarounds.  Keep inline comments brief and relevant.  When implementing new features or addressing edge cases, update the corresponding documentation in `docs/` and adjust templates or ROI definitions as needed.