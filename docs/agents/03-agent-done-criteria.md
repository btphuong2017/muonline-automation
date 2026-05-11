# Agent Done Criteria

This document defines the completion criteria for agents working on the Varka automation project.  A task is considered done when it satisfies all criteria listed here.  Agents should reference this checklist before submitting their work.

## General Criteria

- **Correctness:** The implemented feature behaves as described in the corresponding documentation (issues 1–7, vision, automation, orchestration).  All success and failure conditions are handled.
- **Capability Compliance:** The feature respects the capability matrix.  If a capability is unavailable in background mode, the agent switches to the appropriate fallback.
- **Retry and Error Handling:** Each state or action includes a retry mechanism with a limit of three attempts and proper logging of errors and retries.
- **Logging:** Actions, decisions and errors are logged with timestamps and character context.  Screenshots are saved when detection or interactions fail.
- **Configuration Driven:** ROIs, templates, thresholds and timeouts are read from configuration; no hard‑coded coordinates are used.  Defaults are defined in appropriate config files.
- **No Side Effects:** The agent does not affect windows or processes unrelated to the game.  It can be stopped safely by the user at any time.
- **Documentation:** Code includes docstrings and comments.  Any changes to behaviour are reflected in the markdown documentation.

## Vision Agent

- Correctly captures images from the target window using the appropriate capture backend.
- Performs template matching within ROIs and returns accurate match objects with confidence scores.
- Handles multiple candidate templates and selects the best match.
- Supports screen stability checks by comparing consecutive frames.

## Input Agent

- Sends mouse and keyboard inputs through the designated backend (foreground/background/hybrid) with correct coordinates and modifiers.
- Implements ALT + click sequences atomically to avoid race conditions.
- Verifies that the correct window is targeted before sending input.
- Provides an emergency stop or cancellation mechanism.

## State Machine Agent

- Implements state transitions as defined in the Varka flow documents.
- Each state checks for global interrupts before performing actions.
- Retries are limited and handled gracefully.
- States return explicit result codes for the scheduler to process.

## Scheduler Agent

- Instantiates and manages runtime character objects.
- Implements the cooperative scheduling algorithm described in `02-character-loop-strategy.md`.
- Properly handles retry‑later states and cooldowns.
- Updates the terminal status dashboard after each state change.
- Detects session completion or fatal errors and shuts down cleanly.

## Testing

- Unit tests pass for newly added functions and classes.
- Integration tests validate interactions between modules.
- Capability test harness runs and produces the expected matrix.
- Manual verification guide items have been reviewed where automated tests are insufficient.

Meeting these criteria ensures that the feature is robust, maintainable and integrates smoothly into the overall automation system.