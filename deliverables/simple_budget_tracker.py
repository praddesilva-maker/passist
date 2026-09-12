#!/usr/bin/env python3
"""
Simple Budget Tracker Creator - No External Dependencies

This script creates CSV files that can be easily opened in Excel.
It simulates the structure of a budget tracking spreadsheet without requiring external libraries.
"""

import csv
import os
from datetime import datetime

def create_budget_structure():
    """Create CSV files that represent the budget tracking structure"""
    
    # Create directory if it doesn't exist
    output_dir = "/home/praddesilva/ProjectTeams/personal-assistant/deliverables"
    os.makedirs(output_dir, exist_ok=True)
    
    print("Creating simple budget tracker structure using CSV files...")
    
    # Sheet 1: Expense Tracking (CSV format)
    expense_data = [
        ["Date", "Category", "Description", "Amount ($)", "Payment Method", "Budgeted Amount ($)", "Actual vs Budget", "Notes"],
        ["2023-01-01", "Housing", "Rent", "1200.00", "Check", "1200.00", "0.00", ""],
        ["2023-01-02", "Food", "Groceries", "150.00", "Credit Card", "200.00", "-50.00", "Monthly groceries"],
        ["2023-01-03", "Transportation", "Gas", "45.00", "Debit Card", "50.00", "-5.00", ""],
        ["2023-01-04", "Entertainment", "Movies", "35.00", "Credit Card", "40.00", "-5.00", ""],
        ["2023-01-05", "Healthcare", "Medication", "75.00", "Credit Card", "80.00", "-5.00", ""]
    ]
    
    with open(os.path.join(output_dir, "expense_tracking.csv"), 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(expense_data)
    
    # Sheet 2: Expense Categories 
    categories_data = [
        ["Category"],
        ["Housing"],
        ["Food"],
        ["Transportation"],
        ["Utilities"],
        ["Entertainment"],
        ["Healthcare"],
        ["Education"],
        ["Clothing"],
        ["Insurance"],
        ["Other"]
    ]
    
    with open(os.path.join(output_dir, "expense_categories.csv"), 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(categories_data)
    
    # Sheet 3: Savings Goals
    savings_data = [
        ["Goal Name", "Target Amount ($)", "Current Savings ($)", "Progress (%)", "Timeline (Months)", 
         "Monthly Contribution ($)", "Start Date", "Status", "Notes"],
        ["Emergency Fund", "5000.00", "2500.00", "50.00", "12", "208.33", "2023-01-01", "In Progress", "3 months left to reach goal"],
        ["Retirement", "50000.00", "15000.00", "30.00", "60", "250.00", "2023-01-01", "In Progress", ""],
        ["Children's Education", "10000.00", "3000.00", "30.00", "36", "277.78", "2023-01-01", "In Progress", ""],
        ["Big Purchase (Car)", "15000.00", "5000.00", "33.33", "24", "625.00", "2023-01-01", "In Progress", ""]
    ]
    
    with open(os.path.join(output_dir, "savings_goals.csv"), 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(savings_data)
    
    # Sheet 4: Monthly Summary
    summary_data = [
        ["Month/Year", "Total Income ($)", "Total Expenses ($)", "Net Savings ($)", "Budget Variance ($)",
         "Categories Overview", "Goal Progress Summary", "Notes"],
        ["January 2023", "5000.00", "3200.00", "1800.00", "200.00", 
         "Housing: 30%, Food: 15%, Transportation: 10%", "Emergency Fund: 50%, Retirement: 30%", "Initial month summary"]
    ]
    
    with open(os.path.join(output_dir, "monthly_summary.csv"), 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(summary_data)
    
    # Sheet 5: Budget Tracking
    budget_data = [
        ["Category", "Monthly Budget ($)", "Actual Spending ($)", "Difference ($)", "Percentage of Budget Used (%)", "Status", "Notes"],
        ["Housing", "1200.00", "1200.00", "0.00", "100.00", "Budgeted", ""],
        ["Food", "200.00", "150.00", "50.00", "75.00", "Under", ""],
        ["Transportation", "50.00", "45.00", "5.00", "90.00", "Under", ""],
        ["Utilities", "100.00", "85.00", "15.00", "85.00", "Under", ""]
    ]
    
    with open(os.path.join(output_dir, "budget_tracking.csv"), 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(budget_data)
    
    print("Successfully created CSV files for budget tracking:")
    print("1. expense_tracking.csv")
    print("2. expense_categories.csv") 
    print("3. savings_goals.csv")
    print("4. monthly_summary.csv")
    print("5. budget_tracking.csv")
    print("\nTo open in Excel:")
    print("- Open Excel")
    print("- Go to File → Open")
    print("- Navigate to the deliverables folder")
    print("- Select any of these CSV files")
    print("- Excel will import them, preserving the structure")

if __name__ == "__main__":
    create_budget_structure()