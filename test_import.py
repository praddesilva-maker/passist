#!/usr/bin/env python3

"""
Test script to validate that excel_creator.py can be imported correctly
"""
import sys
import os

# Add current directory to path to mimic how it would work in framework environment  
sys.path.insert(0, '/home/praddesilva/ProjectTeams/personal-assistant/src')

try:
    # Test importing the module we created
    from passist.api.tools.excel_creator import spec
    print("SUCCESS: excel_creator tool imported successfully")
    print(f"Tool name: {spec.name}")
    print(f"Tool description: {spec.description}")
    
    # Test creating args and running function (will fail since no skill impl exists but we'll see if imports work)
    from passist.api.tools.excel_creator import ExcelCreatorArgs
    args = ExcelCreatorArgs(topic="Test Budget Tracker")
    print("SUCCESS: Args model imported and instantiated successfully")
    
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()