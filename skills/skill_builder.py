#!/usr/bin/env python3
"""
Skill Builder.

A small, registry-driven factory for creating *and interactively editing*
skills:

* ``SkillBuilder(registry)`` validates and registers skills *through* the
  central :class:`~skills.registry.SkillRegistry` only.
* There is **no filesystem discovery** and **no writes to
  ``skills/generated/``** - the SQLite registry is the single source of
  truth for skill code.
* :meth:`SkillBuilder.offline_template` produces deterministic, valid skill
  code so skill development keeps working when no ``GLM_API_KEY`` is
  configured (offline mode).
* :meth:`select_skill`, :meth:`describe_skill`, :meth:`edit_description`,
  :meth:`add_parameter`/:meth:`update_parameter`/:meth:`remove_parameter`
  and :meth:`edit_code` implement the interactive builder's basic
  features (selection, description editing, parameter editing, code
  editing). :meth:`run_interactive_session` wires them into a small
  terminal loop, following the same injectable-``input()`` pattern used by
  ``NewSkillPipeline._ask_confirmation`` elsewhere in this codebase.

Every public method returns a structured result dict
(``{"success": bool, "skill_name": ..., "error": ...}``); validation errors
raised by the registry are converted into error payloads instead of
propagating.
"""

import difflib
import json
import re
import sqlite3
from typing import Any, Callable, Dict, List, Optional

from .registry import RegistryError, SkillNotFoundError, SkillRegistry

#: Errors the builder converts into structured payloads rather than raising.
#: Task 13.4 requires handling database errors specifically - those surface
#: as ``sqlite3.Error``, which is *not* a ``RegistryError``, so catching only
#: the latter would let a locked or corrupt database escape as a traceback.
BUILDER_ERRORS = (RegistryError, sqlite3.Error, OSError)

# Canonical parameter types (kept in sync with
# ``pipelines/new_skill_pipeline.PARAMETER_TYPES``; duplicated rather than
# imported to avoid a skills -> pipelines layering dependency).
PARAMETER_TYPES = ("str", "int", "float", "bool", "list", "dict")


def _sanitize_name(name: str) -> str:
    """Reduce an arbitrary name to a registry-safe identifier fragment."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", str(name or "").strip())
    cleaned = cleaned.strip("_-") or "new_skill"
    if not re.match(r"^[A-Za-z0-9]", cleaned):
        cleaned = f"skill_{cleaned}"
    return cleaned


def _sanitize_description(description: Any) -> str:
    """Make a description safe to embed in a docstring."""
    text = str(description or "").strip()
    text = text.replace("\\", "").replace('"""', "'''")
    return " ".join(text.split()) or "New skill"


class SkillBuilder:
    """Registry-driven skill creation with structured payloads."""

    def __init__(self, registry: Optional[SkillRegistry] = None) -> None:
        self.registry = registry or SkillRegistry()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        code: str,
        skill_type: str = "function",
        description: str = "",
        parameters: Optional[Dict[str, Any]] = None,
        examples: Optional[List[Dict[str, Any]]] = None,
        note: str = "",
    ) -> Dict[str, Any]:
        """Validate and register a skill via the registry.

        Returns a structured payload instead of raising:
        ``{"success", "skill_name", "skill_type", "skill", "error"}``.
        """
        try:
            skill = self.registry.register_skill(
                name=name,
                skill_type=skill_type,
                description=description,
                code=code,
                parameters=parameters,
                examples=examples,
                note=note,
            )
        except BUILDER_ERRORS as exc:
            return {
                "success": False,
                "skill_name": name,
                "skill_type": skill_type,
                "skill": None,
                "error": f"{type(exc).__name__}: {exc}",
            }
        except Exception as exc:  # noqa: BLE001 - keep payloads structured
            return {
                "success": False,
                "skill_name": name,
                "skill_type": skill_type,
                "skill": None,
                "error": f"{type(exc).__name__}: {exc}",
            }
        return {
            "success": True,
            "skill_name": skill.get("name", name),
            "skill_type": skill.get("type", skill_type),
            "skill": skill,
            "error": None,
        }

    def list_skills(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """List skills known to the registry (no filesystem scan)."""
        return self.registry.list_skills(include_inactive=include_inactive)

    # ------------------------------------------------------------------
    # Skill selection UI (Task 12.1)
    # ------------------------------------------------------------------

    def format_skill_list(self, include_inactive: bool = False) -> str:
        """Render the registered skills as a numbered, human-readable list."""
        skills = self.list_skills(include_inactive=include_inactive)
        if not skills:
            return "No skills registered."
        lines = []
        for idx, skill in enumerate(skills, start=1):
            lines.append(
                f"{idx}. {skill.get('name')} [{skill.get('type')}] - "
                f"{skill.get('description') or '(no description)'}"
            )
        return "\n".join(lines)

    def select_skill(self, selector: Any) -> Dict[str, Any]:
        """Resolve a user's selection to a registered skill.

        ``selector`` may be a skill name, or a 1-based index into the list
        returned by :meth:`list_skills` (as shown by
        :meth:`format_skill_list`). Never raises: an empty selector, an
        unknown name, or an out-of-range index all come back as a
        structured ``{"success": False, "error": ...}`` payload instead of
        propagating, so callers (interactive or programmatic) can handle an
        invalid selection uniformly.
        """
        text = str(selector).strip() if selector is not None else ""
        if not text:
            return {"success": False, "skill": None, "error": "no skill selected"}

        if text.isdigit():
            skills = self.list_skills()
            idx = int(text)
            if 1 <= idx <= len(skills):
                return {"success": True, "skill": skills[idx - 1], "error": None}
            return {
                "success": False,
                "skill": None,
                "error": f"selection {idx} is out of range (1-{len(skills)})",
            }

        try:
            skill = self.registry.get_skill(text)
        except BUILDER_ERRORS as exc:
            return {
                "success": False,
                "skill": None,
                "error": f"{type(exc).__name__}: {exc}",
            }
        if skill is None:
            return {"success": False, "skill": None, "error": f"skill '{text}' not found"}
        return {"success": True, "skill": skill, "error": None}

    def describe_skill(self, selector: Any) -> Dict[str, Any]:
        """Return a display-ready description of a selected skill."""
        picked = self.select_skill(selector)
        if not picked["success"]:
            return {"success": False, "details": None, "skill": None, "error": picked["error"]}
        skill = picked["skill"]
        params = skill.get("parameters") or {}
        lines = [
            f"Name: {skill.get('name')}",
            f"Type: {skill.get('type')}",
            f"Version: {skill.get('current_version')}",
            f"Description: {skill.get('description') or '(none)'}",
        ]
        if params:
            lines.append("Parameters:")
            for pname, spec in params.items():
                spec = spec if isinstance(spec, dict) else {}
                ptype = spec.get("type", "str")
                pdesc = spec.get("description", "")
                lines.append(f"  - {pname} ({ptype}): {pdesc}")
        else:
            lines.append("Parameters: none")
        return {
            "success": True,
            "details": "\n".join(lines),
            "skill": skill,
            "error": None,
        }

    # ------------------------------------------------------------------
    # Description editing (Task 12.2)
    # ------------------------------------------------------------------

    def edit_description(self, name: str, new_description: str) -> Dict[str, Any]:
        """Validate and update a skill's description via the registry.

        Returns a structured payload showing the change
        (``old_description`` / ``new_description``); an empty description
        or a missing skill are reported as errors rather than raised.
        """
        error_payload = {
            "success": False,
            "skill_name": name,
            "old_description": None,
            "new_description": None,
            "skill": None,
            "error": None,
        }
        if not str(new_description or "").strip():
            error_payload["error"] = "description cannot be empty"
            return error_payload

        cleaned = _sanitize_description(new_description)
        existing = self.registry.get_skill(name)
        if existing is None:
            error_payload["error"] = f"skill '{name}' not found"
            return error_payload

        try:
            updated = self.registry.update_skill(
                name, description=cleaned, note="description update via builder"
            )
        except BUILDER_ERRORS as exc:
            error_payload["error"] = f"{type(exc).__name__}: {exc}"
            return error_payload

        return {
            "success": True,
            "skill_name": name,
            "old_description": existing.get("description", ""),
            "new_description": updated.get("description", cleaned),
            "skill": updated,
            "error": None,
        }

    # ------------------------------------------------------------------
    # Parameter editing (Task 12.3)
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_parameter(param_name: str, param_type: str) -> Optional[str]:
        if not param_name or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", param_name):
            return f"invalid parameter name: {param_name!r}"
        if param_type not in PARAMETER_TYPES:
            return (
                f"invalid parameter type: {param_type!r} "
                f"(must be one of {PARAMETER_TYPES})"
            )
        return None

    def list_parameters(self, name: str) -> Dict[str, Any]:
        """Return the current parameter declarations for a skill."""
        skill = self.registry.get_skill(name)
        if skill is None:
            return {"success": False, "parameters": None, "error": f"skill '{name}' not found"}
        return {"success": True, "parameters": dict(skill.get("parameters") or {}), "error": None}

    def add_parameter(
        self, name: str, param_name: str, param_type: str = "str", description: str = ""
    ) -> Dict[str, Any]:
        """Add a new parameter to a skill's declaration."""
        return self._edit_parameters(
            name,
            param_name,
            action="add",
            param_type=param_type,
            description=description,
        )

    def update_parameter(
        self,
        name: str,
        param_name: str,
        param_type: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Modify an existing parameter's type and/or description."""
        return self._edit_parameters(
            name,
            param_name,
            action="update",
            param_type=param_type,
            description=description,
        )

    def remove_parameter(self, name: str, param_name: str) -> Dict[str, Any]:
        """Delete a parameter from a skill's declaration."""
        return self._edit_parameters(name, param_name, action="remove")

    def _edit_parameters(
        self,
        name: str,
        param_name: str,
        action: str,
        param_type: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        error_payload = {
            "success": False,
            "skill_name": name,
            "parameters": None,
            "error": None,
        }
        skill = self.registry.get_skill(name)
        if skill is None:
            error_payload["error"] = f"skill '{name}' not found"
            return error_payload

        params: Dict[str, Any] = dict(skill.get("parameters") or {})

        if action == "add":
            effective_type = param_type or "str"
            invalid = self._validate_parameter(param_name, effective_type)
            if invalid:
                error_payload["error"] = invalid
                return error_payload
            if param_name in params:
                error_payload["error"] = (
                    f"parameter '{param_name}' already exists; use update_parameter"
                )
                return error_payload
            params[param_name] = {
                "type": effective_type,
                "description": description or "Parameter.",
            }
        elif action == "update":
            if param_name not in params:
                error_payload["error"] = f"parameter '{param_name}' not found"
                return error_payload
            current = dict(params[param_name]) if isinstance(params[param_name], dict) else {}
            new_type = param_type if param_type is not None else current.get("type", "str")
            invalid = self._validate_parameter(param_name, new_type)
            if invalid:
                error_payload["error"] = invalid
                return error_payload
            current["type"] = new_type
            if description is not None:
                current["description"] = description
            params[param_name] = current
        elif action == "remove":
            if param_name not in params:
                error_payload["error"] = f"parameter '{param_name}' not found"
                return error_payload
            del params[param_name]
        else:  # pragma: no cover - defensive, not reachable via public API
            error_payload["error"] = f"unknown parameter action: {action!r}"
            return error_payload

        try:
            updated = self.registry.update_skill(
                name, parameters=params, note=f"parameter {action} via builder"
            )
        except BUILDER_ERRORS as exc:
            error_payload["error"] = f"{type(exc).__name__}: {exc}"
            return error_payload

        return {
            "success": True,
            "skill_name": name,
            "parameters": updated.get("parameters", params),
            "skill": updated,
            "error": None,
        }

    # ------------------------------------------------------------------
    # Code editing (Task 12.4)
    # ------------------------------------------------------------------

    def get_code(self, name: str) -> Dict[str, Any]:
        """Return the current implementation code for a skill."""
        skill = self.registry.get_skill(name)
        if skill is None:
            return {"success": False, "code": None, "error": f"skill '{name}' not found"}
        return {"success": True, "code": skill.get("code", ""), "error": None}

    def edit_code(self, name: str, new_code: str, note: str = "") -> Dict[str, Any]:
        """Validate and update a skill's implementation code.

        Syntax is checked with :func:`compile` and the result is validated
        against :meth:`SkillRegistry.validate_skill` *before* anything is
        written, so an invalid edit never reaches the registry and the
        skill's previous code is left untouched. On success, a unified
        diff of the change is returned so callers can "show changes".
        """
        error_payload = {
            "success": False,
            "skill_name": name,
            "diff": None,
            "skill": None,
            "error": None,
        }
        existing = self.registry.get_skill(name)
        if existing is None:
            error_payload["error"] = f"skill '{name}' not found"
            return error_payload

        try:
            compile(new_code, f"<skill:{name}>", "exec")
        except SyntaxError as exc:
            error_payload["error"] = f"SyntaxError: {exc}"
            return error_payload

        validation = self.registry.validate_skill(
            {"name": name, "type": existing.get("type"), "code": new_code}
        )
        if not validation["valid"]:
            error_payload["error"] = "; ".join(validation["errors"])
            return error_payload

        old_code = existing.get("code", "")
        try:
            updated = self.registry.update_skill(
                name, code=new_code, note=note or "code update via builder"
            )
        except BUILDER_ERRORS as exc:
            error_payload["error"] = f"{type(exc).__name__}: {exc}"
            return error_payload

        diff = "\n".join(
            difflib.unified_diff(
                old_code.splitlines(),
                new_code.splitlines(),
                fromfile=f"{name} (old)",
                tofile=f"{name} (new)",
                lineterm="",
            )
        )
        return {
            "success": True,
            "skill_name": name,
            "old_code": old_code,
            "new_code": new_code,
            "diff": diff,
            "skill": updated,
            "error": None,
        }

    # ------------------------------------------------------------------
    # Interactive terminal loop (ties 12.1-12.4 together)
    # ------------------------------------------------------------------

    def run_interactive_session(
        self,
        input_func: Callable[[str], str] = input,
        output_func: Callable[[str], None] = print,
        selector: Any = None,
    ) -> Dict[str, Any]:
        """Drive a minimal terminal loop: select a skill, then edit it.

        ``input_func``/``output_func`` default to the builtins but accept
        injected stand-ins for testing - the same injectable-``input()``
        pattern ``NewSkillPipeline._ask_confirmation`` uses elsewhere in
        this codebase. An end-of-input condition (``EOFError``, e.g. a
        non-interactive stdin) is treated as "cancel", never as a crash.
        ``selector`` lets a caller skip the first selection prompt (e.g.
        the skill to edit is already known) while still handling an
        invalid value by falling back to the selection prompt.
        """

        def _read(prompt: str) -> Optional[str]:
            try:
                return input_func(prompt)
            except EOFError:
                return None

        picked = None
        pending_selector = selector
        while picked is None:
            if pending_selector is None:
                output_func(self.format_skill_list())
                pending_selector = _read(
                    "Select a skill (name or number, blank to cancel): "
                )
            if pending_selector is None or not str(pending_selector).strip():
                return {"success": False, "skill_name": None, "cancelled": True, "error": None}
            result = self.select_skill(pending_selector)
            if result["success"]:
                picked = result["skill"]
            else:
                output_func(f"Error: {result['error']}")
                pending_selector = None  # force a re-prompt next iteration

        name = picked["name"]
        output_func(self.describe_skill(name)["details"])

        while True:
            choice = _read("Edit (d)escription, (p)arameter, (c)ode, or (q)uit: ")
            if choice is None:
                return {"success": True, "skill_name": name, "cancelled": True, "error": None}
            choice = choice.strip().lower()

            if choice in ("", "q", "quit"):
                return {"success": True, "skill_name": name, "cancelled": False, "error": None}

            if choice in ("d", "description"):
                new_desc = _read("New description: ")
                if new_desc is None:
                    return {"success": True, "skill_name": name, "cancelled": True, "error": None}
                result = self.edit_description(name, new_desc)
                output_func("Updated description." if result["success"] else f"Error: {result['error']}")
            elif choice in ("p", "parameter", "parameters"):
                action = (_read("Add/Update/Remove parameter? (a/u/r): ") or "").strip().lower()
                pname = _read("Parameter name: ")
                if pname is None:
                    return {"success": True, "skill_name": name, "cancelled": True, "error": None}
                pname = pname.strip()
                if action in ("r", "remove"):
                    result = self.remove_parameter(name, pname)
                else:
                    ptype = (_read(f"Type ({', '.join(PARAMETER_TYPES)}): ") or "str").strip() or "str"
                    pdesc = _read("Description: ") or ""
                    if action in ("u", "update"):
                        result = self.update_parameter(name, pname, param_type=ptype, description=pdesc)
                    else:
                        result = self.add_parameter(name, pname, param_type=ptype, description=pdesc)
                output_func("Parameter updated." if result["success"] else f"Error: {result['error']}")
            elif choice in ("c", "code"):
                new_code = _read("New code: ")
                if new_code is None:
                    return {"success": True, "skill_name": name, "cancelled": True, "error": None}
                result = self.edit_code(name, new_code)
                output_func(result["diff"] or "(no changes)" if result["success"] else f"Error: {result['error']}")
            else:
                output_func("Unrecognised option, please choose again.")

    # ------------------------------------------------------------------
    # Offline template
    # ------------------------------------------------------------------

    @staticmethod
    def offline_template(name: str, description: str = "") -> str:
        """Deterministic skill code used when the LLM is unavailable.

        The generated code always passes
        :meth:`SkillRegistry.validate_skill` (top-level ``run`` function,
        valid identifier) and executes cleanly on the unified stage.
        """
        ident = re.sub(r"\W", "_", _sanitize_name(name)) or "new_skill"
        desc = _sanitize_description(description)
        # NOTE: built by concatenation, not str.format().  The generated code
        # contains a dict literal, and its braces would otherwise be parsed as
        # format replacement fields (KeyError at runtime).
        return (
            f'"""{desc}"""'
            "\n\n"
            "def run(input_value: str = \"\"):\n"
            f'    """{ident} (offline template): echo the request."""\n'
            "    return {\n"
            f'        "skill": "{ident}",\n'
            f'        "description": "{desc}",\n'
            '        "input": input_value,\n'
            '        "result": "OK",\n'
            "    }\n"
        )
    # ------------------------------------------------------------------
    # Task 13.1 — version management
    # ------------------------------------------------------------------

    def version_history(self, name: str) -> Dict[str, Any]:
        """Return a skill's version history, newest first (Task 13.1)."""
        if self.registry.get_skill(name) is None:
            return {
                "success": False, "skill_name": name, "versions": [],
                "error": f"skill '{name}' not found",
            }
        try:
            versions = self.registry.get_version_history(name)
        except BUILDER_ERRORS as exc:
            return {
                "success": False, "skill_name": name, "versions": [],
                "error": f"{type(exc).__name__}: {exc}",
            }
        return {
            "success": True, "skill_name": name, "versions": versions,
            "current_version": self.registry.get_skill(name).get("current_version"),
            "error": None,
        }

    def format_version_history(self, name: str) -> str:
        """Render a skill's version history for display (Task 13.1)."""
        result = self.version_history(name)
        if not result["success"]:
            return f"Cannot show history: {result['error']}"
        if not result["versions"]:
            return f"Skill '{name}' has no recorded versions."
        current = result.get("current_version")
        lines = [f"Version history for '{name}':"]
        for version in result["versions"]:
            number = version.get("version")
            marker = "  <- current" if number == current else ""
            note = str(version.get("note") or "").strip() or "(no note)"
            lines.append(
                f"  v{number}  {version.get('created_at', '')}  {note}{marker}"
            )
        return "\n".join(lines)

    def compare_versions(self, name: str, v1: int, v2: int) -> Dict[str, Any]:
        """Compare two versions of a skill (Task 13.1).

        Surfaces the registry's full comparison - code diff, metadata
        changes and parameter changes - rather than only the code diff.
        """
        try:
            comparison = self.registry.compare_versions(name, v1, v2)
        except (*BUILDER_ERRORS, SkillNotFoundError) as exc:
            return {
                "success": False, "skill_name": name, "diff": None,
                "error": f"{type(exc).__name__}: {exc}",
            }
        return {
            "success": True,
            "skill_name": name,
            "diff": comparison["diff"],
            "metadata_changes": comparison["metadata_changes"],
            "parameter_changes": comparison["parameter_changes"],
            "changed": comparison["changed"],
            "error": None,
        }

    def format_version_diff(self, name: str, v1: int, v2: int) -> str:
        """Render a version comparison for display (Task 13.1)."""
        result = self.compare_versions(name, v1, v2)
        if not result["success"]:
            return f"Cannot compare: {result['error']}"
        if not result["changed"]:
            return f"v{v1} and v{v2} of '{name}' are identical."
        lines = [f"Changes in '{name}' from v{v1} to v{v2}:"]
        for field, change in (result["metadata_changes"] or {}).items():
            lines.append(f"  {field}: {change['v1']!r} -> {change['v2']!r}")
        changes = result["parameter_changes"] or {}
        for label in ("added", "removed", "changed"):
            names = changes.get(label) or []
            if names:
                lines.append(f"  parameters {label}: {', '.join(names)}")
        if result["diff"]:
            lines.append("  code:")
            lines.extend(f"    {line}" for line in result["diff"].splitlines())
        return "\n".join(lines)

    def rollback(self, name: str, version: int) -> Dict[str, Any]:
        """Roll a skill back to an earlier version (Task 13.1).

        The registry restores the old code as a *new* version, so history
        is preserved rather than rewritten.
        """
        if self.registry.get_skill(name) is None:
            return {
                "success": False, "skill_name": name, "skill": None,
                "error": f"skill '{name}' not found",
            }
        try:
            restored = self.registry.rollback_to_version(name, version)
        except (*BUILDER_ERRORS, SkillNotFoundError) as exc:
            return {
                "success": False, "skill_name": name, "skill": None,
                "error": f"{type(exc).__name__}: {exc}",
            }
        return {
            "success": True,
            "skill_name": name,
            "skill": restored,
            "restored_from": version,
            "new_version": restored.get("current_version"),
            "error": None,
        }

    # ------------------------------------------------------------------
    # Task 13.2 — code export / import
    # ------------------------------------------------------------------

    def export_skill(self, name: str, indent: int = 2) -> Dict[str, Any]:
        """Export a skill as a portable JSON payload (Task 13.2).

        ``payload`` is the dict and ``json`` its formatted text, so a
        caller can either re-import the dict directly or write the text to
        a file.
        """
        try:
            payload = self.registry.export_skill(name)
        except (*BUILDER_ERRORS, SkillNotFoundError) as exc:
            return {
                "success": False, "skill_name": name, "payload": None,
                "json": None, "error": f"{type(exc).__name__}: {exc}",
            }
        return {
            "success": True,
            "skill_name": name,
            "payload": payload,
            "json": json.dumps(payload, indent=indent, sort_keys=True),
            "error": None,
        }

    def import_skill(self, payload: Any) -> Dict[str, Any]:
        """Import a skill from a payload or JSON text (Task 13.2).

        Accepts either a dict or a JSON string. The payload is validated
        before anything is written: it must decode to an object, carry a
        name and code, and pass the registry's own skill validation.
        """
        error = {
            "success": False, "skill_name": None, "skill": None, "error": None,
        }
        if isinstance(payload, (str, bytes)):
            try:
                payload = json.loads(payload)
            except (ValueError, TypeError) as exc:
                error["error"] = f"payload is not valid JSON: {exc}"
                return error
        if not isinstance(payload, dict):
            error["error"] = "payload must be a JSON object"
            return error

        name = str(payload.get("name") or "").strip()
        code = payload.get("code") or ""
        error["skill_name"] = name or None
        if not name:
            error["error"] = "payload is missing 'name'"
            return error
        if not str(code).strip():
            error["error"] = "payload is missing 'code'"
            return error

        try:
            compile(code, f"<import:{name}>", "exec")
        except SyntaxError as exc:
            error["error"] = f"SyntaxError: {exc}"
            return error

        validation = self.registry.validate_skill(
            {
                "name": name,
                "type": payload.get("type", "function"),
                "code": code,
            }
        )
        if not validation["valid"]:
            error["error"] = "; ".join(validation["errors"])
            return error

        try:
            skill = self.registry.import_skill(payload)
        except BUILDER_ERRORS as exc:
            error["error"] = f"{type(exc).__name__}: {exc}"
            return error
        return {
            "success": True, "skill_name": name, "skill": skill, "error": None,
        }

    # ------------------------------------------------------------------
    # Task 13.3 — skill templates
    # ------------------------------------------------------------------

    @staticmethod
    def _function_template(ident: str, desc: str) -> str:
        return (
            f'"""{desc}"""'
            "\n\n"
            'def run(input_value: str = "") -> str:\n'
            f'    """{ident}: transform the input and return a result."""\n'
            "    return str(input_value)\n"
        )

    @staticmethod
    def _agent_template(ident: str, desc: str) -> str:
        return (
            f'"""{desc}"""'
            "\n\n"
            'def run(question: str = "") -> dict:\n'
            f'    """{ident}: answer a question.\n'
            "\n"
            "    The unified stage supplies the model and tools when this\n"
            "    skill is loaded as an agent; this body is the offline,\n"
            "    dependency-free default so the skill always executes.\n"
            '    """\n'
            "    return {\n"
            f'        "skill": "{ident}",\n'
            '        "question": question,\n'
            '        "answer": "",\n'
            "    }\n"
        )

    @staticmethod
    def _workflow_template(ident: str, desc: str) -> str:
        return (
            f'"""{desc}"""'
            "\n\n"
            "STEPS = (\"prepare\", \"process\", \"finish\")\n"
            "\n"
            'def run(payload: str = "") -> list:\n'
            f'    """{ident}: run each step in order and collect results."""\n'
            "    results = []\n"
            "    for step in STEPS:\n"
            '        results.append({"step": step, "payload": payload})\n'
            "    return results\n"
        )

    #: Template builders by canonical skill type (Task 13.3).
    TEMPLATES = {
        "function": "_function_template",
        "agent": "_agent_template",
        "workflow": "_workflow_template",
    }

    @classmethod
    def available_templates(cls) -> List[str]:
        """Names of the templates a caller may select (Task 13.3)."""
        return sorted(cls.TEMPLATES)

    def template_for(
        self, skill_type: str, name: str, description: str = ""
    ) -> Dict[str, Any]:
        """Return template code for ``skill_type`` (Task 13.3).

        Every template produces code that passes
        :meth:`SkillRegistry.validate_skill` and executes with no network
        access, so a skill built from one works offline immediately.
        """
        builder = self.TEMPLATES.get(str(skill_type or "").strip().lower())
        if builder is None:
            return {
                "success": False, "skill_type": skill_type, "code": None,
                "error": (
                    f"unknown template {skill_type!r}; choose one of: "
                    + ", ".join(self.available_templates())
                ),
            }
        ident = re.sub(r"\W", "_", _sanitize_name(name)) or "new_skill"
        code = getattr(self, builder)(ident, _sanitize_description(description))
        return {
            "success": True, "skill_type": skill_type, "code": code,
            "error": None,
        }

    def create_from_template(
        self,
        name: str,
        skill_type: str = "function",
        description: str = "",
        **register_kwargs: Any,
    ) -> Dict[str, Any]:
        """Register a new skill built from a template (Task 13.3)."""
        template = self.template_for(skill_type, name, description)
        if not template["success"]:
            return {
                "success": False, "skill_name": name, "skill": None,
                "error": template["error"],
            }
        return self.register(
            name=name,
            code=template["code"],
            skill_type=skill_type,
            description=description,
            **register_kwargs,
        )
