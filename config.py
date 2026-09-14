#!/usr/bin/env python3
"""
Personal Assistant Agentic System Configuration
Configuration file for the Personal Assistant agent system
"""

import os
from typing import Optional
from pydantic import BaseModel, Field


class GLMConfig(BaseModel):
    """Configuration for GLM (Qwen 30B) model integration"""
    model_name: str = Field(default="glm-4", description="GLM model name")
    api_key: str = Field(default="", description="GLM API key")
    base_url: str = Field(
        default="https://open.bigmodel.cn/api/paas/v4",
        description="GLM API base URL"
    )
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1, le=8192)


class DatabaseConfig(BaseModel):
    """Configuration for SQLite database"""
    db_path: str = Field(
        default="./skills/skills.db",
        description="Path to SQLite database file"
    )
    enable_version_history: bool = Field(
        default=True,
        description="Enable version history tracking"
    )


class GitConfig(BaseModel):
    """Configuration for Git integration"""
    repo_path: str = Field(
        default="/home/praddesilva/ProjectTeams/personal-assistant",
        description="Path to git repository"
    )
    commit_message_template: str = Field(
        default="feat(skills): {skill_name} v{version}",
        description="Git commit message template"
    )
    auto_commit: bool = Field(
        default=True,
        description="Automatically commit changes"
    )


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


class Config:
    """Central configuration manager"""
    
    def __init__(self):
        self.glm = GLMConfig()
        self.database = DatabaseConfig()
        self.git = GitConfig()
        self.agent = AgentConfig()
    
    def load_from_env(self):
        """Load configuration from environment variables"""
        if api_key := os.getenv("GLM_API_KEY"):
            self.glm.api_key = api_key
        if base_url := os.getenv("GLM_BASE_URL"):
            self.glm.base_url = base_url
        if db_path := os.getenv("SKILLS_DB_PATH"):
            self.database.db_path = db_path
        if repo_path := os.getenv("GIT_REPO_PATH"):
            self.git.repo_path = repo_path
    
    def to_dict(self) -> dict:
        """Convert configuration to dictionary"""
        return {
            "glm": self.glm.model_dump(),
            "database": self.database.model_dump(),
            "git": self.git.model_dump(),
            "agent": self.agent.model_dump()
        }


# Global configuration instance
config = Config()
config.load_from_env()
