#!/usr/bin/env python3
"""
Personal Assistant Agentic System - Configuration.

Environment variables (all optional; sane defaults are applied):
    GLM_API_KEY      - API key for the GLM (Zhipu) / Qwen-compatible API
    GLM_BASE_URL     - OpenAI-compatible base URL (default: GLM 4.0 endpoint)
    GLM_MODEL        - model name (default: glm-4)
    SKILLS_DB_PATH   - path to the SQLite skill registry database
    GIT_REPO_PATH    - path of the git repository backing the registry
    USE_OFFLINE_MODEL - "1" forces the offline (no-network) model
"""

import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class ModelConfig:
    """Configuration for the chat model (GLM 4 / Qwen 30B via OpenAI-compatible API)."""

    provider: str = field(default_factory=lambda: os.getenv("GLM_PROVIDER", "glm"))
    model_name: str = field(default_factory=lambda: os.getenv("GLM_MODEL", "glm-4"))
    api_key: str = field(default_factory=lambda: os.getenv("GLM_API_KEY", ""))
    base_url: str = field(
        default_factory=lambda: os.getenv(
            "GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"
        )
    )
    temperature: float = field(default_factory=lambda: float(os.getenv("GLM_TEMPERATURE", "0.7")))
    max_tokens: int = field(default_factory=lambda: int(os.getenv("GLM_MAX_TOKENS", "2048")))
    use_offline: bool = field(default_factory=lambda: _env_bool("USE_OFFLINE_MODEL", False))

    @property
    def has_credentials(self) -> bool:
        return bool(self.api_key)


def _env_first(*names: str, default: str = "") -> str:
    """First non-empty value among ``names``, else ``default``.

    The test suite's ``isolated_env`` fixture redirects shared state with
    ``PA_``-prefixed variables (``PA_DATABASE_PATH``, ``PA_GIT_REPO_PATH``),
    while this module originally read only the unprefixed names. Anything
    building a ``Config()`` under test therefore pointed at the *real*
    ``skills/skills.db`` and the *real* project git repo rather than the
    per-test temp dir. Reading the ``PA_`` name first closes that isolation
    hole while keeping the unprefixed names working for normal use.
    """
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


@dataclass
class DatabaseConfig:
    """Configuration for the SQLite skill registry."""

    db_path: str = field(
        default_factory=lambda: _env_first(
            "PA_DATABASE_PATH", "SKILLS_DB_PATH", default="./skills/skills.db"
        )
    )
    enable_version_history: bool = True


@dataclass
class GitConfig:
    """Configuration for Git integration."""

    repo_path: str = field(
        default_factory=lambda: _env_first(
            "PA_GIT_REPO_PATH", "GIT_REPO_PATH",
            default=os.path.dirname(os.path.abspath(__file__)),
        )
    )
    commit_message_template: str = "feat(skills): {skill_name} v{version}"
    auto_commit: bool = field(default_factory=lambda: _env_bool("GIT_AUTO_COMMIT", True))


@dataclass
class AgentConfig:
    """Configuration for the Personal Assistant Agent."""

    name: str = "Personal Assistant"
    version: str = "1.0.0"
    description: str = "Personal assistant with skill creation and execution capabilities"
    enable_intent_detection: bool = True
    require_confirmation: bool = False
    max_retries: int = 3
    timeout: int = 120
    memory_limit: int = 50
    verbose: bool = True


@dataclass
class Config:
    """Central configuration manager."""

    model: ModelConfig = field(default_factory=ModelConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    git: GitConfig = field(default_factory=GitConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)

    def to_dict(self) -> dict:
        from dataclasses import asdict

        return asdict(self)


def get_config() -> Config:
    """Build a fresh Config from the current environment."""
    return Config()


# Global configuration instance
config = get_config()
