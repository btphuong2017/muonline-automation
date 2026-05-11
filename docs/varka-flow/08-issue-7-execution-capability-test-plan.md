## Varka Issue 7 – Execution capability test plan

This document defines a test plan for determining whether the automation bot can capture screens and send inputs to game windows when they are in different window states.  It does **not** implement the Varka flow; it provides a repeatable set of tests so that agents can decide which steps in the flow must run in the foreground and which may run in the background.

### Goal

To evaluate, for each critical capability, whether it works when the target game window is:

1. **Active in the foreground** (the user sees and interacts with it)
2. **Visible but overlapped** (not the active window but still visible on the desktop)
3. **Minimised** (not visible at all)

Results should be captured in a *capability matrix* with entries such as `PASS`, `PARTIAL` or `FAIL` along with notes about limitations.  This matrix drives the choice between **background**, **foreground** and **hybrid** execution strategies.  Background execution means that the bot can interact with a window that is not active; foreground means the window must be focused; hybrid means some steps run in the foreground while monitoring and other safe actions run in the background.

### Summary of capabilities to test

Agents should implement a test harness to automate the following tests.  Each test targets one capability; do **not** combine tests into a full Varka flow.

#### Test 1 – Window discovery baseline

* Ensure that all Mu Online game windows are detected via the Win32 API.
* Verify that `hwnd`, `pid` and title parsing work for each instance.
* This test is mandatory for every execution mode and forms the baseline for subsequent tests.

#### Test 2 – Foreground capture

* With the window active, capture the full client area and key regions (map label, helper button, timer, dialog area).
* Verify that images reflect the current frame (no stale or blank frames).

#### Test 3 – Background capture (overlapped)

* Without focusing the window, capture its client area when other windows overlap it.
* Check that frames update in real time (e.g., timers count down, character animation moves).
* If frames are stale or blank, flag this capability as `FAIL`.

#### Test 4 – Minimized capture

* Minimise the window and attempt to capture it via `PrintWindow` or another backend.
* Many games render nothing when minimised; mark this capability as `FAIL` if the capture is blank or stale.

#### Test 5 – Foreground hotkeys

* Send a hotkey such as `Ctrl+T` while the window is active and verify the expected response (e.g., the event window opens).
* This forms the fallback for opening the event window.

#### Test 6 – Background hotkeys

* Send the same hotkey (`Ctrl+T`) to a non‑active window via Win32 `SendMessage` or an equivalent API.
* Record whether the event window opens in the target window; if not, mark as `FAIL`.

#### Test 7 – Foreground UI clicks

* Click fixed UI elements (e.g., event window buttons) while the window is active.
* Verify that the game responds correctly.

#### Test 8 – Background UI clicks

* Send mouse clicks to a non‑active window via the Win32 API and check whether the UI responds.  Test safe elements such as the event window buttons, not NPCs yet.
* If the click is ignored or goes to the wrong window, mark as `FAIL`.

#### Test 9 – Foreground NPC hover indicator

* Hold `Alt`, move the mouse over a known NPC candidate while the window is active, and verify that the hover indicator icon appears and can be captured.

#### Test 10 – Background NPC hover indicator

* Repeat the previous test with the target window overlapped and not active.
* If the hover indicator does not appear in captures, or if the API cannot move the mouse into a background window, mark as `FAIL`.

#### Test 11 – Foreground `Alt` + left‑click on the NPC

* With the window active, hold `Alt` and click the NPC.  Check that the character approaches the NPC and the first NPC dialog appears.

#### Test 12 – Background `Alt` + left‑click on the NPC

* Attempt to perform the same action on a non‑active window.
* If the character does not move or no dialog appears, mark this capability as `FAIL`.

#### Test 13 – Background popup handling

* After clicking the NPC in the foreground or background, attempt to click the Enter buttons in Pop‑up 1 and Pop‑up 2 while the window is not active.

#### Test 14 – Background helper toggle

* In the event map, detect the helper icon and attempt to toggle it from `Play` to `Pause` or vice versa without focusing the window.

#### Test 15 – Background timer monitoring

* In the event map, monitor the timer panel (mode and countdown) via background captures while the window is not active.

#### Test 16 – Finish dialog background detection

* Detect and click the finish dialog’s Exit button in a non‑active window and verify the character returns to the lobby.

#### Test 17 – Multi‑window safety

* When sending background inputs or captures, ensure they target the correct window and do not affect the active window or other game instances.

#### Test 18 – Foreground focus switching stability

* Test rapid focus switching between windows and verify that capture and input coordinates remain correct.

### Expected outcomes and matrix

For each test, record whether the capability works in background, minimised or only in foreground.  Compile the results into a matrix that includes:

| Capability | Background | Minimized | Foreground | Recommended execution mode | Notes |
|------------|-----------|-----------|-----------|---------------------------|------|

Use `PASS` when the capability works as expected, `PARTIAL` when it works only under certain conditions (e.g., the window must remain visible), and `FAIL` when it does not work at all.  For example, if `Ctrl+T` does not open the event window unless the window is active, mark background hotkey as `FAIL` and note that event window operations must run in the foreground.

### Decision guidelines

Once the matrix is compiled, decide on an execution strategy:

* **Full background** – Only if all critical capabilities (capture, hotkeys, NPC hover, NPC click, helper toggle, timer monitoring) pass in the background.  This is unlikely for DirectX games.
* **Hybrid (recommended)** – Use background capture and monitoring wherever it works, but switch to the foreground for sensitive actions such as NPC hover/click and helper toggling.  This balances stability with allowing the user to use their machine.
* **Full foreground** – If background capture or inputs fail for critical steps, run the entire flow in the foreground.  This is the most reliable but occupies the user’s desktop and input devices.

### Reporting results

Agents must deliver a JSON or Markdown report summarising the test results, with evidence screenshots and notes.  The report should reside under `docs/testing` or a similar location.  Use this report to configure the orchestrator and vision modules accordingly.
