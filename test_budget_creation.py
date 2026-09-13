#!/usr/bin/env python3
"""
Simple script to test creating a budget tracker Excel file
"""
import os
import sys

# Add the project root to the path so we can import from src
sys.path.insert(0, '/home/praddesilva/ProjectTeams/personal-assistant')

# Import the function from the excel creator 
from skills.excel_creator.final_excel_creator import create_budget_tracker

def main():
    print("Creating budget tracker Excel file...")
    
    try:
        # Create the budget tracker
        result = create_budget_tracker()
        print(f"Successfully created budget tracker: {result}")
        return 0
    except Exception as e:
        print(f"Error creating budget tracker: {str(e)}")
        return 1

if __name__ == "__main__":
    exit(main())