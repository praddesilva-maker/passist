# role-cheatsheets

Generate and refresh the human-facing role menu over your skills — plus a value-ranked new-build backlog. 

This skill builds the **role-first, human-facing layer** that sits on top of your skills — per role: 
*"I'm in this role → what are my jobs → what exact prompt do I paste?"*

It generates:
1. A role index (`README.md`) with a master `Role × Job-to-be-done × Skill` matrix
2. One sheet per role (fixed shape) with jobs and interactive triggers  
3. A new-build backlog of capabilities to develop next

## Intent

The skill builds the **role-first, human-facing layer** that sits on top of your skills — per role: 
*"I'm in this role → what are my jobs → what exact prompt do I paste?"*

This skill generates:
1. A role index (`README.md`) with a master `Role × Job-to-be-done × Skill` matrix
2. One sheet per role (fixed shape) with jobs and interactive triggers
3. A new-build backlog of capabilities to develop next

## Input Contract

### Interactive Mode  
- Ask the user for their roles/contexts/hats if not already set
- Prompt for lifecycle/phase vocabulary 
- Preview the generated tree and ask approval before writing
- Can run in "dry-run" mode that previews only

### Single-command Mode
- Accept roles directly: `refresh role cheat sheets — Roles: <a, b, c>; Phases: <...>`  
- For missing values (roles or phases), ask back interactively

## Behavior

The skill scans the available skills and creates human-readable cheat sheets that:
1. Provide structured guidance by role
2. Link to actual launch prompts in docs/prompts.md
3. Include value-ranked backlog of new capabilities to develop
4. Are maintained via automatic refreshes that never drift from the catalogue

## Guardrails

- **Never Fabricate Roles**: Only accept roles confirmed by user — never invent roles
- **Grounded Mappings**: Every job → skill mapping must reference existing real skills in the system  
- **Single Source of Truth**: Job triggers link to actual `docs/prompts.md` anchors, not copies of templates
- **Idempotent Upgrades**: Refresh regenerates mechanical parts while preserving human-authored prose
