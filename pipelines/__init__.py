#!/usr/bin/env python3
"""
Pipelines package (PERSONAL_ASSISTANT_GUIDE.md §1.5).

The Personal Assistant routes work through two pipelines:

* :class:`~pipelines.new_skill_pipeline.NewSkillPipeline` — the New Skill
  Development pipeline.  Task 7 delivers its intent-analysis stage
  (``create_skill`` / ``use_skill`` / ``general``); Tasks 8-11 add
  structure generation, code generation, interactive review, and
  testing/registration on top of it.
* :class:`~pipelines.existing_skill_pipeline.ExistingSkillPipeline` — the
  Existing Skill Pipeline (execution flow): skill search (Task 15), skill
  execution (Task 16) and natural-language parameter parsing (Task 17).
"""

from .new_skill_pipeline import (
    ALL_INTENTS,
    INTENT_CREATE_SKILL,
    INTENT_GENERAL,
    INTENT_USE_SKILL,
    NewSkillPipeline,
)
from .new_skill_pipeline import (  # noqa: F401  (Task 8 vocabulary)
    CANONICAL_SKILL_TYPES,
    PARAMETER_TYPES,
    SKILL_TYPE_AGENT,
    SKILL_TYPE_FUNCTION,
    SKILL_TYPE_WORKFLOW,
)
from .new_skill_pipeline import (  # noqa: F401  (Task 11 creation flow)
    ALL_STATUSES,
    STATUS_ALREADY_EXISTS,
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_EDIT_REQUESTED,
    STATUS_ERROR,
    STATUS_QA_FAILED,
    STATUS_REGISTRATION_FAILED,
)

from .existing_skill_pipeline import (  # noqa: F401  (Tasks 15-17)
    ExistingSkillPipeline,
)
from .existing_skill_pipeline import (  # noqa: F401  (execution statuses)
    STATUS_AMBIGUOUS,
    STATUS_EXECUTED,
    STATUS_EXECUTION_FAILED,
    STATUS_INVALID_PARAMS,
    STATUS_NOT_FOUND,
)

__all__ = [
    "NewSkillPipeline",
    "ExistingSkillPipeline",
    "STATUS_AMBIGUOUS",
    "STATUS_EXECUTED",
    "STATUS_EXECUTION_FAILED",
    "STATUS_INVALID_PARAMS",
    "STATUS_NOT_FOUND",
    "ALL_INTENTS",
    "INTENT_CREATE_SKILL",
    "INTENT_GENERAL",
    "INTENT_USE_SKILL",
    "CANONICAL_SKILL_TYPES",
    "PARAMETER_TYPES",
    "SKILL_TYPE_AGENT",
    "SKILL_TYPE_FUNCTION",
    "SKILL_TYPE_WORKFLOW",
    "ALL_STATUSES",
    "STATUS_ALREADY_EXISTS",
    "STATUS_CANCELLED",
    "STATUS_COMPLETED",
    "STATUS_EDIT_REQUESTED",
    "STATUS_ERROR",
    "STATUS_QA_FAILED",
    "STATUS_REGISTRATION_FAILED",
]
