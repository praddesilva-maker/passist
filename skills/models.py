#!/usr/bin/env python3
"""
Skill Data Models.

Plain dataclasses shared by the registry, unified skill stage, skill builder,
pipelines and tests.  All JSON columns in the SQLite registry are stored using
the ``to_dict``/``from_dict`` helpers defined here.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

VALID_SKILL_TYPES = ("function", "agent", "workflow")


def utcnow_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SkillRecord:
    """A single registered skill (the active/latest version)."""

    name: str
    description: str = ""
    skill_type: str = "function"
    code: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    examples: List[Dict[str, Any]] = field(default_factory=list)
    version: int = 1
    created_at: str = field(default_factory=utcnow_iso)
    updated_at: str = field(default_factory=utcnow_iso)

    def __post_init__(self) -> None:
        if self.skill_type not in VALID_SKILL_TYPES:
            raise ValueError(
                f"Invalid skill type '{self.skill_type}'. "
                f"Must be one of {VALID_SKILL_TYPES}"
            )
        if not self.name or not str(self.name).strip():
            raise ValueError("Skill name is required")
        self.name = str(self.name).strip()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillRecord":
        allowed = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in allowed})

    def parameter_names(self) -> List[str]:
        return list(self.parameters.keys())


@dataclass
class SkillVersion:
    """One entry in a skill's version history."""

    skill_name: str
    version: int
    code: str = ""
    code_path: str = ""
    code_hash: str = ""
    git_commit: Optional[str] = None
    note: str = ""
    created_at: str = field(default_factory=utcnow_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SkillRun:
    """One execution log entry for a skill."""

    skill_name: str
    version: Optional[int] = None
    input_data: Dict[str, Any] = field(default_factory=dict)
    output: Any = None
    success: bool = True
    error: Optional[str] = None
    duration_ms: float = 0.0
    timestamp: str = field(default_factory=utcnow_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)