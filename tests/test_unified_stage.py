#!/usr/bin/env python3
"""
Task 6 — Unified Stage: testing (registry, skill loading, integration, QA).

Restored 2026-09-16 (the file was deleted in an earlier run) and rewritten
against the *current* API: ``SkillRegistry.register_skill`` +
``UnifiedSkillStage.execute_skill``/``run``.  The pre-repair copy at
``git show f6a30a8:tests/test_unified_stage.py`` used a removed
``add_skill(name, type, path)`` API.

Covers guide §1.8.7 (Tasks 6.1–6.4):
* 6.1 registry tests   — registration, retrieval, search, listing
* 6.2 skill loading    — function/agent/workflow loading + error cases
* 6.3 integration      — registry→stage, create→execute, versioning, runs
* 6.4 QA verification  — the QA skill confirms the unified stage works
"""

import pytest

from skills.models import VALID_SKILL_TYPES
from skills.qa_skill import SkillQA
from skills.registry import (
    RegistryError,
    SkillAlreadyExistsError,
    SkillNotFoundError,
)
from skills.unified_stage import SkillExecutionError, UnifiedSkillStage


def _register(registry, name, code, skill_type="function", description=""):
    """Register a skill through the public registry API."""
    return registry.register_skill(
        name=name,
        skill_type=skill_type,
        description=description,
        code=code,
    )


# ----------------------------------------------------------------------
# Task 6.1 — Registry tests
# ----------------------------------------------------------------------


def test_registry_register_and_get(temp_registry):
    skill = _register(
        temp_registry,
        "hello",
        'def run(input_value: str = ""):\n    return {"hello": input_value}\n',
    )
    assert skill["name"] == "hello"
    assert skill["type"] == "function"
    assert skill["current_version"] == 1
    assert skill["active"] is True

    fetched = temp_registry.get_skill("hello")
    assert fetched["name"] == "hello"
    assert "def run(" in fetched["code"]


def test_registry_get_missing_returns_none(temp_registry):
    assert temp_registry.get_skill("does-not-exist") is None


def test_registry_duplicate_rejected(temp_registry):
    code = "def run():\n    return 1\n"
    _register(temp_registry, "dup", code)
    with pytest.raises(SkillAlreadyExistsError):
        _register(temp_registry, "dup", code)


def test_registry_invalid_name_rejected(temp_registry):
    with pytest.raises(RegistryError):
        _register(temp_registry, "bad name!", "def run():\n    return 1\n")


def test_registry_invalid_code_rejected(temp_registry):
    with pytest.raises(RegistryError):
        _register(temp_registry, "no_func", "x = 1\n")
    with pytest.raises(RegistryError):
        _register(temp_registry, "empty_code", "")
    with pytest.raises(RegistryError):
        _register(temp_registry, "bad_type", "def run():\n    return 1\n",
                  skill_type="not-a-type")


def test_registry_update_bumps_version(temp_registry):
    _register(temp_registry, "ver", "def run():\n    return 'v1'\n")
    updated = temp_registry.update_skill(
        "ver", code="def run():\n    return 'v2'\n", note="second version"
    )
    assert updated["current_version"] == 2
    assert "v2" in updated["code"]
    assert len(temp_registry.get_version_history("ver")) == 2


def test_registry_update_missing_raises(temp_registry):
    with pytest.raises(SkillNotFoundError):
        temp_registry.update_skill("ghost", code="def run():\n    return 1\n")


def test_registry_delete_is_soft_and_reversible(temp_registry):
    _register(temp_registry, "temp", "def run():\n    return 1\n")
    temp_registry.delete_skill("temp")

    assert temp_registry.get_skill("temp") is None
    assert temp_registry.list_skills() == []
    # Deletion is a flag, not a purge: history survives and re-activation works.
    assert len(temp_registry.get_version_history("temp")) == 1
    reactivated = temp_registry.activate_skill("temp")
    assert reactivated["active"] is True
    assert temp_registry.get_skill("temp") is not None

    with pytest.raises(SkillNotFoundError):
        temp_registry.delete_skill("ghost")


def test_registry_list_and_search(temp_registry):
    _register(
        temp_registry, "adder",
        "def run(a, b):\n    return a + b\n",
        description="Adds two numbers",
    )
    _register(
        temp_registry, "greeter",
        "def run(name):\n    return f'hi {name}'\n",
        description="Greets a person",
    )

    names = {s["name"] for s in temp_registry.list_skills()}
    assert names == {"adder", "greeter"}

    found = temp_registry.search_skills("adds two")
    assert [s["name"] for s in found] == ["adder"]
    found_name = temp_registry.search_skills("greeter")
    assert [s["name"] for s in found_name] == ["greeter"]
    assert temp_registry.search_skills("") == temp_registry.list_skills()


# ----------------------------------------------------------------------
# Task 6.2 — Skill loading tests
# ----------------------------------------------------------------------


def test_load_function_skill_run_entry(temp_registry):
    _register(temp_registry, "hello", "def run():\n    return 'hello world'\n")
    stage = UnifiedSkillStage(temp_registry)
    assert stage.run("hello") == "hello world"


def test_load_function_skill_main_entry(temp_registry):
    # When there is no ``run``, ``main`` is the entry point.
    _register(temp_registry, "mainskill", "def main():\n    return 'main executed'\n")
    stage = UnifiedSkillStage(temp_registry)
    assert stage.run("mainskill") == "main executed"


def test_load_first_def_as_fallback_entry(temp_registry):
    # No run/main: the first top-level def in source order is the entry.
    _register(
        temp_registry, "firstdef",
        "def alpha():\n    return 'alpha'\n\n"
        "def beta():\n    return 'beta'\n",
    )
    stage = UnifiedSkillStage(temp_registry)
    assert stage.run("firstdef") == "alpha"


def test_load_with_arguments(temp_registry):
    _register(temp_registry, "adder", "def run(x, y):\n    return x + y\n")
    stage = UnifiedSkillStage(temp_registry)
    assert stage.run("adder", x=2, y=3) == 5


def test_load_ignores_unknown_extra_kwargs(temp_registry):
    _register(temp_registry, "pick", "def run(a, b=10):\n    return (a, b)\n")
    stage = UnifiedSkillStage(temp_registry)
    assert stage.run("pick", a=1, b=2, extra="ignored") == (1, 2)


def test_load_missing_required_argument_fails(temp_registry):
    _register(temp_registry, "needs", "def run(a, b):\n    return a + b\n")
    stage = UnifiedSkillStage(temp_registry)
    result = stage.execute_skill("needs", {"a": 1})
    assert result["success"] is False
    assert "b" in result["error"]
    with pytest.raises(SkillExecutionError):
        stage.run("needs", a=1)


def test_load_agent_and_workflow_types(temp_registry):
    # The unified stage executes any registered type uniformly.
    for skill_type in ("agent", "workflow"):
        name = f"skill_{skill_type}"
        _register(
            temp_registry, name,
            f"def run(input_value: str = ''):\n    return '{skill_type}:' + input_value\n",
            skill_type=skill_type,
        )
        stage = UnifiedSkillStage(temp_registry)
        result = stage.execute_skill(name, {"input_value": "ok"})
        assert result["success"] is True
        assert result["skill_type"] == skill_type
        assert result["output"] == f"{skill_type}:ok"


def test_load_invalid_python_fails(temp_registry):
    # Validation happens at registration, so an invalid-syntax skill can only
    # enter the registry through a raw update; the stage must still refuse it.
    _register(temp_registry, "broken", "def run():\n    return 1\n")
    temp_registry.update_skill("broken", code="def run(:\n    oops\n")
    stage = UnifiedSkillStage(temp_registry)
    result = stage.execute_skill("broken")
    assert result["success"] is False
    assert "invalid Python code" in result["error"]


def test_load_no_functions_fails(temp_registry):
    # register_skill rejects code without a def, so exercise the loader
    # directly through an update instead.  The stage's pre-execution
    # validation rejects such skills before the AST loader ever runs.
    _register(temp_registry, "hasfunc", "def run():\n    return 1\n")
    temp_registry.update_skill("hasfunc", code="import os\n")
    stage = UnifiedSkillStage(temp_registry)
    result = stage.execute_skill("hasfunc")
    assert result["success"] is False
    assert "no function definition" in result["error"]


# ----------------------------------------------------------------------
# Task 6.3 — Integration tests
# ----------------------------------------------------------------------


def test_integration_registry_to_stage_flow(temp_registry):
    _register(
        temp_registry, "pipeline",
        "def run(value: int = 0):\n    return value * 2\n",
    )
    stage = UnifiedSkillStage(temp_registry)
    assert [s["name"] for s in stage.list_available_skills()] == ["pipeline"]

    result = stage.execute_skill("pipeline", {"value": 21})
    assert result["success"] is True
    assert result["output"] == 42
    assert result["skill_name"] == "pipeline"
    assert result["skill_type"] == "function"
    assert result["version"] == 1
    assert result["error"] is None
    assert result["execution_time_ms"] >= 0


def test_integration_create_then_execute_with_runs(temp_registry):
    _register(
        temp_registry, "calc",
        "def run(x: int = 0):\n    return x + 1\n",
    )
    stage = UnifiedSkillStage(temp_registry)
    assert stage.run("calc", x=1) == 2
    assert stage.run("calc", x=10) == 11

    runs = temp_registry.get_skill_runs("calc")
    assert len(runs) == 2
    # Newest first.
    assert runs[0]["output"] == 11
    assert runs[0]["success"] is True
    assert runs[0]["version"] == 1
    assert runs[0]["input_data"] == {"x": 10}


def test_integration_version_control_roundtrip(temp_registry):
    _register(temp_registry, "vc", "def run():\n    return 'v1'\n")
    temp_registry.update_skill("vc", code="def run():\n    return 'v2'\n")

    history = temp_registry.get_version_history("vc")
    assert [h["version"] for h in history] == [2, 1]
    assert "v1" in temp_registry.get_version("vc", 1)["code"]

    diff = temp_registry.diff_versions("vc", 1, 2)
    assert diff["v1"]["version"] == 1
    assert diff["v2"]["version"] == 2
    assert "v1" in diff["v1"]["code"]
    assert "'v2'" in diff["diff"]

    rolled = temp_registry.rollback_to_version("vc", 1)
    assert rolled["current_version"] == 3
    assert temp_registry.get_skill("vc")["code"].strip().endswith("return 'v1'")

    stage = UnifiedSkillStage(temp_registry)
    assert stage.run("vc") == "v1"

    with pytest.raises(SkillNotFoundError):
        temp_registry.rollback_to_version("vc", 99)


def test_integration_stage_skips_inactive_skill(temp_registry):
    _register(temp_registry, "toggle", "def run():\n    return 'on'\n")
    temp_registry.delete_skill("toggle")
    stage = UnifiedSkillStage(temp_registry)
    result = stage.execute_skill("toggle")
    assert result["success"] is False
    assert "not found" in result["error"]


def test_integration_log_run_disabled(temp_registry):
    _register(temp_registry, "quiet", "def run():\n    return 7\n")
    stage = UnifiedSkillStage(temp_registry)
    result = stage.execute_skill("quiet", log_run=False)
    assert result["success"] is True
    assert temp_registry.get_skill_runs("quiet") == []


def test_run_unknown_skill_raises(temp_registry):
    stage = UnifiedSkillStage(temp_registry)
    with pytest.raises(SkillExecutionError):
        stage.run("ghost")


# ----------------------------------------------------------------------
# Task 6.4 — QA skill verification of the unified stage
# ----------------------------------------------------------------------


def test_qa_verifies_unified_stage(temp_registry):
    for skill_type in VALID_SKILL_TYPES:
        _register(
            temp_registry, f"qa_{skill_type}",
            "def run(v=0):\n    return v\n",
            skill_type=skill_type,
            description=f"QA fixture for {skill_type} skills",
        )

    qa = SkillQA(temp_registry, llm=None)  # offline: no GLM key in tests

    stats = qa.get_statistics()
    assert stats["success"] is True
    assert stats["total_skills"] == 3

    for name in stats["skill_names"]:
        structure = qa.validate_skill_structure(name)
        assert structure["success"] is True
        assert structure["valid"] is True
        executed = qa.test_skill(name, {"v": 99})
        assert executed["success"] is True
        assert executed["output"] == 99

    report = qa.report()
    assert report["success"] is True
    assert report["invalid_skills"] == []
    assert report["offline"] is True
    assert len(report["recent_runs"]) == 3
    assert all(run["success"] for run in report["recent_runs"])