#!/usr/bin/env python3
"""
System-level QA suite (guide §1.8.26, Task 25).

Runs the assembled system against itself and reports what works:

* ``core``     - registry operations, skill loading, version control (25.2)
* ``critical`` - the registration and execution workflows end to end (25.3)
* ``full``     - everything above plus intent routing, memory management
  and system-wide interaction (25.4)

and, orthogonally, which pipeline to exercise (25.1): ``new``, ``existing``
or ``both``.

Two deliberate properties:

* **It never touches the real registry.** Given no registry, the suite
  builds a throwaway one in a temporary directory. A QA run that wrote its
  fixtures into ``skills/skills.db`` would corrupt the thing it is meant to
  be checking.
* **It never raises.** Every check is trapped; a check that explodes is
  reported as a failure with its exception, because a QA suite that dies on
  the first problem tells you less than one that finishes and lists them.
"""

import os
import shutil
import tempfile
import traceback
from typing import Any, Callable, Dict, List, NamedTuple, Optional

TEST_TYPES = ("core", "critical", "full")
PIPELINES = ("new", "existing", "both")


class CheckResult(NamedTuple):
    """One QA check's outcome."""

    category: str
    name: str
    passed: bool
    detail: str

    def __str__(self) -> str:
        return f"[{'PASS' if self.passed else 'FAIL'}] {self.category}: {self.name}"


# Skill fixtures the suite registers into its throwaway registry.
_FIXTURE_CODE = "def run(text: str = '') -> str:\n    return text.upper()\n"
_FIXTURE_PARAMS = {"text": {"description": "input text", "type": "str"}}


class QATestSuite:
    """Run system-level QA checks and report the results."""

    def __init__(
        self,
        registry: Any = None,
        llm: Any = None,
        workdir: Optional[str] = None,
    ) -> None:
        self.llm = llm
        self._owned_workdir: Optional[str] = None
        if registry is None:
            registry = self._build_scratch_registry(workdir)
        self.registry = registry
        self.results: List[CheckResult] = []

    # ------------------------------------------------------------------
    # Setup / teardown
    # ------------------------------------------------------------------

    def _build_scratch_registry(self, workdir: Optional[str]) -> Any:
        """Create a registry in a throwaway directory."""
        from skills.registry import SkillRegistry

        base = workdir or tempfile.mkdtemp(prefix="pa-qa-")
        if workdir is None:
            self._owned_workdir = base
        repo = os.path.join(base, "repo")
        os.makedirs(repo, exist_ok=True)
        return SkillRegistry(
            db_path=os.path.join(base, "qa.db"),
            git_repo_path=repo,
            auto_commit=False,
        )

    def cleanup(self) -> None:
        """Close the registry and remove any directory the suite created."""
        try:
            self.registry.close()
        except Exception:  # noqa: BLE001 - teardown must not raise
            pass
        if self._owned_workdir:
            shutil.rmtree(self._owned_workdir, ignore_errors=True)
            self._owned_workdir = None

    def __enter__(self) -> "QATestSuite":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.cleanup()

    # ------------------------------------------------------------------
    # Check plumbing
    # ------------------------------------------------------------------

    def _check(
        self, category: str, name: str, fn: Callable[[], Any]
    ) -> CheckResult:
        """Run one check, trapping anything it raises."""
        try:
            outcome = fn()
        except Exception as exc:  # noqa: BLE001 - a crash is a failed check
            result = CheckResult(
                category, name, False,
                f"{type(exc).__name__}: {exc}\n"
                + traceback.format_exc(limit=3).strip(),
            )
        else:
            if isinstance(outcome, tuple):
                passed, detail = outcome
            else:
                passed, detail = bool(outcome), ""
            result = CheckResult(category, name, bool(passed), str(detail))
        self.results.append(result)
        return result

    def _fixture_skill(self, name: str) -> str:
        """Register a known-good skill and return its name."""
        existing = self.registry.get_skill(name)
        if existing is None:
            self.registry.register_skill(
                name=name, skill_type="function",
                description=f"QA fixture skill {name}",
                code=_FIXTURE_CODE, parameters=_FIXTURE_PARAMS,
            )
        return name

    # ------------------------------------------------------------------
    # 25.2 — core functionality
    # ------------------------------------------------------------------

    def run_core_checks(self) -> None:
        """Registry operations, skill loading and version control."""
        from skills.unified_stage import UnifiedSkillStage

        def registry_roundtrip():
            name = self._fixture_skill("qa_core_skill")
            skill = self.registry.get_skill(name)
            return skill is not None and skill["type"] == "function", (
                f"registered and retrieved {name!r}"
            )

        def registry_search():
            self._fixture_skill("qa_core_skill")
            hits = self.registry.search_skills("QA fixture")
            return bool(hits), f"search returned {len(hits)} result(s)"

        def registry_listing():
            self._fixture_skill("qa_core_skill")
            listed = self.registry.list_skills()
            typed = self.registry.list_skills(skill_type="function")
            return bool(listed) and len(typed) <= len(listed), (
                f"{len(listed)} skill(s); {len(typed)} of type function"
            )

        def skill_loading():
            name = self._fixture_skill("qa_core_skill")
            loaded = UnifiedSkillStage(self.registry).load_skill(name)
            return loaded is not None, f"loaded {name!r} as {type(loaded).__name__}"

        def version_control():
            name = self._fixture_skill("qa_version_skill")
            self.registry.update_skill(
                name, code=_FIXTURE_CODE.replace("upper", "lower"),
                note="qa version bump",
            )
            history = self.registry.get_version_history(name)
            comparison = self.registry.compare_versions(name, 1, 2)
            return len(history) >= 2 and comparison["changed"], (
                f"{len(history)} versions; diff detected: {comparison['changed']}"
            )

        def rollback():
            name = self._fixture_skill("qa_version_skill")
            before = self.registry.get_skill(name)["current_version"]
            self.registry.rollback_to_version(name, 1)
            after = self.registry.get_skill(name)["current_version"]
            return after > before, f"v{before} -> v{after} (history preserved)"

        self._check("core", "registry register/retrieve", registry_roundtrip)
        self._check("core", "registry search", registry_search)
        self._check("core", "registry listing and filtering", registry_listing)
        self._check("core", "skill loading via unified stage", skill_loading)
        self._check("core", "version history and comparison", version_control)
        self._check("core", "version rollback", rollback)

    # ------------------------------------------------------------------
    # 25.3 — critical paths
    # ------------------------------------------------------------------

    def run_critical_checks(self) -> None:
        """The registration and execution workflows, end to end."""
        from skills.unified_stage import UnifiedSkillStage

        def registration_workflow():
            from skills.skill_builder import SkillBuilder

            builder = SkillBuilder(self.registry)
            outcome = builder.create_from_template(
                "qa_critical_registered", skill_type="function",
                description="QA critical-path skill",
            )
            return outcome["success"], f"builder reported {outcome.get('error') or 'success'}"

        def execution_workflow():
            name = self._fixture_skill("qa_exec_skill")
            result = UnifiedSkillStage(self.registry).execute_skill(
                name, {"text": "qa"}
            )
            return result["success"] and result["output"] == "QA", (
                f"output={result['output']!r} error={result['error']!r}"
            )

        def execution_failure_is_reported():
            name = "qa_failing_skill"
            if self.registry.get_skill(name) is None:
                self.registry.register_skill(
                    name=name, skill_type="function", description="always fails",
                    code="def run(text: str = '') -> str:\n    raise ValueError('qa')\n",
                    parameters=_FIXTURE_PARAMS,
                )
            result = UnifiedSkillStage(self.registry).execute_skill(name, {"text": "x"})
            return (not result["success"]) and bool(result["error"]), (
                f"failure surfaced as {result['error']!r}"
            )

        def execution_is_logged():
            name = self._fixture_skill("qa_exec_skill")
            UnifiedSkillStage(self.registry).execute_skill(name, {"text": "logged"})
            runs = self.registry.get_skill_runs(name)
            return bool(runs), f"{len(runs)} run(s) recorded"

        def invalid_registration_is_rejected():
            from skills.registry import RegistryError

            try:
                self.registry.register_skill(
                    name="qa bad name!", skill_type="function",
                    description="invalid", code=_FIXTURE_CODE,
                )
            except RegistryError as exc:
                return True, f"rejected: {exc}"
            return False, "an invalid skill name was accepted"

        self._check("critical", "skill registration workflow", registration_workflow)
        self._check("critical", "skill execution workflow", execution_workflow)
        self._check("critical", "execution failure reported", execution_failure_is_reported)
        self._check("critical", "execution logged to registry", execution_is_logged)
        self._check("critical", "invalid registration rejected", invalid_registration_is_rejected)

    # ------------------------------------------------------------------
    # 25.1 — pipelines
    # ------------------------------------------------------------------

    def run_new_pipeline_checks(self) -> None:
        """The New Skill Development pipeline."""
        from pipelines import NewSkillPipeline
        from pipelines.new_skill_pipeline import (
            STATUS_ALREADY_EXISTS,
            STATUS_COMPLETED,
        )

        def intent_analysis():
            pipeline = NewSkillPipeline(registry=self.registry, llm=self.llm)
            intents = [
                pipeline.detect_intent("create a skill named foo"),
                pipeline.detect_intent("use skill foo"),
                pipeline.detect_intent("what is the weather?"),
            ]
            return intents == ["create_skill", "use_skill", "general"], (
                f"intents={intents}"
            )

        def creation_flow():
            pipeline = NewSkillPipeline(registry=self.registry, llm=self.llm)
            result = pipeline.create_skill(
                "create a skill named qa_pipeline_made that does a thing",
                auto_confirm=True,
            )
            return result["status"] == STATUS_COMPLETED, (
                f"status={result['status']} errors={result['errors']}"
            )

        def creation_is_idempotent():
            pipeline = NewSkillPipeline(registry=self.registry, llm=self.llm)
            request = "create a skill named qa_pipeline_dup that does a thing"
            pipeline.create_skill(request, auto_confirm=True)
            second = pipeline.create_skill(request, auto_confirm=True)
            return second["status"] == STATUS_ALREADY_EXISTS, (
                f"second attempt status={second['status']}"
            )

        def generated_skill_runs():
            from skills.unified_stage import UnifiedSkillStage

            pipeline = NewSkillPipeline(registry=self.registry, llm=self.llm)
            pipeline.create_skill(
                "create a skill named qa_generated_runs", auto_confirm=True
            )
            structure = self.registry.get_skill("qa_generated_runs")
            if structure is None:
                return False, "skill was not registered"
            result = UnifiedSkillStage(self.registry).execute_skill(
                "qa_generated_runs", {"input": "x"}
            )
            return result["success"], f"error={result['error']!r}"

        self._check("pipeline:new", "intent analysis", intent_analysis)
        self._check("pipeline:new", "skill creation flow", creation_flow)
        self._check("pipeline:new", "duplicate creation is a no-op", creation_is_idempotent)
        self._check("pipeline:new", "generated skill executes", generated_skill_runs)

    def run_existing_pipeline_checks(self) -> None:
        """The Existing Skill Pipeline."""
        from pipelines import ExistingSkillPipeline
        from pipelines.existing_skill_pipeline import (
            STATUS_EXECUTED,
            STATUS_NOT_FOUND,
        )

        def search():
            self._fixture_skill("qa_search_target")
            pipeline = ExistingSkillPipeline(registry=self.registry, llm=self.llm)
            hits = pipeline.find_skills("qa_search_target")
            return bool(hits) and hits[0]["name"] == "qa_search_target", (
                f"top hit={hits[0]['name'] if hits else None!r}"
            )

        def parsing_and_validation():
            name = self._fixture_skill("qa_parse_target")
            pipeline = ExistingSkillPipeline(registry=self.registry, llm=self.llm)
            skill = self.registry.get_skill(name)
            parsed = pipeline._parse_input_to_params("text=hello", skill)
            validation = pipeline.validate_params(parsed, skill)
            return validation["valid"] and parsed.get("text") == "hello", (
                f"parsed={parsed} errors={validation['errors']}"
            )

        def execution():
            self._fixture_skill("qa_run_target")
            pipeline = ExistingSkillPipeline(registry=self.registry, llm=self.llm)
            result = pipeline.handle_request(
                "go", skill_name="qa_run_target", input_data={"text": "qa"}
            )
            return result["status"] == STATUS_EXECUTED, (
                f"status={result['status']} errors={result['errors']}"
            )

        def no_match_suggests():
            pipeline = ExistingSkillPipeline(registry=self.registry, llm=self.llm)
            result = pipeline.handle_request("launch a rocket to mars")
            return (
                result["status"] == STATUS_NOT_FOUND
                and bool(result["suggestions"])
            ), f"status={result['status']}"

        self._check("pipeline:existing", "skill search", search)
        self._check("pipeline:existing", "parameter parsing and validation", parsing_and_validation)
        self._check("pipeline:existing", "skill execution", execution)
        self._check("pipeline:existing", "no match offers suggestions", no_match_suggests)

    # ------------------------------------------------------------------
    # 25.4 — full integration
    # ------------------------------------------------------------------

    def run_integration_checks(self) -> None:
        """Intent routing, memory management and system-wide interaction."""

        def agent_available():
            from agent.main_agent import MainAgent  # noqa: F401

            return True, "agent.main_agent imported"

        def intent_routing():
            from agent.main_agent import MainAgent

            with MainAgent() as agent:
                intents = [
                    agent.detect_intent("create a skill named foo"),
                    agent.detect_intent("use skill foo"),
                ]
            return len({*intents}) == 2, f"intents={intents}"

        def memory_management():
            from agent.main_agent import MainAgent

            with MainAgent() as agent:
                agent.handle_request("what can you do?")
                memory = agent.get_memory()
            return isinstance(memory, dict), f"memory keys={sorted(memory)[:4]}"

        def system_wide_request():
            from agent.main_agent import MainAgent

            with MainAgent() as agent:
                result = agent.handle_request("what can you do?")
            return isinstance(result, dict) and "success" in result, (
                f"envelope keys={sorted(result)[:5]}"
            )

        self._check("integration", "agent module importable", agent_available)
        self._check("integration", "intent routing", intent_routing)
        self._check("integration", "memory management", memory_management)
        self._check("integration", "system-wide request handling", system_wide_request)

    # ------------------------------------------------------------------
    # Entry point and reporting (25.5)
    # ------------------------------------------------------------------

    def run(
        self, test_type: str = "full", pipeline: str = "both"
    ) -> Dict[str, Any]:
        """Run the selected checks and return an analysed report.

        ``test_type`` is one of :data:`TEST_TYPES`; ``pipeline`` one of
        :data:`PIPELINES`. ``full`` implies ``core`` and ``critical``.
        """
        test_type = str(test_type or "full").lower()
        pipeline = str(pipeline or "both").lower()
        if test_type not in TEST_TYPES:
            return {
                "success": False, "test_type": test_type, "pipeline": pipeline,
                "error": (
                    f"unknown test_type {test_type!r}; "
                    f"choose one of: {', '.join(TEST_TYPES)}"
                ),
                "results": [], "summary": {}, "report": "",
            }
        if pipeline not in PIPELINES:
            return {
                "success": False, "test_type": test_type, "pipeline": pipeline,
                "error": (
                    f"unknown pipeline {pipeline!r}; "
                    f"choose one of: {', '.join(PIPELINES)}"
                ),
                "results": [], "summary": {}, "report": "",
            }

        self.results = []
        if test_type in ("core", "full"):
            self.run_core_checks()
        if test_type in ("critical", "full"):
            self.run_critical_checks()
        if pipeline in ("new", "both"):
            self.run_new_pipeline_checks()
        if pipeline in ("existing", "both"):
            self.run_existing_pipeline_checks()
        if test_type == "full":
            self.run_integration_checks()

        analysis = self.analyze()
        return {
            "success": analysis["failed"] == 0,
            "test_type": test_type,
            "pipeline": pipeline,
            "error": None,
            "results": [r._asdict() for r in self.results],
            "summary": analysis,
            "report": self.format_report(),
        }

    def analyze(self) -> Dict[str, Any]:
        """Summarise the current results (Task 25.5)."""
        total = len(self.results)
        failures = [r for r in self.results if not r.passed]
        by_category: Dict[str, Dict[str, int]] = {}
        for result in self.results:
            bucket = by_category.setdefault(
                result.category, {"passed": 0, "failed": 0}
            )
            bucket["passed" if result.passed else "failed"] += 1
        return {
            "total": total,
            "passed": total - len(failures),
            "failed": len(failures),
            "pass_rate": round((total - len(failures)) / total, 4) if total else 0.0,
            "by_category": by_category,
            "failures": [
                {"category": f.category, "name": f.name, "detail": f.detail}
                for f in failures
            ],
        }

    def format_report(self) -> str:
        """Render the results as readable text (Task 25.5)."""
        if not self.results:
            return "No QA checks were run."
        analysis = self.analyze()
        lines = [
            "QA SUITE RESULTS",
            "=" * 60,
            f"{analysis['passed']}/{analysis['total']} checks passed "
            f"({analysis['pass_rate'] * 100:.0f}%)",
            "",
        ]
        current = None
        for result in self.results:
            if result.category != current:
                current = result.category
                counts = analysis["by_category"][current]
                lines.append(
                    f"{current}  ({counts['passed']} passed, {counts['failed']} failed)"
                )
            mark = "PASS" if result.passed else "FAIL"
            lines.append(f"  [{mark}] {result.name}")
            if result.detail:
                first = result.detail.splitlines()[0]
                lines.append(f"         {first}")
        if analysis["failures"]:
            lines += ["", "FAILURES", "-" * 60]
            for failure in analysis["failures"]:
                lines.append(f"  {failure['category']}: {failure['name']}")
                for line in failure["detail"].splitlines():
                    lines.append(f"      {line}")
        return "\n".join(lines)


def run_qa(
    test_type: str = "full",
    pipeline: str = "both",
    registry: Any = None,
    llm: Any = None,
) -> Dict[str, Any]:
    """Run the QA suite once and return its report.

    Cleans up any throwaway registry it created.
    """
    suite = QATestSuite(registry=registry, llm=llm)
    try:
        return suite.run(test_type=test_type, pipeline=pipeline)
    finally:
        if registry is None:
            suite.cleanup()
