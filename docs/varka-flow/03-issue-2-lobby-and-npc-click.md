## Issue 2 – Lobby detection and NPC click

This document covers how the bot determines that a character is in the Varka lobby and how it reliably finds and clicks the Varka NPC.

### Detecting the lobby

Lobby detection uses multiple signals to avoid false positives:

1. **Map label.**  In the top left of the screen, the game displays the current map name (e.g. “Waiting Room for Imperial Fort”).  A template match on this label provides the strongest signal for being in the lobby.
2. **Absence of dungeon timer.**  The event timer panel in the bottom right is only visible inside the event map.  Its absence supports the hypothesis that the character is in the lobby.
3. **Absence of finish dialog.**  If the finish dialog is open, the character is at the end of an event, not in the lobby.
4. **Screen stability.**  After teleporting between maps, the screen takes a moment to update.  The bot waits for several consecutive frames where the lobby signals remain consistent before confirming `LOBBY_READY`.

Do not rely on quest panels or chat messages as primary signals; they can be inconsistent.  Only move on to NPC search once `LOBBY_READY` is confirmed.

### Searching for the NPC

Finding the NPC in a crowded lobby is challenging because other players may obscure it and the spawn position varies.  The bot uses a layered strategy:

1. **Candidate cache.**  For each character the bot stores a limited list of previous click points that successfully selected the NPC.  These points are tested first on subsequent runs.  Each candidate is verified via hover indicator before clicking.
2. **Partial templates.**  Templates of distinct features of the NPC (e.g. shoulders, weapons) are matched within a search region that excludes static UI elements.  Each match yields a new candidate point.
3. **Grid search.**  If no templates produce candidates, the bot explores a grid of positions in the likely NPC region.

Each candidate must pass the hover indicator test before a click is attempted.

### Hover indicator test

Holding Alt and moving the mouse over the NPC causes a small icon to appear above the NPC.  The bot uses this indicator to verify that the candidate is actually an NPC and not a player or the ground.  The test proceeds as follows:

1. Hold Alt.
2. Move the cursor to the candidate point.
3. Capture a small region around the cursor.
4. Match a template of the hover indicator within the captured region.
5. If found, the candidate is accepted; otherwise it is rejected.

### Clicking the NPC

Only after the hover indicator has been detected does the bot perform the click:

1. Hold Alt.
2. Left‑click the verified candidate point.
3. Release Alt.
4. Wait for the NPC dialog to appear within a timeout.  If the dialog appears, the click is considered successful; the candidate’s success count is updated and the point is added to the cache.  If not, the failure count is incremented and the next candidate is tested.

### Retry policy

The NPC search state retries up to three times.  If, after three attempts, the NPC cannot be selected, the bot logs an error, stores a screenshot and moves to the next character.  It does not wander the character around looking for the NPC.

### Summary

- Use a multi‑signal approach to confirm the lobby.  Do not start NPC search until the lobby is stable.
- Search for the NPC using cached click points, partial templates and grid scanning.  Test each candidate with the hover indicator before clicking.
- Hold Alt while clicking the NPC to ignore other players.  Wait for the NPC dialog to confirm a successful click.