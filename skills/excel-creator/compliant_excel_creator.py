#!/usr/bin/env python3
"""
Compliant Excel Creator for Budget Tracking

This script demonstrates how a skill should be implemented with proper folder management
using the passist framework's skill_execution_context.
"""

import os
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

def create_budget_tracker():
    """Create a comprehensive budget tracker Excel file with all required sheets"""
    
    # Use skill execution context for proper temp/deliverables management
    from src.passist.api.skill_folder_manager import skill_execution_context
    
    with skill_execution_context() as (temp_dir, deliverables_dir):
        print(f"Using temp directory: {temp_dir}")
        print(f"Using deliverables directory: {deliverables_dir}")
        
        # Create workbook and worksheets - this happens in temp directory
        wb = Workbook()
        
        # Remove default sheet
        wb.remove(wb.active)
        
        # Create the 5 required sheets
        expense_sheet = wb.create_sheet(title="Expense Tracking")
        categories_sheet = wb.create_sheet(title="Expense Categories")
        savings_sheet = wb.create_sheet(title="Savings Goals")
        summary_sheet = wb.create_sheet(title="Monthly Summary")
        budget_sheet = wb.create_sheet(title="Budget Tracking")
        
        # Define styles
        header_font = Font(bold=True, size=12)
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        header_alignment = Alignment(horizontal="center", vertical="center")
        border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # ==================== Budget Tracking Sheet ====================
        budget_sheet.append([
            "Category", "Monthly Budget ($)", "Actual Spending ($)", "Difference ($)",
            "Percentage of Budget Used (%)", "Status", "Notes"
        ])
        
        # Format header
        for col in range(1, 8):
            cell = budget_sheet.cell(row=1, column=col)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = border
        
        # Add sample data  
        budget_data = [
            ["Housing", 1200.00, 1200.00, 0.00, 100.00, "Budgeted", ""],
            ["Food", 200.00, 150.00, 50.00, 75.00, "Under", ""],
            ["Transportation", 50.00, 45.00, 5.00, 90.00, "Under", ""],
            ["Utilities", 100.00, 85.00, 15.00, 85.00, "Under", ""]
        ]
        
        for row_num, data in enumerate(budget_data, start=2):
            for col_num, value in enumerate(data, start=1):
                budget_sheet.cell(row=row_num, column=col_num, value=value)
                
        # Add formulas 
        # Percentage of Budget Used: =C2/B2*100 (Column E)
        for row in range(2, 6):
            formula = f"=C{row}/B{row}*100"
            budget_sheet.cell(row=row, column=5, value=formula)
            
        # Add data validation to Status column (F)
        status_dv_budget = DataValidation(type="list", formula1='"Over,Under,Budgeted"', allow_blank=True)
        budget_sheet.add_data_validation(status_dv_budget)
        status_dv_budget.add(budget_sheet["F2:F5"])
        
        # Set column widths
        budget_sheet.column_dimensions["A"].width = 15
        budget_sheet.column_dimensions["B"].width = 18
        budget_sheet.column_dimensions["C"].width = 18
        budget_sheet.column_dimensions["D"].width = 18
        budget_sheet.column_dimensions["E"].width = 20
        budget_sheet.column_dimensions["F"].width = 15
        budget_sheet.column_dimensions["G"].width = 30
        
        # Save to deliverables directory (this will be cleaned up automatically after successful execution)
        filename = f"home_budget_tracker_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        output_path = os.path.join(deliverables_dir, filename)
        
        wb.save(output_path)
        print(f"Successfully created Excel budget tracker: {output_path}")
        
        # Return result information  
        return {
            "success": True,
            "filename": filename,
            "filepath": output_path,
            "message": f"Excel budget tracker created successfully in deliverables directory"
        }

if __name__ == "__main__":
    # Example usage with skill execution context
    try:
        result = create_budget_tracker()
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error creating budget tracker: {str(e)}")
        raise