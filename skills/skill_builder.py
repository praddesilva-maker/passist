#!/usr/bin/env python3
"""
Skill Builder.

A small, registry-driven factory for creating new skills:

* ``SkillBuilder(registry)`` validates and registers skills *through* the
  central :class:`~skills.registry.SkillRegistry` only.
* There is **no filesystem discovery** and **no writes to
  ``skills/generated/``** - the SQLite registry is the single source of
  truth for skill code.
* :meth:`SkillBuilder.offline_template` produces deterministic, valid skill
  code so skill development keeps working when no ``GLM_API_KEY`` is
  configured (offline mode).

Every public method returns a structured result dict
(``{"success": bool, "skill_name": ..., "error": ...}``); validation errors
raised by the registry are converted into error payloads instead of
propagating.
"""

import re
from typing import Any, Dict, List, Optional

from .registry import SkillRegistry, RegistryError


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
        except RegistryError as exc:
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