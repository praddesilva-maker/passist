# Personal Assistant Agentic System — project specifics

## The artifacts already exist

This project is mid-build. Do **not** create new planning files — read these:

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

## Known baseline (verified 2026-09-16)

- Test suite is **green**: 27 passed, 1 skipped, 0 failed, 0 errors.
- A repair session fixed six defects, including one where `_handle_develop_skill`
  reported registry-**rejected** skills as successfully registered. If you touch
  skill registration, preserve that fix and its test coverage.
- Twelve tasks are marked `REVIEW` — code exists but has not been verified against
  its spec. A green suite proves the code satisfies *the tests that exist*, not
  that it meets the guide's Definition of Done.
- Substantial work was uncommitted at baseline. Check `git status` before starting.

## Project-specific hard stop

The guide's Definition of Done requires the QA skill to pass after **every** task
(guide §1.7). If the QA skill cannot run, that is a `BLOCKED` condition — do not
proceed to the next task and call it done.
