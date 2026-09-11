# skill-reviewer

Review one skill to deliver an expert critique for distribution-readiness.

## Purpose

Review a single skill and return a realistic-but-critical assessment for distribution-readiness — a **findings TABLE** (good and bad, ranked by severity Blocker/Major/Minor) + a **one-paragraph verdict**.

## Behaviour

1. Read the target `skills/<name>/SKILL.md` + its `references/*`
2. Evaluate against a rubric = general skill-writing best practice **+** this repo's conventions:
   - canonical structure
   - grounding/never-fabricate  
   - dependency check
   - evidence model
   - two intake modes
   - approval gate + dry-run default
   - upsert
   - Run Receipt registration
   - documentation-policy completeness

## Strictly READ-ONLY

- Inspects files and produces a table **writes nothing**
- Never runs the skill under review
- (Like the metrics reporter) **emits no Run Receipt** — record the exemption in `metrics/config.json`
- It does **not** review itself

## Modes

- Interactive (asks which skill)
- Single-command (`start skill review — Skill: <name>`)
- Trigger: "start skill review"

## Documentation Policy Compliance 

### Skills Table Registration
- ✅ README.md skills list updated 
- ✅ .claude/skills/<name>/SKILL.md stub synced  
- ✅ docs/project/skills.md tables updated
- ✅ docs/prompts.md summary row + launch-prompts section updated  
- ✅ CHANGELOG.md entry added