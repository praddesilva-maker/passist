#!/usr/bin/env python3
"""Personal Assistant Agent - Main Implementation"""
import json
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
try:
    from langchain.agents import AgentExecutor, create_tool_calling_agent
    from langchain_core.prompts import PromptTemplate
    from langchain_core.tools import tool
    from langchain_glm import ChatGLM
except ImportError:
    pass
from .agent_config import AgentConfig
from skills.registry import SkillRegistry
from skills.unified_stage import UnifiedSkillStage
from skills.skill_builder import SkillBuilder
from config import config

class IntentType:
    CREATE_SKILL = "create_skill"
    USE_SKILL = "use_skill"
    GENERAL = "general"

@dataclass
class ExecutionResult:
    success: bool
    skill_name: str
    skill_type: str
    output: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {"success": self.success, "skill_name": self.skill_name, "skill_type": self.skill_type, "output": self.output, "metadata": self.metadata, "error": self.error, "execution_time_ms": self.execution_time_ms}

class PersonalAssistantAgent:
    def __init__(self, config: AgentConfig = None, registry: SkillRegistry = None):
        self.config = config or AgentConfig()
        self.registry = registry or SkillRegistry(db_path=config.database.db_path if hasattr(config, "database") else config.db_path)
        self.skill_stage = UnifiedSkillStage(registry=self.registry)
        self.glm = None
        self._init_glm()
        if self.config.enable_skill_builder:
            self.skill_builder = SkillBuilder(registry=self.registry, agent=self)
        self._new_skill_pipeline = None
        self._existing_skill_pipeline = None
        self.stats = {"skills_created": 0, "skills_used": 0, "intent_detections": 0}

    def _init_glm(self):
        if self.config.glm_model:
            try:
                if self.config.glm_api_key:
                    self.glm = ChatGLM(model_name=self.config.glm_model, temperature=self.config.glm_temperature, max_tokens=self.config.glm_max_tokens, api_key=self.config.glm_api_key)
                else:
                    base_url = getattr(config, "glm", None)
                    if base_url and base_url.base_url:
                        self.glm = ChatGLM(model_name=self.config.glm_model, temperature=self.config.glm_temperature, max_tokens=self.config.glm_max_tokens, api_key=self.config.glm_api_key, base_url=base_url.base_url)
            except Exception as e:
                print(f"Warning: Could not initialize GLM: {e}")
                self.glm = None

    @property
    def new_skill_pipeline(self):
        if self._new_skill_pipeline is None:
            self._new_skill_pipeline = NewSkillPipeline(self, self.registry)
        return self._new_skill_pipeline

    @property
    def existing_skill_pipeline(self):
        if self._existing_skill_pipeline is None:
            self._existing_skill_pipeline = ExistingSkillPipeline(self, self.registry)
        return self._existing_skill_pipeline

    async def process_input(self, user_input: str, **kwargs) -> ExecutionResult:
        start_time = datetime.now()
        if "skill_name" in kwargs:
            skill_name = kwargs["skill_name"]
            skill_type = kwargs.get("skill_type", "function")
            params = kwargs.get("parameters", {})
            result = await self._execute_skill_directly(skill_name, skill_type, params, **kwargs)
        else:
            intent = await self._detect_intent(user_input)
            self.stats["intent_detections"] += 1
            if intent == IntentType.CREATE_SKILL:
                result = await self.new_skill_pipeline.create_skill(user_input)
            elif intent == IntentType.USE_SKILL:
                result = await self.existing_skill_pipeline.use_skill(user_input, **kwargs)
            else:
                result = await self._handle_general_input(user_input, **kwargs)
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        result.execution_time_ms = execution_time
        return result

    async def _execute_skill_directly(self, skill_name: str, skill_type: str, params: Dict[str, Any], **kwargs) -> ExecutionResult:
        try:
            skill = self.registry.get_skill(skill_name)
            if not skill:
                return ExecutionResult(success=False, skill_name=skill_name, skill_type=skill_type, output=None, error=f"Skill '{skill_name}' not found in registry")
            result = await self.skill_stage.execute_skill(skill_name, params, skill_type)
            return result
        except Exception as e:
            return ExecutionResult(success=False, skill_name=skill_name, skill_type=skill_type, output=None, error=str(e))

    async def _detect_intent(self, user_input: str) -> str:
        if self.glm:
            return await self._detect_intent_glm(user_input)
        return self._detect_intent_regex(user_input)

    async def _detect_intent_glm(self, user_input: str) -> str:
        try:
            prompt = "Analyze this user input and classify the intent."
            response = await self.glm.ainvoke(prompt)
            intent = response.strip().lower().replace("", "").replace(""", "")
Available intents:
- 'create_skill': User wants to create a new skill
- 'use_skill': User wants to use an existing skill
- 'general': Any other request

Input: "{user_input}"

Return only the intent type as a JSON string, e.g., "create_skill"."
            response = await self.glm.ainvoke(prompt)
            intent = response.strip().lower().replace("", "").replace("'", "")
            if intent == "create_skill" or ("create" in response.lower() and "skill" in response.lower()):
                return IntentType.CREATE_SKILL
            elif intent == "use_skill" or ("use" in response.lower() and "skill" in response.lower()):
                return IntentType.USE_SKILL
            return IntentType.GENERAL
        except Exception as e:
            print(f"GLM intent detection failed: {e}")
            return self._detect_intent_regex(user_input)

    def _detect_intent_regex(self, user_input: str) -> str:
        input_lower = user_input.lower()
        if any(keyword in input_lower for keyword in ["create a new skill", "create skill", "make a skill", "add skill", "new skill", "create function", "create agent", "create workflow"]):
            return IntentType.CREATE_SKILL
        if any(keyword in input_lower for keyword in ["use skill", "run skill", "execute skill", "call skill", "do skill", "apply skill", "skill that", "skill to"]):
            return IntentType.USE_SKILL
        return IntentType.GENERAL

    async def _handle_general_input(self, user_input: str, **kwargs) -> ExecutionResult:
        if self.skill_builder and self.config.enable_skill_builder:
            return ExecutionResult(success=True, skill_name="general", skill_type="function", output={"message": f"General input: {user_input}", "suggestion": "Use 'create a skill' or 'use a skill'"}, metadata={"type": "general"})
        return ExecutionResult(success=True, skill_name="general", skill_type="function", output={"message": f"General input: {user_input}"}, metadata={"type": "general"})

    def get_stats(self) -> Dict[str, Any]:
        return {"skills_created": self.stats["skills_created"], "skills_used": self.stats["skills_used"], "intent_detections": self.stats["intent_detections"], "config": self.config.model_dump()}

    def reset_stats(self):
        self.stats = {"skills_created": 0, "skills_used": 0, "intent_detections": 0}

class NewSkillPipeline:
    def __init__(self, agent, registry):
        self.agent = agent
        self.registry = registry

        try:
    async def create_skill(self, user_input, **kwargs):
            analysis = self._analyze_with_rules(user_input)
            skill_type = self.agent.config.default_skill_type
            skill_structure = self._generate_skill_structure(analysis, skill_type)
            code = self._generate_function_code(skill_structure)
            self.agent.stats["skills_created"] += 1
            skill = self._create_skill_from_structure(skill_structure, skill_type, code)
            return ExecutionResult(
                success=True, skill_name=skill["name"], skill_type=skill_type,
                output={"skill": skill, "code": code},
                metadata={"analysis": analysis}
            )
        except Exception as e:
            return ExecutionResult(
                success=False, skill_name="", skill_type="function",
                output=None, error=str(e)
            )
