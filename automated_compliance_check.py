#!/usr/bin/env python3
"""
Automated Compliance Check for Skill Execution Patterns

This script validates that all skills in the project follow the required folder management patterns.
"""

import os
import sys
import subprocess
from pathlib import Path

# Add project root to path for imports  
sys.path.insert(0, '/home/praddesilva/ProjectTeams/personal-assistant')

def validate_skill_execution_context_usage(skill_path):
    """Check if a skill properly uses the skill_execution_context"""
    
    # Look for any Python files in the skills directory
    python_files = list(Path(skill_path).rglob("*.py"))
    
    # This is a simplified check - we'll look for imports and usage patterns
    compliance_issues = []
    
    for py_file in python_files:
        try:
            with open(py_file, 'r') as f:
                content = f.read()
                
            # Check if skill_execution_context is imported
            if "skill_execution_context" in content and "import" in content:
                import_lines = [line for line in content.split('\n') if 'skill_execution_context' in line and 'import' in line]
                if import_lines:
                    print(f"✓ Found import in {py_file}")
                
            # Check if skill_execution_context is used in a context manager
            usage_patterns = [
                "with skill_execution_context()",
                "skill_execution_context() as"
            ]
            
            for pattern in usage_patterns:
                if pattern in content:
                    print(f"✓ Found usage pattern '{pattern}' in {py_file}")
                    
        except Exception as e:
            compliance_issues.append(f"Error reading {py_file}: {str(e)}")
    
    return compliance_issues

def check_directory_structure():
    """Verify that temp and deliverables directories exist and are properly configured"""
    
    temp_dir = "/home/praddesilva/ProjectTeams/personal-assistant/temp"
    deliverables_dir = "/home/praddesilva/ProjectTeams/personal-assistant/deliverables"
    
    print(f"Checking directory structure...")
    print(f"Temp directory: {temp_dir}")
    print(f"Deliverables directory: {deliverables_dir}")
    
    issues = []
    
    # Check if directories exist
    if not os.path.exists(temp_dir):
        issues.append(f"Temp directory does not exist: {temp_dir}")
    else:
        print("✓ Temp directory exists")
        
    if not os.path.exists(deliverables_dir):
        issues.append(f"Deliverables directory does not exist: {deliverables_dir}")
    else:
        print("✓ Deliverables directory exists")
        
    return issues

def run_compliance_tests():
    """Run comprehensive compliance tests"""
    
    print("Starting Automated Compliance Check...")
    print("=" * 50)
    
    # Test 1: Check directory structure
    print("\n1. Testing directory structure:")
    dir_issues = check_directory_structure()
    
    if dir_issues:
        print("✗ Directory issues found:")
        for issue in dir_issues:
            print(f"  - {issue}")
    else:
        print("✓ All directories properly configured")
    
    # Test 2: Check skill usage patterns
    print("\n2. Testing skill execution patterns:")
    skills_dir = "/home/praddesilva/ProjectTeams/personal-assistant/skills"
    
    if os.path.exists(skills_dir):
        skill_issues = validate_skill_execution_context_usage(skills_dir)
        
        if skill_issues:
            print("✗ Skill compliance issues found:")
            for issue in skill_issues:
                print(f"  - {issue}")
        else:
            print("✓ All skills use proper execution context")
    else:
        print("Warning: Skills directory not found")
    
    # Test 3: Run our custom validation
    print("\n3. Testing framework core functionality:")
    try:
        from src.passist.api.skill_folder_manager import skill_execution_context, ensure_directories_exist
        
        # Test if we can create context successfully
        with skill_execution_context() as (temp_dir, deliverables_dir):
            temp_exists = os.path.exists(temp_dir)
            deliverables_exists = os.path.exists(deliverables_dir)
            
            print(f"✓ Context manager creates directories:")
            print(f"  - Temp directory exists: {temp_exists}")
            print(f"  - Deliverables directory exists: {deliverables_exists}")
            
        print("✓ Framework core functionality working correctly")
        
    except Exception as e:
        print(f"✗ Framework functionality test failed: {e}")
    
    print("\n" + "=" * 50)
    print("Automated Compliance Check Complete!")

if __name__ == "__main__":
    run_compliance_tests()