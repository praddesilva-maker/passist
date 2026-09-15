#!/usr/bin/env python3
"""
Unified Skill Stage.

Executes skills of *any* registered type (``function``, ``agent``,
``workflow``) in one uniform pipeline.  Skills are ONLY loaded from the
central :class:`~skills.registry.SkillRegistry` (no filesystem discovery);
every execution is validated and logged back through the registry.

Uniform execution contract
--------------------------
* The skill code must define at least one top-level function.  The entry
  point is chosen as ``run`` if defined, else ``main`` if defined, else the
  first top-level ``def`` in source order.
* ``input_data`` (dict) is passed as keyword arguments to the entry point.
  Missing optional parameters fall back to their defaults.
"""

import ast
import inspect
import time
from typing import Any, Dict, List, Optional, Tuple

from .registry import SkillRegistry, SkillNotFoundError
from .models import VALID_SKILL_TYPES


class SkillExecutionError(Exception):
    """Raised when a skill cannot be loaded or executed."""


class UnifiedSkillStage:
    """Loads skills from the registry and executes them uniformly."""

    def __init__(self, registry: Optional[SkillRegistry] = None) -> None:
        self.registry = registry or SkillRegistry()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute_skill(
        self,
        name: str,
        input_data: Optional[Dict[str, Any]] = None,
        skill_type: Optional[str] = None,
        log_run: bool = True,
    ) -> Dict[str, Any]:
        """Validate and execute one skill; always returns a result dict.

        Result keys: ``success``, ``skill_name``, ``skill_type``, ``output``,
        ``error``, ``execution_time_ms``, ``version``.
        """
        input_data = dict(input_data or {})
        started = time.perf_counter()
        skill = self.registry.get_skill(name)
        if skill is None:
            return {
                "success": False,
                "skill_name": name,
                "skill_type": skill_type or "unknown",
                "output": None,
                "error": f"Skill '{name}' not found in registry",
                "execution_time_ms": 0.0,
                "version": None,
            }

        skill_type = skill_type or skill.get("type")
        if skill_type not in VALID_SKILL_TYPES:
            return self._fail(
                skill, skill_type, input_data,
                f"Invalid skill type: {skill_type!r}", started,
            )

        # Metadata + code validation (before anything is executed).
        validation = self.registry.validate_skill(
            {"name": skill.get("name", name), "type": skill_type,
             "code": skill.get("code", "")}
        )
        if not validation["valid"]:
            return self._fail(
                skill, skill_type, input_data,
                "Invalid skill: " + "; ".join(validation["errors"]), started,
            )

        try:
            entry_name, namespace = self._load_module(name, skill)
            func = namespace.get(entry_name)
            if not callable(func):
                raise SkillExecutionError(
                    f"Entry point '{entry_name}' of skill '{name}' is not callable"
                )
            kwargs = self._resolve_kwargs(func, input_data)
            output = func(**kwargs)
        except Exception as exc:  # noqa: BLE001 - surface any skill failure
            return self._fail(
                skill, skill_type, input_data,
                f"{type(exc).__name__}: {exc}", started,
            )

        duration_ms = (time.perf_counter() - started) * 1000.0
        version = skill.get("current_version")
        if log_run:
            try:
                self.registry.log_skill_run(
                    name, input_data, output,
                    success=True, duration_ms=duration_ms, version=version,
                )
            except Exception:  # logging must never break execution
                pass
        return {
            "success": True,
            "skill_name": name,
            "skill_type": skill_type,
            "output": output,
            "error": None,
            "execution_time_ms": duration_ms,
            "version": version,
        }

    def run(self, name: str, **kwargs: Any) -> Any:
        """Convenience wrapper returning the raw output (raises on failure)."""
        result = self.execute_skill(name, kwargs)
        if not result["success"]:
            raise SkillExecutionError(result["error"] or "skill failed")
        return result["output"]

    def list_available_skills(self) -> List[Dict[str, Any]]:
        return self.registry.list_skills()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _fail(
        skill: Dict[str, Any],
        skill_type: str,
        input_data: Dict[str, Any],
        error: str,
        started: float,
    ) -> Dict[str, Any]:
        duration_ms = (time.perf_counter() - started) * 1000.0
        name = skill.get("name", "unknown")
        return {
            "success": False,
            "skill_name": name,
            "skill_type": skill_type,
            "output": None,
            "error": error,
            "execution_time_ms": duration_ms,
            "version": skill.get("current_version"),
        }

    def _load_module(self, name: str, skill: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """Compile the skill code from the registry into a fresh namespace.

        Returns ``(entry_point_name, namespace)``.
        """
        code = skill.get("code", "")
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            raise SkillExecutionError(
                f"Skill '{name}' has invalid Python code: {exc}"
            ) from exc

        defs = [
            node.name for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        if not defs:
            raise SkillExecutionError(
                f"Skill '{name}' defines no top-level functions"
            )
        if "run" in defs:
            entry = "run"
        elif "main" in defs:
            entry = "main"
        else:
            entry = defs[0]

        namespace: Dict[str, Any] = {"__name__": f"skill_{name}"}
        exec(compile(tree, f"skill_{name}", "exec"), namespace)  # noqa: S102
        return entry, namespace

    @staticmethod
    def _resolve_kwargs(func: Any, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Map input_data onto the entry point's parameters (ignoring extras)."""
        try:
            signature = inspect.signature(func)
        except (TypeError, ValueError):
            return dict(input_data)
        params = signature.parameters
        kwargs: Dict[str, Any] = {}
        for param, param_obj in params.items():
            if param in input_data:
                kwargs[param] = input_data[param]
            elif param_obj.default is inspect.Parameter.empty:
                raise SkillExecutionError(
                    f"Missing required argument '{param}' for skill entry point"
                )
        for pname, pobj in params.items():
            if pobj.kind == inspect.Parameter.VAR_KEYWORD:
                for key, value in input_data.items():
                    if key not in kwargs:
                        kwargs[key] = value
        return kwargs
