"""
Tool for updating a thing in Personal Assist API (write operation)
"""

from pydantic import BaseModel
from typing import Dict, Any
from ...clients.personal_assist_client import client
from ..registry import ToolSpec

class UpdateThingArgs(BaseModel):
    """Arguments for updateThing tool"""
    id: str  # The ID of the thing to update
    fields: Dict[str, Any]  # Fields to update

def run_update_thing(args: UpdateThingArgs) -> Dict[str, Any]:
    """
    Update a thing in Personal Assist API.
    
    Args:
        args: UpdateThingArgs containing the thing ID and fields to update
        
    Returns:
        Dictionary with operation result
    """
    # Call the client's update_thing method
    return client.update_thing(args.id, args.fields)

# Tool specification
spec = ToolSpec(
    name="updateThing",
    description="Update a thing in Personal Assist API by ID",
    side_effect=True,  # Write operation
    input_model=UpdateThingArgs,
    run=run_update_thing
)