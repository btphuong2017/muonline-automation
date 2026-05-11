---
name: claude-init
description: Initialize or update this project's .claude folder for the Mu Online Varka automation bot. Use when the user asks to create Claude Code agents, skills, hooks, settings, workflow docs, or project agent rules from the existing docs.
disable-model-invocation: true
user-invocable: true
argument-hint: "[optional: target project path or notes]"
---

# claude-init

You are initializing the `.claude/` folder for this specific project: a Windows Python automation bot for Mu Online Varka / Imperial Guardian.

Your job is to read the existing `docs/` folder first, then design and create the Claude Code project configuration needed for disciplined agentic development.

Do not implement the bot itself in this skill.  
This skill only creates or updates Claude Code project assets: agents, skills, hooks, settings, workflow docs, and guardrails.

## Absolute rules

1. Read the project docs before creating anything.
2. Do not invent project requirements.
3. Do not replace existing `.claude/` files without backing them up first.
4. Do not create implementation code for the bot unless the user explicitly asks after initialization is complete.
5. Development must be incremental and user-verified.
6. Every future development phase must produce a runnable verification command before moving to the next phase.
7. If information is missing, write it as an open question instead of guessing.
8. Prefer small, testable steps over large end-to-end implementation.
9. Keep the automation bounded to UI/screen/input only. Do not create instructions for memory reading, packet manipulation, hook/injection, anti-cheat bypass, or game client modification.
10. Use Vietnamese in user-facing docs and workflow instructions unless the project already uses English for that file.

## Required preflight

Before writing files:

1. Identify the project root.
2. List the `docs/` directory.
3. Read, at minimum, these files if present:

   - `docs/00-overview.md`
   - `docs/01-requirements.md`
   - `docs/03-system-boundaries.md`
   - `docs/varka-flow/01-varka-action-overview.md`
   - `docs/varka-flow/02-issue-1-window-discovery.md`
   - `docs/varka-flow/03-issue-2-lobby-and-npc-click.md`
   - `docs/varka-flow/04-issue-3-npc-popups.md`
   - `docs/varka-flow/05-issue-4-event-map-helper-monitoring.md`
   - `docs/varka-flow/06-issue-5-enter-lobby-flow.md`
   - `docs/varka-flow/07-issue-6-varka-orchestrator.md`
   - `docs/varka-flow/08-issue-7-execution-capability-test-plan.md`
   - `docs/varka-flow/10-varka-error-and-retry-policy.md`
   - `docs/automation/04-background-vs-foreground-strategy.md`
   - `docs/testing/02-capability-test-checklist.md`
   - `docs/agents/01-agent-implementation-rules.md`

4. If any of these files are missing, continue with available docs but add the missing files to an `Open Questions / Missing Docs` section in the initialization report.
5. Inspect the current repository structure:
   - Existing `.claude/`
   - Existing `pyproject.toml`, `requirements.txt`, `poetry.lock`, `uv.lock`, `setup.cfg`, `pytest.ini`
   - Existing `src/`, `tests/`, `scripts/`, `docs/`, `assets/`
   - Existing commands for lint/typecheck/test, if any
6. Summarize verified project facts in your response before writing files.

## Backup rule

If `.claude/` already exists:

1. Create a backup directory before modifying it:

   `.claude-migration-backup/YYYYMMDD-HHMMSS/`

2. Copy existing `.claude/` contents into that backup.
3. Preserve user-authored content whenever possible.
4. If a file conflict exists, do not silently overwrite. Either:
   - merge safely, or
   - write a `.new` version and report the conflict.

## Initialization output

After reviewing docs, create a `.claude/` structure appropriate for this project.

You must decide the exact contents from the docs and the repository state, but the default structure should include:

```text
.claude/
  README.md
  settings.json
  agents/
    solution-architect.md
    windows-automation-engineer.md
    computer-vision-engineer.md
    state-machine-orchestrator.md
    python-qa-test-engineer.md
    technical-docs-keeper.md
    code-reviewer.md
  skills/
    docs-review/
      SKILL.md
    capability-test-plan/
      SKILL.md
    incremental-dev-step/
      SKILL.md
    varka-window-discovery/
      SKILL.md
    varka-lobby-npc/
      SKILL.md
    varka-popups/
      SKILL.md
    varka-event-helper-monitoring/
      SKILL.md
    varka-enter-lobby/
      SKILL.md
    varka-orchestrator/
      SKILL.md
    verification-review/
      SKILL.md
  hooks/
    protect-sensitive-files.ps1
    verify-after-edit.ps1
    log-claude-activity.ps1
  workflow/
    implementation-roadmap.md
    verification-gates.md
    agent-routing.md
    test-verify-fix-loop.md
    open-questions.md
```

You may add, remove, or rename files if the docs justify it, but you must explain the reason.

## settings.json requirements

Create or update `.claude/settings.json` conservatively.

The settings should support hooks without making unsafe assumptions.

Recommended hook intentions:

1. Protect sensitive files before edits:
   - `.env`
   - `.env.*`
   - private keys
   - credentials
   - game account secrets
   - real tokens/cookies
   - binary screenshots/templates unless explicitly requested

2. After file edits, run a light verification script if available:
   - Detect the project toolchain.
   - If tests exist, run a narrow safe check.
   - If no tests exist, print a message telling Claude what verification command is missing.
   - Do not run heavy or destructive commands automatically.

3. Log Claude activity to a local `.claude/logs/` file.

If exact hook syntax is uncertain in the local Claude Code version, create the hook scripts and document how they should be registered. Do not invent unsupported settings.

## Agent creation rules

Agents must be specialized and scoped. Do not create one giant agent.

Default agent responsibilities:

### solution-architect
- Reviews requirements and docs.
- Keeps scope small.
- Breaks implementation into user-verifiable phases.
- Does not write large code changes directly unless asked.

### windows-automation-engineer
- Handles Win32 window discovery, window focus, input backends, background/foreground capability tests.
- Must respect system boundaries: no memory/packet/hook/injection.

### computer-vision-engineer
- Handles ROI, templates, OpenCV matching, hover indicator, timer parsing.
- Must prefer screenshot/template validation over guessing.

### state-machine-orchestrator
- Designs Varka state machine and cooperative scheduler.
- Must enforce retry policy and session lifecycle.

### python-qa-test-engineer
- Designs tests, smoke commands, verification commands, and regression checks.
- Must require a runnable verification command for every phase.

### technical-docs-keeper
- Updates technical docs after each phase.
- Maintains implementation roadmap, verification logs, and open questions.

### code-reviewer
- Reviews changes for correctness, scope, safety, testability, and alignment with docs.
- Blocks over-broad or speculative implementations.

Each agent file must include:
- Purpose
- When to use
- Inputs needed
- Output format
- Constraints
- Done criteria
- References to relevant docs

## Skill creation rules

Project skills must be task-focused. Each skill should read the relevant docs first and keep scope narrow.

Default skills:

### docs-review
Use before any implementation task. It reads relevant docs, summarizes verified facts, assumptions, risks, and asks only necessary questions.

### capability-test-plan
Implements Issue 7 only. It creates/runs a capability test harness and outputs a capability matrix. It must not implement full Varka flow.

### incremental-dev-step
Used for each implementation phase. It enforces:
- small step
- plan first
- code second
- local test
- user verification command
- stop until user confirms

### varka-window-discovery
Implements Issue 1 only. Must create a command to scan windows and print discovered characters.

### varka-lobby-npc
Implements Issue 2 only. Must create a command to test lobby detection, NPC candidate detection, hover indicator, and ALT+click flow.

### varka-popups
Implements Issue 3 only. Must create a command to test popup detection and button clicking.

### varka-event-helper-monitoring
Implements Issue 4 only. Must create commands to test event map detection, helper state detection, helper start, timer parsing, and finish dialog handling.

### varka-enter-lobby
Implements Issue 5 only. Must create a command to test Ctrl+T Event Window flow and lobby transition.

### varka-orchestrator
Implements Issue 6 only. Must create a command to dry-run/smoke-test multi-character scheduling.

### verification-review
Runs after each phase. It checks:
- docs alignment
- test/verification result
- no scope creep
- no unsafe automation
- no over-implementation

Each skill file must include:
- Name and description frontmatter
- Scope
- Required docs to read
- Allowed outputs
- Forbidden outputs
- Required verification command
- Stop condition requiring user confirmation

## Incremental development gates

The generated `.claude/workflow/verification-gates.md` must define gates like this:

### Gate 1 — Window discovery
Goal:
- Discover game windows and parse character info.

Required deliverable:
- A command such as `python -m <app> scan-windows` or equivalent.

User verification:
- User runs the command.
- User confirms correct window count, character names, hwnd/pid/rect, visible/minimized status.

Do not proceed until user confirms.

### Gate 2 — Capability matrix
Goal:
- Determine background / foreground / hybrid execution support.

Required deliverable:
- A command such as `python -m <app> capability-test`.
- Output `capability_matrix.json` and readable summary.

User verification:
- User confirms whether tests reflect actual game behavior.

Do not proceed until user confirms.

### Gate 3 — Lobby + NPC test
Goal:
- Detect lobby and test NPC hover/ALT-click.

Required deliverable:
- A command such as `python -m <app> test-lobby-npc --char <name>`.

User verification:
- User confirms lobby detection and NPC dialog opening.

Do not proceed until user confirms.

### Gate 4 — Popup handling test
Goal:
- Detect/click Popup 1 and Popup 2.

Required deliverable:
- A command such as `python -m <app> test-varka-popups --char <name>`.

User verification:
- User confirms correct dialog handling, limit dialog handling, and no wrong clicks.

Do not proceed until user confirms.

### Gate 5 — Event map + helper monitoring test
Goal:
- Detect event map, start helper safely, parse timer, detect finish/return lobby.

Required deliverable:
- A command such as `python -m <app> test-event-helper --char <name>`.

User verification:
- User confirms helper toggles correctly and bot does not pause helper accidentally.

Do not proceed until user confirms.

### Gate 6 — Enter lobby flow test
Goal:
- If outside lobby, open Event Window, select Imperial Guardian, enter lobby.

Required deliverable:
- A command such as `python -m <app> test-enter-lobby --char <name>`.

User verification:
- User confirms character reaches lobby and crash handling is correct.

Do not proceed until user confirms.

### Gate 7 — Orchestrator dry run
Goal:
- Cooperative scheduler across multiple characters.

Required deliverable:
- A command such as `python -m <app> start-varka --dry-run` or a smoke test mode.

User verification:
- User confirms characters are scheduled correctly and status/logs are understandable.

Do not proceed to real full automation until user confirms.

## Test - verify - fix loop

Every implementation step must follow this loop:

1. Read relevant docs.
2. State scope for this step only.
3. Identify files to edit.
4. Implement the smallest viable change.
5. Run available tests/checks.
6. If tests fail:
   - explain failure
   - fix only related files
   - run tests again
7. Create or update one user-facing verification command.
8. Update relevant docs or verification log.
9. Stop and ask the user to verify before moving to the next gate.

Never implement multiple gates in one pass unless the user explicitly instructs.

## Required files created by this skill

At the end of initialization, the project should have:

1. `.claude/README.md`
   - How to use the generated agents/skills/hooks.
   - Recommended invocation order.
   - Safety rules.

2. `.claude/workflow/implementation-roadmap.md`
   - Gates 1–7.
   - Status columns: Not started / In progress / Waiting for user verification / Verified / Blocked.

3. `.claude/workflow/verification-gates.md`
   - Detailed gate definitions.

4. `.claude/workflow/test-verify-fix-loop.md`
   - Mandatory loop for development.

5. `.claude/workflow/agent-routing.md`
   - Which agent/skill should handle which issue.

6. `.claude/workflow/open-questions.md`
   - Any unclear areas found while reading docs.

7. `.claude/settings.json`
   - Conservative hook registration if supported.

8. `.claude/hooks/*.ps1`
   - PowerShell hook scripts, since this project targets Windows.

9. `.claude/agents/*.md`
   - Subagent definitions.

10. `.claude/skills/*/SKILL.md`
   - Project skills.

## Final response after initialization

After creating files, respond with:

1. What docs were reviewed.
2. What `.claude/` files were created or updated.
3. What was backed up.
4. What agents were created and why.
5. What skills were created and when to use them.
6. What hooks were created and what they protect/verify.
7. Any open questions.
8. The recommended first development command/gate.
9. A clear stop message:

   "Initialization complete. Do not start implementation yet. Ask the user to review `.claude/workflow/implementation-roadmap.md` first."

## Strict non-goals

Do not:
- Implement the game bot.
- Create full Varka automation code.
- Build UI/dashboard code.
- Add external dependencies without a plan.
- Modify `.env`, credentials, private keys, screenshots, or template assets without explicit request.
- Skip user verification gates.
- Convert this into a full project architecture rewrite beyond what `.claude/` initialization needs.
