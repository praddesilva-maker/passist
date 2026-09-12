# umcc

**Goal**: Universal Meta-Cognitive Critic - Mandatory QA layer that validates every skill output.

## Runtime Front Door

This skill serves as the mandatory post-processing QA layer in the passist system. It receives outputs from all skills and tools, then performs triple-pass verification:
1. Intent & Ambiguity Alignment
2. Factuality & Provenance (Truth Pass)  
3. Structural & Constraint Integrity

## Behavior

### Triple-Pass Verification Process

**Pass 1: Intent & Ambiguity Alignment**
- Check that output fully addresses every component of the original user goal
- Verify assumptions made by the skill are logical and not hallucinated
- Determine if clarification is needed for ambiguous prompts

**Pass 2: Factuality & Provenance (Truth Pass)**
- Cross-reference all facts against provided sources
- Resolve and validate all URLs/files referenced in output
- Detect fabricated facts or fake citations

**Pass 3: Structural & Constraint Integrity**
- Verify adherence to "Do Not" instructions 
- Check format and syntax compliance with requested output format
- Assess tone consistency and logical soundness 

### Error Handling Protocols

**Protocol A: Correction Manifest (Failure)**
- When the output fails any check, generate a specific correction manifest
- The manifest includes exact details of what needs to be fixed in natural language 
- Return this to original skill for recursive correction loop

**Protocol B: Clarification Trigger (Ambiguity)**  
- If the task was too ambiguous to verify, halt and ask user for clarification before re-handling  

## Receipt Exemption

This skill is **receipt-exempt** as it only serves as a QA layer. It receives inputs from other skills but does not produce its own output that would be counted as a "completed" task.

## Integration Points

- Automatically invoked after every skill/tool execution
- Receives [Task, Output, Sources, Context] from executing skill 
- Can trigger recursive correction loops when validation fails
- Provides mechanism for tool-awareness to expand verification scope over time
