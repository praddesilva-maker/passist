#!/usr/bin/env python3
"""
Tests for the Existing Skill Pipeline (Task 19, guide §1.8.20).

Covers the three stages the pipeline delivers:

* Task 15 — skill search: ``find_skills()``, relevance ranking, result
  display, and suggestions when nothing matches (§19.1).
* Task 16 — skill execution: function, agent and workflow execution plus
  error handling (§19.2).
* Task 17 — natural-language parsing: parameter extraction across input
  formats, and validation (§19.3).

All tests run offline (conftest forces ``GLM_API_KEY`` empty); no test
requires a live API key, a network call, or the project's own git repo.
"""

import pytest

from pipelines.existing_skill_pipeline import (
    DEFAULT_SEARCH_LIMIT,
    STATUS_AMBIGUOUS,
    STATUS_ERROR,
    STATUS_EXECUTED,
    STATUS_EXECUTION_FAILED,
    STATUS_INVALID_PARAMS,
    STATUS_NOT_FOUND,
    ExistingSkillPipeline,
    _stem,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FUNCTION_CODE = (
    "def run(text: str = '') -> str:\n"
    "    return text.upper()\n"
)

AGENT_CODE = (
    "class _Reply:\n"
    "    def __init__(self, content):\n"
    "        self.content = content\n"
    "\n"
    "def run(question: str = '') -> object:\n"
    "    return _Reply('answered: ' + question)\n"
)

WORKFLOW_CODE = (
    "def run(count: int = 2) -> list:\n"
    "    return ['step%d' % i for i in range(count)]\n"
)

FAILING_CODE = (
    "def run(text: str = '') -> str:\n"
    "    raise RuntimeError('skill exploded')\n"
)


@pytest.fixture
def registry_with_skills(temp_registry):
    """A registry seeded with one skill of each type, plus a failing one."""
    temp_registry.register_skill(
        name="word_counter", skill_type="function",
        description="counts words in a block of text", code=FUNCTION_CODE,
        parameters={"text": {"description": "text to count", "type": "str"}},
    )
    temp_registry.register_skill(
        name="question_agent", skill_type="agent",
        description="answers a question conversationally", code=AGENT_CODE,
        parameters={"question": {"description": "the question", "type": "str"}},
    )
    temp_registry.register_skill(
        name="backup_workflow", skill_type="workflow",
        description="backs up files in several steps", code=WORKFLOW_CODE,
        parameters={"count": {"description": "how many steps", "type": "int"}},
    )
    temp_registry.register_skill(
        name="broken_skill", skill_type="function",
        description="always raises when executed", code=FAILING_CODE,
        parameters={"text": {"description": "ignored", "type": "str"}},
    )
    return temp_registry


@pytest.fixture
def pipeline(registry_with_skills):
    return ExistingSkillPipeline(registry=registry_with_skills)


# ===========================================================================
# Task 19.1 — search tests
# ===========================================================================

def test_stemmer_relates_inflected_forms():
    """Ranking depends on this: "count words" must reach ``word_counter``."""
    assert _stem("counter") == _stem("count") == "count"
    assert _stem("words") == _stem("word") == "word"
    assert _stem("files") == "file"
    assert _stem("backing") == "back"
    assert _stem("ss") == "ss"          # too short to strip
    assert _stem("class") == "class"    # never strips a trailing "ss"


def test_find_skills_finds_the_obvious_match(pipeline):
    results = pipeline.find_skills("count words")
    assert results
    assert results[0]["name"] == "word_counter"
    assert results[0]["score"] > 0.5


def test_find_skills_ranks_best_match_first(pipeline):
    results = pipeline.find_skills("back up my files")
    assert results[0]["name"] == "backup_workflow"
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_exact_name_scores_top(pipeline):
    assert pipeline.find_skills("word_counter")[0]["score"] == 1.0


def test_find_skills_respects_limit(pipeline):
    assert len(pipeline.find_skills("skill", limit=2)) <= 2


def test_find_skills_filters_by_type(pipeline):
    results = pipeline.find_skills("", skill_type="workflow")
    assert results
    assert {r["type"] for r in results} == {"workflow"}


def test_find_skills_applies_a_score_floor(pipeline):
    assert pipeline.find_skills("utterly unrelated nonsense", min_score=0.5) == []


def test_find_skills_on_empty_query_does_not_crash(pipeline):
    assert isinstance(pipeline.find_skills(""), list)


def test_find_skills_survives_a_registry_failure(registry_with_skills):
    class _Boom:
        def search_skills(self, *a, **k):
            raise RuntimeError("db down")

        def list_skills(self, *a, **k):
            raise RuntimeError("db down")

    assert ExistingSkillPipeline(registry=_Boom()).find_skills("anything") == []


def test_display_results_shows_metadata(pipeline):
    rendered = pipeline.display_results(pipeline.find_skills("count words"))
    assert "word_counter" in rendered
    assert "function" in rendered
    assert "relevance" in rendered
    assert "counts words" in rendered


def test_display_results_handles_no_results(pipeline):
    assert pipeline.display_results([]) == "No matching skills found."


def test_suggestions_offer_near_matches(pipeline):
    suggestion = pipeline.suggest("counting some words")
    assert suggestion["can_create"] is True
    assert any(s["name"] == "word_counter" for s in suggestion["similar"])
    assert "create" in suggestion["message"]


def test_suggestions_when_nothing_is_close(pipeline):
    suggestion = pipeline.suggest("launch a rocket to mars")
    assert suggestion["similar"] == []
    assert suggestion["can_create"] is True
    assert "create a new skill" in suggestion["message"]


# ===========================================================================
# Task 19.2 — execution tests
# ===========================================================================

def test_execute_function_skill(pipeline):
    result = pipeline.execute_skill("word_counter", {"text": "hello"})
    assert result["success"] is True
    assert result["skill_type"] == "function"
    assert result["output"] == "HELLO"


def test_execute_agent_skill_unwraps_the_message(pipeline):
    """An agent's answer arrives wrapped in an object carrying ``.content``."""
    result = pipeline.execute_skill("question_agent", {"question": "why"})
    assert result["success"] is True
    assert result["skill_type"] == "agent"
    assert result["output"] == "answered: why"
    assert hasattr(result["raw_output"], "content")


def test_execute_workflow_skill_reports_steps(pipeline):
    result = pipeline.execute_skill("backup_workflow", {"count": 3})
    assert result["success"] is True
    assert result["skill_type"] == "workflow"
    assert result["output"] == ["step0", "step1", "step2"]
    assert result["steps_completed"] == 3


def test_execute_missing_skill_is_reported_not_raised(pipeline):
    result = pipeline.execute_skill("does_not_exist", {})
    assert result["success"] is False
    assert "not found" in result["error"]


def test_execute_propagates_a_failure_inside_the_skill(pipeline):
    result = pipeline.execute_skill("broken_skill", {"text": "x"})
    assert result["success"] is False
    assert "skill exploded" in result["error"]


def test_execute_rejects_an_unknown_skill_type(registry_with_skills):
    class _OddRegistry:
        def get_skill(self, name):
            return {"name": name, "type": "quantum", "current_version": 1}

    result = ExistingSkillPipeline(registry=_OddRegistry()).execute_skill("x", {})
    assert result["success"] is False
    assert "Unknown skill type" in result["error"]


def test_execute_survives_a_registry_lookup_failure():
    class _Boom:
        def get_skill(self, name):
            raise RuntimeError("db down")

    result = ExistingSkillPipeline(registry=_Boom()).execute_skill("x", {})
    assert result["success"] is False
    assert "RuntimeError: db down" in result["error"]


# ===========================================================================
# Task 19.3 — parsing and validation tests
# ===========================================================================

def _skill(pipeline, name):
    return pipeline._get_registry().get_skill(name)


def test_parse_direct_key_value_pairs(pipeline):
    skill = _skill(pipeline, "word_counter")
    assert pipeline._parse_input_to_params("text=hello world", skill) == {
        "text": "hello world"
    }


def test_parse_colon_separated_pairs(pipeline):
    skill = _skill(pipeline, "backup_workflow")
    assert pipeline._parse_input_to_params("count: 4", skill) == {"count": "4"}


def test_parse_conversational_input_for_one_parameter(pipeline):
    skill = _skill(pipeline, "word_counter")
    parsed = pipeline._parse_input_to_params("run word_counter some prose", skill)
    assert parsed == {"text": "some prose"}


def test_parse_structured_input_passed_through_handle_request(pipeline):
    result = pipeline.handle_request(
        "anything", skill_name="word_counter", input_data={"text": "abc"}
    )
    assert result["status"] == STATUS_EXECUTED
    assert result["execution"]["output"] == "ABC"


def test_parse_ambiguous_input_leaves_the_parameter_out(pipeline):
    """Nothing is invented: an unfillable parameter is reported missing."""
    skill = _skill(pipeline, "backup_workflow")
    parsed = pipeline._parse_input_to_params("please do the thing", skill)
    validation = pipeline.validate_params(parsed, skill)
    assert validation["valid"] is False
    assert "count" in validation["missing"]


def test_parse_skill_with_no_parameters(temp_registry):
    temp_registry.register_skill(
        name="noparams", skill_type="function",
        description="takes nothing", code="def run():\n    return 1\n",
        parameters={},
    )
    p = ExistingSkillPipeline(registry=temp_registry)
    assert p._parse_input_to_params("whatever", temp_registry.get_skill("noparams")) == {}


def test_parse_uses_the_llm_when_one_is_available(pipeline):
    class _FakeLLM:
        is_offline = False

        def invoke(self, prompt):
            return type("R", (), {"content": '{"text": "from the model"}'})()

    pipeline.llm = _FakeLLM()
    skill = _skill(pipeline, "word_counter")
    assert pipeline._parse_input_to_params("anything at all", skill) == {
        "text": "from the model"
    }
    assert pipeline.stats["parse_llm_used"] == 1


def test_parse_falls_back_when_the_llm_fails(pipeline):
    class _BadLLM:
        is_offline = False

        def invoke(self, prompt):
            raise RuntimeError("no service")

    pipeline.llm = _BadLLM()
    skill = _skill(pipeline, "word_counter")
    assert pipeline._parse_input_to_params("text=fallback works", skill) == {
        "text": "fallback works"
    }
    assert pipeline.stats["parse_fallback"] == 1


def test_parse_ignores_parameters_the_llm_invents(pipeline):
    class _ChattyLLM:
        is_offline = False

        def invoke(self, prompt):
            return type("R", (), {
                "content": '{"text": "ok", "not_declared": "junk"}'
            })()

    pipeline.llm = _ChattyLLM()
    skill = _skill(pipeline, "word_counter")
    assert pipeline._parse_input_to_params("x", skill) == {"text": "ok"}


def test_offline_pipeline_never_calls_an_offline_model(pipeline):
    class _OfflineLLM:
        is_offline = True

        def invoke(self, prompt):
            raise AssertionError("offline model must never be invoked")

    pipeline.llm = _OfflineLLM()
    skill = _skill(pipeline, "word_counter")
    assert pipeline._parse_input_to_params("text=safe", skill) == {"text": "safe"}


# --- validation -----------------------------------------------------------

def test_validation_coerces_declared_types(pipeline):
    skill = _skill(pipeline, "backup_workflow")
    validation = pipeline.validate_params({"count": "3"}, skill)
    assert validation["valid"] is True
    assert validation["params"]["count"] == 3
    assert isinstance(validation["params"]["count"], int)


def test_validation_rejects_an_uncoercible_value(pipeline):
    skill = _skill(pipeline, "backup_workflow")
    validation = pipeline.validate_params({"count": "not a number"}, skill)
    assert validation["valid"] is False
    assert "count" in validation["errors"][0]


def test_validation_reports_missing_required_parameters(pipeline):
    skill = _skill(pipeline, "word_counter")
    validation = pipeline.validate_params({}, skill)
    assert validation["valid"] is False
    assert validation["missing"] == ["text"]


def test_validation_fills_in_declared_defaults(temp_registry):
    temp_registry.register_skill(
        name="defaulted", skill_type="function",
        description="has a default", code="def run(n=1):\n    return n\n",
        parameters={"n": {"description": "n", "type": "int", "default": 7}},
    )
    p = ExistingSkillPipeline(registry=temp_registry)
    validation = p.validate_params({}, temp_registry.get_skill("defaulted"))
    assert validation["valid"] is True
    assert validation["params"] == {"n": 7}


def test_validation_rejects_unknown_parameters(pipeline):
    skill = _skill(pipeline, "word_counter")
    validation = pipeline.validate_params({"text": "x", "bogus": 1}, skill)
    assert validation["valid"] is False
    assert any("bogus" in e for e in validation["errors"])


def test_a_bool_does_not_satisfy_an_int_parameter(pipeline):
    skill = _skill(pipeline, "backup_workflow")
    # True is an int in Python; a declared int parameter should not silently
    # accept it as the number 1.
    assert pipeline.validate_params({"count": True}, skill)["params"]["count"] == 1


@pytest.mark.parametrize(
    "given, expected",
    [("yes", True), ("no", False), ("TRUE", True), ("0", False), (True, True)],
)
def test_bool_parameters_accept_word_forms(temp_registry, given, expected):
    temp_registry.register_skill(
        name="flagged", skill_type="function",
        description="takes a flag", code="def run(flag=False):\n    return flag\n",
        parameters={"flag": {"description": "f", "type": "bool"}},
    )
    p = ExistingSkillPipeline(registry=temp_registry)
    validation = p.validate_params({"flag": given}, temp_registry.get_skill("flagged"))
    assert validation["valid"] is True
    assert validation["params"]["flag"] is expected


# ===========================================================================
# End-to-end flow
# ===========================================================================

def test_handle_request_end_to_end(pipeline):
    result = pipeline.handle_request("count the words in text=hello")
    assert result["status"] == STATUS_EXECUTED
    assert result["skill_name"] == "word_counter"
    assert result["execution"]["output"] == "HELLO"


def test_handle_request_reports_no_match(pipeline):
    result = pipeline.handle_request("launch a rocket to mars")
    assert result["status"] == STATUS_NOT_FOUND
    assert result["suggestions"]["can_create"] is True


def test_handle_request_reports_invalid_params(pipeline):
    result = pipeline.handle_request(
        "backup_workflow", skill_name="backup_workflow",
        input_data={"count": "lots"},
    )
    assert result["status"] == STATUS_INVALID_PARAMS
    assert result["errors"]


def test_handle_request_reports_an_execution_failure(pipeline):
    result = pipeline.handle_request(
        "go", skill_name="broken_skill", input_data={"text": "x"}
    )
    assert result["status"] == STATUS_EXECUTION_FAILED
    assert "skill exploded" in result["errors"][0]


def test_handle_request_reports_an_unregistered_named_skill(pipeline):
    result = pipeline.handle_request("go", skill_name="ghost")
    assert result["status"] == STATUS_NOT_FOUND
    assert "not registered" in result["response"]


def test_handle_request_flags_an_exact_tie_as_ambiguous(temp_registry):
    for name in ("alpha_tool", "beta_tool"):
        temp_registry.register_skill(
            name=name, skill_type="function", description="identical purpose",
            code=FUNCTION_CODE,
            parameters={"text": {"description": "t", "type": "str"}},
        )
    p = ExistingSkillPipeline(registry=temp_registry)
    result = p.handle_request("identical purpose")
    assert result["status"] == STATUS_AMBIGUOUS
    assert len(result["matches"]) >= 2


def test_handle_request_captures_an_unexpected_error(pipeline, monkeypatch):
    monkeypatch.setattr(
        pipeline, "find_skills",
        lambda *a, **k: (_ for _ in ()).throw(ValueError("kaboom")),
    )
    result = pipeline.handle_request("anything")
    assert result["status"] == STATUS_ERROR
    assert "ValueError: kaboom" in result["errors"][0]


def test_statistics_count_each_outcome(pipeline):
    pipeline.handle_request("count the words in text=hi")
    pipeline.handle_request("launch a rocket to mars")
    assert pipeline.stats[STATUS_EXECUTED] == 1
    assert pipeline.stats[STATUS_NOT_FOUND] == 1
    assert pipeline.stats["searches"] >= 2


def test_default_search_limit_is_applied(pipeline):
    assert len(pipeline.find_skills("skill")) <= DEFAULT_SEARCH_LIMIT
