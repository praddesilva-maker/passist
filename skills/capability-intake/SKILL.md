# `capability-intake`

This skill accepts a Change Request (CR) file and turns it into implemented capabilities.

## Intent

The project's front door for building new capability. It reads and processes a Change Request (CR), plans the implementation, and can optionally execute the plan to create new tools, engines, or skills.

## Input Contract

- **CR File Path** — A local markdown file at `docs/change-requests/CR-<id>.md`, filled from the CR template
- **Action** — `plan` (default) or `apply`
- The skill reads a CR from disk as input, validates it, and produces a build plan or executes build steps
- Refuses to proceed without a readable CR

## Mode: Interactive (`interactive`)

1. Reads CR file path from user
2. Asks for action (`plan` or `apply`) 
3. For each item in the CR:
   - Validates item against repo/API capabilities 
   - Classifies as new-tool / new-engine / new-skill / change-to-existing
   - Detects overlaps with existing capabilities
   - Shows a concrete build plan for item
   - Gets explicit approval before any file writes

## Mode: Single Command (`single-run`)

1. Takes CR file path and action as arguments
2. If CR not readable or missing, errors with clear message
3. Proceeds with same validation and planning/execution

### Arguments

- `CR` — full file path to the CR document
- `Action` — `plan` (default) or `apply`

## Guardrails

- **Never fabricate** → write `"To be confirmed"` for unknowns  
- **Dry-run/plan default** — `plan` mode only writes plans, never executes anything
- **Explicit approval gate** before any file writes
- **Upsert, never duplicate** — extend existing capabilities vs re-create them
- **Write-scope limited to CR authorisations** only

## Grounding Sources

- Reads the requested items from the Change Request document
- Scans `skills/*/SKILL.md` and `src/passist/api/registry.py` / `TOOLS.md` for overlap detection 
- Validates each item against real repo/API capabilities

## Acceptance Criteria

1. CR file is readable and parses correctly
2. Plan or apply action executes successfully
3. Build artifacts are properly created and registered  
4. Documentation policy is satisfied (all doc surfaces updated)
5. Hygiene checker passes for newly built content

## Implementation

### Plan Mode Actions

1. Read + validate the CR 
2. Classify each requested item as new-tool / new-engine / new-skill / change-to-existing
3. Detect overlaps with existing capabilities (scan `skills/*/SKILL.md` and `src/passist/api/registry.py` / `TOOLS.md`)
4. For each item, produce concrete build plan:
   - Exact files to create/edit  
   - Registry + TOOLS.md + metrics + docs touchpoints
   - Dependencies
   - Whether external writes are required and how they're gated
   - Test approach and risks
5. Write the plan to `docs/change-requests/CR-<id>/build-plan.md`
6. Present preview + approval gate
7. Stop (no file writes in plan mode)

### Apply Mode Actions

1. Execute each planned item for real (real logic, not stubs)  
2. Run hygiene gates and documentation policy checks
3. Register new capabilities in corresponding docs and metrics
4. Ingest run receipt and write build to logs

## Run Receipt

```json
{
  "category": "dev",
  "primary_volume": "number of capabilities delivered by the CR",
  "secondary_volume": null,
  "description": "capability-intake skill was used to process a change request"
}
```

## References

- `references/change-request-template.md` – CR template that this skill consumes
- `docs/change-requests/CR-001-academic-artefact-review.md` – A ready-to-run sample CR
- `src/passist/api/registry.py` – Tool registry file