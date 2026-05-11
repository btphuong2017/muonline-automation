# Varka Flow Test Cases

This file lists end‑to‑end test cases for verifying the Varka action across various scenarios.  Each test describes the starting conditions, expected behaviour and success criteria.

## 1. Happy Path – Single Character

**Starting conditions:** Character is in the lobby, has available runs, and no prior errors.  Game window is visible and active.

**Steps:**

1. Detect lobby.
2. Locate and click NPC using ALT + click.
3. Handle the two pop‑ups (Enter Varka → Enter).
4. Detect event map and open helper.
5. Monitor timer and wait for event completion.
6. Click exit on finish dialog and verify return to lobby.

**Success criteria:** The character completes one Varka run; the runtime state records `completed_count = 1`, no errors or retries logged.

## 2. Multi‑Character Interleaving

**Starting conditions:** Five characters are all in the lobby with available runs.

**Steps:**

1. Start the orchestrator; it should interleave states across characters (Issue 6).  All characters enter the event map and open helper.
2. Scheduler continues to monitor each character without blocking on any single one.
3. When each character completes a run, verify that the run count increments.

**Success criteria:** All characters complete at least one run; scheduler interleaves steps fairly; terminal dashboard updates correctly for each character.

## 3. Out‑of‑Lobby Start

**Starting conditions:** A character starts outside the lobby (e.g. in Lorencia).  The character has available runs.

**Steps:**

1. The bot should detect that the character is not in the lobby or event map.
2. Open the Event Window (Ctrl + T) and select Imperial Guardian.
3. Click Enter and wait for lobby loading.
4. Continue with the usual flow.

**Success criteria:** The character successfully enters the lobby and proceeds with the Varka flow; no false detection of lobby or event map occurs during map transition.

## 4. Daily Limit Reached

**Starting conditions:** Character has no runs left (daily limit reached).  This is shown by the NPC dialog with “exceeded the daily entrance limit.”

**Steps:**

1. Attempt to start the Varka flow.
2. After clicking NPC, detect the limit dialog.
3. Mark the character as done and do not retry further actions.

**Success criteria:** Character’s state is set to `DONE_BY_GAME_LIMIT` and `completed_count` is set to 10; no error is logged; scheduler moves on to other characters.

## 5. NPC Not Found After Retries

**Starting conditions:** NPC detection fails due to an unexpected scenario (e.g. heavy crowd or new UI skin).

**Steps:**

1. The bot enters the lobby and begins scanning for NPC.
2. After three retries of candidate search and hover, NPC is still not found.

**Success criteria:** The character is marked as `RETRY_LATER` or `SKIPPED_ERROR` with a cooldown.  A screenshot is saved.  The scheduler continues with other characters without crashing.

## 6. Helper State Unknown

**Starting conditions:** In rare cases, the helper icon cannot be detected (e.g. due to UI glitch).  Character is in the event map.

**Steps:**

1. Detect event map ready.
2. Attempt to detect helper state up to three times.
3. Fails to detect state each time.

**Success criteria:** The bot logs an error, does not click the helper blindly and either retries later or asks for user attention.  Scheduler does not hang on this character indefinitely.

These test cases help ensure that both typical and edge‑case scenarios are handled gracefully by the Varka flow.