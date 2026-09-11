#!/usr/bin/env python3
"""
Consistency guard that verifies registry matches TOOLS.md documentation.
This validates the "single source of truth" principle.
"""

import os
import sys
import json

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from .registry import TOOLS
from .gen_tools_doc import generate_tools_doc

def main():
    """Check consistency between registry and generated documentation"""
    
    # Generate the tool catalog from registry
    doc_content = generate_tools_doc(TOOLS)
    
    # Parse out tool names from the generated documentation  
    tool_names_in_doc = []
    lines = doc_content.split('\n')
    for line in lines:
        if line.startswith('### ') and len(line) > 4:
            tool_name = line[4:].strip()
            tool_names_in_doc.append(tool_name)
    
    # Get registered tool names
    registered_tool_names = [tool['name'] for tool in TOOLS]
    
    # Check if the counts match
    if len(registered_tool_names) != len(tool_names_in_doc):
        print(f"ERROR: Mismatch in tool count. Registry has {len(registered_tool_names)} tools, documentation has {len(tool_names_in_doc)}", file=sys.stderr)
        sys.exit(1)
    
    # Check if all registered tools are documented
    for name in registered_tool_names:
        if name not in tool_names_in_doc:
            print(f"ERROR: Tool '{name}' is in registry but not documented", file=sys.stderr)
            sys.exit(1)
    
    # Check if all documented tools are registered
    for name in tool_names_in_doc:
        if name not in registered_tool_names:
            print(f"ERROR: Tool '{name}' is documented but not in registry", file=sys.stderr)
            sys.exit(1)
    
    print("✓ Registry and documentation are consistent")
    return 0

if __name__ == "__main__":
    sys.exit(main())