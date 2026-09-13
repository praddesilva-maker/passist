#!/usr/bin/env python3
"""
Simple home budget tracker creator using openpyxl.
This creates a basic Excel workbook with multiple sheets for home budget management.
"""

import os
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

def create_home_budget_tracker():
    """Create a comprehensive home budget tracker Excel file"""
    
    # Create workbook and remove default sheet
    wb = Workbook()
    wb.remove(wb.active)
    
    # Create sheets
    income_sheet = wb.create_sheet(title="Income Tracking")
    categories_sheet = wb.create_sheet(title="Expense Categories") 
    transactions_sheet = wb.create_sheet(title="Transactions")
    summary_sheet = wb.create_sheet(title="Summary")
    
    # Header styling
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    center_align = Alignment(horizontal="center")
    
    # Income Tracking Sheet
    income_sheet.append(["Date", "Source", "Amount"])
    income_sheet['A1'].font = header_font
    income_sheet['B1'].font = header_font
    income_sheet['C1'].font = header_font
    income_sheet['A1'].fill = header_fill
    income_sheet['B1'].fill = header_fill
    income_sheet['C1'].fill = header_fill
    
    # Add sample data
    income_sheet.append([datetime.now().strftime("%Y-%m-%d"), "Salary", 3500.00])
    income_sheet.append([datetime.now().strftime("%Y-%m-%d"), "Freelance", 500.00])
    
    # Expense Categories Sheet
    categories_sheet.append(["Category", "Budget", "Spent", "Remaining"])
    categories_sheet['A1'].font = header_font
    categories_sheet['B1'].font = header_font
    categories_sheet['C1'].font = header_font
    categories_sheet['D1'].font = header_font
    categories_sheet['A1'].fill = header_fill
    categories_sheet['B1'].fill = header_fill
    categories_sheet['C1'].fill = header_fill
    categories_sheet['D1'].fill = header_fill
    
    # Add sample expense categories
    categories_sheet.append(["Housing", 1200.00, 0, 1200.00])
    categories_sheet.append(["Food", 400.00, 0, 400.00])
    categories_sheet.append(["Transportation", 200.00, 0, 200.00])
    categories_sheet.append(["Entertainment", 150.00, 0, 150.00])
    categories_sheet.append(["Utilities", 300.00, 0, 300.00])
    
    # Transactions Sheet
    transactions_sheet.append(["Date", "Category", "Description", "Amount"])
    transactions_sheet['A1'].font = header_font
    transactions_sheet['B1'].font = header_font
    transactions_sheet['C1'].font = header_font
    transactions_sheet['D1'].font = header_font
    transactions_sheet['A1'].fill = header_fill
    transactions_sheet['B1'].fill = header_fill
    transactions_sheet['C1'].fill = header_fill
    transactions_sheet['D1'].fill = header_fill
    
    # Add sample transactions
    transactions_sheet.append([datetime.now().strftime("%Y-%m-%d"), "Housing", "Monthly rent", 1200.00])
    transactions_sheet.append([datetime.now().strftime("%Y-%m-%d"), "Food", "Groceries", 150.00])
    
    # Summary Sheet
    summary_sheet.append(["Item", "Value"])
    summary_sheet['A1'].font = header_font
    summary_sheet['B1'].font = header_font
    summary_sheet['A1'].fill = header_fill
    summary_sheet['B1'].fill = header_fill
    
    # Add summary data
    summary_sheet.append(["Total Income", 4000.00])
    summary_sheet.append(["Total Expenses", 1350.00])
    summary_sheet.append(["Net Savings", 2650.00])
    
    # Format columns for better readability
    for sheet in [income_sheet, categories_sheet, transactions_sheet, summary_sheet]:
        for col in sheet.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2)
            sheet.column_dimensions[column].width = adjusted_width
    
    # Save the workbook
    filename = "Home_Budget_Tracker.xlsx"
    wb.save(filename)
    print(f"Successfully created budget tracker: {filename}")
    
    return {
        "success": True,
        "filename": filename,
        "message": f"Home budget tracker created successfully"
    }

if __name__ == "__main__":
    try:
        result = create_home_budget_tracker()
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error creating budget tracker: {str(e)}")
        raise