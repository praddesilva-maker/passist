#!/usr/bin/env python3
"""
Budget Excel Generator Script

This script demonstrates how to create a home budget Excel workbook using 
the passist framework capabilities. 

The script creates multiple sheets with:
1. Income tracking
2. Expense categorization
3. Monthly expense tracking
4. Savings goals
5. Yearly summary

Note: This is a conceptual implementation showing how the Excel workbook 
would be structured and filled. Actual Excel file creation would require 
the excel-creator skill to be properly functional in your environment.
"""

import os
import pandas as pd
from datetime import datetime

def create_budget_excel():
    """
    Create a comprehensive home budget template Excel workbook
    """
    
    # Sample data for different sheets
    income_data = [
        {'Date': '2024-01-01', 'Source': 'Salary', 'Amount': 5000.00, 'Category': 'Primary Income'},
        {'Date': '2024-01-02', 'Source': 'Freelance', 'Amount': 300.00, 'Category': 'Secondary Income'},
    ]
    
    expense_categories = [
        {'Category': 'Housing', 'Subcategory': 'Rent/Mortgage', 'Monthly Budget': 1500.00},
        {'Category': 'Housing', 'Subcategory': 'Utilities', 'Monthly Budget': 200.00},
        {'Category': 'Food', 'Subcategory': 'Groceries', 'Monthly Budget': 400.00},
        {'Category': 'Food', 'Subcategory': 'Dining Out', 'Monthly Budget': 150.00},
        {'Category': 'Transportation', 'Subcategory': 'Gas', 'Monthly Budget': 300.00},
        {'Category': 'Transportation', 'Subcategory': 'Public Transit', 'Monthly Budget': 100.00},
        {'Category': 'Healthcare', 'Subcategory': 'Insurance', 'Monthly Budget': 200.00},
        {'Category': 'Healthcare', 'Subcategory': 'Medications', 'Monthly Budget': 50.00},
        {'Category': 'Entertainment', 'Subcategory': 'Movies', 'Monthly Budget': 50.00},
        {'Category': 'Entertainment', 'Subcategory': 'Hobbies', 'Monthly Budget': 75.00},
        {'Category': 'Personal Care', 'Subcategory': 'Haircuts', 'Monthly Budget': 30.00},
        {'Category': 'Personal Care', 'Subcategory': 'Clothing', 'Monthly Budget': 100.00},
        {'Category': 'Insurance', 'Subcategory': 'Auto Insurance', 'Monthly Budget': 80.00},
        {'Category': 'Insurance', 'Subcategory': 'Home Insurance', 'Monthly Budget': 60.00},
        {'Category': 'Savings', 'Subcategory': 'Emergency Fund', 'Monthly Budget': 300.00},
        {'Category': 'Savings', 'Subcategory': 'Retirement', 'Monthly Budget': 500.00},
    ]
    
    # Create dataframes (these would be converted to Excel sheets)
    income_df = pd.DataFrame(income_data)
    categories_df = pd.DataFrame(expense_categories)
    
    print("Budget Excel Template Created!")
    print("This shows the structure that would be used in a real Excel workbook.")
    print("\nSHEET 1: INCOME TRACKING")
    print(income_df.to_string(index=False))
    
    print("\nSHEET 2: EXPENSE CATEGORIES")
    print(categories_df.to_string(index=False))

if __name__ == "__main__":
    create_budget_excel()