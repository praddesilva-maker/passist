"""
In-process CLI dispatcher for passist framework.
This is the fallback path when warm server is not available.
"""

import json
import sys
from typing import Any, Dict
from .registry import TOOLS_BY_NAME

def run_tool(tool_name: str, args: Dict[str, Any], confirm: bool = False) -> Dict[str, Any]:
    """
    Run a tool in-process with validation and write gate enforcement.
    
    Args:
        tool_name: Name of the tool to run
        args: Arguments for the tool
        confirm: Whether to allow side-effect operations
    
    Returns:
        Result from the tool execution
        
    Raises:
        ValueError: If tool is not found or arguments are invalid
        PermissionError: If write operation requires confirmation
    """
    # Look up the tool in registry
    if tool_name not in TOOLS_BY_NAME:
        raise ValueError(f"Tool '{tool_name}' not found")
    
    tool_spec = TOOLS_BY_NAME[tool_name]
    
    # Validate arguments using Pydantic model
    validated_args = tool_spec.input_model(**args)
    
    # Enforce write gate for side-effect operations  
    if tool_spec.side_effect and not confirm:
        raise PermissionError(f"Write operation requires --confirm flag")
    
    # Execute the tool function
    try:
        result = tool_spec.run(validated_args)
        return {"ok": True, "result": result}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def main():
    """Main entry point for CLI operation"""
    if len(sys.argv) < 2:
        print("Usage: python -m passist.api.cli <tool_name>", file=sys.stderr)
        sys.exit(1)
    
    tool_name = sys.argv[1]
    
    # Read arguments from stdin (JSON)
    try:
        stdin_input = sys.stdin.read()
        if not stdin_input.strip():
            args = {}
        else:
            args = json.loads(stdin_input)
        
        confirm = "--confirm" in sys.argv or "-c" in sys.argv
        
        # Run the tool
        result = run_tool(tool_name, args, confirm)
        
        # Print result to stdout as JSON
        print(json.dumps(result))
        
    except Exception as e:
        # Log errors to stderr
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()