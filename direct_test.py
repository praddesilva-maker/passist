#!/usr/bin/env python3

import sys
import os

# Add project root to path
sys.path.insert(0, '/home/praddesilva/ProjectTeams/personal-assistant')

# Ensure the deliverables directory exists
os.makedirs('/home/praddesilva/ProjectTeams/personal-assistant/deliverables', exist_ok=True)

# Try to import and run the function
try:
    from skills.excel_creator.final_excel_creator import create_budget_tracker
    print("Function imported successfully")
    
    result = create_budget_tracker()
    print(f"Function executed successfully: {result}")
    
except ImportError as e:
    print(f"Import error: {e}")
except Exception as e:
    print(f"Error running function: {e}")

print("Script completed")