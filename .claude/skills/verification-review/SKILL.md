---
name: verification-review
description: Use AFTER each gate's code is written and the verification command is ready, but BEFORE the user runs it. Checks docs alignment, scope discipline, no unsafe automation, no over-implementation, and that the verification command is actually wired up. Reports a verdict, no edits.
---

# verification-review

## Scope
Pre-verification static review. Read-only.

## Required docs to read
- `.claude/workflow/verification-gates.md` (definition of the current gate).
- The Issue doc(s) for the current gate.
- `docs/03-system-boundaries.md`
- `docs/agents/01-agent-implementation-rules.md`
- `docs/agents/04-agent-review-checklist.md`

## Allowed outputs
A single review document with:
1. **Gate** — number and short title.
2. **Verdict** — `Ready for user verification` / `Request changes` / `Block (safety)`.
3. **Docs alignment** — does the implementation match the doc(s)? Cite `docs/...` for any divergence.
4. **Scope discipline** — any code that belongs to a later gate? Any speculative abstraction?
5. **Safety** — any prohibited API call (memory, packets, hooks, injection)? Any input to a non-game window?
6. **Verification command** — is it documented, runnable, and does it actually exercise the change?
7. **Hard-coded values** — coordinates / thresholds / timeouts not in config.
8. **Specific issues** — each with `file_path:line` anchor and required action.

## Forbidden outputs
- Editing any file. This is review-only.
- Approving anything that calls `ReadProcessMemory`, `WriteProcessMemory`, raw socket capture, DLL injection, DirectX hooks, anti-cheat evasion, or modifies the game executable.
- Approving when the verification command is missing or only printed in chat (it must be a real CLI subcommand).
- Approving more than one gate's worth of changes in a single review.

## Required verification command
None — this skill produces the verdict that the user reads before running their own verification command.

## Stop condition
After the verdict is delivered, STOP. The user (or `code-reviewer` agent) decides whether to proceed.
