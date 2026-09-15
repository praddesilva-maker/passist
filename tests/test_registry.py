#!/usr/bin/env python3
"""
Tests for the central skill registry and unified stage.
"""

from skills.registry import (
    SkillRegistry,
    SkillAlreadyExistsError,
    SkillNotFoundError,
)


def test_registry_register_and_get(temp_registry):
    skill = temp_registry.register_skill(
        name="hello",
        skill_type="function",
        description="Says hello",
        code='def run(input_value: str = ""):\n    return {"hello": input_value}\n',
    )
    assert skill["name"] == "hello"
    assert skill["type"] == "function"
    assert skill["current_version"] == 1

    fetched = temp_registry.get_skill("hello")
    assert fetched["name"] == "hello"
    assert "def run(" in fetched["code"]


def test_registry_duplicate_rejected(temp_registry):
    temp_registry.register_skill(
        name="dup",
        skill_type="function",
        code="def run(input_value: str = ''): return input_value\n",
    )
    try:
        temp_registry.register_skill(
            name="dup",
            skill_type="function",
            code="def run(input_value: str = ''): return input_value\n",
        )
    except SkillAlreadyExistsError:
        return
    raise AssertionError("expected SkillAlreadyExistsError")


def test_registry_missing_skill(temp_registry):
    # get_skill is a lookup: it is declared -> Optional[Dict] and MainAgent
    # .handle_request relies on the None return, so a miss is not an error.
    assert temp_registry.get_skill("nope") is None

    # Mutating a skill that does not exist IS an error.
    for operation in (
        lambda: temp_registry.update_skill("nope", code="def run():\n    return 1\n"),
        lambda: temp_registry.delete_skill("nope"),
    ):
        try:
            operation()
        except SkillNotFoundError:
            continue
        raise AssertionError("expected SkillNotFoundError")


def test_registry_list_and_runs(temp_registry_with_skills):
    skills = temp_registry_with_skills.list_skills()
    assert any(s["name"] == "echo_skill" for s in skills)

    stage = _stage(temp_registry_with_skills)
    result = stage.execute_skill("echo_skill", {"input_value": "hi"})
    assert result["success"] is True
    assert result["output"] == {"echo": "hi"}

    runs = temp_registry_with_skills.get_skill_runs("echo_skill")
    assert len(runs) == 1
    assert runs[0]["success"] is True


def test_stage_unknown_skill_structured_error(temp_registry):
    from skills.unified_stage import UnifiedSkillStage

    stage = UnifiedSkillStage(temp_registry)
    result = stage.execute_skill("ghost", {"input_value": "x"})
    assert result["success"] is False
    assert result["error"]
    assert result["skill_name"] == "ghost"


def _stage(registry: SkillRegistry):
    from skills.unified_stage import UnifiedSkillStage

    return UnifiedSkillStage(registry)
