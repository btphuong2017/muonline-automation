## Input Backends

Sending mouse and keyboard input to the game clients is handled by an abstraction layer so that different methods can be tested and swapped.  There are two main categories: **foreground (human‑like)** and **background (window‑targeted)**.

### Foreground (human‑like) input

* This approach uses libraries like **pyautogui** or **pynput** to simulate real mouse and keyboard events.  The game window must be focused for the input to be received.
* It mimics user interaction: moving the mouse with a small duration, pressing and releasing keys, and clicking buttons.  This is reliable for tasks like holding `ALT`, hovering candidates, clicking NPCs, handling pop‑ups and toggling the helper.
* Foreground input blocks the use of the machine; the bot temporarily takes over the mouse and keyboard.  The scheduler switches focus between windows as needed.

### Background (window‑targeted) input

* Some games accept input sent directly to the window using the Win32 `SendMessage` or `PostMessage` functions.  Libraries such as **pywinauto** or **pywin32** can deliver mouse clicks and key presses without focusing the window.
* This is useful for tasks that do not require hover indicators, such as clicking dialog buttons or sending hotkeys to open the Event Window.
* However, certain interactions – notably `ALT + hover` and `ALT + click` – may not work when the window is not active.  The capability test plan (issue 7) determines which inputs are reliable in background mode.

### Handling modifiers

* The bot must press and release modifier keys (`ALT`, `CTRL`, etc.) precisely.  For example, when searching for the NPC the bot holds `ALT` while hovering and clicking, then releases it immediately afterwards.
* The input backend ensures that the correct combination is sent even when switching windows.  It tracks which modifiers are currently held to avoid leaving keys stuck.

### Hybrid strategy

* The orchestrator selects the input backend dynamically.  For example, it may send **Ctrl + T** via `SendMessage` to open the Event Window in background, then switch to foreground input for the NPC click.
* If background input fails for a particular step, the orchestrator falls back to focusing the window and using foreground input.

### Safe clicking

* All clicks are performed relative to the client area of the target window.  Absolute screen coordinates are avoided.
* Before clicking, the bot verifies that the click target (dialog button, helper icon, NPC candidate) is visible.  It never clicks blindly.
* When interacting with toggle buttons (e.g. the helper icon), the bot checks the current state to avoid toggling off accidentally.
