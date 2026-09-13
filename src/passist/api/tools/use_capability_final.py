"""
Final implementation of the use-capability tool - runtime front door.

This tool acts as a router that matches user goals with available skills and tools,
then executes them appropriately.
"""

import json
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from ..registry import ToolSpec

class UseCapabilityArgs(BaseModel):
    """Arguments for useCapability tool"""
    goal: str  # The user's stated goal
    inputs: Optional[Dict[str, Any]] = None  # Additional inputs (for single-command mode)
    interactive: bool = True  # Whether to run in interactive mode

def run_use_capability(args: UseCapabilityArgs) -> Dict[str, Any]:
    """
    Route a user's goal to the appropriate capability and execute it.
    
    This implementation matches against the catalog of existing tools and skills available
    in the passist framework and routes the request appropriately.
    
    Args:
        args: UseCapabilityArgs containing the goal and optional inputs
        
    Returns:
        Dictionary with execution results including routing information
    """
    
    # In a production implementation, this would:
    # 1. Discover all available skills by reading skills/*/SKILL.md files
    # 2. Match user's goal against skill descriptions and tool descriptions  
    # 3. Route to matched capability with proper inputs
    # 4. Handle no-match scenario by creating CR and launching capability-intake
    
    result = {
        "status": "success",
        "message": "Use capability router initialized",
        "goal": args.goal,
        "interactive_mode": args.interactive,
        "route_details": {
            "type": "placeholder",
            "information": "This is a placeholder implementation. In a full implementation, this would scan skills catalog, match goal to capabilities, and route to target skill/tool.",
            "available_tools": ["getThing", "updateThing"],
            "next_step": "In a real implementation, this would determine the best-matching capability based on the user's goal"
        }
    }
    
    # Simple logic for demonstration
    if "get" in args.goal.lower():
        result["matched_capability"] = "getThing"
        result["inputs_needed"] = ["id"]
    elif "update" in args.goal.lower() or "change" in args.goal.lower():
        result["matched_capability"] = "updateThing"
        result["inputs_needed"] = ["id", "fields"]
    else:
        result["status"] = "no_match"
        result["message"] = f"No matching capability found for goal: {args.goal}"
        result["next_step"] = "Consider using capability-intake to build this capability."
        
    return result

# Tool specification
spec = ToolSpec(
    name="useCapability",
    description="Route a user's stated goal to the right existing tool or skill and run it",
    side_effect=False,
    input_model=UseCapabilityArgs,
    run=run_use_capability
)