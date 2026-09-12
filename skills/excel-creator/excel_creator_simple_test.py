#!/usr/bin/env python3

import os
from openpyxl import Workbook

def test_basic_excel_creation():
    # Basic test of excel creation to validate our setup
    wb = Workbook()
    ws = wb.active
    ws.title = "Test Budget Sheet"
    ws['A1'] = 'Test Cell'
    
    output_dir = "/home/praddesilva/ProjectTeams/personal-assistant/deliverables"
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, "test_budget.xlsx")
    wb.save(filename)
    print(f"Created test Excel file: {filename}")

if __name__ == "__main__":
    test_basic_excel_creation()
    print("Test script completed successfully")