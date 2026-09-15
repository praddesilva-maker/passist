#!/usr/bin/env python3
"""
Shared pytest fixtures for the Personal Assistant test suite.

Isolation guarantees:
* Every test process runs **offline**: ``GLM_API_KEY`` is forced empty so no
  test depends on a live API key or external service.
* All registries are backed by SQLite databases inside ``tmp_path`` (via the
  :func:`temp_registry` fixture); nothing ever opens ``skills/skills.db``.
* The working directory is never mutated: no test writes shared state
  (``memory/`` or ``skills/`` directories) outside temporary directories.
"""

import os
import sys

import pytest

# Make sure project root is importable regardless of how pytest is invoked.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Force offline mode and redirect all shared state into tmp_path."""
    # Offline: never hit the network, never require a real key.
    monkeypatch.setenv("GLM_API_KEY", "")
    # Redirect persistent state directories into the per-test tmp dir.
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(exist_ok=True)
    monkeypatch.setenv("PA_MEMORY_DIR", str(memory_dir))
    monkeypatch.setenv("PA_SKILLS_DIR", str(tmp_path / "skills"))
    # Point the registry db and git repo at temp locations by default.
    monkeypatch.setenv("PA_DATABASE_PATH", str(tmp_path / "skills.db"))
    monkeypatch.setenv("PA_GIT_REPO_PATH", str(tmp_path))
    yield
    monkeypatch.undo()


@pytest.fixture
def temp_registry(isolated_env, tmp_path):
    """A fresh, isolated SkillRegistry backed by a temp SQLite database."""
    from skills.registry import SkillRegistry

    db_path = str(tmp_path / "registry.db")
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    registry = SkillRegistry(
        db_path=db_path,
        git_repo_path=str(repo),
        auto_commit=False,
    )
    yield registry
    registry.close()


@pytest.fixture
def temp_registry_with_skills(temp_registry):
    """A temp registry preloaded with one simple, valid function skill."""
    temp_registry.register_skill(
        name="echo_skill",
        skill_type="function",
        description="Echoes input",
        code=(
            "def run(input_value: str = \"\"):\n"
            "    return {'echo': input_value}\n"
        ),
    )
    return temp_registry


@pytest.fixture
def temp_agent(temp_registry_with_skills):
    """A MainAgent wired to the temp registry with an offline LLM."""
    from agent.llm import OfflineChatModel
    from agent.main_agent import MainAgent
    from skills.unified_stage import UnifiedSkillStage

    registry = temp_registry_with_skills
    stage = UnifiedSkillStage(registry)
    agent = MainAgent(
        agent_name="test_agent",
        stage=stage,
        registry=registry,
        llm=OfflineChatModel(),
        git_manager=None,
        memory_backend="memory",
    )
    yield agent
    agent.cleanup()
