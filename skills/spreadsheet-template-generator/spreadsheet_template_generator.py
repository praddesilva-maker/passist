def generate_task_management_template() -> str:
    """Generate a task management spreadsheet template."""
    template = """Task Management Template

Columns:
1. Task Name
2. Description
3. Status (To Do, In Progress, Review, Completed)
4. Priority (High, Medium, Low)
5. Assigned To
6. Start Date
7. Due Date
8. Estimated Hours
9. Actual Hours
10. Dependencies
11. Notes

Sample Data:
Design Homepage,"Create wireframes and mockups",In Progress,High,John Smith,2023-01-15,2023-01-20,8,6,"Task 2: Create user flow",
Develop API Endpoint,"Build REST API for user login",To Do,Medium,Jane Doe,2023-01-16,2023-01-25,12,0,"Task 1: Design API schema,Task 3: Testing",
"""
    return template


def generate_research_template() -> str:
    """Generate a research documentation template."""
    template = """Research Documentation Template

Columns:
1. Topic/Query
2. Source Type (Article, Book, Interview, Dataset)
3. Author/Source
4. Date Accessed
5. Key Findings
6. Relevant Quotes
7. Methodology
8. Sample Size (if applicable)
9. Data Type (Primary, Secondary, Experimental)
10. Notes

Sample Data:
AI in Healthcare,Article,"Smith, J. et al.",2023-01-10,"Finding 1: AI improves accuracy by 15%,Finding 2: Cost reduction of 20%",Quote: \"AI shows promise in diagnostics\",\"Systematic review\",100,Secondary,
Blockchain Technology,Book,"Johnson, A. (2022)",2023-01-05,"Finding 1: Most effective in supply chains","Quote: \"Implementation costs are high\", but benefits are significant","Comparative study",50,Primary,
"""
    return template


def get_template_by_purpose(purpose: str) -> str:
    """Select appropriate template based on purpose description."""
    purpose_lower = purpose.lower()
    
    if any(keyword in purpose_lower for keyword in ['project', 'tracking', 'status']):
        return generate_project_tracking_template()
    elif any(keyword in purpose_lower for keyword in ['meeting', 'notes', 'discussion']):
        return generate_meeting_notes_template()
    elif any(keyword in purpose_lower for keyword in ['data', 'form', 'collection', 'survey']):
        return generate_data_collection_template()
    elif any(keyword in purpose_lower for keyword in ['budget', 'finance', 'expense', 'cost']):
        return generate_budget_template()
    elif any(keyword in purpose_lower for keyword in ['task', 'plan', 'todo', 'work']):
        return generate_task_management_template()
    elif any(keyword in purpose_lower for keyword in ['research', 'study', 'analysis', 'investigation']):
        return generate_research_template()
    
    # Default template for undefined purposes
    return """Custom Spreadsheet Template

Columns:
1. Column 1
2. Column 2  
3. Column 3
4. Column 4
5. Column 5

Sample Data:
Value1,Value2,Value3,Value4,Value5
"""
    

def main():
    """Main CLI entry point for spreadsheet template generator."""
    parser = argparse.ArgumentParser(description='Generate a spreadsheet template based on purpose')
    parser.add_argument('--dry-run', action='store_true', help='Preview without generating files')
    parser.add_argument('--purpose', help='Purpose of the spreadsheet')
    parser.add_argument('--columns', type=int, default=5, help='Number of columns (default: 5)')
    
    try:
        args = parser.parse_args()
        
        if not args.purpose:
            # Interactive mode - get purpose from stdin
            purpose = input("Enter the purpose of your spreadsheet template: ").strip()
        else:
            purpose = args.purpose
            
        print("=" * 50)
        print(f"Generating spreadsheet template for: {purpose}")
        print("=" * 50)
        
        # Generate the appropriate template
        template_content = get_template_by_purpose(purpose)
        
        print(template_content)
        print("=" * 50)
        print("Template generated successfully!")
        print("You can copy this content and save it as a .csv or .txt file")
        print("Then open with your spreadsheet application")
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"Error generating template: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()