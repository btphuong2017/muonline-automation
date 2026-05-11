## Terminal Status Dashboard

The terminal status dashboard is the primary interface for the user to
monitor the progress of the Varka bot.  As there is no graphical
interface in the MVP, the dashboard must present clear, concise and
realtime information for each character.  It should highlight
important events (such as critical timer alerts) and provide
immediate feedback on errors or the need for manual intervention.

### Purpose

The dashboard serves several purposes:

* **Overview:**  Show the current action and state of every enabled
  character at a glance.
* **Alerting:**  Highlight critical conditions, such as time left
  below 30 seconds with remaining monsters, `NEED_USER_LOGIN`, or
  fatal errors.
* **Progress tracking:**  Display the number of successful runs
  completed versus the maximum runs configured for each character.
* **Debugging:**  Provide the last error message and retry counts so
  the user can understand why a character may be waiting or has been
  skipped.

### Layout and contents

The dashboard is implemented as a table printed to the terminal.  A
library such as `rich` can be used to render coloured tables and
formatted text.  Each row corresponds to a character.  The following
columns are recommended:

| Column          | Description                                           |
|-----------------|-------------------------------------------------------|
| **Character**   | Display name or identifier of the character.          |
| **Level**       | Optional level for context.                           |
| **Status**      | High‑level status (e.g. `RUNNING`, `LOBBY`, `EVENT`). |
| **State**       | Current state in the state machine.                  |
| **Run**         | Completed runs versus maximum runs (e.g. `3/10`).     |
| **Retry**       | Current retry count for the active state (e.g. `1/3`).|
| **Last error**  | Most recent error message or `-` if none.             |
| **Timer**       | Current timer if in event (`MM:SS(N)`), or `-`.        |
| **Alert**       | Critical alert text such as `CRITICAL: 00:25(8)`.     |
| **Runtime**     | Elapsed time since the character started its action.  |

Additional columns can be added as needed, but avoid overloading the
table.  Long text should be abbreviated or truncated to keep the
dashboard readable.

### Updating the dashboard

The orchestrator refreshes the dashboard at the end of every
scheduler tick.  It reads the latest runtime data from each character
object and rebuilds the table.  To avoid flickering, update the table
in place using a library such as `rich.live`.  The update frequency
should balance responsiveness with CPU usage; updating every 0.5–1 second
is usually sufficient.  When there are no changes, the dashboard can
skip redraws to conserve resources.

### Alert formatting

Critical alerts should be rendered with a distinct colour or style so
they stand out in the terminal.  For example, when the timer
remaining is below 30 seconds and there are still monsters left, the
`Alert` column should show a message like `CRITICAL: 00:23(7)` in
bright red.  Errors such as `NEED_USER_LOGIN` should also be
highlighted.  Use colours and styles sparingly to ensure that
important information is not lost in a sea of formatting.

### Example output

An example dashboard might look like:

```
Char    Lv   Status   State                    Run   Retry   Last error          Timer    Alert             Runtime
PPIK    1190 RUNNING  MONITOR_EVENT           4/10  0/3     -                   01:45(0) -                 00:12:30
PPMG    1150 DONE     DONE_BY_GAME_LIMIT      10/10 -       -                   -        -                 00:45:00
PPDK    1100 RUNNING  START_HELPER            2/10  1/3     helper_unknown      -        -                 00:05:10
PPELF   980  WAITING  RETRY_LATER (NPC click) 1/10  3/3     npc_not_found       -        -                 00:02:00
```

### Logging integration

The dashboard is a runtime view; it should not replace structured
logging.  All events displayed on the dashboard must also be written
to log files with timestamps and details for later review.  The
dashboard can include a line summarising where logs are stored, and
should display the session start time and optional end time when the
session finishes.

### Summary

The terminal status dashboard is a vital tool for operating the
automation.  By presenting the right information at the right time it
allows the user to monitor multiple characters concurrently, respond
to critical conditions promptly and understand why a character may be
paused or has completed its runs.  The dashboard should be kept
simple, updated frequently and integrated tightly with the logging and
state machine framework.