#!/usr/bin/env python3
"""
Simple script to generate TOOLS.md
"""

import subprocess
import sys

if __name__ == "__main__":
    # Run the tool documentation generator
    result = subprocess.run([sys.executable, "-m", "passist.api.gen_tools_doc"], 
                          capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✓ TOOLS.md generated successfully")
        print(result.stdout)
    else:
        print("✗ Failed to generate TOOLS.md")
        print(result.stderr)
        sys.exit(1)