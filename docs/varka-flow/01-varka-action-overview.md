## Varka action overview

The Varka action automates participation in the *Imperial Guardian* event (also known as Varka) in Mu Online.  For each enabled character the bot performs up to ten runs per session or until the daily entry limit is reached.  A run consists of:

1. **Getting to the lobby.**  If the character is not already in the waiting room (“Waiting Room for Imperial Fort”), the bot opens the Event window (Ctrl + T), selects *Imperial Guardian* and clicks *Enter* to travel to the lobby.
2. **Finding and clicking the NPC.**  In the lobby, the bot detects the presence of the Varka NPC.  It uses a candidate search with hover indicators to find a reliable click point, then holds Alt and left‑clicks the NPC.  This opens the NPC dialogs.
3. **Handling NPC dialogs.**  The bot handles two pop‑up dialogs:
   - **Popup 1:** The dialog “Fortress of the Imperial Guard” with buttons *Enter Varka*, *Leave Varka* and *Close*.  The bot clicks *Enter Varka*.  If a dialog appears stating that the daily entrance limit has been exceeded, the character is marked complete for the session.
   - **Popup 2:** A confirmation dialog.  The bot ignores the *Monster Element* and *Level* and clicks *Enter*.
4. **Loading the event map.**  The bot waits for the event map to load, recognising it by the Varka map label and the timer panel.  It waits for the screen to stabilise before proceeding.
5. **Starting the helper.**  Upon entering the event, the bot must click the Varka Helper (Play icon) immediately if the helper is off.  It verifies that the helper changes to the pause icon.  If the helper is already running, no action is taken.
6. **Monitoring the event.**  The bot does not control combat.  It monitors the event timer.  When the mode is “Time Left” and the time is under 30 seconds while monsters remain, it prints a critical alert on the terminal.  Otherwise it waits until the event finishes.
7. **Finishing and returning to the lobby.**  When the event is cleared, a finish dialog appears.  The bot clicks *Exit* to return to the lobby.  If the map returns to the lobby without showing the finish dialog, the run is still counted as success.  The completed count is incremented.

The orchestrator interleaves these steps across characters so that while one character is running the event, the bot advances other characters.  The flow stops when all characters have reached the maximum number of runs or the daily limit.