"""
Tool for creating Excel budget trackers - integrates with skill framework
"""

from pydantic import BaseModel
from typing import Dict, Any
from ..registry import ToolSpec

class ExcelCreatorArgs(BaseModel):
    """Arguments for excel-creator tool"""
    topic: str  # The topic/subject of the budget tracker 
    format: str = "xlsx"  # Output format (currently only supports xlsx)

def run_excel_creator(args: ExcelCreatorArgs) -> Dict[str, Any]:
    """
    Run the excel creator skill through the framework.
    
    This tool acts as a bridge to execute the excel-creator skill,
    leveraging the skill execution context for proper file management.
    
    Args:
        args: ExcelCreatorArgs containing topic and format
        
    Returns:
        Dictionary with execution results
    """
    try:
        # Add the project root to Python path so we can import skills properly
        import os
        import sys
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        
        # Import the skill implementation directly from its file 
        from skills.excel_creator.excel_creator import create_budget_tracker
        
        # Create files using the skill directly - pass the topic argument
        result = create_budget_tracker(args.topic)
        
        return {
            "success": True,
            "filename": result["filename"],
            "filepath": result["filepath"],
            "message": f"Budget tracker created successfully for topic: {args.topic}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to create budget tracker for topic: {args.topic}"
        }

# Tool specification
spec = ToolSpec(
    name="excel-creator",
    description="Create comprehensive Excel spreadsheets with multiple sheets for budget tracking, expense management, and financial analysis",
    side_effect=True,  # Write operation
    input_model=ExcelCreatorArgs,
    run=run_excel_creator
)