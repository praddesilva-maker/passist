# Personal Assistant Agentic System — project specifics

## Build status: COMPLETE (2026-09-17)

**All 27 tasks (0–26) are DONE.** The 27-task build described below is finished;
`RUNBOOK.md` is now a historical record, not a queue of work. New work on this
repo is ordinary feature work, not runbook tasks — do not go looking for the
"next task" to pick up.

Verified baseline at completion:

- `.venv/bin/python -m pytest -q` → **450 passed, 1 skipped**
- System QA → `.venv/bin/python -c "from qa import run_qa; print(run_qa()['report'])"` → **23/23**
- Overall coverage **89%**
- Branch `recovery/repair-and-runbook`; `main` still at `f6a30a8`, nothing pushed

## The artifacts already exist

Do **not** create new planning files — read these:

| File | Role |
|---|---|
| `RUNBOOK.md` | **Start here.** All 27 tasks with exact guide line ranges and status. |
| `status.md` | Current progress report. Keep it updated per the workflow rules. |
| `initial.md` | The original build prompt, plus Rules 0/0b/0c/0d. |
| `PERSONAL_ASSISTANT_GUIDE.md` | The 6,414-line specification. **Never read it end to end** — load only the line range for your current task. |

There is no `PLAN.md`. `RUNBOOK.md` plus the Resolved Decisions section serves that
role for this project; do not generate one retroactively.

## Environment

- Always run in the virtual environment: `.venv/bin/python`
- Test command: `.venv/bin/python -m pytest -q`
- Python 3.10+; LangChain; SQLite registry; Git version control

## Resolved decisions — settled by the project owner, do not re-litigate

1. **Build the `pipelines/` package** as guide §1.5 specifies:
   `pipelines/new_skill_pipeline.py` and `pipelines/existing_skill_pipeline.py`.
   Move routing logic currently embedded in `agent/main_agent.py` into them.
2. **Commit after every completed task. Local commits only — never push.**
3. **Auto-continue between tasks**, stopping only on the hard-stop conditions.
4. **`status.md` is mandatory** and must reflect verified reality, never intent.

## Known baseline (verified 2026-09-17)

- Test suite is **green**: 450 passed, 1 skipped, 0 failed, 0 errors.
- No task is left in `REVIEW`, `BLOCKED` or `NOT_STARTED`.
- **The lesson from the verification sweep, which still applies:** a green suite
  proves the code satisfies *the tests that exist*, not that it works. Nearly
  every task previously marked DONE or REVIEW had a real defect, and in every
  case it surfaced only when something **executed** the code — not from reading
  it and not from the tests that already passed. Three examples: all three code
  generators emitted `return result` naming an unbound variable, so every
  generated skill raised `NameError` on execution; `python main.py list` raised
  `TypeError` on every invocation because `handle_list()` was missing a
  parameter; and failed skill runs were never logged, so the run history
  silently omitted every failure. **Run what you change.**
- Fixes with test coverage that must be preserved if you touch these areas:
  `_handle_create_skill` propagating registry rejections rather than reporting
  them as success; `_fail()` logging failed runs; parameters being derived from
  caller-supplied code; `SkillRegistry()` honouring `PA_DATABASE_PATH`.

## Architecture (post-Task-22)

Requests flow: `MainAgent.process_input()` → `NewSkillPipeline` (create) or
`ExistingSkillPipeline` (use) → `SkillBuilder` / `UnifiedSkillStage` →
`SkillRegistry`. Routing lives in the pipelines, **not** in `agent/main_agent.py`.
The intent vocabulary is `create_skill` / `use_skill` / `general`.

Adding a skill of your own: follow `skills/<skill-name>/SKILL.md` plus its
Python module, and register it through `SkillRegistry` — never by writing files
into `skills/generated/` directly.

## Working against the real registry — read this before running anything

`SkillRegistry` auto-commits by default, and `GIT_REPO_PATH` defaults to the
project root. Running the CLI or the agent against this checkout therefore
writes skills into `skills/skills.db` **and creates git commits**. Always point
it somewhere disposable first:

```bash
export PA_DATABASE_PATH=/tmp/scratch/d.db PA_GIT_REPO_PATH=/tmp/scratch
```

## Project-specific hard stop

The guide's Definition of Done requires the QA skill to pass after **every** task
(guide §1.7). If the QA skill cannot run, that is a `BLOCKED` condition — do not
proceed to the next task and call it done.
