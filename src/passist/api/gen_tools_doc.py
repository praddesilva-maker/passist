#!/usr/bin/env python3
"""
Generate TOOLS.md from tool registry.
"""

import os
import sys
from typing import List

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from .registry import TOOLS

def generate_tools_doc(tools: List[dict]) -> str:
    """Generate markdown documentation for all tools."""
    output = "# Tool Catalog\n\n"
    output += "| Name | Type | Description |\n"
    output += "|------|------|-------------|\n"
    
    for tool in tools:
        tool_type = "Write" if tool["side_effect"] else "Read"
        output += f"| {tool['name']} | {tool_type} | {tool['description']} |\n"
    
    output += "\n## Tool Details\n\n"
    
    for tool in tools:
        output += f"### {tool['name']}\n\n"
        output += f"**Type:** {'Write' if tool['side_effect'] else 'Read'}\n\n"
        output += f"**Description:** {tool['description']}\n\n"
        
        # Generate input schema from Pydantic model
        model = tool['input_model']
        output += "**Input Schema:**\n\n"
        output += "```json\n"
        try:
            # Try to get the model fields and their descriptions
            schema = model.model_json_schema()
            output += str(schema)
        except Exception:
            output += "Schema definition not available\n"
        output += "\n```\n\n"
        
        if tool["side_effect"]:
            output += "**Note:** This is a write operation that requires the `--confirm` flag to execute.\n\n"
            
    return output

def main():
    """Main entry point"""
    doc_content = generate_tools_doc(TOOLS)
    
    # Write to TOOLS.md
    tools_md_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "TOOLS.md")
    with open(tools_md_path, 'w') as f:
        f.write(doc_content)
    
    print(f"Generated {tools_md_path}")

if __name__ == "__main__":
    main()