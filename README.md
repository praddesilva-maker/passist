# passist — knowledge-transfer handoff pack

Everything needed to reproduce this agent's architecture in the **passist** project and
extend it. Two kinds of file:

- **Context** — paste into / fold into your repo files (not "run").
- **Build prompt** — hand to your coding agent as a task, **one at a time**; let it finish
  and pass its own gate before the next.

## Build order

Context before tasks; each task depends only on things built earlier. **Do not reorder
steps 4–7** (metrics → quality gates → build-time intake → runtime router is a strict chain).

| Step | File | Type | Why here |
|------|------|------|----------|
| 1 | `port-architecture-prompt.md` | build | The spine (warm server, forwarder+fallback, registry↔TOOLS.md, receipts, AGENTS.md). Nothing works without it. |
| 2 | `passist-conventions.md` | **context** → `AGENTS.md` | The skill-authoring discipline every later prompt says to read. Must be in context first. |
| 3 | `operational-runbook.md` | **context** → `INSTALL`/`README` | Run/restart/health of the warm server on Linux (`systemd --user`). |
| 4 | `metrics-subsystem-build-prompt.md` | build | Measurement layer; the gate + intake skills register receipts against it. |
| 5 | `quality-gates-build-prompt.md` | build | `skill-reviewer` + `skill-hygiene-check`; the checker verifies metrics registration, so metrics first. |
| 6 | `capability-intake-build-prompt.md` | build | CR → plan → build; its DoD runs the gate (5) and registers a receipt (4). Also creates CR-001. |
| 7 | `usage-intake-build-prompt.md` | build | Runtime router; its no-match path hands off to `capability-intake`, so 6 first. |
| 8 | `role-cheatsheets-build-prompt.md` | build | The human-facing role menu + value-ranked backlog, as views over the catalogue. Refresh it whenever a skill lands. |

## How to run a build prompt (steps 1, 4–8)

1. Hand **one** prompt per session — don't paste several at once.
2. Let the agent finish, then confirm its gate: `skill-hygiene-check` passes, docs synced
   across every surface, `CHANGELOG` entry added.
3. Commit (short branch → `main`), then hand the next.

**First self-test:** after step 5, run `skill-hygiene-check` across the fleet — proof the
conventions + metrics + doc-policy wiring holds before you build the intake loop on it.

**End-to-end shakedown:** after step 7, build **CR-001**
(`run capability-intake — CR: docs/change-requests/CR-001-academic-artefact-review.md;
Action: apply`) — it exercises a new tool + a new skill through the full
plan → apply → gate → register path.

## What you end up with — two closed loops

| | Build / supply side | Human / demand side |
|---|---|---|
| **Runtime** | `use-capability` (routes a goal to a skill) | role cheat sheets (the paste-ready menu) |
| **Change** | `capability-intake` (CR → builds it) | `new-build-backlog` (ranks what to build next) |

Say *"use passist"* → on a real no-match it drafts a CR and launches `capability-intake` to
build the missing capability, which then appears on the router and the cheat sheets.

**Launch prompts:** the canonical paste-ready prompts for *raising a CR to build a new skill*
and for *using a skill* live in `capability-intake-build-prompt.md` and
`usage-intake-build-prompt.md` (each build prompt registers them into the passist
`docs/prompts.md`).

## What's deliberately NOT in this pack

The source project's **domain specifics** (its Jira/Confluence business logic) and its
**SRG delivery-role / ISDF content**. Those don't transfer — but their *patterns* do, and
those patterns are captured in the conventions doc and the role-cheatsheets prompt. Fill in
your own domain and your own roles.
