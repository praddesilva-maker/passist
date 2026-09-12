#!/usr/bin/env python3
"""
Budget Tracker Excel Creator Script

This script demonstrates how to programmatically create a home budget tracker Excel file.
Note: This requires the 'openpyxl' library to be installed in your Python environment.

To install the required library:
pip install openpyxl

Usage: python budget_tracker_creator.py
"""

import os
from datetime import datetime

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    print("openpyxl library is available - Excel file will be created")
    LIBRARY_AVAILABLE = True
except ImportError:
    print("openpyxl library is NOT available. This script will show you the structure only.")
    print("Install with: pip install openpyxl")
    LIBRARY_AVAILABLE = False

def create_budget_tracker():    """Create a comprehensive budget tracker Excel file"""
    
    if not LIBRARY_AVAILABLE:
        print("Creating budget tracker structure documentation instead of actual Excel file...")
        # Create a text representation of what the Excel file would contain
        structure_doc = """
BUDGET TRACKER EXCEL FILE STRUCTURE DOCUMENTATION
        
This is how your Excel file would be structured:

SHEET 1: Expense Tracking
Columns:
A1 Date (mm/dd/yyyy) 
B1 Category (dropdown: Housing, Food, Transportation, Utilities, Entertainment, Healthcare, Education, Clothing, Insurance, Other)
C1 Description
D1 Amount ($)
E1 Payment Method (Cash, Credit Card, Debit Card, Check)
F1 Budgeted Amount ($)
G1 Actual vs Budget (Formula: =F1-D1)
H1 Notes

SHEET 2: Expense Categories  
List of categories:
- Housing
- Food
- Transportation
- Utilities
- Entertainment
- Healthcare
- Education
- Clothing
- Insurance
- Other

SHEET 3: Savings Goals
Columns:
A1 Goal Name (Emergency Fund, Retirement, Children's Education, Big Purchases)
B1 Target Amount ($)
C1 Current Savings ($)
D1 Progress (%) (Formula: =(C1/B1)*100) 
E1 Timeline (Months)
F1 Monthly Contribution ($) (Formula: =(B1-C1)/E1)
G1 Start Date
H1 Status (Not Started, In Progress, Completed)
I1 Notes

SHEET 4: Monthly Summary
Columns:
A1 Month/Year
B1 Total Income ($)
C1 Total Expenses ($)
D1 Net Savings ($) (Formula: =B1-C1)
E1 Budget Variance ($) (Difference between budgeted and actual)
F1 Categories Overview (Text notes)
G1 Goal Progress Summary (Text notes)  
H1 Notes

SHEET 5: Budget Tracking
Columns:
A1 Category
B1 Monthly Budget ($)
C1 Actual Spending ($)
D1 Difference ($) (Formula: =B1-C1)
E1 Percentage of Budget Used (%) (Formula: =(C1/B1)*100)
F1 Status (Over, Under, Budgeted) 
G1 Notes

Key Features:
- Data validation for dropdown lists
- Formulas for automatic calculations
- Conditional formatting capabilities  
- Chart-ready data structure
        """
        with open('/home/praddesilva/ProjectTeams/personal-assistant/deliverables/budget_tracker_structure.txt', 'w') as f:
            f.write(structure_doc)
        print("Created budget_tracker_structure.txt with file structure documentation")
        return
    
    # If library is available, create the actual Excel file
    wb = Workbook()
    
    # Remove the default sheet
    wb.remove(wb.active)
    
    # Create sheets
    expense_sheet = wb.create_sheet("Expense Tracking")
    categories_sheet = wb.create_sheet("Expense Categories") 
    savings_sheet = wb.create_sheet("Savings Goals")
    summary_sheet = wb.create_sheet("Monthly Summary")
    budget_sheet = wb.create_sheet("Budget Tracking")
    
    # Format headers with bold font
    header_font = Font(bold=True)
    center_align = Alignment(horizontal="center")
    
    # Sheet 1: Expense Tracking
    expense_headers = ["Date", "Category", "Description", "Amount ($)", "Payment Method", 
                       "Budgeted Amount ($)", "Actual vs Budget", "Notes"]
    for col, header in enumerate(expense_headers, 1):
        cell = expense_sheet.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.alignment = center_align
    
    # Sheet 2: Expense Categories  
    categories_headers = ["Category"]
    for col, header in enumerate(categories_headers, 1):
        cell = categories_sheet.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.alignment = center_align
    
    # Add sample categories
    categories = ["Housing", "Food", "Transportation", "Utilities", "Entertainment", 
                  "Healthcare", "Education", "Clothing", "Insurance", "Other"]
    for i, category in enumerate(categories, 2):
        categories_sheet.cell(row=i, column=1, value=category)
    
    # Sheet 3: Savings Goals
    savings_headers = ["Goal Name", "Target Amount ($)", "Current Savings ($)", "Progress (%)",
                      "Timeline (Months)", "Monthly Contribution ($)", "Start Date", 
                      "Status", "Notes"]
    for col, header in enumerate(savings_headers, 1):
        cell = savings_sheet.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.alignment = center_align
    
    # Sheet 4: Monthly Summary
    summary_headers = ["Month/Year", "Total Income ($)", "Total Expenses ($)", "Net Savings ($)",
                       "Budget Variance ($)", "Categories Overview", "Goal Progress Summary", "Notes"]
    for col, header in enumerate(summary_headers, 1):
        cell = summary_sheet.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.alignment = center_align
    
    # Sheet 5: Budget Tracking  
    budget_headers = ["Category", "Monthly Budget ($)", "Actual Spending ($)", "Difference ($)",
                      "Percentage of Budget Used (%)", "Status", "Notes"]
    for col, header in enumerate(budget_headers, 1):
        cell = budget_sheet.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.alignment = center_align
    
    # Save the workbook
    filename = "/home/praddesilva/ProjectTeams/personal-assistant/deliverables/home_budget_tracker.xlsx"
    wb.save(filename)
    print(f"Excel file created successfully: {filename}")

if __name__ == "__main__":
    create_budget_tracker()