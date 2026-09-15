# Development Workflow Rules

> These rules govern **how** you execute development work.
> [`AGENT_OPERATING_RULES.md`](../../AGENT_OPERATING_RULES.md) governs **authority,
> roles, gates and merging** and remains authoritative. Where the two overlap, the
> operating rules win. These rules add the execution layer that document does not
> specify: planning artifacts, the runbook loop, and context discipline.

---

## 1. Every development task begins with a plan

**Before writing any implementation code**, produce three files in the project root:

| File | What it is | Who writes it | Lifetime |
|---|---|---|---|
| `PLAN.md` | The approach: what you are building, why this way, what you deliberately are **not** doing, key risks. Prose, not a checklist. | You, once | Updated only when the approach changes |
| `RUNBOOK.md` | The execution plan: every task, in order, each with its spec location, deliverable files, and status. | You, once | You update task statuses as you go |
| `status.md` | The progress report: where you are right now, test results, blockers. | You, continuously | Rewritten constantly |

Write all three, then **proceed without waiting for approval.** The human reads
them to follow along and to intervene when something is wrong; they are not a gate.

### Proportionality

This applies to **multi-step development work** — a new feature, a subsystem, a
migration, anything spanning more than a couple of files or a single sitting.

It does **not** apply to a one-line fix, a typo, a single-file refactor, or
answering a question. Do not generate three ceremony files for ten minutes of work.
If the task is small enough that a plan would be longer than the change, just do it
and note it in `status.md` if one exists.

When genuinely unsure which side of the line a task falls on, write the plan. It is
cheaper than an unplanned run that drifts.

---

## 2. The three files, in detail

### `PLAN.md`

- **Objective** — what done looks like, in one paragraph.
- **Approach** — how you intend to build it, and why this way over the alternatives.
- **Out of scope** — what you are deliberately not doing. This is the most
  valuable section; it is what stops scope creep later.
- **Risks and unknowns** — what could go wrong, what you are unsure of.
- **Decisions** — anything the human has already settled. Record it here so it is
  not re-litigated mid-run.

### `RUNBOOK.md`

A table of tasks, each row carrying everything needed to start that task cold:

| # | Task | Spec location | Deliverable files | Status | Notes |

- **Spec location** must be precise enough to load in one command — a line range
  (`sed -n '503,774p' SPEC.md`), a section anchor, or a file path. "See the design
  doc" is not a spec location.
- **Status:** `NOT_STARTED` | `IN_PROGRESS` | `REVIEW` | `BLOCKED` | `DONE`
- **`REVIEW`** means code already exists from an earlier or unverified run. Read
  and test it against its spec before trusting it. Never mark it `DONE` on the
  strength of its existence.
- Add a **Carry-Forward Notes** section. When you notice a problem belonging to a
  different task, write it there and keep going. Do not fix it now.

### `status.md`

The human cannot see your chat window. This file is how they know what is
happening. Required sections:

1. **Snapshot** — last updated (real timestamp), state, current task, what you are
   doing right now, next action
2. **Task Board** — mirrors the runbook
3. **Current Task Detail** — objective, DoD checklist, files touched, what remains
4. **Test Status** — exact command, timestamp, real pass/fail numbers, failing
   tests with `file:line`
5. **Git Status** — last commit, uncommitted count, branch
6. **Blockers & Questions** — what you need, what you tried, what is stalled
7. **Deviations** — anything built differently from the spec, and why
8. **Activity Log** — append-only, timestamped, newest at the bottom

Sections 1–7 are overwritten in place. Section 8 is **only ever appended to** —
never delete or rewrite earlier entries.

---

## 3. The execution loop

1. Open `RUNBOOK.md`. Find the first task not marked `DONE`.
2. Load **only** that task's context: its spec slice, and the files named in its
   row. Nothing else.
3. Update `status.md` — current task, `IN_PROGRESS`, activity-log line.
4. Do **only** that task.
5. Run the tests. See them pass.
6. Commit (see §5).
7. Update `status.md` with the real numbers and the commit SHA.
8. Mark the task `DONE` in `RUNBOOK.md`, **drop that task's files from working
   context**, and return to step 1.

Continue automatically between tasks. Do not wait to be prompted.

### When to update `status.md`

On session start; before each task; after every test run; after every commit; at
least every 15 minutes of continuous work; the moment you are blocked; and before
you stop for any reason.

A stale timestamp is how the human detects that you are stuck. Keeping it current
is not optional.

---

## 4. Context discipline

Loading an entire specification for every task wastes context and measurably
degrades your accuracy.

- Load **one task's spec slice at a time.** Use `sed -n 'START,ENDp'`, never `cat`
  on a large document.
- Before starting a task, drop the previous task's files from working context.
- Do not read files belonging to other tasks unless the current task depends on them.
- If you find yourself re-reading the spec to remember where you are, that
  information belongs in `status.md`. Write it there instead.
- Shared context (project rules, structure, conventions) is usually short — load it
  once, not per task.

---

## 5. Commit after every completed task

- After a task's DoD is met **and tests pass**: `git add` the relevant files and
  commit as `feat(task-N): <description>` or `fix(task-N): <description>`.
- Never leave more than one completed task's work uncommitted.
- Record the short SHA in `status.md` and in the runbook's row.
- Never commit `.venv/`, `__pycache__/`, `*.db`, `.env`, or cache directories.
- Branching, pushing and merging follow `AGENT_OPERATING_RULES.md` §5. Nothing
  here authorises a push or a merge to `main`.

---

## 6. Evidence — status must reflect verified reality

This restates `AGENT_OPERATING_RULES.md` §3 because it is the rule most often broken:

- **A claim is not evidence. Raw command output is evidence.**
- Never mark a task `DONE` without running the tests and seeing them pass. Paste
  the real summary line into `status.md` before changing the status.
- Timestamps come from the real `date` command, never from memory.
- If tests fail, say so plainly with the real error text. A failing state honestly
  reported is far more useful than a green board that is wrong.
- If you are unsure whether something works, it is `IN_PROGRESS`, not `DONE`.
- Never write that something works because you just wrote it.

---

## 7. Hard stops

`AGENT_OPERATING_RULES.md` §7 lists the halt conditions and they apply in full.
In addition, stop, set `status.md` state to `BLOCKED`, fill in section 6, and wait:

- Tests fail and two focused attempts have not fixed them.
- A task's Definition of Done cannot be met as written.
- You would have to undo or rewrite work from a task already marked `DONE`.
- The same error appears three times in a row.

Do not push past a hard stop. Hours of work built on a broken foundation is the
expensive failure; stopping is always cheaper than unwinding.

---

## 8. Scope discipline

Do the task in front of you. When you notice something else worth fixing, write it
in the runbook's Carry-Forward Notes and continue. Fixing it now means the current
task's diff no longer matches its spec, and the human loses the ability to review
either one cleanly.
