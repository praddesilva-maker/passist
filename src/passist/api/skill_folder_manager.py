"""
Folder Management System for Skills Execution
============================================

This module provides standardized folder management for all skill execution processes,
ensuring proper handling of intermediate and final deliverables with automatic cleanup.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Optional, Tuple
from contextlib import contextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global directory paths - these should be configurable but for now use defaults
TEMP_DIR = "/home/praddesilva/ProjectTeams/personal-assistant/temp"
DELIVERABLES_DIR = "/home/praddesilva/ProjectTeams/personal-assistant/deliverables"

def ensure_directories_exist() -> Tuple[str, str]:
    """
    Ensure that both temp and deliverables directories exist with proper permissions.
    
    Returns:
        Tuple[str, str]: The absolute paths of temp and deliverables directories
    """
    try:
        # Create temp directory if it doesn't exist
        Path(TEMP_DIR).mkdir(parents=True, exist_ok=True)
        
        # Create deliverables directory if it doesn't exist
        Path(DELIVERABLES_DIR).mkdir(parents=True, exist_ok=True)
        
        # Ensure proper permissions (read/write for owner, read for group/others)
        os.chmod(TEMP_DIR, 0o755)
        os.chmod(DELIVERABLES_DIR, 0o755)
        
        logger.info(f"Ensured directories exist: temp={TEMP_DIR}, deliverables={DELIVERABLES_DIR}")
        return TEMP_DIR, DELIVERABLES_DIR
        
    except PermissionError:
        logger.error("Permission denied when creating directories")
        raise
    except Exception as e:
        logger.error(f"Failed to create directories: {e}")
        raise

def cleanup_temp_directory(temp_dir: str) -> bool:
    """
    Clean up all contents from temp directory after successful final deliverable creation.
    
    Args:
        temp_dir (str): Path to the temporary directory
        
    Returns:
        bool: True if cleanup was successful, False otherwise
    """
    try:
        # Check if directory exists
        if not os.path.exists(temp_dir):
            logger.warning(f"Temp directory does not exist: {temp_dir}")
            return True
            
        # List all items in the directory
        items = os.listdir(temp_dir)
        
        if not items:
            logger.info("Temp directory is already empty")
            return True
            
        # Remove all contents (but keep directory itself)
        for item in items:
            item_path = os.path.join(temp_dir, item)
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.unlink(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
                
        logger.info(f"Successfully cleaned up temp directory: {temp_dir}")
        return True
        
    except Exception as e:
        logger.error(f"Cleanup failed for temp directory {temp_dir}: {e}")
        # Continue execution even if cleanup fails (silent failure as per requirements)
        return False

@contextmanager
def skill_execution_context():
    """
    Context manager for skill execution that ensures proper setup and cleanup.
    
    Usage:
        with skill_execution_context() as (temp_dir, deliverables_dir):
            # Execute skill logic here
            pass
    """
    temp_dir = None
    deliverables_dir = None
    
    try:
        # Setup phase
        temp_dir, deliverables_dir = ensure_directories_exist()
        
        logger.info("Skill execution context initialized")
        yield temp_dir, deliverables_dir
        
    except Exception as e:
        logger.error(f"Error in skill execution context: {e}")
        raise
    
    finally:
        # Cleanup should happen at the end of successful execution
        if temp_dir and deliverables_dir:
            # Perform cleanup after successful processing
            cleanup_temp_directory(temp_dir)
            logger.info("Skill execution context cleaned up")
        else:
            logger.warning("Unable to perform cleanup - directories not properly set up")