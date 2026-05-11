## Hover Indicator and NPC Detection

Finding and clicking the Imperial Guardian NPC in the event lobby is one of the most challenging tasks: the NPC does not appear at a fixed position, the lobby is crowded and the character may spawn at different locations.  The bot uses a layered approach to locate the NPC and verify it before clicking.

### Multi‑layer candidate search

1. **Success cache:**  When a click succeeds, the bot records the relative click position along with the window size.  On subsequent runs it first tests the cached points (up to a small number per character and global history) in descending order of recent success.  Each point must still pass hover verification.
2. **Partial templates:**  Instead of matching the entire NPC model, the bot stores several small templates capturing distinctive parts of the NPC (e.g. shoulders, weapon, colour patches).  These templates are matched within a search region that excludes UI panels and the chat box.  Matches become candidate points.
3. **Grid search:**  If no candidate is found, the bot divides the search region into a grid and generates points to probe systematically.  This serves as a last resort.

### Hover verification

* The game shows a small **hover indicator** when the mouse is over an interactable NPC.  To avoid clicking the wrong place, the bot verifies candidates by hovering over them with `ALT` held and detecting this indicator.
* The vision module captures a small ROI around the mouse cursor and matches a template of the hover icon.  Only when the indicator is detected does the bot click.
* If the indicator is not seen, the candidate is marked as a soft fail and the next candidate is tried.  After a fixed number of failed candidates, the bot retries later rather than clicking blindly.

### ALT + click and dialog verification

* When a candidate passes hover verification, the bot holds `ALT`, clicks the centre of the candidate and releases `ALT`.
* The NPC dialog should open within a few seconds.  If it does, the candidate is recorded as a success.  If it does not, the candidate is marked as a fail and the bot tries the next candidate.

### Caching strategy

* The bot caches multiple successful click points per character and a global cache shared across characters.  Each point records the relative position, success and failure counts and timestamps.  Points are prioritised by recency and success rate.
* Only a limited number of points are kept active per character (e.g. 10–20) to keep hover probing efficient.  The full history is kept for analysis but not used at runtime.
* A cached point is never clicked blindly.  It must still be verified via the hover indicator.

### Safety rules

* Never click a candidate if the hover indicator is not detected.
* Do not retry indefinitely.  Each state can be retried up to three times; additional failures trigger a retry‑later state.
* If the NPC is not found after exhausting candidates and retries, the bot logs the error and skips the character for now.  This prevents characters from running in circles.
