# Launch Prompts

This is the canonical list of launch prompts that trigger skills in passist.

| Skill Name         | Prompt Trigger                    | Description                                              |
|--------------------|-----------------------------------|----------------------------------------------------------|
| skill-reviewer      | "start skill review"              | Review one skill to deliver an expert critique           |
| skill-hygiene-check | "start skill hygiene check"       | Audit fleet for conformance and return PASS/FAIL/N-A table |
| use-capability      | "use passist", "run a capability", "what can passist do", "start usage intake" | Route user's stated goal to the right existing tool or skill and run it |

## Quality Gate Skills

### skill-reviewer
- Trigger: "start skill review" 
- Purpose: Expert critique of a single skill against framework conventions
- Output: Findings table + one-paragraph verdict

### skill-hygiene-check  
- Trigger: "start skill hygiene check"
- Purpose: Mechanical conformance sweep of all skills in fleet
- Output: PASS/FAIL/N-A table + one-line verdict

### use-capability
- Trigger: "use passist", "run a capability", "what can passist do", "start usage intake"
- Purpose: Route user's stated goal to the right existing tool or skill and run it
- Output: Information about matched capability, inputs required, and routing decision

## Launch Prompts for use-capability

**Interactive — route a goal to the right skill and run it:**
```
use passist — I want to <describe your goal in plain English>.

Match my goal to the skill whose description fits (discover from skills/*/SKILL.md and
src/passist/api/TOOLS.md — nothing else); confirm the match with me before running; collect
only the inputs that skill needs, pre-filled from config/default-values.txt where possible;
then run it in its normal dry-run → preview → approval → write flow. If nothing matches,
don't improvise or fabricate a capability — draft a CR for the missing skill and hand it to
capability-intake.
```

**Single-command — goal (and any known inputs) in one line:**
```
use passist — Goal: <what you want done>; Inputs: <any you already know>
```
The router resolves the best-fit capability and asks back only for missing inputs; on a real
no-match it drafts a CR and launches `capability-intake` (the closed loop).