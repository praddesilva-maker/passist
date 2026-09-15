#!/usr/bin/env python3
"""
Tests for the New Skill Pipeline — intent analysis (Task 7).

Covers the three intents (``create_skill`` / ``use_skill`` / ``general``)
across many phrasings, the LLM path and its fallbacks, edge cases, and the
stable ``handle_request`` envelope.  All tests run offline (conftest forces
``GLM_API_KEY`` empty), mirroring the agent test conventions.
"""

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

