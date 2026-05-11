## Project requirements

The automation bot must satisfy the following high‑level requirements:

- **Game environment.**  The target game is Mu Online running on Windows.  Up to five game clients may be open simultaneously.  All automation happens through UI interaction; the bot does not read or modify game memory or packets.
- **Character list.**  The bot reads a configuration of characters, with a display name and enabled flag.  At runtime it maps each configured character to a game window via the window title, which includes name, level, master level and reset count.
- **Event scope.**  The first supported action is the “Varka” (Imperial Fort) event.  Each character may run the event up to ten times per session or until the game reports that the daily limit has been reached.  Once at the limit, that character is skipped for the remainder of the session.
- **Flow logic.**  The bot must automatically:
  1. Discover game windows and parse character info.
  2. Ensure each character is in the lobby.  If not, open the Event window (Ctrl + T), select *Imperial Guardian* and click *Enter* to travel to the lobby.
  3. Detect the lobby and NPC; click the NPC with Alt + left click; handle two pop‑up dialogs to enter the event.
  4. Confirm the character has entered the event map and start the official Varka Helper.
  5. Monitor the event timer.  If the time falls below 30 seconds while monsters remain, print an urgent message.  Otherwise, wait for the event to finish and return to the lobby.
- **Multiple characters.**  The bot cycles through characters in a cooperative manner: while a character is auto‑running the event, the bot works on bringing another character into the event.  It does not wait for one character to finish before servicing the next.
- **Retries and errors.**  Each state in the flow may retry up to three times.  If a state fails after all retries, the bot logs the error, skips that character and moves on.  When the game client is lost (e.g., crash), the bot stops and waits for the user to log in again.
- **Alerts.**  The bot does not beep or play sounds.  Critical conditions—such as timer under 30 seconds with monsters remaining or the need for manual login—are reported via terminal messages.

This document set expands on these requirements in detail and provides implementation guidance for each module.