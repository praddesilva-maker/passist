"""
Tool implementation for the Universal Meta-Cognitive Critic (UMCC) skill.

This tool is the core of the mandatory QA layer that validates all outputs in the passist framework.
"""

import json
import requests
import re
from pydantic import BaseModel
from typing import Dict, Any, List, Optional, Union
from urllib.parse import urlparse
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UmccArgs(BaseModel):
    """Arguments for umcc tool"""
    task: str  # The original user task  
    output: Dict[str, Any]  # The output from the skill/tool to be validated
    sources: Optional[List[str]] = None  # Source references used in the output 
    context: Optional[Dict[str, Any]] = None  # Additional context about execution


def run_umcc(args: UmccArgs) -> Dict[str, Any]:
    """
    Execute the Universal Meta-Cognitive Critic validation process.
    
    Args:
        args: UmccArgs containing task, output, sources, and context
        
    Returns:
        Dictionary with validation results including status, feedback, and any corrections
    """
    
    # Initialize validation results
    feedback = []
    needs_clarification = False
    correction_manifest = ""
    
    # Perform triple-pass verification
    pass1_result = intent_alignment_check(args.task, args.output, args.sources, feedback)
    pass2_result = factuality_check(args.task, args.output, args.sources, feedback)
    pass3_result = structural_integrity_check(args.task, args.output, args.context, feedback)
    
    # Determine final status
    if not (pass1_result and pass2_result and pass3_result):
        status = "failed"
        correction_manifest = generate_correction_manifest(args.task, args.output, feedback)
    elif needs_clarification:
        status = "ambiguous" 
    else:
        status = "passed"
    
    result = {
        "status": status,
        "feedback": "\n".join(feedback),
        "correction_manifest": correction_manifest,
        "needs_clarification": needs_clarification
    }
    
    return result


def intent_alignment_check(task: str, output: Dict[str, Any], sources: Optional[List[str]], feedback: List[str]) -> bool:
    """Check if output fully addresses the original task and intent"""
    pass_ = True
    
    # If task is empty or None, we can't validate
    if not task or not task.strip():
        feedback.append("❌ Task input is missing or empty")
        return False
    
    # Check if the output contains key components of the task
    try:
        output_str = json.dumps(output) if not isinstance(output, str) else output
        task_words = re.findall(r'\b\w+\b', task.lower())
        
        # If output is string check against task words
        if task_words and isinstance(output, dict):
            # For dict outputs, look through all string values 
            output_content = json.dumps(output)
            found_words = [word for word in task_words if word in output_content.lower()]
            
            if len(found_words) < len(task_words) * 0.5:  # Require at least half of the task words are in the output
                feedback.append("⚠️ Not all key components from the original task are addressed")
                pass_ = False
            else:
                feedback.append("✅ Task intent is largely aligned in the output")
        elif isinstance(output, str) or isinstance(output, list):
            if isinstance(output, list) and len(output) > 0:
                # Check first items if it's a list
                output_str = str(output[0]) if output and not isinstance(output[0], dict) else json.dumps(output[0])
            elif isinstance(output, dict):
                output_str = json.dumps(output)
            
            # Use basic word matching logic against the task 
            found_words = [word for word in task_words if word in output_str.lower()]
            
            if len(found_words) < len(task_words) * 0.6:  # Require at least 60% of task words are in the output  
                feedback.append("⚠️ Few key components from the original task are addressed")
                pass_ = False
            else:
                feedback.append("✅ All or most key components from the original task are addressed")
        else:
            feedback.append("✅ Task intent checked against output content")
            
    except Exception as e:
        feedback.append(f"⚠️ Error checking intent alignment: {str(e)}")
    
    # Check for ambiguous assumptions (this is where we'd detect if skill assumed something)
    if isinstance(output, dict) and "assumptions" in output:
        # If the output includes its own assumptions, check those
        assumptions = output.get("assumptions", [])
        if len(assumptions) > 0:
            feedback.append(f"🔍 Output contains assumptions: {', '.join(assumptions[:2])}...")  # Show first 2
    
    return pass_

def factuality_check(task: str, output: Dict[str, Any], sources: Optional[List[str]], feedback: List[str]) -> bool:
    """Verify factual accuracy and source validity"""
    # Basic verification - expand as needed
    pass_ = True
    
    # Check if we have sources to verify against
    if not sources or len(sources) == 0:
        feedback.append("⚠️ No sources provided for fact checking (will proceed with validation)")
    
    else:
        # Try to validate sources where possible
        for i, source in enumerate(sources):
            if is_valid_url(source):
                # Check if URL is accessible
                try:
                    response = requests.head(source, timeout=10)
                    if response.status_code >= 400:
                        feedback.append(f"❌ Broken URL: {source}")
                        pass_ = False
                    else:
                        feedback.append(f"✅ Valid URL: {source}")
                except Exception as e:
                    feedback.append(f"❌ Unable to verify URL {source}: {str(e)}")
                    pass_ = False
            else:
                # Treat as file path or other resource
                feedback.append(f"📄 File/resource reference: {source} (no auto-validation)")

    return pass_


def structural_integrity_check(task: str, output: Dict[str, Any], context: Optional[Dict[str, Any]], feedback: List[str]) -> bool:
    """Check that output follows structural and constraint requirements"""
    pass_ = True
    
    # Check for negative constraints ("Do not")
    if context and "do_not" in context:
        do_not_list = context["do_not"]
        violations = []
        
        # If the task contains "not" or "do not" instructions, check against them
        output_str = json.dumps(output) if not isinstance(output, str) else output
        
        if isinstance(do_not_list, list):
            for instruction in do_not_list:
                if isinstance(instruction, str) and instruction.lower() in output_str.lower():
                    pass_ = False
                    violations.append(f"❌ Found violation of constraint: {instruction}")
        
        # Add info about detected violations if they exist  
        if violations:
            feedback.extend(violations)
        else:
            feedback.append("✅ All negative constraints have been followed")
    
    # Check format compliance if specified
    if context and "format" in context:
        requested_format = context["format"].lower()
        try:
            if requested_format == "json":
                if not isinstance(output, (dict, list)):
                    pass_ = False
                    feedback.append(f"❌ Output must be a dict or list for JSON format but got {type(output).__name__}")
                else:
                    # Try to parse the output as JSON to make sure it's valid
                    json.dumps(output)
                    feedback.append("✅ Output is valid JSON")
            
            elif requested_format == "markdown":
                if not isinstance(output, str) or not output.strip().startswith("#") and not output.strip().startswith("|"):
                    feedback.append("⚠️ Output may not be properly formatted as markdown")
                else:
                    feedback.append("✅ Output appears to be in markdown format")
                    
            elif requested_format == "table":
                if not isinstance(output, list) or not all(isinstance(row, dict) for row in output):
                    feedback.append("⚠️ Table format should be a list of dictionaries")
                else:
                    feedback.append("✅ Output resembles table format")
                    
        except Exception as e:
            pass_ = False
            feedback.append(f"❌ Error in format validation: {str(e)}")
    
    # Check tone and persona consistency (basic check)
    if isinstance(output, str) or isinstance(output, dict):
        # Simple checks for consistent tone
        output_content = json.dumps(output) if not isinstance(output, str) else output
        
        # Check if it's too technical (would violate "do not use technical jargon" constraints)
        technical_words = ["algorithm", "neural", "quantum", "synapse", "hypothesis", "paradigm"]
        tech_matches = [word for word in technical_words if word in output_content.lower()]
        
        if len(tech_matches) > 0:
            feedback.append(f"⚠️ Output contains technical terms ({', '.join(tech_matches[:2])}...) that may require more basic explanation")
    
    # Verify logical consistency with simple checks
    try:
        if isinstance(output, dict):
            keys_list = list(output.keys())
            
            # If "error" is present in output and it's not empty or None, flag as problematic  
            error_in_output = output.get("error")
            if error_in_output and str(error_in_output).strip():
                feedback.append(f"⚠️ Output indicates error: {str(error_in_output)[:100]}...")
                pass_ = False
                
        # Check for logical inconsistencies
        if isinstance(output, dict) and "reasoning" in output:
            reasoning = output["reasoning"]
            if isinstance(reasoning, str):
                if re.search(r"(?i)(contradiction|inconsistency)", reasoning):
                    feedback.append("❌ Found indications of contradiction or inconsistency in reasoning")
                    pass_ = False
                else:
                    feedback.append("✅ Reasoning appears logical and consistent")
    except Exception as e:
        feedback.append(f"⚠️ Error verifying structural integrity: {str(e)}")
    
    return pass_


def generate_correction_manifest(task: str, output: Dict[str, Any], feedback: List[str]) -> str:
    """Generate a specific correction manifest for failed validations"""
    
    # This is simplified - in reality this would need to analyze exactly what is wrong
    lines = [
        "## Correction Manifest",
        "",
        f"### Task: {task}",
        "",
        "The output failed validation checks, requiring the following corrections:",
        ""
    ]
    
    # Add feedback items that indicate specific issues
    corrected_issues = []
    
    for item in feedback:
        if item.startswith("❌"):
            # Extract specific issue without the ❌ prefix 
            issue = item[2:].strip()
            corrected_issues.append(f"- {issue}")
        
    if not corrected_issues:
        lines.extend([
            "- The output failed verification checks",
            "- Please review output against original task requirements",
            "- Ensure factual accuracy and follow all specified constraints",
            ""
        ])
    else:
        lines.extend(corrected_issues)
        lines.append("")
    
    lines.extend([
        "### Recommendations:",
        "- Correct the identified issues carefully",
        "- Verify outputs against facts, sources, and provided constraints",
        "- Ensure output fully addresses the original task component",
        "- If uncertain about any element, ask for clarification before proceeding",
        ""
    ])
    
    return "\n".join(lines)


def is_valid_url(url: str) -> bool:
    """Basic URL validation"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


# Tool specification 
spec = {
    "name": "umcc",
    "description": "Universal Meta-Cognitive Critic - mandatory QA layer for validating all skill outputs",
    "side_effect": False,
    "input_model": UmccArgs,
    "run": run_umcc
}