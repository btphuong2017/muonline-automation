---
name: incremental-dev-step
description: Use for EVERY implementation phase. Enforces small step → plan first → code second → local test → user verification command → STOP until user confirms. Wraps any of the gate-specific skills.
---

# incremental-dev-step

## Scope
One step, one file or small file set, one verification command. Never two gates in one pass.

## Required docs to read
- `.claude/workflow/test-verify-fix-loop.md`
- `.claude/workflow/verification-gates.md`
- The gate-specific doc(s) for the current step.

## Required loop (do not skip steps)
1. **Read relevant docs** for this step only.
2. **State scope** in one paragraph: what is in scope, what is explicitly NOT in scope.
3. **List files to edit/create** (table: path → 1-line purpose).
4. **Implement the smallest viable change.**
5. **Run available local checks** (lint/type/test). If none exist, say so and propose adding one.
6. **If checks fail**: explain failure → fix only related files → rerun. Do not bypass with `--no-verify` or skip flags.
7. **Create or update one user-facing verification command.** Document expected output.
8. **Update `.claude/workflow/implementation-roadmap.md`** with status `Waiting for user verification`.
9. **STOP. Print the verification command and wait for the user to confirm.**

## Allowed outputs
- Code edits within the scope of one gate.
- One new or updated CLI subcommand.
- Updates to the roadmap entry for the current gate.
- Updates to `open-questions.md` if a new question surfaces.

## Forbidden outputs
- Implementing more than one gate in a single pass (unless the user explicitly says "do gates N and M together").
- Adding new dependencies without listing them and getting approval.
- Refactoring code outside the immediate scope.
- Writing tests that depend on real game windows by default — gate them behind a marker.
- Running the verification command on behalf of the user when it requires a live game window.

## Required verification command
The skill's deliverable IS the verification command. The skill is incomplete without one.

## Stop condition
Print the command, the expected output, and the line: "Stop. Please run the command and confirm before continuing to the next gate."
