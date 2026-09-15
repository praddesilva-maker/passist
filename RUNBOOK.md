# RUNBOOK — Personal Assistant Agentic System

**This file is the execution plan. `status.md` is the progress report. Do not
confuse them: you READ this file to decide what to do, and you WRITE `status.md`
to say what you did.**

---

## How to use this runbook

You are working through a 6,414-line specification. Loading all of it for every
task wastes context and degrades your accuracy. Work **one task at a time**, and
load only that task's slice.

### The loop

1. **Open the runbook** (this file) and find the first task whose Status is not
   `DONE`. That is your current task. Load nothing else yet.
2. **Load the task's context, and only that:**
   - The task's line range from the table below, e.g.
     `sed -n '503,774p' PERSONAL_ASSISTANT_GUIDE.md`
   - The specific source files named in that task's row.
   - Nothing else. Do **not** re-read the whole guide. Do **not** read files
     belonging to other tasks unless the task explicitly depends on them.
3. **Update `status.md`** — set Current Task, flip the board row to
   `IN_PROGRESS`, append an activity-log line.
4. **Do the work** for that task only. Resist scope creep: if you notice a
   problem belonging to another task, write it in the runbook's Carry-Forward
   Notes and keep going.
5. **Verify** — run the tests and see them pass:
   ```
   .venv/bin/python -m pytest -q
   ```
6. **Commit** — `feat(task-N): <description>`, local only, no push.
7. **Update `status.md`** with real test numbers and the commit SHA.
8. **Mark the task `DONE` in this runbook's table**, then **discard that task's
   context and return to step 1.** Do not carry the previous task's file
   contents into the next task.

### Stop conditions — hard stops, do not push through

Stop, set `status.md` State to `BLOCKED`, fill in section 6 (Blockers &
Questions), and wait for a human when any of these occur:

- Tests fail and two focused attempts to fix them have not worked.
- The task's Definition of Done cannot be met as written.
- A task requires a decision not answered by the guide or this runbook.
- You would need to delete or rewrite work from a task already marked `DONE`.
- The same error appears three times in a row.

Otherwise, **continue automatically to the next task.** Do not wait for a prompt
between tasks.

### Context discipline

- One task's guide slice at a time. `sed -n 'START,ENDp'`, never `cat` the guide.
- Before starting a task, drop the previous task's loaded files from working context.
- Sections 1.2 (rules), 1.5 (structure) and 1.6 (DoD protocol) of the guide are
  short and shared — `sed -n '1,227p'` covers all of them if you need a refresher.
- If you catch yourself re-reading the guide to remember where you are, that
  belongs in `status.md` instead. Write it there.

---

## Resolved decisions

These were decided by the project owner on 2026-09-16. Treat them as settled;
do not re-litigate them mid-run.

1. **`pipelines/` package: BUILD IT** as guide §1.5 specifies —
   `pipelines/new_skill_pipeline.py` and `pipelines/existing_skill_pipeline.py`.
   Move routing logic currently embedded in `agent/main_agent.py` into them.
   This unblocks Tasks 7-11, 15-19 and 22.
2. **Commit after every completed task.** Local commits only, never push.
3. **Auto-continue between tasks**, stopping only on the conditions above.
4. **`status.md` is mandatory** and must reflect verified reality, never intent.

---

## Task table

Status values: `NOT_STARTED` | `IN_PROGRESS` | `REVIEW` | `BLOCKED` | `DONE`

`REVIEW` means code exists from an earlier unverified run: **read it and test it
against the guide slice before trusting it.** Do not assume it is correct, and
do not mark it `DONE` without verifying it meets that task's stated DoD.

| # | Task | Guide lines | Size | Primary files | Status | Notes |
|---|------|-------------|------|---------------|--------|-------|
| 0 | Setup and Foundation | `228-502` | 275 | requirements.txt, .gitignore, venv, package skeletons | IN_PROGRESS |  |
| 1 | Registry System — Database Schema | `503-774` | 272 | skills/registry.py (schema) | REVIEW |  |
| 2 | Registry System — Basic Operations | `775-1052` | 278 | skills/registry.py (CRUD) | REVIEW |  |
| 3 | Registry System — Version Control Operations | `1053-1348` | 296 | skills/registry.py (versions) | REVIEW |  |
| 4 | Unified Stage — Basic Implementation | `1349-1578` | 230 | skills/unified_stage.py | REVIEW |  |
| 5 | Unified Stage — Skill Loading | `1579-1856` | 278 | skills/unified_stage.py (loading) | REVIEW |  |
| 6 | Unified Stage — Testing | `1857-2070` | 214 | tests/test_unified_stage.py | DONE | restored+rewritten vs current API; 25 tests, suite green, 82% coverage (2026-09-16); commits 8b8875d, d159245 |
| 7 | New Skill Pipeline — Intent Analysis | `2071-2295` | 225 | pipelines/new_skill_pipeline.py | NOT_STARTED | pipelines/ package does not exist yet |
| 8 | New Skill Pipeline — Skill Structure Generation | `2296-2549` | 254 | pipelines/new_skill_pipeline.py | NOT_STARTED | pipelines/ package does not exist yet |
| 9 | New Skill Pipeline — Code Generation | `2550-2778` | 229 | pipelines/new_skill_pipeline.py | NOT_STARTED | pipelines/ package does not exist yet |
| 10 | New Skill Pipeline — Interactive Review | `2779-3000` | 222 | pipelines/new_skill_pipeline.py | NOT_STARTED | pipelines/ package does not exist yet |
| 11 | New Skill Pipeline — Testing and Registration | `3001-3145` | 145 | pipelines/new_skill_pipeline.py + tests | NOT_STARTED | pipelines/ package does not exist yet |
| 12 | Interactive Skill Builder — Basic Features | `3146-3369` | 224 | skills/skill_builder.py | REVIEW | offline_template brace bug fixed 2026-09-16 |
| 13 | Interactive Skill Builder — Advanced Features | `3370-3588` | 219 | skills/skill_builder.py | NOT_STARTED |  |
| 14 | Interactive Skill Builder — Testing and Integration | `3589-3762` | 174 | tests/test_skill_builder.py | REVIEW | passing after 2026-09-16 fixes |
| 15 | Existing Skill Pipeline — Skill Search | `3763-3982` | 220 | pipelines/existing_skill_pipeline.py | NOT_STARTED | pipelines/ package does not exist yet |
| 16 | Existing Skill Pipeline — Skill Execution | `3983-4211` | 229 | pipelines/existing_skill_pipeline.py | NOT_STARTED | pipelines/ package does not exist yet |
| 17 | Existing Skill Pipeline — Natural Language Parsing | `4212-4432` | 221 | pipelines/existing_skill_pipeline.py | NOT_STARTED | pipelines/ package does not exist yet |
| 18 | Version Control Integration | `4433-4568` | 136 | skills/version_control.py (currently skills/git_manager.py) | REVIEW | named git_manager.py, not version_control.py |
| 19 | Test Existing Skill Pipeline | `4569-4828` | 260 | tests for existing-skill pipeline | NOT_STARTED |  |
| 20 | Main Agent — GLM Integration | `4829-5004` | 176 | agent/llm.py, agent/agent_config.py | REVIEW | create_chat_model + OfflineChatModel fixed 2026-09-16 |
| 21 | Main Agent — Intent Detection | `5005-5267` | 263 | agent/main_agent.py (intent) | REVIEW |  |
| 22 | Main Agent — Pipeline Integration | `5268-5477` | 210 | agent/main_agent.py (pipeline wiring) | BLOCKED | blocked until Tasks 7-11 and 15-17 create pipelines/ |
| 23 | Main Agent — Memory Management | `5478-5687` | 210 | agent/main_agent.py (memory) | REVIEW |  |
| 24 | Main Agent — Entry Point | `5688-5904` | 217 | main.py | REVIEW |  |
| 25 | Complete System QA Testing | `5905-6169` | 265 | qa/qa_test_suite.py, skills/qa_skill.py | BLOCKED | qa/ package missing; QA logic lives in skills/qa_skill.py |
| 26 | Final Documentation | `6170-6303` | 134 | README.md, qa_prompt_template.md | NOT_STARTED | no README.md exists |

**Load a task's spec with:** `sed -n 'START,ENDp' PERSONAL_ASSISTANT_GUIDE.md`
using the Guide lines column. Example for Task 7:

```
sed -n '2071,2295p' PERSONAL_ASSISTANT_GUIDE.md
```

---

## Recommended order

The board is not strictly sequential. Given the verified state on 2026-09-16:

1. **Task 6 first** — restore `tests/test_unified_stage.py`. Test coverage for
   already-written code is the cheapest safety net for everything after it.
2. **Tasks 7-11** — build `pipelines/new_skill_pipeline.py`. Largest gap.
3. **Tasks 15-17, 19** — build `pipelines/existing_skill_pipeline.py`.
4. **Task 22** — wire both pipelines into `agent/main_agent.py`.
5. **Tasks 1-5, 12, 18, 20-21, 23-24** — verify the `REVIEW` code against its
   guide slice, fix what fails, mark `DONE`.
6. **Task 25** — full-system QA, including creating the `qa/` package.
7. **Task 26** — `README.md` and `qa_prompt_template.md`.
8. **Task 0 last** — confirm setup/structure matches §1.5 once everything exists.

---

## Carry-Forward Notes

Problems you notice that belong to a **different** task. Write them here instead
of fixing them now; pick them up when you reach that task. Include the task
number.

- **Task 0 / 26:** `_probe.txt`, `_probe2.txt`, `_probe3.txt` are scratch files
  and should be deleted.
- **Task 18:** guide §1.5 calls for `skills/version_control.py`; the code has
  `skills/git_manager.py`. Rename or record as an accepted deviation.
- **Task 25:** guide §1.5 calls for a `qa/` package with `qa_test_suite.py`;
  QA logic currently lives only in `skills/qa_skill.py`.
- **Task 20/24:** `config.py` (root) and `agent/agent_config.py` both exist and
  overlap. Decide on one, record the other as a deviation.
- **Task 0:** `.gitignore` is untracked — commit it so its rules take effect.
- **Any task:** `tests/test_type_check.py` skips because pyright is not
  installed. Either install it or remove the test.

---

## Baseline as of 2026-09-16 06:20

Established by an external audit, with fixes applied. This is verified, not claimed.

- **Test suite: 27 passed, 1 skipped, 0 failed, 0 errors.** The suite is green.
- Fixed this session:
  - `SkillRegistry.close()` and `MainAgent.cleanup()` added (25 teardown errors).
  - `SkillBuilder.offline_template` brace bug (`KeyError`, 10 failures).
  - **`_handle_develop_skill` reported rejected skills as successfully
    registered** — a real correctness bug, not a test mismatch.
  - `create_chat_model` accepts `model_name`/`temperature`/`max_tokens`.
  - `OfflineChatModel.invoke` returns a structured `AIMessage` instead of raising.
  - `handle_request` gained top-level `success` and `response` fields.
  - `tests/test_registry.py::test_registry_missing_skill` corrected: it asserted
    `get_skill` raises, contradicting both its `Optional[Dict]` signature and its
    call site in `handle_request`.
- **Uncommitted at baseline:** ~21 modified + 9 untracked files, oldest dating to
  2026-09-14. Commit this before starting new work.
