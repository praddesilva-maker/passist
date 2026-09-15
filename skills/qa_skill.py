#!/usr/bin/env python3
"""
QA Skill - testing and validation for registered skills.

:class:`SkillQA` is fully registry-driven: it inspects and exercises skills
through the central :class:`~skills.registry.SkillRegistry` and the unified
:class:`~skills.unified_stage.UnifiedSkillStage`.  There is no filesystem
discovery and no generated-skill directory.

An optional LLM client may be provided (see :mod:`agent.llm`).  When the LLM
is absent, offline (``is_offline``), or fails, every LLM-backed path degrades
to a deterministic offline response - the QA skill works without
``GLM_API_KEY``.  All public methods return structured result dicts with a
``"success"`` flag.
"""

from typing import Any, Dict, List, Optional

from .registry import SkillRegistry, RegistryError
from .unified_stage import UnifiedSkillStage

OFFLINE_ANSWER = (
    "QA mode: running offline (no GLM API key). "
    "Skill execution and structure validation are still fully available; "
    "LLM-assisted analysis is disabled."
)


class SkillQA:
    """QA helper for the central skill registry (online + offline safe)."""

    def __init__(
        self,
        registry: Optional[SkillRegistry] = None,
        llm: Any = None,
    ) -> None:
        self.registry = registry or SkillRegistry()
        self.llm = llm
        self.stage = UnifiedSkillStage(self.registry)

    # ------------------------------------------------------------------
    # Execution / structure checks
    # ------------------------------------------------------------------

    def test_skill(
        self, name: str, input_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a registered skill and report the outcome."""
        try:
            result = self.stage.execute_skill(name, input_data or {})
        except Exception as exc:  # noqa: BLE001 - QA must never crash
            return {
                "success": False,
                "skill_name": name,
                "output": None,
                "error": f"{type(exc).__name__}: {exc}",
            }
        return {
            "success": bool(result.get("success")),
            "skill_name": result.get("skill_name", name),
            "skill_type": result.get("skill_type"),
            "version": result.get("version"),
            "output": result.get("output"),
            "error": result.get("error"),
            "execution_time_ms": result.get("execution_time_ms"),
        }

    def validate_skill_structure(self, name: str) -> Dict[str, Any]:
        """Validate a registered skill's structure without executing it."""
        try:
            skill = self.registry.get_skill(name)
        except RegistryError:
            skill = None
        if skill is None:
            return {
                "success": False,
                "valid": False,
                "skill_name": name,
                "error": f"Skill '{name}' not found in registry",
            }
        validation = self.registry.validate_skill(
            {
                "name": skill.get("name", name),
                "type": skill.get("type"),
                "code": skill.get("code", ""),
            }
        )
        params = skill.get("parameters") or {}
        examples = skill.get("examples") or []
        structure = {
            "type": skill.get("type"),
            "version": skill.get("current_version"),
            "has_code": bool(str(skill.get("code") or "").strip()),
            "parameters_count": len(params) if isinstance(params, (dict, list)) else 0,
            "examples_count": len(examples) if isinstance(examples, list) else 0,
        }
        return {
            "success": True,
            "valid": bool(validation.get("valid")),
            "skill_name": skill.get("name", name),
            "errors": validation.get("errors", []),
            "structure": structure,
            "error": None,
        }


    def get_statistics(self) -> Dict[str, Any]:
        """Registry-level skill statistics."""
        try:
            skills = self.registry.list_skills()
            inactive = self.registry.list_skills(include_inactive=True)
        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
                "total_skills": 0,
                "active_skills": 0,
                "inactive_skills": 0,
                "skill_names": [],
                "error": f"{type(exc).__name__}: {exc}",
            }
        return {
            "success": True,
            "total_skills": len(skills),
            "active_skills": len(skills),
            "inactive_skills": max(len(inactive) - len(skills), 0),
            "skill_names": sorted(s.get("name", "") for s in skills),
            "error": None,
        }

    # ------------------------------------------------------------------
    # LLM-assisted (with offline fallback)
    # ------------------------------------------------------------------

    def chat(self, question: str, context: str = "") -> Dict[str, Any]:
        """Answer a QA question using the LLM when available.

        Falls back to :data:`OFFLINE_ANSWER` when no LLM is configured, the
        model is offline, or generation fails.
        """
        question = str(question or "").strip()
        if not question:
            return {
                "success": False,
                "answer": "",
                "offline": False,
                "error": "question is required",
            }
        if self.llm is None or bool(getattr(self.llm, "is_offline", False)):
            return {
                "success": True,
                "answer": OFFLINE_ANSWER,
                "offline": True,
                "error": None,
            }
        prompt = "Answer this question about the skill registry.\n"
        if context:
            prompt += f"Context: {context}\n"
        prompt += f"Question: {question}"
        try:
            from agent.llm import extract_text

            answer = extract_text(self.llm.invoke(prompt)).strip()
        except Exception as exc:  # noqa: BLE001 - offline fallback
            return {
                "success": True,
                "answer": f"{OFFLINE_ANSWER} ({type(exc).__name__})",
                "offline": True,
                "error": None,
            }
        if not answer:
            return {
                "success": True,
                "answer": OFFLINE_ANSWER,
                "offline": True,
                "error": None,
            }
        return {
            "success": True,
            "answer": answer,
            "offline": False,
            "error": None,
        }

    def report(self, limit: int = 10) -> Dict[str, Any]:
        """Aggregate QA report: statistics, structure checks, recent runs."""
        stats = self.get_statistics()
        validations: List[Dict[str, Any]] = []
        if stats.get("success"):
            for name in stats.get("skill_names", []):
                validations.append(self.validate_skill_structure(name))
        recent_runs: List[Dict[str, Any]] = []
        for name in stats.get("skill_names", []):
            try:
                runs = self.registry.get_skill_runs(name, limit=limit)
            except Exception:  # noqa: BLE001 - runs are best-effort
                continue
            for run in runs:
                recent_runs.append(
                    {
                        "skill_name": run.get("skill_name"),
                        "success": bool(run.get("success")),
                        "version": run.get("version"),
                        "error": run.get("error"),
                    }
                )
        invalid = [v for v in validations if not v.get("valid")]
        return {
            "success": True,
            "statistics": stats,
            "validations": validations,
            "invalid_skills": [v.get("skill_name") for v in invalid],
            "recent_runs": recent_runs,
            "offline": self.llm is None
            or bool(getattr(self.llm, "is_offline", False)),
            "error": None,
        }
