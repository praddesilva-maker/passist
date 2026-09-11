# Tools

This is the canonical list of tools available in the passist framework.

| Tool Name    | Description                                 | Side Effect |
|--------------|---------------------------------------------|-------------|
| getThing     | Read a thing from Personal Assist API by ID | No          |
| updateThing  | Update a thing in Personal Assist API by ID | Yes         |
| useCapability| Route user's stated goal to the right existing tool or skill and run it | No          |

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