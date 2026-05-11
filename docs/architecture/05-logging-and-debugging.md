## Logging and debugging

Reliable logging is essential for developing and maintaining the bot.  It allows agents to understand what the automation is doing, why it made decisions and where failures occur.

### Logging principles

* **Structured messages.**  Log entries should include the timestamp, character, current state, action taken and outcome.  Use consistent keys so logs are machine‑parsable.
* **Levels.**  Support at least `INFO`, `WARNING` and `ERROR` levels.  Normal state transitions produce `INFO` messages; retries and non‑critical issues produce `WARNING`; unrecoverable errors produce `ERROR`.
* **Screenshots on errors.**  When a state fails after its retry limit or when an unexpected condition is detected, capture a screenshot of the relevant window region.  Reference the screenshot in the log message.
* **Session summary.**  At the end of the session, log how many runs were completed by each character, how many were skipped due to errors and which characters reached the entry limit.
* **Terminal status.**  Display current status for all characters in a terminal dashboard, updating in real time.  Include action, state, retry count, run count and last error.

### Debugging guidelines

* **Reproduce with screenshots.**  Use error screenshots to replicate the environment when debugging vision or input problems.  Compare them to expected UI states and update templates or ROIs accordingly.
* **Tune thresholds.**  If template matching is too permissive or too strict, adjust thresholds in the configuration file.  Always test changes across multiple scenarios.
* **Investigate edge cases.**  Look for cases where UI overlays (e.g. chat, other players) interfere with detection.  Consider adding additional signals or fallback strategies.
* **Isolate components.**  Test vision functions separately from input to confirm detection accuracy before clicking.  Test input in isolation to ensure clicks are delivered correctly.
* **Use the capability matrix.**  Refer to the capability test results from Issue 7 to decide when to use background or foreground interaction.  If a capability fails, adjust the strategy accordingly.