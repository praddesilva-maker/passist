# Folder Management in Skills Execution

## Overview

This document describes the standardized folder management system for all skill execution processes within the passist framework. This system ensures proper handling of intermediate and final deliverables with automatic cleanup.

## Directory Structure

The framework maintains two dedicated directories for skill execution:

### Temporary Directory
- **Path**: `/home/praddesilva/ProjectTeams/personal-assistant/temp`
- **Purpose**: Stores all intermediate files created during skill execution
- **Persistence**: Directory exists across execution steps but is emptied after each skill completion

### Deliverables Directory  
- **Path**: `/home/praddesilva/ProjectTeams/personal-assistant/deliverables`
- **Purpose**: Stores final deliverables created by completed skills
- **Persistence**: Directory persists across multiple skill executions

## Implementation Details

The folder management system is implemented in `src/passist/api/skill_folder_manager.py` and provides:

1. **Automatic Setup** - Creates directories if they don't exist with proper permissions (755)
2. **Context Management** - Uses Python's context manager for automatic cleanup
3. **Robust Error Handling** - Handles permission errors and other exceptions gracefully  
4. **Logging** - Comprehensive logging for monitoring cleanup operations

## Usage Patterns

### For Existing Skills
When updating existing skills, follow these steps:
1. Import the folder management module
2. Use the `skill_execution_context()` context manager to ensure proper setup/cleanup
3. Write intermediate files to the temporary directory (temp_dir)
4. Place final deliverables in the deliverables directory (deliverables_dir)

### For New Skills
New skills should immediately follow this pattern:
```python
from src.passist.api.skill_folder_manager import skill_execution_context

with skill_execution_context() as (temp_dir, deliverables_dir):
    # Your skill logic here
    # Write temporary files to temp_dir
    # Save final deliverable to deliverables_dir
    pass
```

## Cleanup Process

After successful skill execution:
1. All contents of the temporary directory are automatically deleted (but the directory itself remains)
2. Final deliverables are preserved in the deliverables directory
3. Cleanup failures are logged but don't interrupt main execution flow

This ensures clean separation between temporary and final artifacts while maintaining system integrity through automatic cleanup.