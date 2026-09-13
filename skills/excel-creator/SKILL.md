# Excel Creator Skill

This skill creates comprehensive Excel spreadsheets with multiple sheets for budget tracking, expense management, and financial analysis.

## Framework Compliance

All skills must use the `skill_execution_context()` from `src.passist.api.skill_folder_manager`. This ensures:

- Proper temporary file handling in `/temp` directory  
- Correct deliverable storage in `/deliverables` directory
- Automatic cleanup of temporary resources after execution
- Consistent audit trails for compliance verification

## Skill Execution Pattern

Every skill execution follows this standardized pattern:

1. **Setup**: Temporary files are created using `skill_execution_context()` 
2. **Processing**: Intermediate results are stored temporarily during processing
3. **Finalization**: Completed deliverable is moved to `/deliverables` directory
4. **Cleanup**: Temporary files are automatically removed after successful execution

## Requirements

- Python 3.8+
- Required packages: openpyxl, pandas, numpy
- Access to create files in `/temp` and `/deliverables` directories

## Usage

```
python -m passist.api.run excel-creator --topic "Budget Analysis" --format "xlsx"
```

## Implementation Details

The actual implementation uses the standardized framework pattern:

```python
from src.passist.api.skill_folder_manager import skill_execution_context

def run():
    with skill_execution_context() as (temp_dir, deliverables_dir):
        # Process in temp directory for interim files
        interim_file = os.path.join(temp_dir, "interim_analysis.txt")
        # ... perform processing ...
        
        # Save final deliverable to deliverables directory  
        final_deliverable = os.path.join(deliverables_dir, "budget_tracker.xlsx")
        # ... save results ...
        
        # Automatic cleanup handled by context manager
```

## Testing and Validation

Skills must pass compliance validation that checks:
- Temporary directory is properly cleaned up after execution
- Final deliverables are correctly located in `/deliverables`  
- No files remain in temp directory at completion
- Execution logs show proper compliance verification
