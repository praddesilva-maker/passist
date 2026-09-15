#!/usr/bin/env python3
"""
Tests for SkillBuilder registration and offline template behavior.
"""

import inspect

from skills.skill_builder import SkillBuilder


def test_offline_template_is_valid_skill_code(temp_registry):
    code = SkillBuilder.offline_template("My Cool Skill", "Does a thing")
    # Valid identifier + top-level run function.
    assert "def run(" in code
    validation = temp_registry.validate_skill(
        {"name": "my_cool_skill", "type": "function", "code": code}
    )
    assert validation["valid"] is True, validation["errors"]


def test_register_via_builder(temp_registry):
    builder = SkillBuilder(temp_registry)
    code = SkillBuilder.offline_template("adder", "Adds numbers")
    result = builder.register("adder", code, "function", "Adds numbers")
    assert result["success"] is True
    assert result["skill"]["name"] == "adder"
    assert result["error"] is None


def test_register_duplicate_returns_error_payload(temp_registry):
    builder = SkillBuilder(temp_registry)
    code = SkillBuilder.offline_template("one", "First")
    assert builder.register("one", code, "function", "First")["success"] is True
    again = builder.register("one", code, "function", "First")
    assert again["success"] is False
    assert "AlreadyExists" in (again["error"] or "")


def test_register_bad_type_returns_error_payload(temp_registry):
    builder = SkillBuilder(temp_registry)
    result = builder.register(
        "bad", "def run(input_value: str = ''): return input_value\n", "workflowx"
    )
    assert result["success"] is False
    assert result["error"]


def test_register_bad_code_returns_error_payload(temp_registry):
    builder = SkillBuilder(temp_registry)
    result = builder.register("broken", "not def run: pass", "function", "broken")
    assert result["success"] is False
    assert result["error"]


def test_list_skills_does_not_scan_filesystem(temp_registry):
    builder = SkillBuilder(temp_registry)
    assert builder.list_skills() == []
