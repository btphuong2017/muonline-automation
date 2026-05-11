## Timer Recognition Strategy

The timer panel in the bottom‑right corner of the event map provides crucial information: the **round** and **zone**, whether the round is in **standby**, the **time left** and the **number of monsters remaining**.  The bot must interpret this panel to decide when to raise an alert and when the event is finished.  The following approach is used:

### Panel detection

* The timer panel always appears in a fixed region of the client window once the character has entered the event map.
* A small **anchor template** is used to locate the panel.  The vision module crops a region of interest (ROI) around the expected position and runs a template match to confirm the panel is present.
* Only when the panel is detected does the bot proceed to parse its contents.  Absence of the panel indicates that the character is not in the event map or that the map is still loading.

### Mode identification

The panel shows different modes:

* **Standby Time:** The round has not started yet.  The bot should wait silently; no alert is needed.
* **Time Left (Remaining Monsters):** Displays a countdown (`MM:SS`) and the number of monsters remaining in parentheses.  This mode requires parsing the digits.
* **Exit Waiting Time:** Indicates that the event is about to end or has ended.  No alert is raised.

To identify the mode, the vision layer matches the mode label within the panel using small templates.  It avoids OCR on the entire panel, using templates for `Standby`, `Time Left`, `Remaining Monsters` and `Exit Waiting`.

### Reading the countdown and monster count

* When the mode is **Time Left**, the vision layer extracts a small ROI containing the countdown and monster count.
* For robustness, the bot prefers **digit templates** over OCR.  Templates for digits `0–9`, the colon `:`, the opening `(` and closing `)` parentheses are stored.  The ROI is thresholded and compared against these templates to build the string `MM:SS(N)`.
* If OCR must be used, the ROI is preprocessed (grayscale, scaled up and thresholded) and parsed with a regex.  OCR results are validated to ensure they match the expected format.

### Alert logic

* Only when the mode is **Time Left (Remaining Monsters)** does the bot consider alerting.
* The parsed time is converted to seconds and compared to a **critical threshold** (30 seconds by default).
* The remaining monster count is parsed from within the parentheses.  If the time is below the threshold and the monster count is greater than zero, the bot raises a **critical alert** in the terminal.  Alerts are rate‑limited (e.g. once every five seconds) to avoid spamming.
* Standby and exit modes never trigger alerts.

### Finishing the event

The disappearance of the timer panel or the transition to **Exit Waiting Time** alone does not guarantee event completion.  The orchestrator checks for the **finish dialog** or the **lobby label** in parallel.  Once the event is confirmed finished, the timer parsing stops.
