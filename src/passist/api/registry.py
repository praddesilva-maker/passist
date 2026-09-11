"""
Tool registry for passist framework.
This is the single source of truth for all available tools.
"""

from dataclasses import dataclass
from typing import Callable, Any
from pydantic import BaseModel

@dataclass(frozen=True)
class ToolSpec:
    name: str                       # unique, e.g. "getThing"
    description: str                # prose used verbatim in generated TOOLS.md
    side_effect: bool               # True = write; requires confirm=True to run
    input_model: type[BaseModel]    # pydantic model = the arg schema (zod equivalent)
    run: Callable[[BaseModel], Any] # pure-ish function: validated args -> JSON-able data

# Import tools - these will be defined below
from .tools.get_thing import spec as get_thing_spec
from .tools.update_thing import spec as update_thing_spec
from .tools.use_capability_final import spec as use_capability_spec

TOOLS: list[ToolSpec] = [
    get_thing_spec,
    update_thing_spec,
    use_capability_spec,
]

TOOLS_BY_NAME = {t.name: t for t in TOOLS}