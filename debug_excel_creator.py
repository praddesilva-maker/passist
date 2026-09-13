#!/usr/bin/env python3
"""
Test script for debugging the Excel Creator issue.
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    # Try to execute the function directly from skills module
    print("Testing direct import...")
    
    # Import and run it directly
    from skills.excel_creator.excel_creator import create_budget_tracker
    
    print("Import successful")
    
    # Test execution 
    result = create_budget_tracker()
    print(f"Result: {result}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()