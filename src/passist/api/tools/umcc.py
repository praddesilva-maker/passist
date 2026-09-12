"""
Tool implementation for the Universal Meta-Cognitive Critic (UMCC) skill.

This tool is the core of the mandatory QA layer that validates all outputs in the passist framework.
"""

import json
import requests
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse


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
    
    # Convert output to dict if it's a string or simple value 
    output_dict = args.output if isinstance(args.output, dict) else {"result": args.output}
    
    # Perform triple-pass verification
    pass1_result = intent_alignment_check(args.task, args.output, feedback)
    pass2_result = factuality_check(args.task, args.output, args.sources, feedback)
    pass3_result = structural_integrity_check(args.task, args.output, args.context, feedback)
    
    # Determine final status
    if not pass1_result or not pass2_result or not pass3_result:
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


def intent_alignment_check(task: str, output: Dict[str, Any], feedback: List[str]) -> bool:
    """Check if output aligns with original task and intent"""
    # Basic check - in a real implementation, this would be more sophisticated
    pass_ = True
    
    # Check if the output actually addresses key components of the task
    if not output:
        feedback.append("❌ Output is empty or None")
        pass_ = False
    else:
        feedback.append("✅ Intent alignment passed: Output contains content")
        
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
    # Basic structural check
    pass_ = True
    
    # Check format if specified in context
    if context and "format" in context:
        requested_format = context["format"].lower()
        # Validate JSON format if required
        if requested_format == "json":
            try:
                # Try to parse as JSON 
                json.dumps(output)
                feedback.append("✅ Output is valid JSON")
            except Exception:
                feedback.append("❌ Output is not valid JSON format")
                pass_ = False
        
    return pass_


def generate_correction_manifest(task: str, output: Dict[str, Any], feedback: List[str]) -> str:
    """Generate a specific correction manifest for failed validations"""
    
    # This is simplified - in reality this would need to analyze exactly what is wrong
    lines = [
        "## Correction Manifest",
        "",
        f"### Task: {task}",
        "",
        "The output failed validation checks:",
        ""
    ]
    
    # Add feedback as bullet points
    for item in feedback:
        if item.startswith("❌"):
            lines.append(f"- {item[2:].strip()}")  # Remove the ❌ prefix
    
    lines.extend([
        "",
        "### Recommendations:",
        "- Please correct the identified issues",
        "- Ensure output follows all requirements and constraints",
        "- Verify facts against sources",
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