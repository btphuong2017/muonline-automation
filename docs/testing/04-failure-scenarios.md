# Failure Scenarios

This document outlines common failure scenarios that the Varka automation should handle gracefully.  Identifying these scenarios helps testers verify that error handling and retry policies are correctly implemented.

## 1. Window Loss or Game Crash

- **Symptoms:** The game window disappears or the process terminates during execution.  Capture calls fail or return empty images.
- **Handling:** Detect via window enumeration or capture failure.  Set `NEED_USER_LOGIN` and stop the bot.  Alert the user to restart the game.  Do not retry automatically.

## 2. Popup Buttons Missing

- **Symptoms:** After clicking the NPC, the expected “Enter Varka” or “Enter” buttons do not appear in the pop‑ups.  Templates return no match.
- **Handling:** Retry detection and clicking up to three times.  If still missing, log an error and skip the character for this run.  Consider that the event may not be available.

## 3. NPC Hover Indicator Never Detected

- **Symptoms:** Despite scanning the lobby and hovering candidate points, the hover indicator for the NPC is never found.  Clicking at random positions would cause the character to move incorrectly.
- **Handling:** Retry candidate selection and hover three times.  If unsuccessful, save a screenshot, log a `npc_not_found` error and put the character into the retry‑later queue.  Do not click blindly.

## 4. Helper Toggle Error

- **Symptoms:** The helper toggle cannot be detected reliably; repeated clicks might toggle the helper on and off.  The helper state may remain unknown.
- **Handling:** Detect the helper icon state before clicking.  If state remains unknown after retries, log an error and skip the helper step.  Alert the user to check the UI manually.

## 5. Timer Parsing Failure

- **Symptoms:** The timer panel is visible but parsing the time or monster count fails repeatedly (e.g. due to an update to the UI font or layout).
- **Handling:** Log a `timer_parse_failed` error but continue monitoring other states.  Alert the user that countdown alerts may not function.  Consider updating digit templates.

## 6. Event Does Not Start

- **Symptoms:** After entering the event map, the helper is started but the “Standby” state never transitions to “Time Left.”
- **Handling:** Monitor for a reasonable timeout (e.g. 2–3 minutes).  If no progress, log an error, count the run as a failure and move to the next character.

## 7. Event Clears Without Popup

- **Symptoms:** The timer expires and the character is returned to the lobby without the event cleared popup appearing.
- **Handling:** Treat this as a successful run (Issue 6).  Increment completed_count by 1 and log that the popup was missing.

## 8. Daily Limit Not Detected

- **Symptoms:** The daily limit dialog appears but is not detected due to missing template or changed text.
- **Handling:** If the bot retries NPC click three times and continues to receive pop‑ups without proceeding, log an error and count the character as done by limit.  Capture a screenshot for later template updates.

## 9. Multi‑Window Interference

- **Symptoms:** Input intended for one game window affects another (e.g. clicks are applied to the wrong window, or timers are parsed from the wrong screen).
- **Handling:** Ensure that all capture and input operations reference the correct window handle and client coordinates.  If interference is detected, stop the bot and review the capability matrix.

Proper handling of these scenarios improves robustness and user trust in the automation tool.