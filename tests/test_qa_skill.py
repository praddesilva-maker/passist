#!/usr/bin/env python3
"""
Tests for the SkillQA skill (offline-safe, registry-driven).
"""

from skills.qa_skill import OFFLINE_ANSWER, SkillQA


def test_qa_statistics(temp_registry_with_skills):
    qa = SkillQA(temp_registry_with_skills, llm=None)
    stats = qa.get_statistics()
    assert stats["success"] is True
    assert stats["total_skills"] == 1
    assert stats["skill_names"] == ["echo_skill"]


def test_qa_validate_structure(temp_registry_with_skills):
    qa = SkillQA(temp_registry_with_skills, llm=None)
    validation = qa.validate_skill_structure("echo_skill")
    assert validation["success"] is True
    assert validation["valid"] is True
    assert validation["structure"]["has_code"] is True

    missing = qa.validate_skill_structure("ghost")
    assert missing["success"] is False
    assert missing["error"]


def test_qa_test_skill(temp_registry_with_skills):
    qa = SkillQA(temp_registry_with_skills, llm=None)
    result = qa.test_skill("echo_skill", {"input_value": "ping"})
    assert result["success"] is True
    assert result["output"] == {"echo": "ping"}

    bad = qa.test_skill("ghost")
    assert bad["success"] is False
    assert bad["error"]


def test_qa_chat_offline_without_llm(temp_registry):
    qa = SkillQA(temp_registry, llm=None)
    answer = qa.chat("What skills exist?")
    assert answer["success"] is True
    assert answer["offline"] is True
    assert answer["answer"] == OFFLINE_ANSWER
    assert answer["error"] is None


def test_qa_chat_offline_when_llm_fails(temp_registry):
    class FailingLLM:
        is_offline = False

        def invoke(self, prompt):
            raise RuntimeError("network down")

    qa = SkillQA(temp_registry, llm=FailingLLM())
    answer = qa.chat("What skills exist?")
    assert answer["success"] is True
    assert answer["offline"] is True
    assert "RuntimeError" in answer["answer"]


def test_qa_chat_empty_question(temp_registry):
    qa = SkillQA(temp_registry, llm=None)
    answer = qa.chat("   ")
    assert answer["success"] is False
    assert answer["error"]


def test_qa_report(temp_registry_with_skills):
    qa = SkillQA(temp_registry_with_skills, llm=None)
    report = qa.report()
    assert report["success"] is True
    assert report["offline"] is True
    assert report["statistics"]["total_skills"] == 1
    assert report["invalid_skills"] == []
