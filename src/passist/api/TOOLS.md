# Tools

This is the canonical list of tools available in the passist framework.

| Tool Name    | Description                                 | Side Effect |
|--------------|---------------------------------------------|-------------|
| getThing     | Read a thing from Personal Assist API by ID | No          |
| updateThing  | Update a thing in Personal Assist API by ID | Yes         |
| useCapability| Route user's stated goal to the right existing tool or skill and run it | No          |
| researchAI   | Perform intelligent research on topics with APA citations in multiple formats | Yes         |
| readLocalFile| Read a local .md/.txt/.docx/.pdf and return extracted text + basic metadata | No          |
| umcc         | Universal Meta-Cognitive Critic - mandatory QA layer for validating all skill outputs | No          |

## Tool Details

### getThing
Read a thing from Personal Assist API by ID

**Arguments:**
- `id` (string): The ID of the thing to retrieve

### updateThing  
Update a thing in Personal Assist API by ID

**Arguments:**
- `id` (string): The ID of the thing to update  
- `fields` (object): Fields to update

### useCapability
Route user's stated goal to the right existing tool or skill and run it

**Arguments:**
- `goal` (string): User's stated goal in plain English
- `inputs` (object, optional): Inputs for the capability (if known)

### researchAI
Perform intelligent research on topics with APA citations in multiple formats

**Arguments:**
- `topic` (string): The research topic to investigate
- `level` (string): Research level ("academic", "professional", or "general")
- `format` (string): Output format ("pptx", "docx", "pdf", "md", or "xlsx")

**Side Effect:** Yes - creates files with research results and APA citations

## readLocalFile
Read a local .md/.txt/.docx/.pdf and return extracted text + basic metadata

**Arguments:**
- `path` (string): The path to the local file to read

**Side Effect:** No - this is a read-only operation

## umcc
Universal Meta-Cognitive Critic - mandatory QA layer for validating all skill outputs

**Arguments:**
- `task` (string): The original user task that was executed 
- `output` (object): The output from the skill/tool to be validated
- `sources` (array of strings, optional): Source references used in the output
- `context` (object, optional): Additional context about execution

**Side Effect:** No - this is a read-only validation tool

## Output Format
The umcc tool returns:
- `status` (string): "passed", "failed" or "ambiguous"
- `feedback` (string): Human-readable feedback about validation results  
- `correction_manifest` (string, optional): Manifest for corrections when output fails
- `needs_clarification` (boolean): Whether clarification is needed from user

This tool verifies all outputs through triple-pass verification:
1. Intent & Ambiguity Alignment
2. Factuality & Provenance (Truth Pass)
3. Structural & Constraint Integrity

The tool can trigger a recursive correction loop when issues are found.