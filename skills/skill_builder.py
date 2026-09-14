#!/usr/bin/env python3
"""
Skill Builder Module
Interactive skill creation and review
"""

from typing import Dict, Any, Optional
import json
from datetime import datetime
from skills.registry import SkillRegistry
from skills.unified_stage import UnifiedSkillStage


class SkillBuilder:
    """Interactive skill builder with review and validation"""

    def __init__(self, registry: SkillRegistry, agent):
        self.registry = registry
        self.agent = agent
        self.skill_stage = UnifiedSkillStage(registry)

    def create_skill(self, user_input: str) -> Dict[str, Any]:
        """Create a new skill from user input"""
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            analysis = loop.run_until_complete(
                self.analyze_request(user_input) if self.agent.glm else self.analyze_request_rules(user_input)
            )
            skill_type = self.agent.config.default_skill_type
            skill_structure = self.generate_skill_structure(analysis, skill_type)
            code = self.generate_skill_code(skill_structure, skill_type)
            skill = self.register_skill(skill_structure, skill_type, code)
            
            return {
                "success": True,
                "skill": skill,
                "code": code,
                "skill_structure": skill_structure
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def analyze_request_rules(self, user_input: str) -> Dict[str, Any]:
        return {
            "name": user_input.strip().replace(" ", "_").lower(),
            "description": user_input,
            "parameters": []
        }

    def generate_skill_structure(self, analysis: Dict[str, Any], skill_type: str) -> Dict[str, Any]:
        return {
            "name": analysis.get("name", "unnamed_skill"),
            "description": analysis.get("description", ""),
            "type": skill_type,
            "parameters": analysis.get("parameters", []),
            "examples": [],
            "code": ""
        }

    def generate_skill_code(self, skill_structure: Dict[str, Any], skill_type: str) -> str:
        if skill_type == "function":
            return self._generate_function_code(skill_structure)
        else:
            return self._generate_function_code(skill_structure)

    def _generate_function_code(self, skill_structure: Dict[str, Any]) -> str:
        name = skill_structure["name"]
        parameters = skill_structure.get("parameters", [])
        code = f'"""{skill_structure["description"]}"""\n\n'
        code += f'@tool\ndef {name}(\n'
        param_list = [f'    {p["name"]}: {p.get("type", "Any")}' for p in parameters]
        code += ",\n".join(param_list) + ",\n)\n\n"
        code += f'    """{skill_structure["description"]}"""\n\n'
        code += "    # Validate parameters\n"
        for p in parameters:
            if p.get("required", True):
                code += f'    if {p["name"]} is None:\n        raise ValueError(f"{p["name"]} is required")\n\n'
        code += "    # Your implementation here\n"
        for p in parameters:
            code += f"    {p['name']} = {p['name']}\n"
        code += "\n    return {\n        \"status\": \"success\",\n        \"result\": \"Your implementation here\"\n    }\n"
        return code

    def register_skill(self, skill_structure: Dict[str, Any], skill_type: str, code: str) -> Dict[str, Any]:
        skill_filename = f"{skill_structure['name']}.py"
        with open(f"skills/generated/{skill_filename}", 'w') as f:
            f.write(code)
        skill_data = {
            "name": skill_structure["name"],
            "description": skill_structure.get("description", ""),
            "type": skill_type,
            "code": code,
            "parameters": skill_structure.get("parameters", []),
            "examples": skill_structure.get("examples", []),
            "created_at": datetime.now().isoformat(),
            "versions": [skill_filename]
        }
        return self.registry.add_skill(skill_data)

    def list_skills(self):
        return self.registry.list_skills()

