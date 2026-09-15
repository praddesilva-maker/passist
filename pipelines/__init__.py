#!/usr/bin/env python3
"""
Pipelines package (PERSONAL_ASSISTANT_GUIDE.md §1.5).

The Personal Assistant routes work through two pipelines:

* :class:`~pipelines.new_skill_pipeline.NewSkillPipeline` — the New Skill
  Development pipeline.  Task 7 delivers its intent-analysis stage
  (``create_skill`` / ``use_skill`` / ``general``); Tasks 8-11 add
  structure generation, code generation, interactive review, and
  testing/registration on top of it.
* The Existing Skill Pipeline (execution flow) — delivered in Tasks 15-17.
"""

from .new_skill_pipeline import (
    ALL_INTENTS,
    INTENT_CREATE_SKILL,
    INTENT_GENERAL,
    INTENT_USE_SKILL,
    NewSkillPipeline,
)

__all__ = [
    "NewSkillPipeline",
    "ALL_INTENTS",
    "INTENT_CREATE_SKILL",
    "INTENT_GENERAL",
    "INTENT_USE_SKILL",
]
