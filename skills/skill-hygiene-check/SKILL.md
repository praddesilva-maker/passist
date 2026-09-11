# skill-hygiene-check

Audit the whole fleet (or a named subset) for conformance and return a PASS / FAIL / N-A table + a one-line verdict.

## Purpose

Audit the whole fleet (or a named subset) for **conformance** and return a **PASS / FAIL / N-A table** (worst-first) + a one-line verdict. Objective and repeatable — the opposite of `skill-reviewer`'s judgement.

## Default Scope

- ALL skills  
- Default action: REPORT (writes nothing)

## Checklist per skill (each a mechanical PASS/FAIL)

### Documentation completeness
- ✅ Registered in EVERY surface:
  - AGENTS.md/README skills list  
  - .claude/skills/<name> stub with synced description
  - README + docs/project/skills.md tables
  - docs/prompts.md summary row + launch-prompts section
  - CHANGELOG entry
  - For receipt-emitting skills: metrics/baselines.json, metrics/config.json skill_category_map, and primary_volume() dispatch

### Both intake modes present and convergent
- ✅ Interactive mode available
- ✅ Single-command mode available  

### Canonical structure
- ✅ Section order follows canonical format

### Guardrails present  
- ✅ Never-fabricate
- ✅ Approval gate + dry-run default 
- ✅ Upsert functionality
- ✅ Raw output format
- ✅ Write-scope limit (referencing _shared/guardrails.md)

### Tools resolve
- ✅ Every tool the skill names exists in src/passist/api/TOOLS.md  
- ✅ Every engine under src/passist/scripts/
- ✅ CLI stdin contract + pinned interpreter path used (referencing _shared/execution-rules.md)

### Run Receipt
- ✅ Present + fully registered in metrics, OR
- ✅ Justified read-only exemption recorded in config.json  

### Fragments resolve
- ✅ Every _shared/reference file it links exists on disk

## Output Format

Table in chat: 
```
Skill | Check | Result | Severity | Gap/evidence | Fix
```

## Optional Action: fix

Remediates ONLY mechanical, unambiguous gaps:
- Missing stub / table row / CHANGELOG line / metrics entry / fragment pointer  
- Behind preview + explicit "Approve applying N fixes?" gate
- Dry-run default
- **Judgement items** (missing gate, absent mode) flagged MANUAL, never auto-written

## Modes

- Interactive (asks which skill or scope)
- Single-command (`start skill hygiene check — Scope: <name>`)  
- Trigger: "start skill hygiene check"

## Run Receipt

This skill **emits a Run Receipt** (it does real work); register it in metrics.