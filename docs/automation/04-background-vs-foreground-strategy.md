## Background vs Foreground Strategy

Different tasks within the Varka flow may or may not work when the game window is not active.  Issue 7 defines a detailed capability test plan to determine which operations succeed in **background** (window‑targeted) mode and which require the window to be **foreground**.  Based on the results, the bot adopts a **hybrid** strategy:

### General rules

* **Background by default:** tasks that involve simple UI interactions or monitoring (e.g. sending `Ctrl + T` to open the Event Window, clicking pop‑up buttons, monitoring timers and finish dialogs) are attempted in background mode when the capture and input backends support it.
* **Foreground when needed:** tasks that rely on hover indicators, `ALT` modifiers or subtle timing – notably finding and clicking the NPC – require the window to be focused.  The bot brings the window to the foreground, performs the action, then yields control to the scheduler.
* **Minimised windows are not supported.**  Capture and input generally fail when windows are minimised.  The bot ensures that each game window stays visible; overlapped windows can still be captured with `PrintWindow` if supported.

### When to focus the window

The orchestrator focuses a window before performing any of the following:

* **NPC hover and click:** `ALT + hover` must be seen by the game; background hover does not produce the indicator in most tests.
* **Helper toggle:** verifying the helper icon and clicking it safely is more reliable when the window is active.
* **Timer parsing fallback:** if background capture fails to update the timer panel, the bot focuses the window for a quick foreground capture.

### When background works

Tasks that typically succeed in background mode include:

* **Window discovery:** enumerating windows and parsing their titles does not require focus.
* **Hotkeys:** sending `Ctrl + T` or other hotkeys via `SendMessage` can open the Event Window without focusing the window (subject to capability test results).
* **Dialog buttons:** clicking “Enter Varka” and “Enter” in the two pop‑ups often works through window‑targeted clicks.
* **Timer monitoring:** capturing the timer panel and parsing the countdown generally works in background when `PrintWindow` returns a fresh frame.  Foreground fallback is used if frames are stale.
* **Finish detection:** detecting the finish dialog or lobby label can run in background, as these are large, static UI elements.

### Hybrid fallback

* If a background action fails, the orchestrator marks the capability as unsupported and automatically retries in foreground.  The capability matrix, produced as part of issue 7, configures which mode to use for each step.
* For example, if `Ctrl + T` does not open the Event Window in background, the bot focuses the window and sends the hotkey in foreground.
* A task is never attempted indefinitely in background mode; after a small number of failures, the bot switches to foreground to avoid deadlocks.

### Manual override

* The user can disable background mode entirely in the configuration.  This forces the bot to run all interactions in the foreground.  It is useful on systems where background capture or input is unreliable.

### Summary

The hybrid strategy achieves the best of both worlds: tasks that do not need user‑visible interaction run quietly in the background, while sensitive tasks run in the foreground for reliability.  This maximises throughput when managing multiple characters and minimises the time the bot monopolises the user’s screen and input devices.
