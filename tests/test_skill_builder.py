#!/usr/bin/env python3
"""
Tests for SkillBuilder: registration/offline-template behavior (Task 11
carryover), and the interactive builder's basic features - skill selection,
description editing, parameter editing, and code editing (Task 12) - plus
registry-integration and end-to-end workflow coverage (Task 14).
"""

import inspect

import pytest

from skills.registry import RegistryError
from skills.skill_builder import PARAMETER_TYPES, SkillBuilder


def _scripted_input(responses):
    """Build an ``input()``-shaped callable that replays canned responses.

    Exhausting the script raises ``EOFError``, matching real ``input()`` on
    a closed stdin - this is what lets ``run_interactive_session`` cancel
    cleanly instead of hanging in a test.
    """
    it = iter(responses)

    def _input(prompt=""):
        try:
            return next(it)
        except StopIteration:
            raise EOFError

    return _input


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


# ---------------------------------------------------------------------------
# Task 12.1 - Skill selection UI
# ---------------------------------------------------------------------------


def _builder_with_skill(temp_registry, name="adder", description="Adds numbers"):
    builder = SkillBuilder(temp_registry)
    code = SkillBuilder.offline_template(name, description)
    result = builder.register(name, code, "function", description)
    assert result["success"] is True
    return builder


def test_format_skill_list_empty(temp_registry):
    builder = SkillBuilder(temp_registry)
    assert builder.format_skill_list() == "No skills registered."


def test_format_skill_list_shows_registered_skills(temp_registry):
    builder = _builder_with_skill(temp_registry)
    listing = builder.format_skill_list()
    assert "1. adder [function] - Adds numbers" == listing


def test_select_skill_by_name(temp_registry):
    builder = _builder_with_skill(temp_registry)
    result = builder.select_skill("adder")
    assert result["success"] is True
    assert result["skill"]["name"] == "adder"
    assert result["error"] is None


def test_select_skill_by_index(temp_registry):
    builder = _builder_with_skill(temp_registry)
    result = builder.select_skill("1")
    assert result["success"] is True
    assert result["skill"]["name"] == "adder"


def test_select_skill_invalid_name_is_handled(temp_registry):
    builder = _builder_with_skill(temp_registry)
    result = builder.select_skill("does-not-exist")
    assert result["success"] is False
    assert result["skill"] is None
    assert "not found" in result["error"]


def test_select_skill_out_of_range_index_is_handled(temp_registry):
    builder = _builder_with_skill(temp_registry)
    result = builder.select_skill("99")
    assert result["success"] is False
    assert "out of range" in result["error"]


def test_select_skill_empty_selection_is_handled(temp_registry):
    builder = SkillBuilder(temp_registry)
    result = builder.select_skill("")
    assert result["success"] is False
    assert result["error"] == "no skill selected"
    # None must also be handled without raising.
    assert builder.select_skill(None)["success"] is False


def test_describe_skill_shows_details(temp_registry):
    builder = _builder_with_skill(temp_registry)
    builder.add_parameter("adder", "x", "int", "first number")
    result = builder.describe_skill("adder")
    assert result["success"] is True
    assert "Name: adder" in result["details"]
    assert "Type: function" in result["details"]
    assert "x (int): first number" in result["details"]


def test_describe_skill_unknown_is_handled(temp_registry):
    builder = SkillBuilder(temp_registry)
    result = builder.describe_skill("ghost")
    assert result["success"] is False
    assert result["details"] is None


# ---------------------------------------------------------------------------
# Task 12.2 - Description editing
# ---------------------------------------------------------------------------


def test_edit_description_updates_and_shows_change(temp_registry):
    builder = _builder_with_skill(temp_registry)
    result = builder.edit_description("adder", "Adds two numbers together")
    assert result["success"] is True
    assert result["old_description"] == "Adds numbers"
    assert result["new_description"] == "Adds two numbers together"
    # Persisted: re-reading the skill reflects the update.
    assert builder.registry.get_skill("adder")["description"] == "Adds two numbers together"


def test_edit_description_bumps_version(temp_registry):
    builder = _builder_with_skill(temp_registry)
    before = builder.registry.get_skill("adder")["current_version"]
    builder.edit_description("adder", "New description")
    after = builder.registry.get_skill("adder")["current_version"]
    assert after == before + 1


def test_edit_description_rejects_empty(temp_registry):
    builder = _builder_with_skill(temp_registry)
    result = builder.edit_description("adder", "   ")
    assert result["success"] is False
    assert "empty" in result["error"]
    # Original description must be untouched.
    assert builder.registry.get_skill("adder")["description"] == "Adds numbers"


def test_edit_description_unknown_skill_is_handled(temp_registry):
    builder = SkillBuilder(temp_registry)
    result = builder.edit_description("ghost", "New text")
    assert result["success"] is False
    assert "not found" in result["error"]


# ---------------------------------------------------------------------------
# Task 12.3 - Parameter editing
# ---------------------------------------------------------------------------


def test_list_parameters_empty_then_populated(temp_registry):
    builder = _builder_with_skill(temp_registry)
    assert builder.list_parameters("adder")["parameters"] == {}
    builder.add_parameter("adder", "x", "int", "first number")
    assert "x" in builder.list_parameters("adder")["parameters"]


def test_add_parameter_success(temp_registry):
    builder = _builder_with_skill(temp_registry)
    result = builder.add_parameter("adder", "x", "int", "first number")
    assert result["success"] is True
    assert result["parameters"]["x"] == {"type": "int", "description": "first number"}


def test_add_parameter_duplicate_rejected(temp_registry):
    builder = _builder_with_skill(temp_registry)
    builder.add_parameter("adder", "x", "int", "first number")
    result = builder.add_parameter("adder", "x", "int", "again")
    assert result["success"] is False
    assert "already exists" in result["error"]


def test_add_parameter_invalid_type_rejected(temp_registry):
    builder = _builder_with_skill(temp_registry)
    result = builder.add_parameter("adder", "x", "not-a-type")
    assert result["success"] is False
    assert "invalid parameter type" in result["error"]
    assert builder.list_parameters("adder")["parameters"] == {}


def test_add_parameter_invalid_name_rejected(temp_registry):
    builder = _builder_with_skill(temp_registry)
    result = builder.add_parameter("adder", "1bad-name", "str")
    assert result["success"] is False
    assert "invalid parameter name" in result["error"]


def test_add_parameter_all_canonical_types_accepted(temp_registry):
    builder = _builder_with_skill(temp_registry)
    for i, ptype in enumerate(PARAMETER_TYPES):
        result = builder.add_parameter("adder", f"p_{i}", ptype)
        assert result["success"] is True, (ptype, result["error"])


def test_update_parameter_success(temp_registry):
    builder = _builder_with_skill(temp_registry)
    builder.add_parameter("adder", "x", "int", "first number")
    result = builder.update_parameter("adder", "x", param_type="float", description="updated")
    assert result["success"] is True
    assert result["parameters"]["x"] == {"type": "float", "description": "updated"}


def test_update_parameter_missing_param_rejected(temp_registry):
    builder = _builder_with_skill(temp_registry)
    result = builder.update_parameter("adder", "ghost", description="x")
    assert result["success"] is False
    assert "not found" in result["error"]


def test_update_parameter_missing_skill_rejected(temp_registry):
    builder = SkillBuilder(temp_registry)
    result = builder.update_parameter("ghost", "x", description="x")
    assert result["success"] is False
    assert "skill 'ghost' not found" in result["error"]


def test_remove_parameter_success(temp_registry):
    builder = _builder_with_skill(temp_registry)
    builder.add_parameter("adder", "x", "int", "first number")
    result = builder.remove_parameter("adder", "x")
    assert result["success"] is True
    assert result["parameters"] == {}


def test_remove_parameter_missing_rejected(temp_registry):
    builder = _builder_with_skill(temp_registry)
    result = builder.remove_parameter("adder", "x")
    assert result["success"] is False
    assert "not found" in result["error"]


# ---------------------------------------------------------------------------
# Task 12.4 - Code editing
# ---------------------------------------------------------------------------


def test_get_code_returns_current_code(temp_registry):
    builder = _builder_with_skill(temp_registry)
    result = builder.get_code("adder")
    assert result["success"] is True
    assert "def run(" in result["code"]


def test_get_code_unknown_skill_is_handled(temp_registry):
    builder = SkillBuilder(temp_registry)
    result = builder.get_code("ghost")
    assert result["success"] is False


def test_edit_code_success_shows_diff_and_persists(temp_registry):
    builder = _builder_with_skill(temp_registry)
    old_code = builder.get_code("adder")["code"]
    new_code = old_code.replace('"result": "OK"', '"result": "UPDATED"')
    result = builder.edit_code("adder", new_code)
    assert result["success"] is True
    assert "-        \"result\": \"OK\"," in result["diff"]
    assert "+        \"result\": \"UPDATED\"," in result["diff"]
    assert builder.get_code("adder")["code"] == new_code


def test_edit_code_bumps_version(temp_registry):
    builder = _builder_with_skill(temp_registry)
    before = builder.registry.get_skill("adder")["current_version"]
    builder.edit_code("adder", "def run(input_value=''):\n    return input_value\n")
    after = builder.registry.get_skill("adder")["current_version"]
    assert after == before + 1


def test_edit_code_syntax_error_rejected_and_original_kept(temp_registry):
    builder = _builder_with_skill(temp_registry)
    old_code = builder.get_code("adder")["code"]
    result = builder.edit_code("adder", "def broken(:\n    pass")
    assert result["success"] is False
    assert "SyntaxError" in result["error"]
    assert builder.get_code("adder")["code"] == old_code


def test_edit_code_without_function_rejected(temp_registry):
    builder = _builder_with_skill(temp_registry)
    old_code = builder.get_code("adder")["code"]
    result = builder.edit_code("adder", '"""just a docstring"""')
    assert result["success"] is False
    assert "function definition" in result["error"]
    assert builder.get_code("adder")["code"] == old_code


def test_edit_code_unknown_skill_is_handled(temp_registry):
    builder = SkillBuilder(temp_registry)
    result = builder.edit_code("ghost", "def run():\n    pass\n")
    assert result["success"] is False
    assert "not found" in result["error"]


# ---------------------------------------------------------------------------
# Interactive terminal loop (ties 12.1-12.4 together)
# ---------------------------------------------------------------------------


def test_interactive_session_edits_description_then_quits(temp_registry):
    builder = _builder_with_skill(temp_registry)
    fake_input = _scripted_input(["1", "d", "Interactive description", "q"])
    outputs = []
    result = builder.run_interactive_session(input_func=fake_input, output_func=outputs.append)
    assert result == {"success": True, "skill_name": "adder", "cancelled": False, "error": None}
    assert builder.registry.get_skill("adder")["description"] == "Interactive description"
    assert any("Updated description." in line for line in outputs)


def test_interactive_session_adds_parameter(temp_registry):
    builder = _builder_with_skill(temp_registry)
    fake_input = _scripted_input(["adder", "p", "a", "count", "int", "how many", "q"])
    outputs = []
    result = builder.run_interactive_session(input_func=fake_input, output_func=outputs.append)
    assert result["success"] is True
    params = builder.registry.get_skill("adder")["parameters"]
    assert params["count"] == {"type": "int", "description": "how many"}


def test_interactive_session_edits_code(temp_registry):
    builder = _builder_with_skill(temp_registry)
    new_code = "def run(input_value=''):\n    return {'ok': True}\n"
    fake_input = _scripted_input(["adder", "c", new_code, "q"])
    outputs = []
    result = builder.run_interactive_session(input_func=fake_input, output_func=outputs.append)
    assert result["success"] is True
    assert builder.registry.get_skill("adder")["code"] == new_code


def test_interactive_session_retries_after_invalid_selection(temp_registry):
    builder = _builder_with_skill(temp_registry)
    fake_input = _scripted_input(["nonexistent", "adder", "q"])
    outputs = []
    result = builder.run_interactive_session(input_func=fake_input, output_func=outputs.append)
    assert result["success"] is True
    assert result["skill_name"] == "adder"
    assert any("Error:" in line for line in outputs)


def test_interactive_session_cancels_on_blank_selection(temp_registry):
    builder = _builder_with_skill(temp_registry)
    fake_input = _scripted_input([""])
    result = builder.run_interactive_session(input_func=fake_input, output_func=lambda *_: None)
    assert result == {"success": False, "skill_name": None, "cancelled": True, "error": None}


def test_interactive_session_cancels_on_eof(temp_registry):
    builder = _builder_with_skill(temp_registry)
    fake_input = _scripted_input([])  # immediately exhausted -> EOFError
    result = builder.run_interactive_session(input_func=fake_input, output_func=lambda *_: None)
    assert result["success"] is False
    assert result["cancelled"] is True


def test_interactive_session_removes_parameter_via_interactive(temp_registry):
    builder = _builder_with_skill(temp_registry)
    builder.add_parameter("adder", "x", "int", "first number")
    fake_input = _scripted_input(["adder", "p", "r", "x", "q"])
    outputs = []
    result = builder.run_interactive_session(input_func=fake_input, output_func=outputs.append)
    assert result["success"] is True
    assert builder.registry.get_skill("adder")["parameters"] == {}


def test_interactive_session_cancels_mid_description_edit_on_eof(temp_registry):
    builder = _builder_with_skill(temp_registry)
    # "d" is read, but the follow-up "new description" prompt hits EOF.
    fake_input = _scripted_input(["adder", "d"])
    result = builder.run_interactive_session(input_func=fake_input, output_func=lambda *_: None)
    assert result == {"success": True, "skill_name": "adder", "cancelled": True, "error": None}
    # Nothing was changed.
    assert builder.registry.get_skill("adder")["description"] == "Adds numbers"


def test_interactive_session_cancels_mid_code_edit_on_eof(temp_registry):
    builder = _builder_with_skill(temp_registry)
    old_code = builder.get_code("adder")["code"]
    fake_input = _scripted_input(["adder", "c"])
    result = builder.run_interactive_session(input_func=fake_input, output_func=lambda *_: None)
    assert result == {"success": True, "skill_name": "adder", "cancelled": True, "error": None}
    assert builder.get_code("adder")["code"] == old_code


def test_interactive_session_unrecognised_option_reprompts(temp_registry):
    builder = _builder_with_skill(temp_registry)
    fake_input = _scripted_input(["adder", "zzz", "q"])
    outputs = []
    result = builder.run_interactive_session(input_func=fake_input, output_func=outputs.append)
    assert result["success"] is True
    assert any("Unrecognised option" in line for line in outputs)


# ---------------------------------------------------------------------------
# Task 14.2 - Integration with the registry
# ---------------------------------------------------------------------------


def test_builder_operates_on_skill_registered_directly_via_registry(temp_registry_with_skills):
    """The builder must work on skills it did not itself create."""
    builder = SkillBuilder(temp_registry_with_skills)
    result = builder.select_skill("echo_skill")
    assert result["success"] is True
    edit = builder.edit_description("echo_skill", "Echoes back whatever it is given")
    assert edit["success"] is True


def test_builder_update_reflected_in_registry_get_skill(temp_registry):
    builder = _builder_with_skill(temp_registry)
    builder.edit_description("adder", "Updated via builder")
    # Read through the registry directly (not through the builder) to prove
    # the change is really persisted centrally, not cached in the builder.
    fresh = temp_registry.get_skill("adder")
    assert fresh["description"] == "Updated via builder"


def test_builder_new_skill_creation_is_immediately_listable(temp_registry):
    builder = SkillBuilder(temp_registry)
    code = SkillBuilder.offline_template("brand_new", "Brand new skill")
    created = builder.register("brand_new", code, "function", "Brand new skill")
    assert created["success"] is True
    names = [s["name"] for s in builder.list_skills()]
    assert "brand_new" in names


def test_registry_error_from_update_skill_is_converted_to_payload(temp_registry, monkeypatch):
    """A RegistryError raised deep inside update_skill must never propagate."""
    builder = _builder_with_skill(temp_registry)

    def _boom(*args, **kwargs):
        raise RegistryError("simulated failure")

    monkeypatch.setattr(temp_registry, "update_skill", _boom)
    result = builder.edit_description("adder", "New description")
    assert result["success"] is False
    assert "simulated failure" in result["error"]


# ---------------------------------------------------------------------------
# Task 14.3 - Complete workflow (create -> select -> edit -> version history)
# ---------------------------------------------------------------------------


def test_complete_builder_workflow_create_edit_and_version_history(temp_registry):
    builder = SkillBuilder(temp_registry)

    # Create.
    code = SkillBuilder.offline_template("workflow_skill", "Initial description")
    created = builder.register("workflow_skill", code, "function", "Initial description")
    assert created["success"] is True
    assert created["skill"]["current_version"] == 1

    # Select.
    selected = builder.select_skill("workflow_skill")
    assert selected["success"] is True

    # Edit description, parameters, and code in sequence.
    builder.edit_description("workflow_skill", "Updated description")
    builder.add_parameter("workflow_skill", "n", "int", "a number")
    new_code = code.replace('"result": "OK"', '"result": "DONE"')
    edited = builder.edit_code("workflow_skill", new_code)
    assert edited["success"] is True

    # Version control integration: each mutation bumped current_version,
    # and the full history is retrievable from the registry.
    final = temp_registry.get_skill("workflow_skill")
    assert final["current_version"] == 4  # register + 3 edits
    assert final["description"] == "Updated description"
    assert final["parameters"]["n"] == {"type": "int", "description": "a number"}
    assert final["code"] == new_code

    history = temp_registry.get_version_history("workflow_skill")
    assert len(history) == 4


def test_complete_workflow_via_interactive_session(temp_registry):
    """End-to-end: create through the builder, then drive the full
    selection + description + parameter + code edit loop interactively."""
    builder = SkillBuilder(temp_registry)
    code = SkillBuilder.offline_template("e2e_skill", "Starts here")
    assert builder.register("e2e_skill", code, "function", "Starts here")["success"] is True

    new_code = "def run(input_value=''):\n    return {'done': True}\n"
    fake_input = _scripted_input(
        [
            "e2e_skill",       # select
            "d", "Ends here",  # edit description
            "p", "a", "flag", "bool", "a flag",  # add parameter
            "c", new_code,     # edit code
            "q",               # quit
        ]
    )
    outputs = []
    result = builder.run_interactive_session(input_func=fake_input, output_func=outputs.append)
    assert result == {"success": True, "skill_name": "e2e_skill", "cancelled": False, "error": None}

    final = temp_registry.get_skill("e2e_skill")
    assert final["description"] == "Ends here"
    assert final["parameters"]["flag"] == {"type": "bool", "description": "a flag"}
    assert final["code"] == new_code
    assert final["current_version"] == 4  # register + description + parameter + code


# ===========================================================================
# Task 13 (guide §1.8.14): advanced features — version management, code
# export/import, skill templates, and robust error handling.
# ===========================================================================

import json as _json

from skills.unified_stage import UnifiedSkillStage


@pytest.fixture
def builder(temp_registry):
    return SkillBuilder(temp_registry)


# --- 13.1 version management ---------------------------------------------

@pytest.fixture
def versioned(builder):
    builder.create_from_template("vers", skill_type="function", description="first")
    builder.edit_description("vers", "second description")
    builder.edit_code(
        "vers", 'def run(input_value: str = "") -> str:\n    return input_value.upper()\n'
    )
    return builder


def test_version_history_lists_newest_first(versioned):
    result = versioned.version_history("vers")
    assert result["success"] is True
    assert [v["version"] for v in result["versions"]] == [3, 2, 1]
    assert result["current_version"] == 3


def test_version_history_of_a_missing_skill(builder):
    result = builder.version_history("ghost")
    assert result["success"] is False
    assert "not found" in result["error"]


def test_format_version_history_marks_the_current_version(versioned):
    rendered = versioned.format_version_history("vers")
    assert "v3" in rendered and "<- current" in rendered
    assert rendered.index("v3") < rendered.index("v1")     # newest first


def test_format_version_history_of_a_missing_skill(builder):
    assert "Cannot show history" in builder.format_version_history("ghost")


def test_compare_versions_surfaces_metadata_and_code(versioned):
    result = versioned.compare_versions("vers", 1, 3)
    assert result["success"] is True
    assert result["changed"] is True
    assert result["metadata_changes"]["description"]["v2"] == "second description"
    assert "upper()" in result["diff"]


def test_compare_identical_versions_reports_no_change(builder):
    builder.create_from_template("same", skill_type="function")
    result = builder.compare_versions("same", 1, 1)
    assert result["changed"] is False


def test_format_version_diff_renders_each_kind_of_change(versioned):
    rendered = versioned.format_version_diff("vers", 1, 3)
    assert "description:" in rendered
    assert "code:" in rendered


def test_format_version_diff_on_identical_versions(builder):
    builder.create_from_template("same2", skill_type="function")
    assert "identical" in builder.format_version_diff("same2", 1, 1)


def test_rollback_preserves_history_as_a_new_version(versioned):
    result = versioned.rollback("vers", 1)
    assert result["success"] is True
    assert result["restored_from"] == 1
    assert result["new_version"] == 4                     # history not rewritten
    assert versioned.get_code("vers")["code"] == versioned.registry.get_version(
        "vers", 1
    )["code"]


def test_rollback_to_a_nonexistent_version(versioned):
    result = versioned.rollback("vers", 99)
    assert result["success"] is False
    assert "99" in result["error"]


def test_rollback_of_a_missing_skill(builder):
    assert builder.rollback("ghost", 1)["success"] is False


# --- 13.2 export / import -------------------------------------------------

def test_export_returns_both_payload_and_json(builder):
    builder.create_from_template("exp", skill_type="function", description="d")
    result = builder.export_skill("exp")
    assert result["success"] is True
    assert result["payload"]["name"] == "exp"
    assert _json.loads(result["json"])["name"] == "exp"   # json is valid + formatted


def test_export_of_a_missing_skill(builder):
    assert builder.export_skill("ghost")["success"] is False


def test_export_then_import_round_trips(builder):
    builder.create_from_template("orig", skill_type="function", description="d")
    payload = dict(builder.export_skill("orig")["payload"])
    payload["name"] = "copy"
    result = builder.import_skill(payload)
    assert result["success"] is True
    assert builder.registry.get_skill("copy")["code"] == (
        builder.registry.get_skill("orig")["code"]
    )


def test_import_accepts_json_text(builder):
    builder.create_from_template("orig2", skill_type="function")
    payload = dict(builder.export_skill("orig2")["payload"])
    payload["name"] = "from_text"
    assert builder.import_skill(_json.dumps(payload))["success"] is True


@pytest.mark.parametrize(
    "payload, expected",
    [
        ("{not json", "not valid JSON"),
        ([1, 2, 3], "must be a JSON object"),
        ({"code": "def run(): pass"}, "missing 'name'"),
        ({"name": "x"}, "missing 'code'"),
        ({"name": "x", "code": "def ("}, "SyntaxError"),
    ],
)
def test_import_validates_before_writing(builder, payload, expected):
    result = builder.import_skill(payload)
    assert result["success"] is False
    assert expected in result["error"]


def test_a_rejected_import_writes_nothing(builder):
    builder.import_skill({"name": "rejected", "code": "def ("})
    assert builder.registry.get_skill("rejected") is None


# --- 13.3 templates -------------------------------------------------------

def test_available_templates_covers_every_canonical_type(builder):
    assert builder.available_templates() == ["agent", "function", "workflow"]


@pytest.mark.parametrize("skill_type", ["function", "agent", "workflow"])
def test_every_template_registers_and_executes(temp_registry, skill_type):
    """A template is only useful if the skill it produces actually runs."""
    builder = SkillBuilder(temp_registry)
    name = f"tpl_{skill_type}"
    assert builder.create_from_template(
        name, skill_type=skill_type, description="a templated skill"
    )["success"] is True
    result = UnifiedSkillStage(temp_registry).execute_skill(name, {})
    assert result["success"] is True, result["error"]


def test_unknown_template_is_rejected_with_the_valid_choices(builder):
    result = builder.template_for("nonsense", "x")
    assert result["success"] is False
    assert "function" in result["error"] and "workflow" in result["error"]


def test_create_from_an_unknown_template_registers_nothing(builder):
    assert builder.create_from_template("x", skill_type="nonsense")["success"] is False
    assert builder.registry.get_skill("x") is None


def test_template_code_is_syntactically_valid(builder):
    for skill_type in builder.available_templates():
        code = builder.template_for(skill_type, "probe", "desc")["code"]
        compile(code, "<template>", "exec")


# --- 13.4 error handling --------------------------------------------------

def test_database_errors_become_payloads_not_tracebacks(builder):
    """Task 13.4 requires handling database errors. Those arrive as
    sqlite3.Error, which is not a RegistryError - catching only the latter
    would let a locked or corrupt database escape as a traceback."""
    import sqlite3

    class _BrokenRegistry:
        def get_skill(self, name):
            return {"name": name, "type": "function", "code": "", "current_version": 1}

        def get_version_history(self, name):
            raise sqlite3.OperationalError("database is locked")

    broken = SkillBuilder.__new__(SkillBuilder)
    broken.registry = _BrokenRegistry()
    result = broken.version_history("anything")
    assert result["success"] is False
    assert "database is locked" in result["error"]
