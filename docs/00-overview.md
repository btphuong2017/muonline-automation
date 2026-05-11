## Project Overview

This repository documents the design of a Windows automation bot for the **Varka** event in *Mu Online*.  The goal is to build a command‑line tool that can control up to five game clients, bringing each character into the event lobby, entering the event map, enabling the in‑game *Varka Helper*, waiting for the run to finish and returning to the lobby.  Everything must be done through the visible user interface – **no memory reading or packet manipulation** is allowed.  The bot uses a state machine to track progress, a scheduler to coordinate multiple characters and a vision layer to detect UI elements.  Logging and a terminal dashboard provide real‑time feedback.

### Features

* **Multi‑character support:** up to five game windows discovered via their titles.  Characters are matched by display name and can be enabled or disabled individually.
* **State machine flow:** the bot goes through well‑defined states: check whether the character is in the lobby, enter the lobby if necessary, click the event NPC using `ALT + Left Mouse`, handle two pop‑ups, detect that the character has entered the event map, open the Varka Helper, monitor the timer and finish when the event is cleared or the daily limit is reached.
* **Cooperative scheduling:** characters share CPU time.  The orchestrator processes a short step for one character, then switches to the next, rather than waiting for a full run to complete.  This maximises throughput when the helper is running.
* **Vision driven:** the bot uses template matching within regions of interest (ROIs) to detect labels, buttons, timers, helper icons and dialogs.  OCR is avoided unless absolutely necessary; partial templates and multiple signals improve robustness.  Successful click positions are cached to accelerate subsequent runs.
* **Retry and error handling:** each state is retried up to three times.  Recoverable errors (e.g. a dialog not detected) trigger a limited retry; non‑recoverable errors (e.g. no game window) stop the character.  If the game reports that the daily limit has been reached, the character is marked done without error.
* **Extensible architecture:** the core modules include window discovery, vision, input, automation, state machine, orchestrator, configuration and logging.  Additional actions (e.g. elite hunting) can reuse the same structure.

### Not in scope

* **No game hacking:** the bot must not read or write game memory, modify the network protocol or hook DirectX.  All actions are performed via the official UI.
* **No GUI application:** the MVP uses a terminal dashboard to display status.  A graphical interface may be added later, but it is outside the current scope.
* **No persistent state between sessions:** runtime data such as window handles, cached click points and completed counts are kept in memory.  When the program exits, these are discarded.  Daily limits reset each day.
