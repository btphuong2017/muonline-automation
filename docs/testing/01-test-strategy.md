# Test Strategy

This document outlines the overall strategy for testing the Varka automation bot.  The goal of testing is to ensure that individual components (vision, input, orchestration) behave correctly and that the end‑to‑end Varka flow works reliably across different characters and window setups.

## 1. Test Layers

Testing should be performed at three layers:

### Unit Tests

Unit tests validate the behaviour of small, deterministic functions.  Examples include:

- Parsing window titles into character metadata.
- Matching templates within a region of interest (ROI).
- Computing relative click offsets from anchors.
- Updating state machine transitions based on return codes.

Unit tests should mock external dependencies (e.g. file IO, time) and focus on logic correctness.

### Integration Tests

Integration tests validate interactions between modules.  Examples include:

- Capturing a window and detecting the lobby label using the vision module.
- Simulating input sequences (ALT + click) and verifying that the state machine receives expected events.
- Running the cooperative scheduler with a mocked clock and verifying that characters interleave states correctly.

Integration tests may require a headless or virtualised environment to simulate multiple windows.  They rely on the capability matrix from Issue 7 to determine whether background or foreground methods are available.

### End‑to‑End (E2E) Tests

E2E tests exercise the entire Varka flow in a controlled environment.  A typical test will:

1. Start the bot with test configuration and template assets.
2. Launch game clients (or mocks) representing multiple characters at various states (outside the lobby, in lobby, in event map).
3. Let the scheduler run until all characters have reached their success conditions.
4. Verify final states (`DONE_MAX_RUNS`, `DONE_BY_GAME_LIMIT`) and logs.

E2E tests ensure that the bot can handle asynchronous state changes, retries and cooperative scheduling.

## 2. Automation vs Manual Testing

While automated tests cover the logic and flow, some behaviours (e.g. hover indicator appearance, helper toggle) can only be verified on the live game.  A manual verification guide (see `05-manual-verification-guide.md`) provides checklists for human testers to confirm key interactions.

## 3. Test Environment

Tests should be run in an isolated Windows environment with the same resolution and DPI settings as production.  For background capability tests, ensure that game windows can be overlapped and minimised.  Use test character accounts to avoid interference with actual gameplay.

## 4. Reporting

All tests should record results to structured logs.  Automated tests should use assertions to flag failures.  For E2E tests, capture screenshots at each major step and attach them to the test report.

## 5. Continual Integration

Whenever changes are made to templates or logic, run the full test suite.  If a capability previously marked as PASS begins to fail (e.g. due to game update), re‑evaluate execution strategies and update the capability matrix accordingly.