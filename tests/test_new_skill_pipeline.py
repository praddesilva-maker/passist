#!/usr/bin/env python3
"""
Tests for the New Skill Pipeline.

Task 7 (guide §1.8.8): intent analysis — the three intents
(``create_skill`` / ``use_skill`` / ``general``) across many phrasings, the
LLM path and its fallbacks, edge cases, and the stable ``handle_request``
envelope.

Task 8 (guide §1.8.9): ``analyze_request()`` — LLM-first analysis of a
skill-creation request into a normalized, registry-compatible structure
(``function`` / ``agent`` / ``workflow`` types) with a deterministic
fallback when no LLM answer is usable.

All tests run offline (conftest forces ``GLM_API_KEY`` empty), mirroring the
agent test conventions.
"""

import re

import pytest

from pipelines import NewSkillPipeline
from pipelines.new_skill_pipeline import (
    ALL_INTENTS,
    INTENT_CREATE_SKILL,
    INTENT_GENERAL,
    INTENT_USE_SKILL,
)

# ---------------------------------------------------------------------------
# Phrasing corpora (Task 7.1-7.3: "test with various phrasings")
# ---------------------------------------------------------------------------

CREATE_PHRASES = [
    "develop a skill named adder",
    "create a skill that adds numbers",
    "I want a new skill called translator",
    "build me a skill to translate text",
    "write a skill for scraping web pages",
    "add a skill that summarizes text",
    "make a workflow skill for backups",
    "develop the skill for my todo list",
    "I need a skill that checks the weather",
    "create function skill adder",
    "please develop a new skill",
    "develop a simple weather skill",
    "Develop A Skill Named Foo",
    "RUN THIS: create a skill",
    "can you make me a skill that sorts lists",
]

USE_PHRASES = [
    "use skill echo_skill",
    "run the echo skill",
    "execute skill adder",
    "call skill translator",
    "use my skill named helper",
    "apply skill formatter",
    "do skill echo_skill",
    "run the fast echo skill",
    "RUN SKILL ADDER",
]

GENERAL_PHRASES = [
    "hello there",
    "what can you do?",
    "list my skills",
    "what skills do I have?",
    "how do I use skills?",          # plural — a question, not a command
    "tell me about skills",
    "the weather is nice today",
    "delete skill adder",            # no delete intent in the vocabulary
    "what is a skill that runs fast?",
    "",
    "   ",
]

EDGE_CASES = [
    # create wins over use inside one request
    ("develop a skill that uses the echo skill", INTENT_CREATE_SKILL),
    # "created" is not a creation verb; this is a use request
    ("use the skill you created earlier", INTENT_USE_SKILL),
    # ambiguous statements without a creation verb stay general
    ("a skill that adds numbers", INTENT_GENERAL),
    ("this skill that I wrote is broken", INTENT_GENERAL),
    # defensive: None input must not crash
    (None, INTENT_GENERAL),
]


# ---------------------------------------------------------------------------
# Task 7.1 / 7.2 / 7.3 — intent detection per intent
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("phrase", CREATE_PHRASES)
def test_create_skill_phrases(phrase):
    assert NewSkillPipeline().detect_intent(phrase) == INTENT_CREATE_SKILL


@pytest.mark.parametrize("phrase", USE_PHRASES)
def test_use_skill_phrases(phrase):
    assert NewSkillPipeline().detect_intent(phrase) == INTENT_USE_SKILL


@pytest.mark.parametrize("phrase", GENERAL_PHRASES)
def test_general_phrases(phrase):
    assert NewSkillPipeline().detect_intent(phrase) == INTENT_GENERAL


# ---------------------------------------------------------------------------
# Task 7.4 — edge cases, no false positives/negatives
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("phrase, expected", EDGE_CASES)
def test_edge_cases(phrase, expected):
    assert NewSkillPipeline().detect_intent(phrase) == expected


def test_no_false_positive_between_intents():
    """Create/use phrases must not classify as general; general stays general."""
    pipeline = NewSkillPipeline()
    for phrase in CREATE_PHRASES:
        assert pipeline.detect_intent(phrase) != INTENT_GENERAL
    for phrase in USE_PHRASES:
        assert pipeline.detect_intent(phrase) == INTENT_USE_SKILL
    for phrase in GENERAL_PHRASES:
        assert pipeline.detect_intent(phrase) == INTENT_GENERAL


def test_intent_vocabulary_is_stable():
    assert ALL_INTENTS == (INTENT_CREATE_SKILL, INTENT_USE_SKILL, INTENT_GENERAL)
    assert set(ALL_INTENTS) == {"create_skill", "use_skill", "general"}


def test_package_level_imports():
    import pipelines

    assert pipelines.NewSkillPipeline is NewSkillPipeline
    assert pipelines.INTENT_CREATE_SKILL == "create_skill"
    assert pipelines.INTENT_USE_SKILL == "use_skill"
    assert pipelines.INTENT_GENERAL == "general"


# ---------------------------------------------------------------------------
# LLM path and fallbacks
# ---------------------------------------------------------------------------


class _FakeLLM:
    """Duck-typed stand-in for a LangChain chat model (online)."""

    is_offline = False

    def __init__(self, reply: str = "general", raises: bool = False) -> None:
        self.reply = reply
        self.raises = raises
        self.calls = 0

    def invoke(self, prompt: str):
        self.calls += 1
        if self.raises:
            raise RuntimeError("boom")
        return self.reply


class _CountingOfflineModel:
    """Offline model that records whether it was (wrongly) invoked."""

    is_offline = True

    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("an offline model must never be invoked")


def test_llm_classification_is_used_when_available():
    llm = _FakeLLM(reply="create_skill")
    pipeline = NewSkillPipeline(llm=llm)
    # The heuristic would call this "general", so the LLM answer must win.
    assert pipeline.detect_intent("hello there") == INTENT_CREATE_SKILL
    assert llm.calls == 1


@pytest.mark.parametrize("reply, expected", [
    ("create_skill", INTENT_CREATE_SKILL),
    ("use_skill", INTENT_USE_SKILL),
    ("general", INTENT_GENERAL),
    ("  `use_skill`\n", INTENT_USE_SKILL),
    ("I think this is general", INTENT_GENERAL),
])
def test_llm_various_valid_answers(reply, expected):
    pipeline = NewSkillPipeline(llm=_FakeLLM(reply=reply))
    assert pipeline.detect_intent("hello there") == expected


def test_llm_failure_falls_back_to_heuristics():
    llm = _FakeLLM(reply="", raises=True)
    pipeline = NewSkillPipeline(llm=llm)
    assert pipeline.detect_intent("use skill echo") == INTENT_USE_SKILL
    assert pipeline.detect_intent("develop a skill named x") == INTENT_CREATE_SKILL
    assert pipeline.detect_intent("hello") == INTENT_GENERAL
    assert llm.calls == 3


def test_llm_unparseable_answer_falls_back():
    pipeline = NewSkillPipeline(llm=_FakeLLM(reply="I am not sure."))
    assert pipeline.detect_intent("run skill adder") == INTENT_USE_SKILL


def test_offline_model_is_never_invoked():
    model = _CountingOfflineModel()
    pipeline = NewSkillPipeline(llm=model)
    assert pipeline.detect_intent("use skill echo") == INTENT_USE_SKILL
    assert pipeline.detect_intent("hello there") == INTENT_GENERAL
    assert model.calls == 0


class _OfflineModel:  # minimal duck-typed stand-in for an offline model
    is_offline = True

    def invoke(self, *args, **kwargs):  # pragma: no cover - never called
        raise AssertionError("an offline model must never be invoked")


def test_offline_flag_reported_in_envelope():
    assert NewSkillPipeline().handle_request("hello")["offline"] is True
    assert NewSkillPipeline(llm=_OfflineModel()).handle_request(
        "hello"
    )["offline"] is True
    assert NewSkillPipeline(llm=_FakeLLM()).handle_request(
        "hello"
    )["offline"] is False


# ---------------------------------------------------------------------------
# handle_request envelope (routing contract for Task 22)
# ---------------------------------------------------------------------------


def test_handle_request_create_envelope():
    out = NewSkillPipeline().handle_request("develop a skill named adder")
    assert out["intent"] == INTENT_CREATE_SKILL
    assert out["success"] is True
    assert out["offline"] is True
    assert out["error"] is None
    assert isinstance(out["response"], str) and out["response"]


def test_handle_request_use_envelope():
    out = NewSkillPipeline().handle_request("use skill echo")
    assert out["intent"] == INTENT_USE_SKILL
    assert out["success"] is True


def test_handle_request_general_envelope_mentions_offline():
    out = NewSkillPipeline().handle_request("hello there")
    assert out["intent"] == INTENT_GENERAL
    assert "offline" in out["response"].lower()


def test_handle_request_empty_and_data_do_not_crash():
    out = NewSkillPipeline().handle_request("")
    assert out["intent"] == INTENT_GENERAL
    assert out["success"] is True
    out2 = NewSkillPipeline().handle_request(
        "use skill echo", request_data={"name": "echo"}
    )
    assert out2["intent"] == INTENT_USE_SKILL
    assert out2["success"] is True


def test_stats_counted_per_intent():
    pipeline = NewSkillPipeline()
    pipeline.detect_intent("develop a skill named adder")
    pipeline.detect_intent("use skill echo")
    pipeline.detect_intent("hello")
    assert pipeline.stats["requests"] == 3
    assert pipeline.stats[INTENT_CREATE_SKILL] == 1
    assert pipeline.stats[INTENT_USE_SKILL] == 1
    assert pipeline.stats[INTENT_GENERAL] == 1


# ---------------------------------------------------------------------------
# Task 8 — analyze_request(): LLM-first structure generation with a
# deterministic fallback (guide §1.8.9, lines 2296-2549)
# ---------------------------------------------------------------------------

CANONICAL_TYPES = ("function", "agent", "workflow")
EXPECTED_KEYS = {
    "name", "description", "type", "parameters", "requires", "returns",
}


def _assert_well_formed(structure: dict) -> None:
    """Shared DoD check: a structure that the registry can consume."""
    assert set(structure) == EXPECTED_KEYS
    name = structure["name"]
    assert isinstance(name, str) and re.match(r"^[A-Za-z][A-Za-z0-9_]*$", name)
    description = structure["description"]
    assert isinstance(description, str) and description.strip()
    assert structure["type"] in CANONICAL_TYPES
    for section in ("parameters", "returns"):
        values = structure[section]
        assert isinstance(values, dict) and values
        for entry in values.values():
            assert isinstance(entry, dict)
            assert isinstance(entry.get("description"), str)
            assert entry.get("type") in ("str", "int", "float", "bool",
                                         "list", "dict")
    assert isinstance(structure["requires"], dict)


def test_analyze_request_without_llm_is_well_formed():
    """No LLM configured: the deterministic fallback always produces a
    registry-compatible structure (Task 8.5: edge cases handled)."""
    pipeline = NewSkillPipeline()
    structure = pipeline.analyze_request(
        "develop a skill named adder that adds two numbers"
    )
    _assert_well_formed(structure)
    assert structure["name"] == "adder"
    assert structure["type"] == "function"
    assert pipeline.stats["analyze_total"] == 1
    assert pipeline.stats["analyze_fallback"] == 1
    assert pipeline.stats["analyze_llm_used"] == 0


def test_analyze_request_offline_model_never_invoked():
    model = _CountingOfflineModel()
    pipeline = NewSkillPipeline(llm=model)
    structure = pipeline.analyze_request("develop a skill named adder")
    _assert_well_formed(structure)
    assert model.calls == 0
    assert pipeline.stats["analyze_fallback"] == 1


@pytest.mark.parametrize("reply, expected_type", [
    ('{"name": "sum_skill", "description": "Adds numbers.", '
     '"type": "function"}', "function"),
    ('{"name": "researcher", "description": "Autonomous research.", '
     '"type": "agent"}', "agent"),
    ('{"name": "night_backup", "description": "Backup chain.", '
     '"type": "workflow"}', "workflow"),
])
def test_llm_structure_is_used_when_available(reply, expected_type):
    llm = _FakeLLM(reply=reply)
    pipeline = NewSkillPipeline(llm=llm)
    structure = pipeline.analyze_request("develop a skill named adder")
    _assert_well_formed(structure)
    assert structure["type"] == expected_type
    assert llm.calls == 1
    assert pipeline.stats["analyze_total"] == 1
    assert pipeline.stats["analyze_llm_used"] == 1
    assert pipeline.stats["analyze_fallback"] == 0


def test_llm_json_inside_markdown_fences_is_parsed():
    reply = 'Here is the structure:\n```json\n' \
            '{"name": "text_summarizer", "description": "Summarizes text.", ' \
            '"type": "function"}\n```\nHope that helps!'
    llm = _FakeLLM(reply=reply)
    pipeline = NewSkillPipeline(llm=llm)
    structure = pipeline.analyze_request("build a skill to summarize text")
    assert structure["name"] == "text_summarizer"
    assert structure["description"] == "Summarizes text."
    assert pipeline.stats["analyze_llm_used"] == 1


@pytest.mark.parametrize("reply", [
    "I cannot answer that right now.",            # no JSON at all
    '{"name": "adder", "description": "Adds."',   # invalid JSON (trailing)
    '{"name": "adder" "description": "Adds."}',
    '[1, 2, 3]',                                  # JSON but not an object
    "",
])
def test_llm_unusable_answer_falls_back(reply):
    llm = _FakeLLM(reply=reply)
    pipeline = NewSkillPipeline(llm=llm)
    structure = pipeline.analyze_request("develop a skill named adder")
    _assert_well_formed(structure)
    # Deterministic values must be present in the fallback result.
    assert structure["name"] == "adder"
    assert llm.calls == 1
    assert pipeline.stats["analyze_fallback"] == 1
    assert pipeline.stats["analyze_llm_used"] == 0


def test_llm_exception_falls_back():
    llm = _FakeLLM(reply="", raises=True)
    pipeline = NewSkillPipeline(llm=llm)
    structure = pipeline.analyze_request("develop a skill named adder")
    _assert_well_formed(structure)
    assert pipeline.stats["analyze_fallback"] == 1
    assert llm.calls == 1


def test_llm_partial_answer_is_repaired_not_fallen_back():
    """A usable JSON object with missing fields is completed, not discarded
    (guide Task 8.3/8.4: generation must handle various formats)."""
    llm = _FakeLLM(reply='{"name": "adder"}')
    pipeline = NewSkillPipeline(llm=llm)
    structure = pipeline.analyze_request(
        "develop a skill named adder that adds two numbers"
    )
    _assert_well_formed(structure)
    assert structure["name"] == "adder"
    # Missing description/type/parameters/returns are all filled in.
    assert structure["description"]
    assert structure["type"] in CANONICAL_TYPES
    assert structure["parameters"]
    assert structure["returns"]
    assert pipeline.stats["analyze_llm_used"] == 1


def test_llm_invalid_fields_are_canonicalized():
    reply = (
        '{"name": "9bad!! name", "description": "", '
        '"type": "composite", '
        '"parameters": {"x": 5, "y": "count: int"}, '
        '"returns": {"out": "value"}, "requires": ["echo_skill"]}'
    )
    llm = _FakeLLM(reply=reply)
    pipeline = NewSkillPipeline(llm=llm)
    structure = pipeline.analyze_request("develop a skill")
    _assert_well_formed(structure)
    # "9bad!! name" -> registry-safe identifier starting with a letter.
    assert re.match(r"^[A-Za-z][A-Za-z0-9_]*$", structure["name"])
    # Unknown synonym "composite" canonicalizes safely to a valid type.
    assert structure["type"] in CANONICAL_TYPES
    assert structure["parameters"]["x"]["type"] == "str"
    assert structure["parameters"]["y"]["type"] == "int"
    assert structure["returns"]["out"]["type"] == "str"
    assert structure["requires"] == {"skills": ["echo_skill"]}


@pytest.mark.parametrize("raw_type, expected", [
    ("function", "function"),
    ("Function", "function"),
    ("agent", "agent"),
    ("workflow", "workflow"),
    ("Workflow", "workflow"),
    ("pipeline", "workflow"),
    ("multi-step", "workflow"),
    ("tool", "function"),
    ("simple", "function"),
    ("autonomous", "agent"),
    ("bogus", "function"),   # unrecognized -> function (never unusable)
    ("", "function"),
    (None, "function"),
])
def test_type_canonicalization(raw_type, expected):
    pipeline = NewSkillPipeline()
    structure = pipeline.analyze_request(
        "develop a skill named adder", request_data={"type": raw_type}
    )
    assert structure["type"] == expected


def test_explicit_request_data_takes_priority_over_fallback():
    pipeline = NewSkillPipeline()
    structure = pipeline.analyze_request(
        "develop a skill named adder",
        request_data={
            "name": "explicit_name",
            "description": "Explicit description.",
            "type": "agent",
            "parameters": {"count": {"description": "How many", "type": "int"}},
        },
    )
    assert structure["name"] == "explicit_name"
    assert structure["description"] == "Explicit description."
    assert structure["type"] == "agent"
    assert structure["parameters"] == {
        "count": {"description": "How many", "type": "int"},
    }


def test_defaults_applied_when_parameters_returns_missing():
    pipeline = NewSkillPipeline()
    structure = pipeline.analyze_request("please develop a new skill")
    # No parameter declarations in the request -> defaults.
    assert structure["parameters"] == {
        "input": {
            "description": "Primary input value for the skill.",
            "type": "str",
        },
    }
    assert structure["returns"] == {
        "result": {
            "description": "Primary output value of the skill.",
            "type": "str",
        },
    }
    assert structure["requires"] == {}


def test_derived_name_is_registry_safe_for_various_requests():
    pipeline = NewSkillPipeline()
    for request in (
        "develop a skill named my-cool skill that does x y z",
        "create a skill with 2 weird symbols!!",
        "I want a new skill called WeatherFetcher",
        "make me a skill",
        "   ",
        "",
    ):
        structure = pipeline.analyze_request(request)
        _assert_well_formed(structure)


def test_analyze_request_counts_stats_in_both_paths():
    pipeline = NewSkillPipeline(llm=_FakeLLM(reply="not json"))
    pipeline.analyze_request("develop a skill")       # fallback (bad JSON)
    pipeline.analyze_request("develop a skill")       # fallback again
    pipeline2 = NewSkillPipeline(
        llm=_FakeLLM(reply='{"name": "x", "description": "y"}')
    )
    pipeline2.analyze_request("develop a skill")      # LLM path
    assert pipeline.stats["analyze_total"] == 2
    assert pipeline.stats["analyze_fallback"] == 2
    assert pipeline.stats["analyze_llm_used"] == 0
    assert pipeline2.stats["analyze_total"] == 1
    assert pipeline2.stats["analyze_llm_used"] == 1
    assert pipeline2.stats["analyze_fallback"] == 0


def test_llm_prompt_requests_registry_types():
    """The LLM is told to return only the registry execution types."""
    prompts: list = []

    class _RecordingLLM:
        is_offline = False

        def invoke(self, prompt):
            prompts.append(prompt)
            return '{"name": "x", "description": "y", "type": "agent"}'

    NewSkillPipeline(llm=_RecordingLLM()).analyze_request("develop a skill")
    prompt = prompts[0]
    assert '"function", "agent", "workflow"' in prompt
    assert "JSON" in prompt


def test_analyze_request_none_request_data_is_safe():
    pipeline = NewSkillPipeline()
    structure = pipeline.analyze_request("develop a skill named adder")
    _assert_well_formed(structure)
    # A non-dict request_data must not crash (forward-compat with wiring).
    structure2 = pipeline.analyze_request(
        "develop a skill named adder", request_data=None
    )
    _assert_well_formed(structure2)


def test_analyzed_structure_passes_registry_validation(temp_registry):
    """Task 8 contract check: the analyzed structure's name/type/description
    satisfy the registry's validation rules, so Task 9/11 can register it
    without rework (code generation is Task 9's job, so a stub body is
    used here only to exercise validate_skill's code checks)."""
    requests = [
        ("develop a skill named adder that adds numbers", "function"),
        ("make a workflow skill for backups", "workflow"),
        ("build me an agent skill that researches topics", "agent"),
    ]
    for request, expected_type in requests:
        pipeline = NewSkillPipeline()
        structure = pipeline.analyze_request(request)
        _assert_well_formed(structure)
        assert structure["type"] == expected_type
        # Registry validation accepts the analyzed name and type as-is.
        validation = temp_registry.validate_skill({
            "name": structure["name"],
            "type": structure["type"],
            "code": "def run():\n    return 1\n",
        })
        assert validation["valid"], validation["errors"]


def test_workflow_and_agent_phrases_get_registry_types_offline():
    pipeline = NewSkillPipeline()
    structure = pipeline.analyze_request(
        "make a workflow skill for backups",
        request_data={"type": "workflow"},
    )
    assert structure["type"] == "workflow"
    structure = pipeline.analyze_request(
        "build me an agent skill that researches topics",
        request_data={"type": "agent"},
    )
    assert structure["type"] == "agent"


def test_handle_request_envelope_unchanged_by_task_8():
    """Routing contract stability: Task 8 adds analyze_request() without
    altering the Task 7 envelope (main-agent wiring is Task 22)."""
    out = NewSkillPipeline().handle_request("develop a skill named adder")
    assert set(out) == {"intent", "success", "offline", "response", "error"}
    assert out["intent"] == INTENT_CREATE_SKILL
    assert out["success"] is True


def test_vocabulary_exports_are_consistent():
    from pipelines import (
        CANONICAL_SKILL_TYPES as PKG_TYPES,
        SKILL_TYPE_AGENT as PKG_AGENT,
        SKILL_TYPE_FUNCTION as PKG_FUNCTION,
        SKILL_TYPE_WORKFLOW as PKG_WORKFLOW,
    )
    from pipelines.new_skill_pipeline import (
        CANONICAL_SKILL_TYPES as MOD_TYPES,
        SKILL_TYPE_AGENT,
        SKILL_TYPE_FUNCTION,
        SKILL_TYPE_WORKFLOW,
    )
    from skills.models import VALID_SKILL_TYPES

    assert PKG_TYPES == MOD_TYPES == VALID_SKILL_TYPES
    assert (SKILL_TYPE_FUNCTION, SKILL_TYPE_AGENT, SKILL_TYPE_WORKFLOW) == (
        PKG_FUNCTION, PKG_AGENT, PKG_WORKFLOW,
    )

