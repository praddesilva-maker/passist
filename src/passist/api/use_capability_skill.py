"""
Implementation of the use-capability skill - runtime front door.

This module implements the logic for routing user goals to appropriate capabilities.
"""

import os
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

# Mock implementation of skill discovery - in practice this would scan skills/*/SKILL.md files 
def discover_skills() -> List[Dict[str, str]]:
    """Discover available skills from the skills directory."""
    # For now return a mock catalog - in a real system this would read SKILL.md files
    skills = [
        {
            "name": "getThing",
            "description": "Read a thing from Personal Assist API by ID", 
            "type": "tool"
        },
        {
            "name": "updateThing", 
            "description": "Update a thing in Personal Assist API by ID",
            "type": "tool"
        }
    ]
    
    # This would scan skills/*/SKILL.md files in practice
    return skills

def find_best_match(goal: str, catalog: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """Find the best matching capability for a given goal."""
    # Simple keyword-based matching (would be more sophisticated in real implementation)
    goal_lower = goal.lower()
    
    best_match = None
    best_score = 0
    
    for item in catalog:
        desc = item["description"].lower()
        score = 0
        
        # Calculate match score based on keyword overlap
        for word in goal_lower.split():
            if word in desc:
                score += 1
                
        if score > best_score:
            best_score = score
            best_match = item
            
    return best_match

def handle_single_command(goal: str, inputs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Handle single-command mode (goal + inputs in one prompt)."""
    # Discover available capabilities
    catalog = discover_skills()
    
    # Find best match
    match = find_best_match(goal, catalog)
    
    if not match:
        return {
            "status": "no_match",
            "message": f"No matching capability found for goal: {goal}",
            "suggestion": "Consider using capability-intake to build this capability."
        }
    
    # Return information about the matched capability
    return {
        "status": "success",
        "matched_capability": match,
        "goal": goal,
        "inputs": inputs or {},
        "message": f"Matched capability: {match['name']}"
    }

def interactive_routing(goal: str) -> Dict[str, Any]:
    """Handle interactive mode - guided routing."""
    # Discover available capabilities  
    catalog = discover_skills()
    
    # Find all matches
    match = find_best_match(goal, catalog)
    
    if not match:
        return {
            "status": "no_match",
            "message": f"No matching capability found for goal: {goal}",
            "suggestion": "Offering to hand off to capability-intake to build this capability.",
            "handoff_to": "capability-intake"
        }
    
    # Return match information
    return {
        "status": "success",
        "matched_capability": match,
        "interactive_mode": True,
        "message": f"Found matching capability: {match['name']}"
    }

def run_use_capability(goal: str, inputs: Optional[Dict[str, Any]] = None, 
                      interactive: bool = True) -> Dict[str, Any]:
    """
    Main entry point for use-capability skill.
    
    Args:
        goal: User's stated goal
        inputs: Additional inputs (in single-command mode)
        interactive: Whether to run in interactive mode
        
    Returns:
        Dictionary with execution results and routing information
    """
    if interactive:
        return interactive_routing(goal)
    else:
        return handle_single_command(goal, inputs)

# Mock test function for demonstration
def mock_test():
    """Test the capability router."""
    print("Testing use-capability skill...")
    
    # Test cases
    test_goals = [
        "get a thing from API",
        "update information",
        "something else"
    ]
    
    for goal in test_goals:
        result = run_use_capability(goal)
        print(f"Goal: '{goal}' -> {result}")

if __name__ == "__main__":
    mock_test()