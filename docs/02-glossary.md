## Glossary of terms

This glossary defines key terms used throughout the documentation.

- **Character** – A specific player avatar within Mu Online.  Each character has a display name and is associated with a specific game window.
- **Window discovery** – The process of enumerating all top‑level Windows GUI windows, finding those that correspond to Mu Online clients, and extracting the character name, level, master level and resets from the window title.  Uses Win32 APIs rather than OCR.
- **Lobby** – The “Waiting Room for Imperial Fort” map where characters queue before entering the event.  Characters must be in the lobby to click the Varka NPC.
- **Varka NPC** – The non‑player character in the lobby that provides access to the event.  The bot clicks this NPC via Alt + left click to open the Varka dialogs.
- **Popup 1** – The first dialog after clicking the NPC, containing the button “Enter Varka”.  If the character has remaining entries, clicking this button leads to Popup 2.
- **Popup 2** – The dialog that appears after Popup 1, asking for confirmation.  The bot ignores Monster Element and Level fields and clicks the button “Enter” to enter the event.
- **Event map** – The Varka dungeon where characters fight monsters.  Distinguished by a timer panel labelled “Round X (Zone Y)” in the lower right and a map label for “Varka” in the upper left.
- **Helper** – The official Mu Online auto‑combat feature.  It has a play/pause icon in the top left of the screen.  The bot must click the play icon after entering the event map and must not click the pause icon once the helper is running.
- **Run** – A complete cycle of entering the lobby, starting the event, letting the helper fight, finishing the event and returning to the lobby.  Each character may complete a maximum of ten runs per session or until the daily entrance limit is reached.
- **Retry** – Attempting a state again after a failure.  Each state is retried up to three times before the character is skipped for the session.
- **Done by limit** – A terminal state for a character when the game reports that the daily entrance limit has been exceeded.  The bot stops running that character for the session and counts it as complete.