Read and follow the PERSONAL_ASSISTANT_GUIDE.md which documents the plan for Personal Assistant Agentic System.

Note that previous attempts have been made and the implementation is partially completed; test anything that is implemented, don't assume its correct. If you find issues resolve these as part of this job.

> **Rule precedence.** `.clinerules/` holds the standing workflow rules for this
> project and applies to every session. This file is the task prompt for *this*
> build. Rules 0-0d below restate the parts of `.clinerules/` that matter most
> here; where they agree, either wording is fine — where this file is more
> specific about the Personal Assistant build, follow this file.

---

# ⚠️ RULE 0 — STATUS REPORTING IS MANDATORY (do this before anything else)

You are running unattended for long periods. The human operator **cannot see your
chat window**. `status.md` in the project root is the ONLY way they know what is
happening. Treat maintaining it as a hard requirement of every task, equal in
importance to the code itself.

**Your very first action in this session** — before reading the guide, before
writing any code — is to read `RUNBOOK.md` (see Rule 0b) and then create or
refresh `status.md` at the project root.

## 0.1 Required structure of `status.md`

Reproduce these eight sections, in this order, with these exact headings.

```markdown
# Project Status — Personal Assistant Agentic System

## 1. Snapshot
- **Last updated:** <YYYY-MM-DD HH:MM:SS, from the real `date` command>
- **State:** RUNNING | BLOCKED | AWAITING_INPUT | TASK_COMPLETE | STOPPED
- **Current task:** <Task N — title from the guide>
- **Doing right now:** <one sentence, present tense>
- **Next action:** <the single next concrete step>

## 2. Task Board
One row for EVERY task in PERSONAL_ASSISTANT_GUIDE.md (Task 0 through Task 26).

| # | Task | Status | Tests | Committed | Notes |
|---|------|--------|-------|-----------|-------|
| 0 | Setup and Foundation | DONE | 12/12 | yes (abc1234) | |
| 1 | Registry — DB Schema | IN_PROGRESS | — | no | |

Status values: NOT_STARTED | IN_PROGRESS | BLOCKED | DONE
`DONE` requires a real passing test run — see 0.3.

## 3. Current Task Detail
- **Objective:** <from the guide>
- **Definition of Done checklist:** <the guide's DoD, with [ ] / [x] boxes>
- **Files created/modified this task:** <paths>
- **Remaining work:** <bullets>

## 4. Test Status
- **Command run:** <exact command, e.g. `.venv/bin/python -m pytest -q`>
- **Run at:** <timestamp>
- **Result:** N passed, N failed, N errors, N skipped
- **Coverage:** <% if measured, else "not measured">
- **Failing tests:** each as `tests/file.py::test_name — ErrorType: message`
  with the `file.py:line` of the root cause where you know it.

## 5. Git Status
- **Last commit:** <short sha> — <subject> — <date>
- **Uncommitted files:** <count> (<list, or "see git status" if >15>)
- **Untracked files:** <count>
- **Branch:** <name>

## 6. Blockers & Questions for the Human
Numbered. Empty means genuinely nothing is blocked. For each:
- **What I need:** <the decision or input required>
- **What I tried:** <what you already attempted>
- **Impact:** <what is stalled until this is answered>

## 7. Deviations from the Guide
Anything built differently from PERSONAL_ASSISTANT_GUIDE.md — missing modules,
renamed files, extra files, skipped requirements — with a one-line reason each.
Include files you created that the guide does not mention.

## 8. Activity Log
Append-only. Newest entries at the BOTTOM. Never delete or rewrite earlier lines.
Format: `- HH:MM:SS — <what happened>`

- 2026-09-16 06:00:00 — Session started, read guide, refreshed status.md
```

## 0.2 When to update `status.md`

Update it at EVERY one of these moments — not in a batch at the end:

1. **On session start or resume** — immediately, before other work.
2. **Before starting each task** — set Current Task, flip the board row to `IN_PROGRESS`.
3. **After every `pytest` run** — paste the real numbers into section 4.
4. **After every git commit** — update section 5.
5. **At least every 15 minutes of continuous work** — even if only to append one
   activity-log line. A stale timestamp is how the operator detects you are stuck.
6. **The moment you are blocked or need a human decision** — set State to
   `BLOCKED` or `AWAITING_INPUT` and fill in section 6. Do not silently retry.
7. **Before you stop for any reason** — set State to `TASK_COMPLETE` or `STOPPED`
   and make sure sections 1, 4, 5 and 6 are accurate.

Sections 1–7 are overwritten in place. Section 8 is only ever appended to.

## 0.3 Truthfulness rules — these are not negotiable

- `status.md` must describe **verified reality, never intent**. Do not write that
  something works because you just wrote it.
- **Never mark a task `DONE` without running the tests and seeing them pass.**
  Paste the actual pytest summary line into section 4 first.
- Timestamps come from the real `date` command, never from memory or estimation.
- If tests fail, say so plainly with the real error text. A failing state honestly
  reported is far more useful than a green board that is wrong.
- If you are unsure whether something works, mark it `IN_PROGRESS`, not `DONE`.

---

# ⚠️ RULE 0b — WORK FROM `RUNBOOK.md`, ONE TASK AT A TIME

`RUNBOOK.md` in the project root is your execution plan. It lists all 27 tasks
from `PERSONAL_ASSISTANT_GUIDE.md`, each with the **exact line range** of that
task's specification, its deliverable files, and its current status.

**Do not read `PERSONAL_ASSISTANT_GUIDE.md` end to end.** It is 6,414 lines.
Loading all of it for every task wastes context and makes you less accurate.

## The loop — follow this exactly

1. **Read `RUNBOOK.md`.** Find the first task not marked `DONE`. That is your
   current task.
2. **Load only that task's context:**
   - its guide slice, e.g. `sed -n '2071,2295p' PERSONAL_ASSISTANT_GUIDE.md`
   - the source files named in that task's row
   - nothing else
3. **Update `status.md`** — current task, `IN_PROGRESS`, activity-log line.
4. **Do only that task.** If you spot a problem belonging to a different task,
   write it in the runbook's Carry-Forward Notes and move on. Do not fix it now.
5. **Run the tests** and see them pass: `.venv/bin/python -m pytest -q`
6. **Commit** (Rule 0c).
7. **Update `status.md`** with the real numbers and the commit SHA.
8. **Mark the task `DONE` in `RUNBOOK.md`**, drop that task's files from your
   working context, and **return to step 1 for the next task.**

## Auto-continue, but stop on trouble

Continue to the next task automatically — do not wait to be prompted between
tasks. **But stop immediately**, set `status.md` State to `BLOCKED`, and fill in
its Blockers section when any of these happen:

- Tests fail and two focused attempts have not fixed them.
- The task's Definition of Done cannot be met as written.
- A decision is needed that neither the guide nor the runbook answers.
- You would have to undo or rewrite work from a task already marked `DONE`.
- The same error appears three times in a row.

Do not push on past a hard stop. Hours of work built on a broken foundation is
exactly the failure mode this protocol exists to prevent.

## Tasks marked `REVIEW`

`REVIEW` means code from an earlier, unverified run already exists. **Read and
test it against its guide slice before trusting it.** Do not assume it is
correct, and do not mark it `DONE` until you have confirmed it meets that task's
stated Definition of Done.

## Keeping the runbook accurate

`RUNBOOK.md` is yours to maintain: update task statuses, and add to Carry-Forward
Notes. Do **not** rewrite the loop, the stop conditions, or the Resolved
Decisions section — those are set by the project owner.

---

# ⚠️ RULE 0c — GIT COMMIT AFTER EVERY COMPLETED TASK

The guide requires version control, but work has previously gone 24+ hours
uncommitted, putting it at risk.

- After each task's Definition of Done is met **and tests pass**, `git add` the
  relevant files and commit with a message of the form
  `feat(task-N): <short description>` (or `fix(task-N): ...`).
- Commit locally only. **Do not push to any remote.**
- Do not commit `.venv/`, `__pycache__/`, `*.db`, `.pytest_cache/`, or `.env` —
  confirm `.gitignore` covers these.
- Record the resulting short SHA in section 5 of `status.md` and in the
  `Committed` column of the task board.
- If there is uncommitted work older than one completed task, commit it (or
  explain in section 7 why you cannot) before starting new work.

---

# ⚠️ RULE 0d — RESUME FROM THE CURRENT STATE, DO NOT RESTART

Substantial work already exists in this repository. Before writing new code:

1. Run the full test suite and record the true result in `status.md` section 4:
   ```
   .venv/bin/python -m pytest -q
   ```
2. Read `status.md` and `RUNBOOK.md` (both are already populated with a verified
   assessment) and reconcile them against what you actually observe. Correct
   anything that is wrong.
3. **Fix the existing failing tests before building new features.** A broken
   suite makes every later Definition of Done unverifiable.
4. Audit the tree against the Project Structure in section 1.5 of the guide and
   record every difference in section 7. Do not silently delete or recreate
   existing modules — note the discrepancy and resolve it deliberately.
5. Remove scratch/probe files that are not part of the design, listing them in
   the activity log.

---

I need you to implement a Personal Assistant Agentic System with the following specifications:

## Core Architecture
- Use Cline (VS Code extension) + GLM (Qwen 30B model)
- Implement two pipelines: New Skill Development and Existing Skill Usage
- Use LangChain as the agent framework
- Centralized skill registry with version control (SQLite + Git)
- Single unified skill stage for all skill types (function, agent, workflow)

## Project Requirements
- Python 3.10+
- LangChain for agent framework
- GLM integration (Qwen 30B)
- SQLite database with version history
- pytest for testing
- Git for version control

## Key Deliverables
1. Complete implementation plan with all Python files
2. Comprehensive test suite with 80%+ coverage
3. Documentation for usage and API
4. Git integration with automatic commits
5. Interactive CLI for skill building
6. Python API for Cline integration

## Development Phases
1. Core foundation (registry + skill stage) - Days 1-2
2. New skill pipeline - Days 3-5  
3. Existing skill pipeline - Days 6-7
4. Main agent implementation - Days 8-9
5. Testing and validation - Days 10-12

## Critical Requirements
- Skills ONLY accessible through central registry (no auto-discovery)
- All skills must be version-controlled with Git
- pytest framework for all skills
- Clean Python API for Cline
- Self-contained in VS Code project

## Testing
- Run all tests with pytest
- Ensure 100% pass rate
- Generate coverage reports
- Test all core functionality

## Documentation
- Provide README.md with usage examples
- Document API usage
- Create troubleshooting guide
- Add code comments

Please implement this complete system following the detailed specifications provided in the implementation guide document. Start with Phase 1 and work through each phase systematically.

---

## Reminder: Status Reporting

Before you finish this response, and at every checkpoint described in Rule 0.2,
make sure `status.md` is current. If `status.md` has not been touched in the last
15 minutes of work, that is a bug in your process — fix it immediately.
