## Template assets list

This file lists the visual templates that need to be prepared for the Varka automation.  Templates are grouped by use case.  Each entry should exist as a PNG file in the assets directory along with its recommended ROI and confidence threshold.  Agents should not change template names without updating the configuration.

### Lobby and map detection

* `lobby_label.png` – The *Waiting Room for Imperial Fort* text or background in the top‑left corner used to confirm that the character is in the lobby.
* `event_map_label_varka.png` – The *Varka* or equivalent label in the event map used to confirm that the character has entered the dungeon.
* `timer_panel_anchor.png` – A consistent part of the timer panel frame to detect the presence of the dungeon timer.  The content inside the timer will vary.
* `finish_dialog_anchor.png` – The frame of the event clear dialog.
* `finish_dialog_exit_button.png` – The Exit button in the event clear dialog.

### NPC detection and interaction

* `npc_partial_body*.png` – Multiple small templates capturing distinctive parts of the NPC’s model (shoulder, weapon, emblem).  The asterisk denotes an index or description.
* `hover_indicator.png` – The indicator icon that appears when the cursor hovers over the NPC while `Alt` is held.
* `npc_dialog_title.png` – The title text of the NPC dialog (“Fortress of the Imperial Guard”).

### Pop‑up 1 (NPC dialog)

* `popup1_enter_varka_button.png` – The `Enter Varka` button in the first NPC pop‑up.
* `popup1_leave_varka_button.png` – The `Leave Varka` button (used only to avoid clicking it by mistake).
* `popup1_close_button.png` – The close button in the first pop‑up.

### Pop‑up 2 (Entrance selection)

* `popup2_enter_button.png` – The `Enter` button used to join the event.
* `popup2_cancel_button.png` – The `Cancel` button (to avoid accidental clicks).
* `popup2_anchor.png` – An area of the pop‑up (e.g., its frame) that identifies it when template matching.

### Event window (enter lobby flow)

* `event_window_header.png` – The header of the event window (“Events Info” or similar) to detect that the window is open.
* `event_map_tab.png` – The Event Map tab in the event window.
* `imperial_guardian_list_item.png` – The list entry for the *Imperial Guardian* event.
* `imperial_guardian_content_anchor.png` – A distinctive part of the content area that appears once Imperial Guardian is selected.
* `event_enter_button_enabled.png` – The Enter button when it is enabled (light colour).
* `event_enter_button_disabled.png` – The Enter button when disabled (greyed out).

### Helper and timer

* `helper_play_icon.png` – The play (start) icon for the Varka helper indicating it is not running.
* `helper_pause_icon.png` – The pause icon for the Varka helper indicating it is running.
* `timer_mode_standby.png` – Template identifying the standby timer mode (e.g., “Standing by”).
* `timer_mode_time_left.png` – Template identifying the active timer mode (“Time Left” or similar).
* `timer_mode_exit_waiting.png` – Template identifying the exit waiting mode.
* `timer_digit_0.png` to `timer_digit_9.png` – Templates for each digit to parse the countdown.  Additional templates for `colon` (`:`) and parentheses may be needed.

### Limit and error dialogs

* `daily_limit_dialog.png` – A frame or title identifying the dialog that states the daily entrance limit has been exceeded.
* `daily_limit_ok_button.png` – The OK button in the daily limit dialog.

### Finish dialog

* `event_cleared_text.png` – A text or emblem in the event cleared dialog to confirm that the event has been completed.

The list above may evolve as new UI elements are encountered.  Each template should be stored under an organised path (e.g., `assets/templates/lobby/`, `assets/templates/npc/`, etc.) and referenced through configuration files so the code remains data driven.
