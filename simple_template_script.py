#!/usr/bin/env python3
"""
Simple home renovation template creator.
"""

import pandas as pd
from datetime import datetime

def create_simple_template():
    # Create minimal sample data
    project_overview = pd.DataFrame({
        'Project Name': ['Whole House Renovation'],
        'Start Date': [datetime.now().strftime('%Y-%m-%d')],
        'Status': ['Planning']
    })
    
    room_budgets = pd.DataFrame({
        'Room': ['Kitchen', 'Bathroom', 'Living Room'],
        'Estimated Budget': ['$25,000', '$8,000', '$15,000'],
        'Actual Spent': ['$0', '$0', '$0']
    })
    
    # Create spreadsheet with 3 sheets
    try:
        with pd.ExcelWriter('home_renovation_template.xlsx', engine='openpyxl') as writer:
            project_overview.to_excel(writer, sheet_name='Project Overview', index=False)
            room_budgets.to_excel(writer, sheet_name='Room Budgets', index=False)
            
            # Add a simple instructions sheet
            instructions = pd.DataFrame({
                'Instructions': [
                    'Home Renovation Project Template',
                    'Update data in each tab as your project progresses',
                    'This is a simplified version - full template has more features'
                ]
            })
            instructions.to_excel(writer, sheet_name='Instructions', index=False)
        
        print("Basic home renovation Excel template created successfully!")
        return True
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

if __name__ == "__main__":
    create_simple_template()