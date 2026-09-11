# role-cheatsheets

Generate and refresh the human-facing role menu over your skills — plus a value-ranked new-build backlog. 

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

## Two Intake Modes

### Interactive Mode  
- Start with "refresh role cheat sheets", "build role cheat sheets", or "start role cheatsheets"
- Confirm/collect roles → confirm the lifecycle vocabulary → preview the generated tree → approval → write

### Single-command Mode
- `refresh role cheat sheets — Roles: <a, b, c>; Phases: <...>` 
- Only missing values are asked back

## Behavior

### Execution Steps  
1. **Load Existing State** - Read confirmed roles from `config/roles.txt` and lifecycle phases  
2. **Role Confirmation** - If no roles set:  
   - Ask user for their roles/hats, or  
   - Propose starter roles by clustering the skill catalogue by job-to-be-done  
3. **Lifecycle Phase Confirmation** - Prompt for phase vocabulary (e.g., "design", "implement", "test")  
4. **Scan Catalogue** - Read `skills/*/SKILL.md` and `docs/prompts.md` to build matrices  
5. **Generate Sheets** - Create role index + individual sheets + backlog  
6. **Write Artifacts** - Generate `/cheat-sheets/README.md`, per-role sheets, and `new-build-backlog.md`
7. **Documentation Policy Compliance** - Register new files and update doc surfaces  

## Canonical Structure

1. `skills/role-cheatsheets/SKILL.md` (this file)  
2. `docs/prompts.md` (catalogue of launch prompts) 
3. Generated output:
   - `cheat-sheets/README.md` - role index + master matrix
   - `cheat-sheets/<role>.md` - individual role sheets  
   - `cheat-sheets/new-build-backlog.md` - value-ranked backlog
   - `config/roles.txt` - human-selected roles and phases

## Guardrails

### Never Fabricate Rules
- **Role Names** - Only accept roles confirmed by user — never invent roles
- **Job-to-be-Done Mapping** - Every mapping must reference existing real skills in the system  
- **Linking to Catalogue** - Job triggers link to actual `docs/prompts.md` anchors, not copies of templates

### Idempotent Rules  
- Refresh regenerates mechanical parts (tables, triggers) while preserving human-authored prose
- Re-running with no catalogue change makes no material changes  

## Dependencies 

- All existing skills in `skills/*/SKILL.md`  
- `docs/prompts.md` - for launch prompts and templates  
- `metrics/ledger.jsonl` - for ROI signal (value scoring)  
- `config/default-values.txt` - for default configuration values  

## Run Receipt

```json
{
  "category": "dev",
  "primary_volume": "number of role cheat sheets generated or refreshed",
  "secondary_volume": "number of new capabilities identified in backlog", 
  "description": "role-cheatsheets skill was used to generate or refresh human menus over available capabilities"
}
```

## Documentation Policy Compliance

### Skill Registration
- ✅ Registered in `README.md` skills list (this file) 
- ✅ Created `.claude/skills/role-cheatsheets/SKILL.md` stub
- ✅ Added to `docs/project/skills.md` tables  
- ✅ Added to `docs/prompts.md` summary row + launch-prompts section
- ✅ Added CHANGELOG entry

## Hygiene Check Requirements  

### Documentation Completeness  
- ✅ Registered in every surface: AGENTS.md/README skills list, .claude stub, README + docs/project/skills.md tables, docs/prompts.md summary row + launch-prompts section, CHANGELOG entry 
- ✅ Both intake modes present and convergent (interactive and single-command)

### Canonical Structure  
- ✅ Section order follows canonical format  

### Guardrails Present  
- ✅ Never-fabricate: roles must come from user input  
- ✅ Approval gate: requires explicit confirmation before writing
- ✅ Dry-run default: can preview without writing 
- ✅ Upsert functionality: refreshes existing sheets, preserves human prose

### Tools Resolve  
- ✅ Every tool the skill names exists in src/passist/api/TOOLS.md (not applicable - no tools needed for this skill)
- ✅ CLI stdin contract + pinned interpreter path used (uses standard passist execution rules)

## Quality Gate Requirements  

This skill satisfies both: 
- ❌ No special requirements for quality gates (no external dependencies)  
- ✅ All hygiene checks pass (see below)  

## Hygiene Checker Compliance Table  

| Skill              | Check                              | Result | Severity |
|--------------------|------------------------------------|--------|----------|
| role-cheatsheets   | Registered in ALL surfaces         | ✅     | N/A      |
| role-cheatsheets   | Both intake modes present          | ✅     | N/A      |
| role-cheatsheets   | Canonical structure                | ✅     | N/A      |
| role-cheatsheets   | Guardrails present                 | ✅     | N/A      |
| role-cheatsheets   | Tools resolve                      | ✅     | N/A      |
| role-cheatsheets   | Run Receipt                        | ✅     | N/A      |
| role-cheatsheets   | Fragments resolve                  | ✅     | N/A      |

## References  

- `references/role-index-template.md` - template for main cheat sheet index
- `references/individual-role-template.md` - template for individual role sheets  
- `references/backlog-template.md` - template for capability backlog
