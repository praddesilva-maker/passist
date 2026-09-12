# Tools

This is the canonical list of tools available in the passist framework.

| Tool Name    | Description                                 | Side Effect |
|--------------|---------------------------------------------|-------------|
| getThing     | Read a thing from Personal Assist API by ID | No          |
| updateThing  | Update a thing in Personal Assist API by ID | Yes         |
| useCapability| Route user's stated goal to the right existing tool or skill and run it | No          |
| researchAI   | Perform intelligent research on topics with APA citations in multiple formats | Yes         |

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

## Output Format
The researchAI tool generates documents with proper APA formatting:
- Academic: Peer-reviewed sources, scholarly articles
- Professional: Industry reports, expert opinions  
- General: News sources, public information

**Note:** This tool will be fully functional when implemented with appropriate libraries (docx, pptx, openpyxl) for document generation.