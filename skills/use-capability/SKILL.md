# use-capability

**Goal**: Route user's stated goal to the right *existing* tool or skill and run it.

## Runtime Front Door

This is the runtime counterpart to `capability-intake`. It accepts a goal from the user and:
1. Scans the available capabilities in the catalog
2. Matches the user's goal against skills/tools that can fulfill it
3. Invokes the matched capability with proper inputs and routing

## Behavior 

### Interactive Mode
- Start with "use passist", "run a capability", "what can passist do", or "start usage intake"
- Guide the user through goal analysis
- Show matching capabilities if ambiguous 
- Ask for target inputs from corresponding SKILL.md
- Offer single-run vs interactive handoff
- Execute with proper input collection

### Single-command Mode  
- User provides goal + inputs in one prompt: `use passist — Goal: <what you want>; Inputs: <...>`
- Auto-detect best-fit capability
- Launch target skill/tool with required/missing inputs collected

### No-Match Path (Closed Loop)
- If nothing fits, plain "no match" response
- Offer to hand off to `capability-intake` to build a new capability
- Draft a CR in `docs/change-requests/CR-<id>.md` from the user's goal
- Launch `capability-intake` in plan mode

## Catalog Sources

### Skills Catalog
- Read: all `skills/*/SKILL.md` files for name + description  
- Match user goal vs all skill names/descriptions

### Tools Catalog
- Read: `/home/praddesilva/ProjectTeams/personal-assistant/src/passist/api/TOOLS.md`
- Match user goal vs tool names/descriptions

## Dependencies

This skill depends on all existing skills and tools in the system being readable and accessible. 

## Receipt Exemption  
This skill is **receipt-exempt** as it only delegates to other skills. The invoked skill emits the run receipt.

In metrics/config.json:
```json
{
  "exemptions": {
    "use-capability": "Delegates to target capabilities; receipt emitted by invoked skill"
  }
}
```
