# Manual Verification Guide

Some interactions cannot be fully automated or may change after game updates.  This guide provides checklists for manual testers to verify key behaviours of the Varka automation bot.  Follow these steps in a controlled environment using test accounts.

## 1. Lobby Detection and NPC Interaction

1. Place a character in the lobby and start the bot.
2. Observe whether the bot waits until the screen is stable before detecting the lobby label.
3. Watch the bot move the cursor and hover candidate points; verify that the hover indicator appears before clicking.
4. Ensure that the bot uses ALT + click and opens the NPC dialog.  Confirm that it does not click randomly.

## 2. Popup Handling

1. After the NPC dialog opens, confirm that the bot clicks the “Enter Varka” button.
2. Wait for the second pop‑up; verify that the bot clicks the “Enter” button without interacting with level or element options.
3. In case of a daily limit dialog, confirm that the bot recognises it, clicks OK and marks the character as done.

## 3. Event Entry and Helper

1. When the event map loads, note whether the bot waits a short time before attempting to open the Varka Helper.
2. Check that the bot clicks the helper only when the Play icon is visible and does not toggle it off when the Pause icon is displayed.
3. Confirm that the helper begins running and the character starts moving automatically.

## 4. Timer Monitoring and Alerts

1. Observe the timer panel as the event progresses.
2. Verify that the bot parses the countdown and monster count correctly.
3. When the timer drops below 30 seconds and monsters remain, ensure that a critical alert is printed in the terminal dashboard.

## 5. Event Completion

1. At the end of the event, watch for the “event cleared” dialog.
2. Confirm that the bot clicks the Exit button promptly.
3. If the map returns to the lobby without a dialog, verify that the bot still counts it as a success.
4. Check that the completed count increments appropriately and that the character enters the next run or finishes when the limit is reached.

## 6. Multi‑Character Scheduling

1. Run the bot with multiple characters.  Observe that the bot interleaves states (entering lobbies, clicking NPCs, opening helpers) rather than blocking on one character.
2. Ensure that the terminal status dashboard updates each character’s state, run count, retry count and alerts.
3. Confirm that characters marked as `DONE_BY_GAME_LIMIT` or `DONE_MAX_RUNS` are skipped in subsequent loops.

Manual verification complements automated tests by catching UI changes and ensuring user‑visible behaviours are correct.