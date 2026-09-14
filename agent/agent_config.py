#!/usr/bin/env python3
"""
Agent Configuration Module
Configuration for Personal Assistant Agent
"""

from pydantic import BaseModel, Field
from typing import Optional


class AgentConfig(BaseModel):
    """Configuration for the Personal Assistant Agent"""
    name: str = Field(default="Personal Assistant", description="Agent name")
    version: str = Field(default="1.0.0", description="Agent version")
    description: str = Field(
        default="Personal assistant with skill creation and execution capabilities",
        description="Agent description"
    )
    enable_intent_detection: bool = Field(default=True)
    enable_skill_builder: bool = Field(default=True)
    enable_new_skill_pipeline: bool = Field(default=True)
    enable_existing_skill_pipeline: bool = Field(default=True)
    default_skill_type: str = Field(
        default="function",
        description="Default skill type to create"
    )
    enable_caching: bool = Field(default=True)
    cache_ttl: int = Field(default=300, description="Cache time-to-live in seconds")

    # GLM settings
    glm_model: str = Field(default="glm-4", description="GLM model name")
    glm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    glm_max_tokens: int = Field(default=2048, ge=1, le=8192)

    # Pipeline settings
    require_confirmation: bool = Field(default=False, description="Require confirmation before skill execution")
    max_retries: int = Field(default=3, ge=0, le=10)
    timeout: int = Field(default=120, description="Timeout in seconds for skill execution")

    # Output settings
    verbose: bool = Field(default=True, description="Enable verbose output")
    include_metadata: bool = Field(default=True, description="Include metadata in skill execution")
