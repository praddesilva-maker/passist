#!/usr/bin/env python3
"""
Simple test of excel-creator function directly.
"""

import sys
import os

# Add project root to Python path  
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def test_excel_creator():
    try:
        # Import and run it directly
        from skills.excel_creator.excel_creator import create_budget_tracker
        
        print("Testing excel-creator with topic 'Home Budget Tracker'...")
        
        result = create_budget_tracker("Home Budget Tracker")
        
        if result.get('success'):
            print(f"✓ SUCCESS: {result['message']}")
            print(f"  File created: {result['filepath']}")
            return True
        else:
            print(f"✗ FAILED: {result['message']}")
            return False
            
    except Exception as e:
        print(f"✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_excel_creator()
    sys.exit(0 if success else 1)