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

    def __init__(
        self,
        registry: Optional[SkillRegistry] = None,
        version_controller: Any = None,
    ) -> None:
        self.registry = registry or SkillRegistry()
        # Task 4.1 requires a version-controller parameter.  The stage does
        # not drive version control itself: the registry owns skill
        # versioning (its own skill_versions table plus an optional
        # GitManager), and the guide's Task 4/5 slices never say what the
        # stage should do with this reference.  It is therefore accepted and
        # held for callers that need it - the main agent's pipeline wiring
        # (Task 22) - rather than given invented behaviour here.
        self.version_controller = version_controller
        # In-memory skill-record cache keyed by (name, version); version=None
        # means "whatever is currently active".  Populated by ``load_skill``
        # (via ``_get_skill_record``) only -- ``execute_skill`` deliberately
        # keeps reading the registry directly on every call so a long-lived
        # stage never serves stale code after a skill is updated mid-session.
        self._skill_cache: Dict[Tuple[str, Optional[int]], Dict[str, Any]] = {}
        self._cache_hits = 0
        self._cache_misses = 0

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
    # Skill loading (registry + cache; Task 4.2/4.3) and per-type loaders
    # (Task 5.1-5.3).
    # ------------------------------------------------------------------

    def load_skill(self, name: str, version: Optional[int] = None) -> Any:
        """Load ``name`` from the registry and return it as a runnable.

        The skill record itself is fetched through the in-memory cache (see
        ``_get_skill_record``); the record is then dispatched by
        ``skill["type"]`` to the matching loader:

        * ``function`` -> :meth:`_load_function_skill` (a LangChain
          ``StructuredTool`` wrapping the compiled entry point)
        * ``agent``    -> :meth:`_load_agent_skill` (a LangGraph ReAct agent)
        * ``workflow`` -> :meth:`_load_workflow_skill` (a compiled LangGraph
          graph)

        Raises :class:`~skills.registry.SkillNotFoundError` if the skill (or
        the requested version) does not exist, and :class:`SkillExecutionError`
        for an unsupported type or any failure while building the runnable.
        """
        skill = self._get_skill_record(name, version)
        skill_type = skill.get("type")
        try:
            if skill_type == "function":
                return self._load_function_skill(name, skill)
            if skill_type == "agent":
                return self._load_agent_skill(name, skill)
            if skill_type == "workflow":
                return self._load_workflow_skill(name, skill)
        except SkillExecutionError:
            raise
        except Exception as exc:  # noqa: BLE001 - surface as a graceful error
            raise SkillExecutionError(
                f"Failed to load skill '{name}' (type={skill_type!r}): "
                f"{type(exc).__name__}: {exc}"
            ) from exc
        raise SkillExecutionError(
            f"Invalid skill type {skill_type!r} for skill '{name}'"
        )

    def clear_cache(self) -> None:
        """Drop all cached skill records (does not touch the registry)."""
        self._skill_cache.clear()

    def cache_stats(self) -> Dict[str, int]:
        """Return ``{"hits", "misses", "size"}`` for the skill-record cache."""
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "size": len(self._skill_cache),
        }

    def _get_skill_record(
        self, name: str, version: Optional[int] = None
    ) -> Dict[str, Any]:
        """Cached fetch of a skill's registry record.

        ``version=None`` returns the active record as-is; a specific
        ``version`` returns the active record with ``code``/``version``
        overridden from that version's history entry, so callers always see
        the full metadata (type, description, parameters) alongside the
        requested code.
        """
        key = (name, version)
        cached = self._skill_cache.get(key)
        if cached is not None:
            self._cache_hits += 1
            return cached

        self._cache_misses += 1
        base = self.registry.get_skill(name)
        if base is None:
            raise SkillNotFoundError(f"Skill '{name}' not found in registry")

        if version is None:
            skill = base
        else:
            version_row = self.registry.get_version(name, version)
            if version_row is None:
                raise SkillNotFoundError(
                    f"Version {version} of skill '{name}' not found"
                )
            skill = dict(base)
            skill["code"] = version_row["code"]
            skill["version"] = version
            skill["current_version"] = version

        self._skill_cache[key] = skill
        return skill

    def _load_function_skill(
        self, name: str, skill: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Load a ``function`` skill as a LangChain ``StructuredTool``.

        Compiles the skill's code (via ``_load_module``) and wraps its entry
        point so it can be handed to a LangChain/LangGraph agent as a tool.
        Metadata (``name`` / ``description``) is taken from the registry
        record.
        """
        skill = skill if skill is not None else self._get_skill_record(name)
        entry_name, namespace = self._load_module(name, skill)
        func = namespace.get(entry_name)
        if not callable(func):
            raise SkillExecutionError(
                f"Entry point '{entry_name}' of skill '{name}' is not callable"
            )

        from langchain_core.tools import StructuredTool

        return StructuredTool.from_function(
            func=func,
            name=skill.get("name", name),
            description=skill.get("description") or f"Skill '{name}'",
        )

    def _load_agent_skill(
        self, name: str, skill: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Load an ``agent`` skill as a LangGraph ReAct agent with memory.

        The chat model comes from ``agent.llm.create_chat_model`` (the same
        online/offline GLM factory used elsewhere), so this works without a
        GLM API key configured.  Tools are built from a ``tools`` list of
        other skill names under ``skill["parameters"]["tools"]`` (each loaded
        via :meth:`_load_function_skill`); unresolved tool names are skipped
        rather than failing the whole agent.  ``skill["parameters"]`` is
        otherwise a plain "argument name -> type info" map (see
        ``skills.models.SkillRecord``), so a non-list value there is treated
        as "no tools declared" rather than an error.

        Note: the installed LangGraph calls ``model.bind_tools(tools)`` while
        building the agent whenever any tools are passed, and the offline
        chat model deliberately raises on ``bind_tools`` (no tool calling
        without a real LLM). When running offline with declared tools, this
        loader falls back to a tool-less agent rather than failing, so the
        skill can still be loaded and demonstrated without credentials.
        """
        skill = skill if skill is not None else self._get_skill_record(name)

        from agent.llm import create_chat_model
        from langgraph.checkpoint.memory import InMemorySaver
        from langgraph.prebuilt import create_react_agent

        llm = create_chat_model()

        raw_tool_names = (skill.get("parameters") or {}).get("tools", [])
        tool_names: List[str] = (
            raw_tool_names
            if isinstance(raw_tool_names, list)
            and all(isinstance(t, str) for t in raw_tool_names)
            else []
        )
        tools: List[Any] = []
        for tool_name in tool_names:
            try:
                tools.append(self._load_function_skill(tool_name))
            except (SkillNotFoundError, SkillExecutionError):
                continue  # an unresolvable tool reference is skipped, not fatal

        if tools and getattr(llm, "is_offline", False):
            tools = []

        checkpointer = InMemorySaver()
        return create_react_agent(llm, tools, checkpointer=checkpointer)

    def _load_workflow_skill(
        self, name: str, skill: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Load a ``workflow`` skill as a compiled LangGraph graph.

        Steps are a ``steps`` list of other skill names under
        ``skill["parameters"]["steps"]`` (same caveat as ``_load_agent_skill``
        about ``parameters`` otherwise meaning function arguments); each step
        becomes a node that runs the corresponding skill via
        :meth:`execute_skill` and merges its output into the shared state
        dict under the step's name.  With no declared steps, the skill's own
        code is used as the sole node, so every existing ``workflow``-typed
        skill still loads. Nodes are wired sequentially and the graph is
        compiled before being returned.
        """
        skill = skill if skill is not None else self._get_skill_record(name)

        from langgraph.graph import END, START, StateGraph

        raw_steps = (skill.get("parameters") or {}).get("steps", [])
        step_names: List[str] = (
            raw_steps
            if isinstance(raw_steps, list) and all(isinstance(s, str) for s in raw_steps)
            else []
        ) or [name]

        def _make_node(step_name: str):
            def _node(state: Dict[str, Any]) -> Dict[str, Any]:
                result = self.execute_skill(step_name, state, log_run=False)
                if not result["success"]:
                    raise SkillExecutionError(
                        f"Workflow step '{step_name}' failed: {result['error']}"
                    )
                merged = dict(state)
                merged[step_name] = result["output"]
                return merged

            return _node

        graph = StateGraph(dict)
        for step_name in step_names:
            graph.add_node(step_name, _make_node(step_name))

        graph.add_edge(START, step_names[0])
        for left, right in zip(step_names, step_names[1:]):
            graph.add_edge(left, right)
        graph.add_edge(step_names[-1], END)

        return graph.compile()

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
