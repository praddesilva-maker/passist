#!/usr/bin/env python3
"""
Tests for the system-level QA suite (Task 25, guide §1.8.26).

The suite is the thing that says whether the assembled system works, so it
needs its own tests: a QA runner that reports success regardless of reality
is worse than none at all. These check that it selects the right checks,
reports real failures, analyses results correctly, and never touches the
project's real registry.
"""

import pytest

from qa import PIPELINES, TEST_TYPES, QATestSuite, run_qa


@pytest.fixture
def suite(temp_registry):
    return QATestSuite(registry=temp_registry)


# --- selection -------------------------------------------------------------

def test_core_run_covers_core_and_both_pipelines(suite):
    report = suite.run(test_type="core", pipeline="both")
    categories = {r["category"] for r in report["results"]}
    assert categories == {"core", "pipeline:new", "pipeline:existing"}


def test_critical_run_skips_core(suite):
    report = suite.run(test_type="critical", pipeline="new")
    categories = {r["category"] for r in report["results"]}
    assert categories == {"critical", "pipeline:new"}


def test_full_run_covers_everything(suite):
    report = suite.run(test_type="full", pipeline="both")
    categories = {r["category"] for r in report["results"]}
    assert categories == {
        "core", "critical", "pipeline:new", "pipeline:existing", "integration",
    }


@pytest.mark.parametrize("pipeline", ["new", "existing"])
def test_pipeline_selector_runs_only_that_pipeline(suite, pipeline):
    report = suite.run(test_type="core", pipeline=pipeline)
    categories = {r["category"] for r in report["results"]}
    assert f"pipeline:{pipeline}" in categories
    other = "existing" if pipeline == "new" else "new"
    assert f"pipeline:{other}" not in categories


def test_unknown_test_type_is_rejected_with_the_valid_choices(suite):
    report = suite.run(test_type="nonsense")
    assert report["success"] is False
    assert "unknown test_type" in report["error"]
    for name in TEST_TYPES:
        assert name in report["error"]


def test_unknown_pipeline_is_rejected_with_the_valid_choices(suite):
    report = suite.run(pipeline="nonsense")
    assert report["success"] is False
    assert "unknown pipeline" in report["error"]
    for name in PIPELINES:
        assert name in report["error"]


# --- the system actually passes -------------------------------------------

def test_the_assembled_system_passes_every_check(suite):
    report = suite.run(test_type="full", pipeline="both")
    assert report["success"] is True, report["report"]
    assert report["summary"]["failed"] == 0
    assert report["summary"]["pass_rate"] == 1.0


# --- failure reporting -----------------------------------------------------

def test_a_failing_check_is_reported_not_raised(suite):
    result = suite._check("demo", "explodes", lambda: 1 / 0)
    assert result.passed is False
    assert "ZeroDivisionError" in result.detail


def test_a_false_check_is_recorded_as_a_failure(suite):
    assert suite._check("demo", "false", lambda: False).passed is False
    assert suite._check("demo", "tuple", lambda: (False, "why")).detail == "why"


def test_analysis_counts_and_groups_results(suite):
    suite._check("a", "pass", lambda: True)
    suite._check("a", "fail", lambda: (False, "broken"))
    suite._check("b", "pass", lambda: True)
    analysis = suite.analyze()
    assert analysis["total"] == 3
    assert analysis["passed"] == 2
    assert analysis["failed"] == 1
    assert analysis["by_category"]["a"] == {"passed": 1, "failed": 1}
    assert analysis["failures"][0]["name"] == "fail"


def test_report_names_every_failure(suite):
    suite._check("a", "the-broken-one", lambda: (False, "because reasons"))
    report = suite.format_report()
    assert "FAILURES" in report
    assert "the-broken-one" in report
    assert "because reasons" in report


def test_report_with_no_checks(suite):
    assert suite.format_report() == "No QA checks were run."


def test_a_real_system_failure_is_caught(temp_registry):
    """If a component genuinely breaks, the suite must say so - not pass."""
    class _BrokenRegistry:
        def get_skill(self, name):
            raise RuntimeError("registry offline")

        def __getattr__(self, item):
            def _boom(*a, **k):
                raise RuntimeError("registry offline")
            return _boom

    broken = QATestSuite(registry=_BrokenRegistry())
    report = broken.run(test_type="core", pipeline="new")
    assert report["success"] is False
    assert report["summary"]["failed"] > 0


# --- isolation -------------------------------------------------------------

def test_suite_builds_its_own_scratch_registry_by_default():
    """A QA run must never write fixtures into the real skills registry."""
    import os

    suite = QATestSuite()
    try:
        assert suite._owned_workdir is not None
        assert os.path.isdir(suite._owned_workdir)
        db = suite.registry.db_path
        assert suite._owned_workdir in db
        assert "skills/skills.db" not in db.replace("\\", "/")
    finally:
        suite.cleanup()


def test_cleanup_removes_the_scratch_directory():
    import os

    suite = QATestSuite()
    workdir = suite._owned_workdir
    suite.cleanup()
    assert not os.path.exists(workdir)


def test_cleanup_is_idempotent():
    suite = QATestSuite()
    suite.cleanup()
    suite.cleanup()          # must not raise


def test_a_supplied_registry_is_not_deleted(temp_registry):
    suite = QATestSuite(registry=temp_registry)
    suite.cleanup()
    assert suite._owned_workdir is None


def test_context_manager_cleans_up():
    import os

    with QATestSuite() as suite:
        workdir = suite._owned_workdir
        assert os.path.isdir(workdir)
    assert not os.path.exists(workdir)


# --- convenience entry point ----------------------------------------------

def test_run_qa_returns_a_report_and_cleans_up():
    report = run_qa(test_type="core", pipeline="new")
    assert report["success"] is True, report["report"]
    assert report["summary"]["total"] > 0
    assert "QA SUITE RESULTS" in report["report"]


def test_run_qa_honours_a_supplied_registry(temp_registry):
    report = run_qa(test_type="core", pipeline="new", registry=temp_registry)
    assert report["success"] is True
    # The fixtures it registered are in the supplied registry, not a scratch one.
    assert temp_registry.get_skill("qa_core_skill") is not None
