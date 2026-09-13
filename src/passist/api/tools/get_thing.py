"""
Tool for getting a thing from Personal Assist API (read operation)
"""

from pydantic import BaseModel
from typing import Dict, Any
from ...clients.personal_assist_client import client
from ..registry import ToolSpec

class GetThingArgs(BaseModel):
    """Arguments for getThing tool"""
    id: str  # The ID of the thing to retrieve

def run_get_thing(args: GetThingArgs) -> Dict[str, Any]:
    """
    Get a thing by ID from Personal Assist API.
    
    Args:
        args: GetThingArgs containing the thing ID
        
    Returns:
        Dictionary with thing data
    """
    # Call the client's get_thing method
    return client.get_thing(args.id)

# Tool specification
spec = ToolSpec(
    name="getThing",
    description="Read a thing from Personal Assist API by ID",
    side_effect=False,  # Read-only operation
    input_model=GetThingArgs,
    run=run_get_thing
)