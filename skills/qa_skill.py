#!/usr/bin/env python3
"""QA Expert Skill Module - Testing and validation"""
from typing import Dict, Any, Optional
from datetime import datetime
from skills.registry import SkillRegistry
from skills.unified_stage import UnifiedSkillStage

class QAExpertSkill:
    def __init__(self, registry: SkillRegistry = None):
        self.registry = registry or SkillRegistry()
        self.skill_stage = UnifiedSkillStage(self.registry)
    
    def test_skill(self, skill_name: str, input_data: Dict[str, Any] = None) -> Dict[str, Any]:
        result = self.skill_stage.execute_skill(skill_name, input_data or {}, "function")
        return {
            "success": result.get("success"),
            "skill_name": result.get("skill_name"),
            "output": result.get("output"),
            "error": result.get("error")
        }
    
    def validate_skill_structure(self, skill_name: str) -> Dict[str, Any]:
        skill = self.registry.get_skill(skill_name)
        if not skill:
            return {"valid": False, "error": f"Skill '{skill_name}' not found"}
        return {
            "valid": True,
            "skill_name": skill["name"],
            "structure": {
                "type": skill["type"],
                "has_code": bool(skill["code"]),
                "parameters_count": len(skill.get("parameters", [])),
                "version_count": len(skill.get("versions", []))
            }
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        skills = self.registry.list_skills()
        return {
            "total_skills": len(skills),
            "skills": skills
        }
    
    def create_test_skill(self, name: str, description: str) -> Dict[str, Any]:
        skill_data = {
            "name": name,
            "description": description,
            "type": "function",
            "code": f'''"""{description}"""\n\n@tool\ndef {name}(input_value: str = "test"):\n    """{description}"""\n    return {{"status": "success", "output": f"Processed {{input_value}}"}}\n''',
            "parameters": [{"name": "input_value", "type": "str", "description": "Input value", "required": False}],
            "examples": [],
            "created_at": datetime.now().isoformat(),
            "versions": []
        }
        return self.registry.add_skill(skill_data)
