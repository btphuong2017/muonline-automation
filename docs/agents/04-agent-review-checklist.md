# Agent Review Checklist

This checklist is intended for reviewers evaluating agent implementations.  It helps ensure that contributions adhere to project guidelines and maintain a high standard of quality.

## 1. Functional Correctness

- [ ] Does the code implement the required functionality as described in the corresponding issue and documentation?
- [ ] Are all expected states, signals and error cases handled?
- [ ] Does the agent respect retry limits and move to retry‑later or skip appropriately?
- [ ] Are daily limit dialogs detected and handled?

## 2. Capability Compliance

- [ ] Does the implementation check the capability matrix before using background operations?
- [ ] Are fallbacks to foreground or hybrid mode used when required?
- [ ] Is the window focus managed safely when switching between characters?

## 3. Code Quality

- [ ] Is the code modular and does it follow the single‑responsibility principle?
- [ ] Are functions and classes named clearly and consistently?
- [ ] Are there adequate docstrings and inline comments explaining complex logic or workarounds?
- [ ] Is error handling explicit and meaningful?
- [ ] Are magic numbers or hard‑coded coordinates avoided?

## 4. Logging and Diagnostics

- [ ] Does the agent log actions, detections and errors with enough detail to debug issues?
- [ ] Are screenshots captured when detection or click failures occur?
- [ ] Is the terminal dashboard updated appropriately by the scheduler?

## 5. Configuration and Templates

- [ ] Are ROI definitions and template paths loaded from configuration files?
- [ ] Are default thresholds and timeouts configurable?
- [ ] If new templates are added, are they documented and stored in the correct location?

## 6. Testing

- [ ] Have unit tests been added or updated to cover new logic?
- [ ] Do integration tests still pass?  Are new interactions tested?
- [ ] If capability tests are affected, are matrix entries updated?
- [ ] Have manual verification instructions been considered where automated tests cannot cover the behaviour?

## 7. Documentation

- [ ] Are changes reflected in the relevant markdown documentation (e.g. vision strategy, Varka flow issues)?
- [ ] Are any new configuration options documented?
- [ ] Is the overall behaviour of the new feature documented for future maintainers?

Completing this checklist helps reviewers ensure that each contribution maintains quality, consistency and reliability across the project.