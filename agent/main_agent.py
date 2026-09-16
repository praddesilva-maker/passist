#!/usr/bin/env python3
"""
Main Agent.

:class:`MainAgent` is the single entry point of the Personal Assistant.  It
combines:

* the central :class:`~skills.registry.SkillRegistry` (SQLite, Git-controlled),
* the unified :class:`~skills.unified_stage.UnifiedSkillStage` that executes
  every skill type (``function`` / ``agent`` / ``workflow``) uniformly,
* an optional LLM (see :mod:`agent.llm`) for intent detection and skill
  development, with deterministic regex/heuristic fallbacks so the agent is
  fully operational offline,
* a small in-memory (or file-backed) memory store,
* an optional :class:`~skills.git_manager.GitManager` for commit history.

``handle_request`` always returns a stable dict::

    {
        "intent": "use_skill" | "create_skill" | "general",
        "success": bool,         # request handled without an unhandled error
        "skill_name": str | None,
        "result": dict,          # success/error/output payload
        "response": str,         # human-readable text for display
        "error": str | None,
        # development-only extras:
        "registry_status": dict, # {"total_skills": int, "active_skills": int}
        "skill": dict | None,    # registry row for the named skill
    }
"""

import json
import os
import re
import time
from typing import Any, Dict, Optional, Tuple

from skills.registry import SkillRegistry, SkillAlreadyExistsError
from skills.unified_stage import UnifiedSkillStage
from skills.skill_builder import SkillBuilder
from skills.git_manager import GitManager, GitManagerError

from .llm import extract_text

# ---------------------------------------------------------------------------
# Intent vocabulary (stable, documented in PERSONAL_ASSISTANT_GUIDE.md)
# ---------------------------------------------------------------------------

# Intent vocabulary.  These are the guide's names (§1.8.8) and the ones the
# pipelines/ package already used; the agent previously said "develop_skill"
# and "unknown", so an intent had two spellings depending on which half of
# the system you asked.  Task 22 unifies them - the old names remain as
# aliases so any external caller keeps working.
INTENT_USE_SKILL = "use_skill"
INTENT_CREATE_SKILL = "create_skill"
INTENT_GENERAL = "general"

#: Deprecated aliases for the pre-Task-22 spellings.
INTENT_DEVELOP_SKILL = INTENT_CREATE_SKILL
INTENT_UNKNOWN = INTENT_GENERAL

ALL_INTENTS = (INTENT_USE_SKILL, INTENT_CREATE_SKILL, INTENT_GENERAL)

_DEVELOP_KEYWORDS = (
    "develop skill", "develop a skill", "develop the skill", "develop new skill",
    "create skill", "create a skill", "create new skill", "new skill",
    "add skill", "add a skill", "make a skill", "build a skill", "write a skill",
    "create function", "create agent", "create workflow",
)

_USE_KEYWORDS = (
    "use skill", "run skill", "execute skill", "call skill",
    "do skill", "apply skill", "use the skill", "use my skill",
    "run the skill",
)

_NAME_PATTERNS = (
    r"(?:use|run|execute|call|do|apply)\s+skill\s+named\s+['\"]?([A-Za-z0-9_\-]+)",
    r"(?:use|run|execute|call|do|apply)\s+skill\s+['\"]?([A-Za-z0-9_\-]+)",
    r"(?:use|run|execute|call|do|apply)\s+['\"]?([A-Za-z0-9_\-]+)",
    r"skill\s+(?:named\s+)?['\"]?([A-Za-z0-9_\-]+)",
)

_DEVELOP_NAME_PATTERNS = (
    r"(?:develop|create|make|build|add|write)\s+(?:a\s+|new\s+)?(?:\w+\s+)?skill\s+(?:named\s+|called\s+)?['\"]?([A-Za-z0-9_\-]+)",
)


class _DictMemoryBackend:
    """Minimal in-process memory backend (dict of string values)."""

    def __init__(self) -> None:
        self._store: Dict[str, str] = {}

    def get(self, key: str, default: Any = None) -> Any:
        value = self._store.get(key)
        if value is None:
            return default
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value if isinstance(value, str) else json.dumps(value)

    def snapshot(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k, v in self._store.items():
            try:
                out[k] = json.loads(v)
            except (ValueError, TypeError):
                out[k] = v
        return out


class _FileMemoryBackend:
    """Tiny JSON-file memory backend (one file, last-write-wins)."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._store: Dict[str, str] = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    loaded = json.load(fh)
                self._store = {
                    k: v if isinstance(v, str) else json.dumps(v, default=str)
                    for k, v in loaded.items()
                }
            except (ValueError, OSError):
                self._store = {}

    def get(self, key: str, default: Any = None) -> Any:
        value = self._store.get(key)
        if value is None:
            return default
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value if isinstance(value, str) else json.dumps(value)
        try:
            dirname = os.path.dirname(os.path.abspath(self.path))
            if dirname:
                os.makedirs(dirname, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(self._store, fh)
        except OSError:
            pass

    def snapshot(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k, v in self._store.items():
            try:
                out[k] = json.loads(v)
            except (ValueError, TypeError):
                out[k] = v
        return out


class MainAgent:
    """Personal assistant agent with intent detection, skill use and development."""

    MEMORY_KEY_SKILL_COUNT = "skill_count"
    MEMORY_KEY_RECENT_ACTIONS = "recent_actions"
    MEMORY_KEY_LAST_RESULT = "last_result"
    RECENT_ACTIONS_LIMIT = 10

    def __init__(
        self,
        agent_name: str = "Personal Assistant",
        stage: Optional[UnifiedSkillStage] = None,
        registry: Optional[SkillRegistry] = None,
        llm: Any = None,
        git_manager: Optional[GitManager] = None,
        memory_backend: Any = "memory",
        new_pipeline: Any = None,
        existing_pipeline: Any = None,
    ) -> None:
        self.agent_name = agent_name
        self.registry = registry or SkillRegistry()
        self.stage = stage or UnifiedSkillStage(self.registry)
        self.llm = llm
        self.git_manager = git_manager
        self.skill_builder = SkillBuilder(self.registry)
        self.memory = self._build_memory(memory_backend)
        self.stats = {"requests": 0, "skills_used": 0, "skills_created": 0}
        # Task 22.1/22.2: the agent routes through the two pipelines rather
        # than re-implementing creation and execution.  Imported here rather
        # than at module scope because pipelines/ imports skills/, and a
        # module-level import would make agent -> pipelines -> skills -> agent
        # a cycle the moment a pipeline wants an agent helper.
        from pipelines.existing_skill_pipeline import ExistingSkillPipeline
        from pipelines.new_skill_pipeline import NewSkillPipeline

        self.new_pipeline = new_pipeline or NewSkillPipeline(
            llm=self.llm, registry=self.registry, builder=self.skill_builder
        )
        self.existing_pipeline = existing_pipeline or ExistingSkillPipeline(
            registry=self.registry, stage=self.stage, llm=self.llm
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Release agent resources and close the underlying registry.

        Safe to call more than once, and never raises: teardown must not mask
        a test failure or crash a shutting-down CLI.
        """
        try:
            if self.registry is not None:
                self.registry.close()
        except Exception:  # pragma: no cover - teardown must never raise
            pass
        self.llm = None
        self.git_manager = None

    def __enter__(self) -> "MainAgent":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.cleanup()

    # ------------------------------------------------------------------
    # Memory
    #
    # The guide (PERSONAL_ASSISTANT_GUIDE.md Task 23) asks for
    # ``langchain.memory.ConversationBufferMemory``.  That module does not
    # exist in the pinned LangChain 1.x (``langchain-community``, which used
    # to host it, is not even a dependency here) -- see the Task 23
    # verification report.  ``_DictMemoryBackend`` / ``_FileMemoryBackend``
    # below are a deliberate, minimal replacement: a bounded conversation
    # turn log (this section) plus a plain key/value snapshot
    # (:meth:`get_memory`), so the agent keeps working fully offline without
    # a LangChain memory dependency.
    # ------------------------------------------------------------------

    def _build_memory(self, memory_backend: Any) -> Any:
        if memory_backend is None or memory_backend == "memory":
            return _DictMemoryBackend()
        if isinstance(memory_backend, str):
            return _FileMemoryBackend(memory_backend)
        # Assume an object exposing .get / .set
        return memory_backend

    def _remember_action(
        self,
        intent: str,
        skill_name: Optional[str],
        request: Optional[str] = None,
        response: Optional[str] = None,
    ) -> None:
        """Append one conversation turn to the bounded recent-actions log.

        Storing ``request``/``response`` (in addition to ``intent``/
        ``skill``) is what makes this history retrievable as an actual
        conversation via :meth:`get_history`, rather than only an intent
        audit trail.
        """
        try:
            actions = self.memory.get(self.MEMORY_KEY_RECENT_ACTIONS, []) or []
            if not isinstance(actions, list):
                actions = []
            actions.append(
                {
                    "intent": intent,
                    "skill": skill_name,
                    "request": request,
                    "response": response,
                    "at": time.time(),
                }
            )
            self.memory.set(
                self.MEMORY_KEY_RECENT_ACTIONS,
                actions[-self.RECENT_ACTIONS_LIMIT :],
            )
        except Exception:  # memory must never break the request
            pass

    def get_memory(self) -> Dict[str, Any]:
        try:
            return self.memory.snapshot()
        except Exception:
            return {}

    def get_history(self, limit: Optional[int] = None) -> list:
        """Return recent conversation turns, oldest first.

        Each entry is ``{"intent", "skill", "request", "response", "at"}`` --
        already the shape a caller (CLI, Cline) can format for display
        (e.g. ``f"You: {t['request']}\\nAssistant: {t['response']}"``). Size
        is bounded by :data:`RECENT_ACTIONS_LIMIT` at write time (see
        :meth:`_remember_action`); ``limit`` further truncates to the most
        recent N turns for a caller that wants fewer.
        """
        try:
            actions = self.memory.get(self.MEMORY_KEY_RECENT_ACTIONS, []) or []
            if not isinstance(actions, list):
                return []
        except Exception:
            return []
        if limit is not None and limit >= 0:
            return actions[-limit:] if limit else []
        return list(actions)

    # ------------------------------------------------------------------
    # Intent detection
    # ------------------------------------------------------------------

    def detect_intent(self, request: str) -> str:
        """Classify a request into use_skill / create_skill / general.

        Uses the LLM when one is available and can generate; otherwise (or on
        any failure) falls back to deterministic keyword matching.
        """
        text = (request or "").strip()
        if not text:
            return INTENT_UNKNOWN
        if self.llm is not None and not getattr(self.llm, "is_offline", False):
            intent = self._detect_intent_llm(text)
            if intent:
                return intent
        return self._detect_intent_heuristic(text)

    def _detect_intent_llm(self, text: str) -> Optional[str]:
        prompt = (
            "Classify the user request into exactly one of: "
            f"'{INTENT_USE_SKILL}', '{INTENT_DEVELOP_SKILL}', '{INTENT_UNKNOWN}'. "
            "Return only the intent string, nothing else.\n\n"
            f"Request: {text!r}"
        )
        try:
            response = self.llm.invoke(prompt)
        except Exception:
            return None
        raw = extract_text(response).strip().strip("`\"' \n")
        for intent in (INTENT_USE_SKILL, INTENT_DEVELOP_SKILL, INTENT_UNKNOWN):
            if intent in raw.lower():
                return intent
        return None

    @staticmethod
    def _detect_intent_heuristic(text: str) -> str:
        lowered = text.lower()
        # "develop a skill that uses X" must classify as develop, not use.
        if any(k in lowered for k in _DEVELOP_KEYWORDS) or re.search(
            r"\b(?:develop|create|make|build|write|add)\s+"
            r"(?:a\s+|new\s+|the\s+)?(?:[A-Za-z]+\s+)?skill\b",
            lowered,
        ):
            return INTENT_DEVELOP_SKILL
        if any(k in lowered for k in _USE_KEYWORDS) or re.search(
            r"\b(run|execute|call|do|apply)\s+(?:a\s+)?skill\b", lowered
        ):
            return INTENT_USE_SKILL
        if re.search(r"\b(?:use|run|execute)\s+(?:my\s+|the\s+)?skill\b", lowered):
            return INTENT_USE_SKILL
        return INTENT_UNKNOWN

    # ------------------------------------------------------------------
    # Request extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def extract_skill_args(
        request: str, request_data: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        """Extract (skill_name, input_data) from a use_skill request.

        ``request_data`` (a dict, or a JSON string under ``"input"``) takes
        precedence for arguments.  A trailing JSON object or ``key=value``
        pairs in the request text are parsed as arguments.
        """
        data: Dict[str, Any] = {}
        name: Optional[str] = None

        if request_data:
            if isinstance(request_data, str):
                try:
                    request_data = json.loads(request_data)
                except (ValueError, TypeError):
                    request_data = {}
            if isinstance(request_data, dict):
                if isinstance(request_data.get("name"), str):
                    name = request_data["name"].strip()
                for key in ("input", "input_data", "arguments", "args"):
                    if isinstance(request_data.get(key), dict):
                        data.update(request_data[key])
                for key, value in request_data.items():
                    if key not in ("name", "input", "input_data", "arguments", "args"):
                        data[key] = value

        text = (request or "").strip()
        # Trailing JSON object:  use skill adder {"x": 2, "y": 3}
        json_match = re.search(r"(\{.*\})\s*$", text, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group(1))
                if isinstance(parsed, dict):
                    data.update(parsed)
                    text = text[: json_match.start()].strip()
            except (ValueError, TypeError):
                pass
        # key=value pairs:  use skill adder x=2 y=3
        kv = re.findall(
            r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*('[^']*'|\"[^\"]*\"|\S+)", text
        )
        for key, raw_value in kv:
            if key.lower() in ("skill", "name"):
                continue
            value: Any = raw_value
            try:
                value = json.loads(raw_value)
            except (ValueError, TypeError):
                if (
                    len(raw_value) >= 2
                    and raw_value[0] == raw_value[-1]
                    and raw_value[0] in ("'", '"')
                ):
                    value = raw_value[1:-1]
            data[key] = value

        if not name:
            for pattern in _NAME_PATTERNS:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    name = match.group(1)
                    break

        return name, data

    @staticmethod
    def extract_develop_args(
        request: str, request_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Extract {name, code, skill_type, description} from a develop request."""
        args: Dict[str, Any] = {
            "name": None, "code": None, "skill_type": None, "description": None,
        }
        parsed = request_data
        if isinstance(request_data, str):
            try:
                parsed = json.loads(request_data)
            except (ValueError, TypeError):
                parsed = None
        if isinstance(parsed, dict):
            args["name"] = parsed.get("name")
            args["code"] = parsed.get("code")
            args["skill_type"] = parsed.get("skill_type") or parsed.get("type")
            args["description"] = parsed.get("description")

        text = (request or "").strip()
        # Fenced code block
        fence = re.search(r"```[a-zA-Z]*\n(.*?)```", text, re.DOTALL)
        if fence and not args["code"]:
            args["code"] = fence.group(1).strip()
        # Explicit "code:" line
        if not args["code"]:
            code_line = re.search(r"^\s*code\s*:\s*(.+)$", text, re.MULTILINE)
            if code_line:
                args["code"] = code_line.group(1).strip()
        # Skill type
        if not args["skill_type"]:
            type_match = re.search(
                r"\b(?:skill\s+type|type)\s*[:=]\s*(function|agent|workflow)",
                text, re.IGNORECASE,
            )
            if type_match:
                args["skill_type"] = type_match.group(1).lower()
        # Name
        if not args["name"]:
            for pattern in _DEVELOP_NAME_PATTERNS:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    args["name"] = match.group(1)
                    break
        if args["name"] is None and args["code"]:
            args["name"] = "generated_skill"
        return args

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def process_input(
        self,
        request: str,
        request_data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """Route one request to the pipeline that serves it (Task 22.3).

        Returns ``(intent, result)``. This is the routing seam: it detects
        the intent and dispatches to :meth:`_handle_create_skill` (New Skill
        Pipeline), :meth:`_handle_use_skill` (Existing Skill Pipeline) or
        :meth:`_handle_general_query`. :meth:`handle_request` wraps it in the
        agent's response envelope.
        """
        intent = self.detect_intent(request)
        if intent == INTENT_CREATE_SKILL:
            return intent, self._handle_create_skill(request, request_data)
        if intent == INTENT_USE_SKILL:
            return intent, self._handle_use_skill(request, request_data)
        return intent, self._handle_general_query(request, request_data)

    def run(
        self,
        reader: Optional[Any] = None,
        writer: Optional[Any] = None,
    ) -> int:
        """Run an interactive read-eval-print loop (Task 24.2).

        ``reader`` and ``writer`` are injectable so the loop can be driven
        by a test without touching real stdin/stdout, matching the pattern
        used by the skill builder and the new-skill pipeline's review step.
        Returns the number of requests handled.
        """
        read = reader or input
        emit = writer or print
        handled = 0
        emit(f"{self.agent_name} ready. Type 'exit' to quit.")
        while True:
            try:
                line = read("> ")
            except (EOFError, KeyboardInterrupt):
                emit("")
                break
            if line is None:
                break
            line = str(line).strip()
            if not line:
                continue
            if line.lower() in {"exit", "quit", ":q"}:
                break
            response = self.handle_request(line)
            handled += 1
            emit(response.get("response") or "(no response)")
        emit(f"{self.agent_name} stopped after {handled} request(s).")
        return handled

    def handle_request(
        self,
        request: str,
        request_data: Optional[Dict[str, Any]] = None,
        include_dev: bool = True,
    ) -> Dict[str, Any]:
        """Handle one user request; always returns a stable result dict."""
        self.stats["requests"] += 1
        intent, result = self.process_input(request, request_data)
        skill_name = result.get("skill_name")
        # Computed once and reused for both the conversation-history record
        # (_remember_action) and the response payload below, so "what got
        # remembered" and "what the caller saw" can never drift apart.
        response_text = (
            result.get("message") or result.get("error") or ""
            if isinstance(result, dict)
            else str(result)
        )
        self._remember_action(intent, skill_name, request=request, response=response_text)
        try:
            self.memory.set(self.MEMORY_KEY_LAST_RESULT, result)
            self.memory.set(
                self.MEMORY_KEY_SKILL_COUNT,
                self.get_registry_status()["total_skills"],
            )
        except Exception:
            pass

        # "success" here means the request was handled without an unhandled
        # error -- an unrecognised intent is still handled successfully.  Whether
        # the requested operation itself succeeded is result["success"].
        response: Dict[str, Any] = {
            "intent": intent,
            "success": True,
            "skill_name": skill_name,
            "result": result,
            # Human-readable text for the CLI / Cline to surface directly.
            "response": response_text,
            "error": result.get("error") if isinstance(result, dict) else None,
        }
        if include_dev:
            response["registry_status"] = self.get_registry_status()
            response["skill"] = (
                self.registry.get_skill(skill_name) if skill_name else None
            )
        return response

    def _handle_use_skill(
        self, request: str, request_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        name, input_data = self.extract_skill_args(request, request_data)
        if not name:
            return {
                "success": False,
                "skill_name": None,
                "error": "No skill name found in the request.",
            }
        skill = self.registry.get_skill(name)
        if skill is None:
            return {
                "success": False,
                "skill_name": name,
                "error": f"Skill '{name}' is not registered (or inactive).",
            }
        # Task 22.2: execution goes through the Existing Skill Pipeline,
        # which owns parameter parsing, validation and per-type dispatch.
        # The agent keeps its own payload shape so callers are unaffected.
        try:
            routed = self.existing_pipeline.handle_request(
                request, skill_name=name, input_data=input_data
            )
            result = routed.get("execution") or {
                "success": False,
                "output": None,
                "error": "; ".join(routed.get("errors") or []) or routed.get("response"),
                "skill_type": None,
                "version": None,
                "execution_time_ms": 0.0,
            }
        except Exception as exc:  # noqa: BLE001 - agent must stay alive
            return {
                "success": False,
                "skill_name": name,
                "error": f"{type(exc).__name__}: {exc}",
            }
        self.stats["skills_used"] += 1
        succeeded = bool(result.get("success"))
        return {
            "success": succeeded,
            "skill_name": name,
            "output": result.get("output"),
            "error": result.get("error"),
            "skill_type": result.get("skill_type"),
            "version": result.get("version"),
            "execution_time_ms": result.get("execution_time_ms"),
            # Without this, handle_request()'s "response" (the human-readable
            # text surfaced by the CLI/Cline, and now also stored per-turn by
            # get_history()) was "" for every successful skill run -- the
            # single most common outcome -- because it falls back to
            # result.get("message") or result.get("error") or "", and this
            # dict had neither key on success.
            "message": (
                f"Skill '{name}' executed successfully."
                if succeeded
                else (result.get("error") or f"Skill '{name}' execution failed.")
            ),
        }

    def _handle_create_skill(
        self, request: str, request_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create a skill through the New Skill Pipeline (Task 22.1).

        The agent no longer builds and registers skills itself; it hands the
        request to the pipeline, which owns analysis, code generation, the
        QA gate and registration, then maps the pipeline's envelope back to
        the agent's payload shape.

        ``auto_confirm=True`` because the agent runs non-interactively - the
        interactive review belongs to the CLI and the skill builder, and a
        pipeline that called ``input()`` here would hang any caller.
        """
        from pipelines.new_skill_pipeline import (
            STATUS_ALREADY_EXISTS,
            STATUS_COMPLETED,
        )

        args = self.extract_develop_args(request, request_data)
        skill_type = args.get("skill_type") or "function"
        if skill_type not in ("function", "agent", "workflow"):
            skill_type = "function"
        name = args.get("name") or "new_skill"
        description = args.get("description") or request

        # The pipeline sanitizes an unusable name into a registry-safe one
        # (that is right when it is inferring a name from free text).  But
        # when the caller *states* a name, silently renaming it is wrong:
        # they asked for "@bad name!" and would get "bad_name" with no
        # indication.  Validate an explicitly supplied name and reject it.
        explicit_name = (request_data or {}).get("name")
        if explicit_name:
            check = self.registry.validate_skill(
                {"name": explicit_name, "type": skill_type, "code": "def run(): pass"}
            )
            if not check["valid"]:
                return {
                    "success": False, "created": False, "registered": False,
                    "skill_name": explicit_name, "skill": None,
                    "error": "Invalid skill: " + "; ".join(check["errors"]),
                }

        pipeline_data = dict(request_data or {})
        pipeline_data.update(
            {"name": name, "type": skill_type, "description": description}
        )
        if args.get("code"):
            pipeline_data["code"] = args["code"]

        try:
            outcome = self.new_pipeline.create_skill(
                request, request_data=pipeline_data, auto_confirm=True
            )
        except Exception as exc:  # noqa: BLE001 - agent must stay alive
            return {
                "success": False, "created": False, "registered": False,
                "skill_name": name, "skill": None,
                "error": f"Skill registration failed: {type(exc).__name__}: {exc}",
            }

        created_name = outcome.get("skill_name") or name
        if outcome["status"] == STATUS_ALREADY_EXISTS:
            return {
                "success": False,
                "created": False,
                "registered": False,
                "skill_name": created_name,
                "skill": self.registry.get_skill(created_name),
                "error": f"Skill '{created_name}' already exists",
                "suggestion": (
                    f"Skill '{created_name}' already exists; "
                    f"use 'use skill {created_name}'."
                ),
            }
        if outcome["status"] != STATUS_COMPLETED:
            return {
                "success": False,
                "created": False,
                "registered": False,
                "skill_name": created_name,
                "skill": outcome.get("skill"),
                "error": (
                    "; ".join(outcome.get("errors") or [])
                    or outcome.get("response")
                    or f"Skill '{created_name}' was rejected."
                ),
            }

        skill = outcome.get("skill") or self.registry.get_skill(created_name)
        version = skill.get("current_version") if isinstance(skill, dict) else None
        self.stats["skills_created"] += 1
        return {
            "success": True,
            "created": True,
            "registered": True,
            "skill_name": created_name,
            "skill": skill,
            "qa": outcome.get("qa"),
            "message": f"Skill '{created_name}' registered (v{version}).",
        }

    #: Pre-Task-22 name, kept so external callers keep working.
    _handle_develop_skill = _handle_create_skill

    def _handle_general_query(
        self, request: str, request_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Handle a request that matches neither pipeline (Task 22.3)."""
        offline = self.llm is None or getattr(self.llm, "is_offline", False)
        mode = (
            " (running offline: intent is matched with deterministic rules, "
            "not an LLM)"
            if offline
            else ""
        )
        return {
            "success": False,
            "skill_name": None,
            "message": (
                "I could not determine what you want to do"
                f"{mode}. "
                "Try 'use skill <name>' or 'develop a skill named <name>'."
            ),
        }

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def get_registry_status(self) -> Dict[str, Any]:
        try:
            skills = self.registry.list_skills()
            inactive = self.registry.list_skills(include_inactive=True)
            return {
                "total_skills": len(skills),
                "active_skills": len(skills),
                "inactive_skills": len(inactive) - len(skills),
            }
        except Exception:
            return {"total_skills": 0, "active_skills": 0, "inactive_skills": 0}

    def get_git_log(self, limit: int = 10) -> list:
        """Delegate to :meth:`GitManager.log`; empty list when no git is wired."""
        if self.git_manager is None:
            return []
        try:
            return self.git_manager.log(limit=limit)
        except GitManagerError:
            return []

    def get_stats(self) -> Dict[str, Any]:
        return dict(self.stats)