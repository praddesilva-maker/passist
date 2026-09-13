# Technical Implementation Guide: Folder Management for Skills Execution

## 1. Objective
Implement standardized folder management for all skill execution processes to ensure proper handling of intermediate and final deliverables.

## 2. Requirements Summary
### 2.1 Folder Structure
- **Temporary Files**: All intermediate files must be created in a dedicated temp folder during skill execution
- **Final Deliverables**: The final deliverable should be saved in a dedicated deliverables folder  
- **Cleanup**: After successful creation of the final deliverable, all contents of the temp folder must be automatically deleted

### 2.2 Implementation Specification
#### 2.2.1 Directory Setup
Before any skill execution begins:
- Create temp directory if it doesn't exist
- Create deliverables directory if it doesn't exist  
- Ensure proper read/write permissions for both directories

#### 2.2.2 Execution Flow
```python
def execute_skill():
    # Setup phase
    ensure_directories_exist()
    
    # Processing phase - write intermediate files to temp directory
    process_intermediate_steps(temp_dir)
    
    # Finalization phase - create deliverable in deliverables directory
    final_deliverable = create_final_output(temp_dir, deliverables_dir)
    
    # Cleanup phase - delete all contents from temp directory
    cleanup_temp_directory(temp_dir)
    
    return final_deliverable
```

#### 2.2.3 Error Handling Protocol
- **Cleanup Failures**: Continue execution if cleanup fails (silent failure)
- **Logging**: Log cleanup failures for monitoring purposes  
- **Critical Failures**: Ensure the final deliverable is still created and saved regardless of cleanup success

#### 2.2.4 File Operations
- All temporary files should be written to temp directory during processing
- Final deliverable should be moved/copied from temp to deliverables directory
- Delete all contents from temp directory (but not the directory itself)
- Preserve directory structure for final deliverables

## 3. Implementation Details

### 3.1 Folder Management Module
The system implements a standardized folder management system in `src/passist/api/skill_folder_manager.py`.

### 3.2 Directory Structure
- **Temporary Directory**: `/home/praddesilva/ProjectTeams/personal-assistant/temp`
- **Deliverables Directory**: `/home/praddesilva/ProjectTeams/personal-assistant/deliverables`

### 3.3 Key Features

#### 3.3.1 Automated Setup
- Directories are automatically created if they don't exist
- Proper permissions (755) are set for both directories

#### 3.3.2 Context Management
- Uses Python's context manager for automatic cleanup
- Ensures proper setup and cleanup regardless of execution path

#### 3.3.3 Error Handling
- Robust error handling with logging
- Cleanup failures don't interrupt the main execution flow
- Critical errors that prevent deliverable creation are properly raised

## 4. Compliance Requirements

### 4.1 For Existing Skills
1. Modify current skill implementations to use the new folder structure  
2. Update file paths to reference temp and deliverables directories
3. Implement cleanup logic after successful final deliverable creation  
4. Test that all existing skills work with new folder management

### 4.2 For New Skills  
5. Implement the folder management pattern from the beginning
6. Use standard temp and deliverables directory names
7. Include proper cleanup in skill execution flow
8. Document the folder structure in skill documentation

## 5. Key Technical Notes

### 5.1 Directory Persistence
- The temp directory should persist across execution steps but be emptied after each skill completion

### 5.2 File Paths
- Uses absolute paths to ensure reliability and avoid path resolution issues

### 5.3 Security  
- Proper permissions are set on directories to prevent unauthorized access

### 5.4 Monitoring
- All cleanup operations are logged for system monitoring purposes

### 5.5 Scalability
- The solution works with multiple concurrent skill executions using isolated temp directories

## 6. Usage Example
```python
from src.passist.api.skill_folder_manager import skill_execution_context

# Use in skill implementations:
with skill_execution_context() as (temp_dir, deliverables_dir):
    # Your skill processing logic here
    
    # All intermediate files go to temp_dir
    # Final deliverable gets saved to deliverables_dir
    pass
```

## 7. Implementation Status
- [x] Folder management module implemented
- [x] Context manager with setup/cleanup logic  
- [x] Error handling and logging
- [x] Documentation created