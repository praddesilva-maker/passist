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


# ----------------------------------------------------------------------
# Task 4.2/4.3 — load_skill() and the skill-record cache
# ----------------------------------------------------------------------


def test_cache_starts_empty(temp_registry):
    stage = UnifiedSkillStage(temp_registry)
    assert stage.cache_stats() == {"hits": 0, "misses": 0, "size": 0}


def test_load_skill_caches_records_and_tracks_hits(temp_registry):
    _register(temp_registry, "cached", "def run():\n    return 1\n")
    stage = UnifiedSkillStage(temp_registry)

    stage.load_skill("cached")
    assert stage.cache_stats() == {"hits": 0, "misses": 1, "size": 1}

    stage.load_skill("cached")
    assert stage.cache_stats() == {"hits": 1, "misses": 1, "size": 1}

    stage.clear_cache()
    assert stage.cache_stats()["size"] == 0
    stage.load_skill("cached")
    assert stage.cache_stats()["misses"] == 2


def test_load_skill_missing_raises_not_found(temp_registry):
    stage = UnifiedSkillStage(temp_registry)
    with pytest.raises(SkillNotFoundError):
        stage.load_skill("ghost")


def test_load_skill_version_is_a_separate_cache_key(temp_registry):
    _register(temp_registry, "vhist", "def run():\n    return 'v1'\n")
    temp_registry.update_skill("vhist", code="def run():\n    return 'v2'\n")
    stage = UnifiedSkillStage(temp_registry)

    latest = stage._load_function_skill("vhist")
    pinned = stage.load_skill("vhist", version=1)
    assert latest.invoke({}) == "v2"
    assert pinned.invoke({}) == "v1"
    # Two distinct cache entries: (name, None) and (name, 1).
    stage.load_skill("vhist")
    assert stage.cache_stats()["size"] == 2


def test_load_skill_missing_version_raises_not_found(temp_registry):
    _register(temp_registry, "onlyv1", "def run():\n    return 1\n")
    stage = UnifiedSkillStage(temp_registry)
    with pytest.raises(SkillNotFoundError):
        stage.load_skill("onlyv1", version=99)


# ----------------------------------------------------------------------
# Task 5.1 — Function skill loading as a LangChain tool
# ----------------------------------------------------------------------


def test_load_skill_function_type_returns_invocable_tool(temp_registry):
    _register(
        temp_registry, "adder2",
        "def run(a: int, b: int) -> int:\n    return a + b\n",
        description="Adds two numbers",
    )
    stage = UnifiedSkillStage(temp_registry)
    tool = stage.load_skill("adder2")
    assert tool.name == "adder2"
    assert tool.description == "Adds two numbers"
    assert tool.invoke({"a": 2, "b": 3}) == 5


# ----------------------------------------------------------------------
# Task 5.2 — Agent skill loading (GLM LLM + tools + memory)
# ----------------------------------------------------------------------


def test_load_skill_agent_type_returns_agent_with_memory(temp_registry):
    _register(
        temp_registry, "myagent",
        "def run(input_value: str = ''):\n    return 'agent:' + input_value\n",
        skill_type="agent",
    )
    stage = UnifiedSkillStage(temp_registry)
    agent = stage.load_skill("myagent")
    # A compiled LangGraph agent exposes a checkpointer (its "memory").
    assert agent.checkpointer is not None
    # Runnable end-to-end offline (no GLM_API_KEY in the test environment;
    # conftest.py forces GLM_API_KEY="").
    config = {"configurable": {"thread_id": "t1"}}
    result = agent.invoke({"messages": [("user", "hi")]}, config=config)
    assert "messages" in result


def test_load_skill_agent_type_with_offline_tools_falls_back_gracefully(temp_registry):
    _register(temp_registry, "helper_fn", "def run():\n    return 'helped'\n")
    _register(
        temp_registry, "toolagent",
        "def run(input_value: str = ''):\n    return input_value\n",
        skill_type="agent",
    )
    temp_registry.update_skill("toolagent", parameters={"tools": ["helper_fn"]})
    stage = UnifiedSkillStage(temp_registry)
    # Must not raise even though a real GLM key is unavailable: offline model
    # can't bind_tools, so the loader drops to a tool-less agent.
    agent = stage.load_skill("toolagent")
    assert agent.checkpointer is not None


# ----------------------------------------------------------------------
# Task 5.3 — Workflow skill loading (LangGraph graph of nodes/edges)
# ----------------------------------------------------------------------


def test_load_skill_workflow_type_defaults_to_single_step(temp_registry):
    _register(
        temp_registry, "wf_single",
        "def run(input_value: str = ''):\n    return 'wf:' + input_value\n",
        skill_type="workflow",
    )
    stage = UnifiedSkillStage(temp_registry)
    graph = stage.load_skill("wf_single")
    result = graph.invoke({"input_value": "go"})
    assert result["wf_single"] == "wf:go"


def test_load_skill_workflow_type_chains_declared_steps(temp_registry):
    _register(temp_registry, "step_a", "def run(x: int = 0):\n    return x + 1\n")
    _register(temp_registry, "step_b", "def run(x: int = 0):\n    return x * 2\n")
    _register(
        temp_registry, "wf_multi",
        "def run(x: int = 0):\n    return x\n",
        skill_type="workflow",
    )
    temp_registry.update_skill("wf_multi", parameters={"steps": ["step_a", "step_b"]})
    stage = UnifiedSkillStage(temp_registry)
    graph = stage.load_skill("wf_multi")
    result = graph.invoke({"x": 5})
    assert result["step_a"] == 6
    # step_b's node re-reads the shared state's "x" key (unchanged by
    # step_a, which only adds its own output key), so it doubles the
    # original input rather than chaining step_a's result.
    assert result["step_b"] == 10


def test_load_skill_workflow_step_failure_raises(temp_registry):
    _register(
        temp_registry, "wf_broken",
        "def run(x):\n    return x\n",
        skill_type="workflow",
    )
    stage = UnifiedSkillStage(temp_registry)
    graph = stage.load_skill("wf_broken")
    with pytest.raises(SkillExecutionError):
        graph.invoke({})  # missing required arg "x" -> step execution fails


# ----------------------------------------------------------------------
# Task 5.4 — Error handling for skill loading
# ----------------------------------------------------------------------


def test_load_skill_invalid_type_raises_execution_error(temp_registry, monkeypatch):
    _register(temp_registry, "weird", "def run():\n    return 1\n")
    stage = UnifiedSkillStage(temp_registry)
    # No public registry API can persist an out-of-band type, so exercise the
    # loader's guard directly against a crafted record.
    monkeypatch.setattr(
        stage.registry, "get_skill",
        lambda name: {"name": "weird", "type": "not-a-real-type", "code": "def run():\n    return 1\n"},
    )
    with pytest.raises(SkillExecutionError, match="Invalid skill type"):
        stage.load_skill("weird")


def test_load_skill_not_found_is_skill_not_found_error(temp_registry):
    stage = UnifiedSkillStage(temp_registry)
    with pytest.raises(SkillNotFoundError):
        stage.load_skill("does-not-exist")

# ---------------------------------------------------------------------------
# Task 4.1's version-controller parameter (escalation resolved 2026-09-17).
# ---------------------------------------------------------------------------

def test_version_controller_defaults_to_none(temp_registry):
    from skills.unified_stage import UnifiedSkillStage

    assert UnifiedSkillStage(temp_registry).version_controller is None


def test_version_controller_is_held_when_supplied(temp_registry):
    from skills.unified_stage import UnifiedSkillStage

    sentinel = object()
    stage = UnifiedSkillStage(temp_registry, version_controller=sentinel)
    assert stage.version_controller is sentinel


def test_registry_is_still_accepted_positionally(temp_registry):
    """Existing callers pass the registry positionally; that must keep working."""
    from skills.unified_stage import UnifiedSkillStage

    assert UnifiedSkillStage(temp_registry).registry is temp_registry
