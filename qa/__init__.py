#!/usr/bin/env python3
"""
QA package (PERSONAL_ASSISTANT_GUIDE.md §1.5, Task 25).

`skills/qa_skill.py` provides per-skill QA helpers (validate one skill,
execute one skill, report on the registry). This package adds the
*system-level* suite that exercises the assembled system end to end:
both pipelines, the core registry/stage machinery, the critical
registration and execution paths, and full integration.
"""

from .qa_test_suite import (
    PIPELINES,
    TEST_TYPES,
    CheckResult,
    QATestSuite,
    run_qa,
)

__all__ = [
    "QATestSuite",
    "CheckResult",
    "TEST_TYPES",
    "PIPELINES",
    "run_qa",
]
