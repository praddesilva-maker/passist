#!/usr/bin/env python3
"""
New Skill Pipeline — Intent Analysis (Task 7, guide §1.8.8).

This module is the first stage of the New Skill Development pipeline.  It
classifies an incoming user request into exactly one of three intents:

* ``"create_skill"`` — the user wants to create/develop a new skill.
* ``"use_skill"`` — the user wants to run an existing skill.  That work
  belongs to the Existing Skill Pipeline; it is detected here so a router
  can hand the request over instead of treating it as a creation request.
* ``"general"`` — everything else: questions, greetings, chit-chat.

When an LLM client (see :mod:`agent.llm`) is configured and able to
generate, the LLM classifies the request; a missing LLM, an offline model
(``is_offline``), or any LLM failure falls back to deterministic
keyword + regex rules, so the pipeline is fully operational offline.

The vocabulary deliberately mirrors the main agent's
``develop_skill`` / ``use_skill`` / ``unknown`` intents under the guide's
pipeline names (``create_skill`` / ``use_skill`` / ``general``).  Task 7
delivers intent analysis; Task 8 adds skill-structure generation
(:meth:`NewSkillPipeline.analyze_request`), with code generation,
interactive review, testing and registration following in Tasks 9-11, and
wiring into :class:`agent.main_agent.MainAgent` in Task 22.
"""

import json
import re
from typing import Any, Dict, List, Optional, Union

# ---------------------------------------------------------------------------
# Intent vocabulary (stable; documented in PERSONAL_ASSISTANT_GUIDE.md §1.8.8)
# ---------------------------------------------------------------------------

INTENT_CREATE_SKILL = "create_skill"
INTENT_USE_SKILL = "use_skill"
INTENT_GENERAL = "general"

ALL_INTENTS = (INTENT_CREATE_SKILL, INTENT_USE_SKILL, INTENT_GENERAL)

# ---------------------------------------------------------------------------
# Skill-structure vocabulary (Task 8, guide §1.8.9)
# ---------------------------------------------------------------------------

# Canonical structure-level types, mirroring the registry's execution types
# (``function`` / ``agent`` / ``workflow``, see ``skills/registry.py``).  The
# type is decided here, in analysis (guide §1.8.9 Task 8.2: "Support function
# skills / agent skills / workflow skills"); Task 9's code generators
# (``_generate_function_code`` / ``_generate_agent_code`` /
# ``_generate_workflow_code``) consume exactly these values, and an invalid
# or missing type always falls back to ``function``.
SKILL_TYPE_FUNCTION = "function"
SKILL_TYPE_AGENT = "agent"
SKILL_TYPE_WORKFLOW = "workflow"
CANONICAL_SKILL_TYPES = (
    SKILL_TYPE_FUNCTION,
    SKILL_TYPE_AGENT,
    SKILL_TYPE_WORKFLOW,
)

# Simple, JSON-friendly parameter types accepted in a generated structure.
PARAMETER_TYPES = ("str", "int", "float", "bool", "list", "dict")

# Default parameters offered when a request declares none.
DEFAULT_PARAMETERS = {
    "input": {
        "description": "Primary input value for the skill.",
        "type": "str",
    },
}

# Default structure returned when a request declares no outputs.
DEFAULT_RETURNS = {
    "result": {
        "description": "Primary output value of the skill.",
        "type": "str",
    },
}

# Signals that the user wants to *create* a new skill.
_CREATE_KEYWORDS = (
    "develop skill", "develop a skill", "develop the skill",
    "develop new skill",
    "create skill", "create a skill", "create new skill",
    "add skill", "add a skill", "make a skill", "build a skill",
    "write a skill", "make me a skill", "build me a skill",
    "create function", "create agent", "create workflow",
    "want a skill", "want a new skill", "need a skill", "need a new skill",
    "like a skill",
)

_CREATE_PATTERNS = (
    # develop/create/make/build/write/add [a|new|the] [adjective(s)] skill
    r"\b(?:develop|create|make|build|write|add)\s+"
    r"(?:a\s+|new\s+|the\s+)?(?:[A-Za-z]+\s+){0,2}skill\b",
    # I want/need/like [a|some] [new] [adjective(s)] skill
    r"\b(?:want|need|like|would\s+like)\s+"
    r"(?:a\s+|some\s+)?(?:new\s+)?(?:[A-Za-z]+\s+){0,2}skill\b",
)

# Signals that the user wants to *use* an existing skill.
_USE_KEYWORDS = (
    "use skill", "run skill", "execute skill", "call skill",
    "do skill", "apply skill", "use the skill", "use my skill",
    "run the skill",
)

_USE_PATTERNS = (
    # use/run/execute/call/do/apply [the|my|a] [adjective(s)] skill
    r"\b(?:use|run|execute|call|do|apply)\s+"
    r"(?:the\s+|my\s+|a\s+)?(?:[A-Za-z]+\s+){0,2}skill\b",
)


# ---------------------------------------------------------------------------
# Deterministic structure helpers (Task 8 — offline / fallback paths)
# ---------------------------------------------------------------------------


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Extract the first JSON object from arbitrary text.

    Handles bare JSON objects, JSON wrapped in markdown code fences, and JSON
    embedded inside a longer LLM answer.  Returns ``None`` when no object
    can be parsed.
    """
    if not isinstance(text, str):
        return None
    stripped = text.strip()
    candidates = [stripped]
    fences = re.findall(r"```[a-zA-Z]*\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidates.extend(fences)
    # Longest braces object last-to-first: prefer the largest candidate so a
    # trailing comment object does not shadow the real payload.
    brace_matches = re.findall(r"\{.*\}", text, re.DOTALL)
    brace_matches.sort(key=len, reverse=True)
    candidates.extend(brace_matches)
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except (ValueError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _derive_name_from_request(text: str) -> str:
    """Deterministically derive a registry-safe skill name from a request.

    Preference order: an explicitly named skill ("named/called ``x``"),
    then the meaningful words of the request.  The result always matches
    the registry name rule ``^[A-Za-z][A-Za-z0-9_]*$``.
    """
    lowered = (text or "").lower()
    named = re.search(
        r"\bnamed\s+['\"]?([A-Za-z][A-Za-z0-9_\-]*)|called\s+['\"]?"
        r"([A-Za-z][A-Za-z0-9_\-]*)",
        lowered,
    )
    if named:
        raw_name = named.group(1) or named.group(2)
    else:
        words = re.findall(r"[a-z][a-z0-9_]*", lowered)
        stop = {
            "a", "an", "the", "that", "which", "named", "called", "skill",
            "new", "simple", "make", "make me", "build", "develop", "create",
            "write", "add", "i", "you", "please", "can", "would", "like",
            "want", "need", "me", "my", "to", "for", "of", "in", "on",
        }
        picked = []
        for word in words:
            if word in stop or len(word) < 3:
                continue
            if word not in picked:
                picked.append(word)
            if len(picked) >= 3:
                break
        raw_name = "_".join(picked)
    cleaned = re.sub(r"[^a-z0-9_]+", "_", (raw_name or "").lower()).strip("_")
    cleaned = re.sub(r"_+", "_", cleaned) or "new_skill"
    if not cleaned[0].isalpha():
        cleaned = f"skill_{cleaned}"
    return cleaned


def _derive_description_from_request(text: str) -> str:
    """Build a safe, single-line description from the raw request text."""
    clean = re.sub(r"\s+", " ", (text or "").strip()).strip().strip("\"'")
    clean = re.sub(r"^\s*(develop|create|make|build|write|add)\s+"
                   r"(?:a\s+|new\s+|the\s+)?", "", clean, flags=re.IGNORECASE)
    return (clean or "New skill").strip() or "New skill"


def _derive_type_from_request(text: str) -> str:
    """Determine the skill type deterministically from request wording.

    When the request explicitly asks for a workflow or an agent, that
    type is chosen; everything else defaults to ``function`` so the
    deterministic fallback never invents a structure the user did not
    ask for.  The result is always a canonical skill type.
    """
    lowered = (text or "").lower()
    if "workflow" in lowered:
        return SKILL_TYPE_WORKFLOW
    if "agent" in lowered:
        return SKILL_TYPE_AGENT
    return SKILL_TYPE_FUNCTION


def _canonicalize_skill_type(value: Any) -> str:
    """Map any requested type onto a canonical skill type.

    Accepts the canonical names (``function`` / ``agent`` / ``workflow``)
    and a handful of close synonyms.  Anything unrecognized becomes
    ``function`` so an invalid LLM answer can never produce an unusable
    structure.
    """
    lowered = str(value or "").strip().lower()
    aliases = {
        "function": SKILL_TYPE_FUNCTION,
        "func": SKILL_TYPE_FUNCTION,
        "tool": SKILL_TYPE_FUNCTION,
        "simple": SKILL_TYPE_FUNCTION,
        "basic": SKILL_TYPE_FUNCTION,
        "agent": SKILL_TYPE_AGENT,
        "autonomous": SKILL_TYPE_AGENT,
        "sub-agent": SKILL_TYPE_AGENT,
        "subagent": SKILL_TYPE_AGENT,
        "workflow": SKILL_TYPE_WORKFLOW,
        "pipeline": SKILL_TYPE_WORKFLOW,
        "multi-step": SKILL_TYPE_WORKFLOW,
        "multistep": SKILL_TYPE_WORKFLOW,
        "sequence": SKILL_TYPE_WORKFLOW,
    }
    return aliases.get(lowered, SKILL_TYPE_FUNCTION)


def _coerce_parameter_entry(value: Any) -> Optional[Dict[str, str]]:
    """Coerce one parameter declaration into ``{description, type}``.

    Accepts a dict (keys ``description`` / ``type`` or ``name``), a
    ``"name: type"`` string, or a bare string (treated as the name with a
    string type).  Returns ``None`` when nothing usable remains.
    """
    if isinstance(value, dict):
        description = str(
            value.get("description") or value.get("desc") or ""
        ).strip()
        ptype = str(value.get("type") or "str").strip().lower()
        if ptype not in PARAMETER_TYPES:
            ptype = "str"
        if not description:
            description = "Parameter."
        return {"description": description, "type": ptype}
    if isinstance(value, str):
        if ":" in value:
            _, _, ptype = value.partition(":")
            ptype = ptype.strip().lower()
            if ptype not in PARAMETER_TYPES:
                ptype = "str"
        else:
            ptype = "str"
        return {"description": "Parameter.", "type": ptype}
    return None


def _coerce_parameters(value: Any) -> Dict[str, Dict[str, str]]:
    """Coerce a whole parameter declaration into the canonical shape.

    Accepts a mapping of ``name -> declaration`` (where a declaration is a
    dict, a ``"name: type"`` string, or ``None``), a JSON string of such a
    mapping, or ``None``.  Unknown parameter names are sanitized to valid
    identifiers; non-dict leftovers fall back to the ``input`` default.
    """
    if isinstance(value, str):
        parsed = _extract_json_object(value)
        value = parsed if parsed is not None else {}
    if not isinstance(value, dict):
        return dict(DEFAULT_PARAMETERS)
    params: Dict[str, Dict[str, str]] = {}
    for key, entry in value.items():
        name = re.sub(r"\W", "_", str(key).strip()).strip("_") or "parameter"
        if not name[0].isalpha():
            name = f"parameter_{name}"
        if name in params:
            continue
        coerced = _coerce_parameter_entry(entry)
        if coerced is None:
            coerced = {"description": "Parameter.", "type": "str"}
        params[name] = coerced
    return params or dict(DEFAULT_PARAMETERS)


def _coerce_returns(value: Any) -> Dict[str, Dict[str, str]]:
    """Coerce a ``returns`` declaration like :func:`_coerce_parameters`."""
    if isinstance(value, str):
        value = _extract_json_object(value) or {}
    if not isinstance(value, dict):
        return dict(DEFAULT_RETURNS)
    coerced = _coerce_parameters(value)
    # A ``returns`` block that lost every entry falls back to a single
    # ``result`` entry rather than reusing the input-parameter defaults.
    if set(coerced) == {"input"}:
        return dict(DEFAULT_RETURNS)
    return coerced


def _coerce_requires(value: Any) -> Dict[str, Any]:
    """Coerce a ``requires`` declaration into a JSON-serializable dict.

    Accepts a mapping, a list of skill names (kept under ``skills``), or
    ``None`` (empty dict).
    """
    if isinstance(value, str):
        value = _extract_json_object(value)
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        names = [str(item).strip() for item in value if str(item).strip()]
        return {"skills": names} if names else {}
    return {}


# ---------------------------------------------------------------------------
# Creation-flow statuses (Task 11, guide §1.8.12)
# ---------------------------------------------------------------------------

# Distinct terminal statuses for :meth:`NewSkillPipeline.create_skill`.
# Each outcome of the creation flow has its own status so callers can tell
# "registered", "QA rejected", "registry rejected", "name already taken
# (idempotent no-op)" and "unexpected error" apart.
STATUS_COMPLETED = "completed"
STATUS_QA_FAILED = "qa_failed"
STATUS_REGISTRATION_FAILED = "registration_failed"
STATUS_ALREADY_EXISTS = "already_exists"
STATUS_CANCELLED = "cancelled"
STATUS_EDIT_REQUESTED = "edit_requested"
STATUS_ERROR = "error"

ALL_STATUSES = (
    STATUS_COMPLETED,
    STATUS_QA_FAILED,
    STATUS_REGISTRATION_FAILED,
    STATUS_ALREADY_EXISTS,
    STATUS_CANCELLED,
    STATUS_EDIT_REQUESTED,
    STATUS_ERROR,
)

# Fallback smoke-test input for a skill that declares no parameters.  The
# generated ``run`` for a parameterless skill takes ``input_value``; skills
# that declare parameters get an input derived from them by
# :meth:`NewSkillPipeline._qa_input_for` instead.
DEFAULT_QA_INPUT = {"input_value": "qa-gate"}

# Representative smoke-test values per declared parameter type.
_QA_SAMPLE_VALUES = {
    "str": "qa-gate",
    "int": 1,
    "float": 1.0,
    "bool": True,
    "list": [],
    "dict": {},
}


# Type-appropriate placeholder literals for a generated skill's return value.
_PLACEHOLDER_LITERALS = {
    "str": '""',
    "int": "0",
    "float": "0.0",
    "bool": "False",
    "list": "[]",
    "dict": "{}",
}


def _placeholder_literal(type_name: Any) -> str:
    """Source text for a placeholder value of ``type_name``.

    The generated ``run`` bodies must bind their return variable before
    returning it - emitting a bare ``return result`` names an undefined
    variable and raises ``NameError`` the moment the skill executes.
    """
    return _PLACEHOLDER_LITERALS.get(str(type_name), "None")


def _parameters_from_code(code: str) -> Optional[Dict[str, Dict[str, str]]]:
    """Derive declared parameters from a hand-written skill's own signature.

    When a caller supplies the implementation, the analysed structure's
    generated parameters describe a function that was never written. The
    registry would then advertise a parameter the code does not take (and
    miss the ones it does), and the skill becomes uncallable through the
    existing-skill pipeline, which validates against that metadata.

    Returns ``None`` if the code cannot be parsed or defines no entry point,
    so the caller can fall back to the analysed structure.
    """
    import ast as _ast

    try:
        tree = _ast.parse(code)
    except SyntaxError:
        return None
    functions = [n for n in tree.body if isinstance(n, _ast.FunctionDef)]
    if not functions:
        return None
    by_name = {f.name: f for f in functions}
    entry = by_name.get("run") or by_name.get("main") or functions[0]

    annotation_types = {
        "str": "str", "int": "int", "float": "float",
        "bool": "bool", "list": "list", "dict": "dict",
    }
    parameters: Dict[str, Dict[str, str]] = {}
    args = list(entry.args.args)
    defaults = list(entry.args.defaults)
    first_default = len(args) - len(defaults)
    for index, arg in enumerate(args):
        if arg.arg in ("self", "cls"):
            continue
        declared = "str"
        annotation = getattr(arg, "annotation", None)
        if isinstance(annotation, _ast.Name):
            declared = annotation_types.get(annotation.id, "str")
        entry_info: Dict[str, str] = {
            "description": f"Parameter '{arg.arg}' of the supplied implementation.",
            "type": declared,
        }
        if index >= first_default:
            default_node = defaults[index - first_default]
            try:
                entry_info["default"] = _ast.literal_eval(default_node)
            except (ValueError, SyntaxError):
                pass
        parameters[arg.arg] = entry_info
    return parameters


class NewSkillPipeline:
    """Intent-analysis stage of the New Skill Development pipeline.

    * :meth:`detect_intent` — public classifier (counts requests in
      ``self.stats``), backed by the guide-named :meth:`_detect_intent`.
    * :meth:`analyze_request` — Task 8: analyzes a creation request into a
      normalized, registry-compatible skill structure (LLM-first,
      deterministic fallback).
    * :meth:`handle_request` — stable routing envelope used by
      demonstrations and by the main-agent wiring (Task 22).

    Construction takes only what intent analysis needs (an optional LLM);
    Tasks 8-11 will extend the pipeline with the rest of the creation flow.
    """

    def __init__(
        self,
        llm: Any = None,
        registry: Optional[Any] = None,
        builder: Optional[Any] = None,
        qa: Optional[Any] = None,
        review_callback: Optional[Any] = None,
    ) -> None:
        self.llm = llm
        self.stats = {
            "requests": 0,
            INTENT_CREATE_SKILL: 0,
            INTENT_USE_SKILL: 0,
            INTENT_GENERAL: 0,
            "analyze_total": 0,
            "analyze_llm_used": 0,
            "analyze_fallback": 0,
            "create_total": 0,
            STATUS_COMPLETED: 0,
            STATUS_QA_FAILED: 0,
            STATUS_REGISTRATION_FAILED: 0,
            STATUS_ALREADY_EXISTS: 0,
            STATUS_CANCELLED: 0,
            STATUS_EDIT_REQUESTED: 0,
            STATUS_ERROR: 0,
        }
        # Lazily-built dependencies for the creation flow (Task 11).  The
        # constructor stays backward-compatible: intent analysis (Tasks
        # 7-8) and structure generation (Task 8) never need a registry.
        self._registry = registry
        self._builder = builder
        self._qa = qa
        self._review_callback = review_callback

    # ------------------------------------------------------------------
    # Intent detection
    # ------------------------------------------------------------------

    def detect_intent(self, request: str) -> str:
        """Classify ``request`` into one of :data:`ALL_INTENTS`.

        Counts the request (and the resulting intent) in ``self.stats``.
        """
        intent = self._detect_intent(request)
        self.stats["requests"] += 1
        self.stats[intent] += 1
        return intent

    def _detect_intent(self, request: str) -> str:
        """Core classifier: LLM when available, deterministic rules otherwise.

        An empty/whitespace-only request is ``general`` (there is nothing to
        classify).  When an LLM is configured and not offline it is asked to
        pick one of :data:`ALL_INTENTS`; any failure or unparseable answer
        falls back to :meth:`_detect_intent_heuristic`.
        """
        text = (request or "").strip()
        if not text:
            return INTENT_GENERAL
        if self.llm is not None and not getattr(self.llm, "is_offline", False):
            intent = self._detect_intent_llm(text)
            if intent:
                return intent
        return self._detect_intent_heuristic(text)

    def _detect_intent_llm(self, text: str) -> Optional[str]:
        """Ask the LLM to classify ``text``; ``None`` if the answer is unusable."""
        # Lazy import: keeps the pipeline importable without the agent package
        # (same pattern as skills/qa_skill.py).
        from agent.llm import extract_text

        prompt = (
            "Classify the user request into exactly one of: "
            f"'{INTENT_CREATE_SKILL}', '{INTENT_USE_SKILL}', '{INTENT_GENERAL}'. "
            "Return only the intent string, nothing else.\n\n"
            f"Request: {text!r}"
        )
        try:
            response = self.llm.invoke(prompt)
        except Exception:  # noqa: BLE001 - any LLM failure falls back
            return None
        raw = extract_text(response).strip().strip("`\"' \n")
        for intent in ALL_INTENTS:
            if intent in raw.lower():
                return intent
        return None

    @staticmethod
    def _match(text: str, keywords: tuple, patterns: tuple) -> bool:
        """True when ``text`` contains a keyword (word-bounded) or pattern."""
        for keyword in keywords:
            if re.search(r"\b" + re.escape(keyword) + r"\b", text):
                return True
        for pattern in patterns:
            if re.search(pattern, text):
                return True
        return False

    @classmethod
    def _detect_intent_heuristic(cls, text: str) -> str:
        """Deterministic offline classifier (keyword + regex rules).

        ``create_skill`` is checked before ``use_skill`` so that a request
        like "develop a skill that uses the echo skill" classifies as a
        creation request, not a use request.  Anything unmatched is
        ``general`` — ambiguous phrasing must not trigger a pipeline.
        """
        lowered = text.lower()
        if cls._match(lowered, _CREATE_KEYWORDS, _CREATE_PATTERNS):
            return INTENT_CREATE_SKILL
        if cls._match(lowered, _USE_KEYWORDS, _USE_PATTERNS):
            return INTENT_USE_SKILL
        return INTENT_GENERAL

    # ------------------------------------------------------------------
    # Skill structure generation (Task 8, guide §1.8.9)
    # ------------------------------------------------------------------

    _STRUCTURE_PROMPT = (
        "You convert a user's skill-creation request into a normalized skill "
        "structure.  Return ONLY a JSON object (no prose, no markdown) with "
        "exactly these keys:\n"
        '  "name": a short identifier starting with a letter (use [a-z0-9_] '
        'only, e.g. "text_summarizer"),\n'
        '  "description": one or two sentences describing what the skill does,\n'
        '  "type": one of "function", "agent", "workflow",\n'
        '  "parameters": an object mapping each parameter name to an object '
        'with "description" and "type" (type one of str|int|float|bool|'
        "list|dict),\n"
        '  "returns": an object like "parameters" describing the skill '
        "outputs,\n"
        '  "requires": an object of dependencies; {{}} when there are none.\n'
        "Guidance: 'function' is a single self-contained operation; 'agent' "
        "is an autonomous, tool-using assistant skill; 'workflow' is a "
        "multi-step process chaining several skills.\n\n"
        "Request: {request!r}"
    )

    def analyze_request(
        self,
        request: str,
        request_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Analyze a creation request into a normalized skill structure.

        Produces a registry-compatible structure::

            {
                "name": str,            # registry-safe identifier
                "description": str,     # non-empty
                "type": "function" | "agent" | "workflow",
                "parameters": {name: {"description": str, "type": str}},
                "requires": dict,       # dependencies; {} when none
                "returns": {name: {"description": str, "type": str}},
            }

        When an LLM is configured and able to generate it proposes the
        structure; any missing LLM, offline model, LLM failure, unparseable
        answer, or invalid field falls back to a deterministic structure
        derived from the request text, so a well-formed result is always
        returned.  ``request_data`` may carry pre-filled ``name`` /
        ``description`` / ``type`` / ``parameters`` values that take
        priority over the generated ones.

        Counts the analysis in ``self.stats`` (``analyze_total`` and either
        ``analyze_llm_used`` or ``analyze_fallback``).
        """
        text = (request or "").strip()
        explicit = request_data if isinstance(request_data, dict) else {}
        if self.llm is not None and not getattr(self.llm, "is_offline", False):
            structure = self._analyze_request_llm(text, explicit)
            used_llm = structure is not None
        else:
            structure = None
            used_llm = False
        if structure is None:
            structure = self._analyze_request_fallback(text, explicit)
        self.stats["analyze_total"] += 1
        if used_llm:
            self.stats["analyze_llm_used"] += 1
        else:
            self.stats["analyze_fallback"] += 1
        return structure

    # ------------------------------------------------------------------
    # Code generation helpers – Task 9 implementations
    # ------------------------------------------------------------------
    def _generate_function_code(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        returns: Dict[str, Any],
        requires: Dict[str, Any],
    ) -> str:
        """Generate a minimal function‑skill source file.

        The generated code is a simple Python module that imports
        :func:`tool` from :mod:`langchain.tools` and defines a ``run``
        function with the provided signature, exported as a LangChain tool
        (installed LangChain 1.x: ``tool`` takes a single positional name
        plus a ``description`` keyword).  The function body simply returns
        a placeholder value – the real implementation will be provided by
        the user.
        """

        param_lines = []
        for pname, pinfo in parameters.items():
            ptype = pinfo.get("type", "str")
            param_lines.append(f"{pname}: {ptype}")
        param_str = ", ".join(param_lines) or "input_value: str = ''"

        return_key = list(returns.keys())[0]
        return_type = list(returns.values())[0].get("type", "str")
        code = (
            "from langchain.tools import tool\n"
            "\n"
            "def run(" + param_str + ") -> " + return_type + ":\n"
            '    """Placeholder implementation for ' + name + '."""\n'
            "    " + return_key + ": " + return_type + " = "
            + _placeholder_literal(return_type) + "\n"
            "    return " + return_key + "\n"
            "\n"
            "run_tool = tool("
            + repr(name)
            + ", description=" + repr(description) + ")(run)\n"
        )
        return code

    def _generate_agent_code(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        returns: Dict[str, Any],
        requires: Dict[str, Any],
    ) -> str:
        """Generate a minimal agent‑skill source file.

        An agent skill wraps the plain function implementation with a thin
        LangChain ``tool`` so that the generated code executes under the
        installed LangChain (1.x, where ``tool`` takes a single positional
        name plus a ``description`` keyword).  The placeholder body keeps
        the module runnable without any API keys.
        """
        param_lines = []
        for pname, pinfo in parameters.items():
            ptype = pinfo.get("type", "str")
            param_lines.append(f"{pname}: {ptype}")
        param_str = ", ".join(param_lines) or "input_value: str = ''"

        return_key = list(returns.keys())[0]
        return_type = list(returns.values())[0].get("type", "str")
        code = (
            "from langchain.tools import tool\n"
            "\n"
            "def run(" + param_str + ") -> " + return_type + ":\n"
            "    \"\"\"Agent skill " + name + ": " + description + "\"\"\"\n"
            "    " + return_key + ": " + return_type + " = "
            + _placeholder_literal(return_type) + "\n"
            "    return " + return_key + "\n"
            "\n"
            "agent_tool = tool("
            + repr(name)
            + ", description=" + repr(description) + ")("
            + "run)\n"
        )
        return code

    def _generate_workflow_code(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        returns: Dict[str, Any],
        requires: Dict[str, Any],
    ) -> str:
        """Generate a minimal workflow‑skill source file.

        A workflow is represented as a simple function that composes
        several tools.  For the purposes of the test suite, we return a
        string that defines a function named ``run`` that just returns a
        placeholder.
        """
        return_key = list(returns.keys())[0]
        return_type = list(returns.values())[0].get("type", "str")
        param_str = ", ".join(parameters.keys()) or "input_value: str = ''"
        code = (
            f"# Workflow skill – placeholder\n"
            f"def run({param_str}) -> {return_type}:\n"
            f"    \"\"\"Placeholder workflow implementation for {name}.\"\"\"\n"
            f"    {return_key}: {return_type} = {_placeholder_literal(return_type)}\n"
            f"    return {return_key}\n"
        )
        return code

    def _analyze_request_llm(
        self, text: str, explicit: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Ask the LLM for a structure; ``None`` when unusable."""
        from agent.llm import extract_text

        prompt = self._STRUCTURE_PROMPT.format(request=text)
        try:
            response = self.llm.invoke(prompt)
        except Exception:  # noqa: BLE001 - any LLM failure falls back
            return None
        raw = extract_text(response)
        data = _extract_json_object(raw)
        if not data:
            return None
        return self._normalize_structure(data, text, explicit)

    def _normalize_structure(
        self,
        data: Dict[str, Any],
        text: str,
        explicit: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Coerce an LLM proposal into the canonical shape.

        Repairs any defect (missing/invalid name, type, parameters,
        returns, requires) so an LLM answer almost never triggers the
        fallback; only an unusable proposal returns ``None``.
        """
        name = str(data.get("name") or "").strip()
        if not name:
            name = str(explicit.get("name") or "").strip()
        if not name:
            name = _derive_name_from_request(text)
        name = re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_")
        name = re.sub(r"_+", "_", name) or "new_skill"
        if not name[0].isalpha():
            name = f"skill_{name}"
        description = str(
            data.get("description") or explicit.get("description") or ""
        ).strip()
        if not description:
            description = _derive_description_from_request(text)
        type_value = data.get("type")
        if type_value in (None, ""):
            type_value = explicit.get("type") or _derive_type_from_request(text)
        parameters = _coerce_parameters(
            data.get("parameters")
            if data.get("parameters") is not None
            else explicit.get("parameters")
        )
        returns = _coerce_returns(data.get("returns"))
        requires = _coerce_requires(data.get("requires"))
        return {
            "name": name,
            "description": description,
            "type": _canonicalize_skill_type(type_value),
            "parameters": parameters,
            "requires": requires,
            "returns": returns,
        }

    def _analyze_request_fallback(
        self, text: str, explicit: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deterministic structure used when no LLM answer is usable."""
        name = str(explicit.get("name") or "").strip()
        if not name:
            name = _derive_name_from_request(text)
        name = re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_")
        name = re.sub(r"_+", "_", name) or "new_skill"
        if not name[0].isalpha():
            name = f"skill_{name}"
        description = str(explicit.get("description") or "").strip()
        if not description:
            description = _derive_description_from_request(text)
        type_value = explicit.get("type") or _derive_type_from_request(text)
        parameters = _coerce_parameters(explicit.get("parameters"))
        returns = _coerce_returns(explicit.get("returns"))
        requires = _coerce_requires(explicit.get("requires"))
        return {
            "name": name,
            "description": description,
            "type": _canonicalize_skill_type(type_value),
            "parameters": parameters,
            "requires": requires,
            "returns": returns,
        }

    # ------------------------------------------------------------------
    # Request envelope
    # ------------------------------------------------------------------

    def handle_request(
        self,
        request: str,
        request_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Classify one request and return a stable routing envelope.

        Task 7 is intent analysis only, so the envelope reports the intent,
        whether the offline rule path was used, and a human-readable routing
        message.  The creation flow (Tasks 8-11) and the execution flow
        (Tasks 15-17) build on this entry point.

        ``request_data`` is accepted for forward compatibility with the
        main-agent wiring (Task 22); it does not affect intent
        classification yet.
        """
        intent = self.detect_intent(request)
        offline = self.llm is None or bool(getattr(self.llm, "is_offline", False))
        if intent == INTENT_CREATE_SKILL:
            message = (
                "New-skill creation intent recognized; the creation flow "
                "(structure and code generation) takes over from here."
            )
        elif intent == INTENT_USE_SKILL:
            message = (
                "Use-skill intent recognized; the request should be routed "
                "to the existing-skill pipeline for execution."
            )
        else:
            message = (
                "No skill intent detected; treating the request as a "
                "general question."
            )
        if offline:
            message += " (offline: deterministic rules, not an LLM)"
        return {
            "intent": intent,
            "success": True,
            "offline": offline,
            "response": message,
            "error": None,
        }

    # ------------------------------------------------------------------
    # Creation flow — Task 11 implementations (guide §1.8.12)
    # ------------------------------------------------------------------

    def _get_registry(self) -> Any:
        """Return the registry (injected, or lazily built)."""
        if self._registry is None:
            from skills.registry import SkillRegistry

            self._registry = SkillRegistry()
        return self._registry

    def _get_builder(self) -> Any:
        """Return the skill builder (injected, or lazily built)."""
        if self._builder is None:
            from skills.skill_builder import SkillBuilder

            self._builder = SkillBuilder(self._get_registry())
        return self._builder

    def _get_qa(self) -> Any:
        """Return the QA skill (injected, or lazily built)."""
        if self._qa is None:
            from skills.qa_skill import SkillQA

            self._qa = SkillQA(registry=self._get_registry(), llm=self.llm)
        return self._qa

    def _register_skill(
        self, structure: Dict[str, Any], code: str
    ) -> Dict[str, Any]:
        """Register the built skill through the builder (v1).

        Returns ``{"ok": bool, "skill": dict|None, "error": str|None,
        "duplicate": bool}``.  A ``SkillAlreadyExistsError`` is reported as
        ``duplicate`` so the caller can treat re-registration of the same
        name as an idempotent no-op.
        """
        from skills.registry import SkillAlreadyExistsError

        builder = self._get_builder()
        name = structure.get("name", "new_skill")
        try:
            registered = builder.register(
                name=name,
                code=code,
                skill_type=structure.get("type", SKILL_TYPE_FUNCTION),
                description=structure.get("description", ""),
                parameters=structure.get("parameters"),
                examples=structure.get("examples"),
            )
        except SkillAlreadyExistsError as exc:
            return {
                "ok": True,
                "skill": None,
                "error": None,
                "duplicate": True,
                "error_detail": str(exc),
            }
        except Exception as exc:  # noqa: BLE001 - surface as structured failure
            return {
                "ok": False,
                "skill": None,
                "error": f"{type(exc).__name__}: {exc}",
                "duplicate": False,
            }
        if not isinstance(registered, dict) or registered.get("success") is False:
            detail = registered.get("error") if isinstance(registered, dict) else None
            # SkillBuilder.register() catches RegistryError and returns a
            # structured payload rather than raising, so a duplicate name
            # arrives here as a failure string - not via the except branch
            # above.  Classify it from the payload, or a re-registration
            # would be misreported as registration_failed.
            if detail and "SkillAlreadyExistsError" in detail:
                return {
                    "ok": True,
                    "skill": None,
                    "error": None,
                    "duplicate": True,
                    "error_detail": detail,
                }
            return {
                "ok": False,
                "skill": None,
                "error": detail or f"Skill '{name}' was rejected.",
                "duplicate": False,
            }
        return {
            "ok": True,
            "skill": registered.get("skill"),
            "error": None,
            "duplicate": False,
        }

    @staticmethod
    def _qa_input_for(structure: Dict[str, Any]) -> Dict[str, Any]:
        """Build a smoke-test input matching the structure's parameters.

        The generated ``run`` for a parameterless skill takes a defaulted
        ``input_value``, but a skill that declares parameters gets a ``run``
        whose signature is those parameters - the workflow template gives
        them no defaults at all.  Passing a fixed ``{"input_value": ...}``
        to such a skill raises ``TypeError`` and would fail every
        parameterised skill at the QA gate, so derive the input instead.
        """
        params = structure.get("parameters") or {}
        if not isinstance(params, dict) or not params:
            return dict(DEFAULT_QA_INPUT)
        payload: Dict[str, Any] = {}
        for pname, pinfo in params.items():
            ptype = pinfo.get("type", "str") if isinstance(pinfo, dict) else "str"
            payload[pname] = _QA_SAMPLE_VALUES.get(ptype, "qa-gate")
        return payload

    def _run_qa_gate(
        self, skill_name: str, qa_input: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run the QA gate: structure validation + a smoke-test execution.

        ``qa_input`` is the payload handed to the skill for the smoke test;
        it defaults to :data:`DEFAULT_QA_INPUT`.  Callers that have the
        proposed structure should pass :meth:`_qa_input_for` instead.

        Returns ``{"passed": bool, "valid": bool, "execution": {...},
        "errors": [...]}``; ``errors`` holds the human-readable reasons the
        skill was rejected.
        """
        qa = self._get_qa()
        validation = qa.validate_skill_structure(skill_name)
        execution = qa.test_skill(
            skill_name,
            dict(qa_input) if qa_input else dict(DEFAULT_QA_INPUT),
        )
        errors: List[str] = []
        if not validation.get("success"):
            errors.append(
                f"structure validation error: {validation.get('error')}"
            )
        elif not validation.get("valid"):
            errors.extend(
                f"structure invalid: {err}" for err in validation.get("errors", [])
            )
        if not execution.get("success"):
            errors.append(
                f"smoke test failed: {execution.get('error') or 'unknown error'}"
            )
        return {
            "passed": bool(validation.get("valid"))
            and bool(execution.get("success")),
            "valid": bool(validation.get("valid")),
            "execution": execution,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # Code-generation dispatch and the complete creation flow (Task 11)
    # ------------------------------------------------------------------

    def generate_code(self, structure: Dict[str, Any]) -> str:
        """Generate source for ``structure`` using its declared type.

        Dispatches to :meth:`_generate_function_code`,
        :meth:`_generate_agent_code` or :meth:`_generate_workflow_code`.
        An unrecognized type is canonicalized to ``function``.
        """
        skill_type = _canonicalize_skill_type(structure.get("type"))
        args = (
            structure.get("name", "new_skill"),
            structure.get("description", ""),
            structure.get("parameters") or {},
            structure.get("returns") or dict(DEFAULT_RETURNS),
            structure.get("requires") or {},
        )
        if skill_type == SKILL_TYPE_AGENT:
            return self._generate_agent_code(*args)
        if skill_type == SKILL_TYPE_WORKFLOW:
            return self._generate_workflow_code(*args)
        return self._generate_function_code(*args)

    def _creation_result(
        self,
        status: str,
        *,
        structure: Optional[Dict[str, Any]] = None,
        code: str = "",
        skill: Optional[Dict[str, Any]] = None,
        qa: Optional[Dict[str, Any]] = None,
        errors: Optional[List[str]] = None,
        committed: bool = False,
        response: str = "",
    ) -> Dict[str, Any]:
        """Build the creation envelope and count the outcome in ``stats``."""
        if status in self.stats:
            self.stats[status] += 1
        return {
            "success": status == STATUS_COMPLETED,
            "status": status,
            "skill_name": (structure or {}).get("name"),
            "structure": structure,
            "code": code,
            "skill": skill,
            "qa": qa,
            "errors": list(errors or []),
            "committed": committed,
            "response": response,
        }

    def create_skill(
        self,
        request: str,
        request_data: Optional[Dict[str, Any]] = None,
        auto_confirm: bool = False,
        git: Any = None,
        max_edit_rounds: int = 3,
    ) -> Dict[str, Any]:
        """Run the complete New Skill Development flow (guide §1.8.12).

        Analyze the request, generate the structure and the code, show the
        proposal for review, register it, and run the QA gate over the
        registered skill.

        ``auto_confirm`` skips the interactive review entirely - required
        for non-interactive callers and for the test suite, which must
        never block on ``input()``.  ``git`` is an optional
        :class:`~skills.git_manager.GitManager`; when given, a successful
        creation is committed.  Version control stays **opt-in** so that
        neither a test nor an offline run commits as a side effect.

        The outcome is reported by ``status``, one of :data:`ALL_STATUSES`.
        Note that the QA gate runs *after* registration - both of its
        checks look the skill up in the registry - so a ``qa_failed``
        result means the skill is registered but did not pass its
        smoke test.
        """
        self.stats["create_total"] += 1
        try:
            structure = self.analyze_request(request, request_data)
            # A caller may supply the implementation itself (the CLI's
            # --code flag, or the main agent passing a hand-written skill).
            # There is nothing to generate in that case, and generating
            # anyway would silently discard what they wrote.
            explicit_code = (request_data or {}).get("code")
            explicit_code = explicit_code if str(explicit_code or "").strip() else None
            code = explicit_code or self.generate_code(structure)
            if explicit_code:
                # Describe the code that was actually supplied, not the one
                # the analyser imagined - otherwise the registry advertises
                # parameters the implementation does not take.
                derived = _parameters_from_code(explicit_code)
                if derived is not None:
                    structure = {**structure, "parameters": derived}

            if not auto_confirm:
                decision = self._review_skill({**structure, "code": code})
                rounds = 0
                while decision == "edit":
                    if self._review_callback is None:
                        return self._creation_result(
                            STATUS_EDIT_REQUESTED,
                            structure=structure,
                            code=code,
                            response=(
                                "Edit requested, but no review callback is "
                                "wired up; the interactive skill builder "
                                "(Tasks 12-13) provides one. Nothing was "
                                "registered."
                            ),
                        )
                    rounds += 1
                    if rounds > max_edit_rounds:
                        return self._creation_result(
                            STATUS_CANCELLED,
                            structure=structure,
                            code=code,
                            errors=[
                                f"Review did not settle within "
                                f"{max_edit_rounds} edit rounds."
                            ],
                            response="Review abandoned after too many edit rounds.",
                        )
                    edited = self._review_callback(structure)
                    if not isinstance(edited, dict):
                        decision = None
                        break
                    structure = edited
                    code = explicit_code or self.generate_code(structure)
                    decision = self._review_skill({**structure, "code": code})
                if decision is None:
                    return self._creation_result(
                        STATUS_CANCELLED,
                        structure=structure,
                        code=code,
                        response="Skill creation cancelled at review; nothing was registered.",
                    )
                if isinstance(decision, dict):
                    structure = decision
                    code = explicit_code or self.generate_code(structure)

            name = structure.get("name", "new_skill")
            registration = self._register_skill(structure, code)

            if registration.get("duplicate"):
                return self._creation_result(
                    STATUS_ALREADY_EXISTS,
                    structure=structure,
                    code=code,
                    response=(
                        f"Skill '{name}' is already registered; "
                        "nothing was changed."
                    ),
                )
            if not registration.get("ok"):
                error = registration.get("error") or "registration failed"
                return self._creation_result(
                    STATUS_REGISTRATION_FAILED,
                    structure=structure,
                    code=code,
                    errors=[error],
                    response=f"Skill '{name}' could not be registered: {error}",
                )

            skill = registration.get("skill")
            qa = self._run_qa_gate(name, self._qa_input_for(structure))
            if not qa.get("passed"):
                return self._creation_result(
                    STATUS_QA_FAILED,
                    structure=structure,
                    code=code,
                    skill=skill,
                    qa=qa,
                    errors=qa.get("errors", []),
                    response=(
                        f"Skill '{name}' was registered but failed the QA "
                        f"gate: {'; '.join(qa.get('errors') or ['unknown'])}"
                    ),
                )

            committed = False
            if git is not None:
                try:
                    committed = bool(
                        git.commit(f"feat(skill): register '{name}' (v1)")
                    )
                except Exception:  # noqa: BLE001 - VCS must not fail creation
                    committed = False

            version = (skill or {}).get("current_version", 1)
            return self._creation_result(
                STATUS_COMPLETED,
                structure=structure,
                code=code,
                skill=skill,
                qa=qa,
                committed=committed,
                response=(
                    f"Skill '{name}' created, registered (v{version}) and "
                    f"passed the QA gate."
                    + (" Committed to version control." if committed else "")
                ),
            )
        except Exception as exc:  # noqa: BLE001 - creation returns, never raises
            return self._creation_result(
                STATUS_ERROR,
                errors=[f"{type(exc).__name__}: {exc}"],
                response=f"Skill creation failed: {type(exc).__name__}: {exc}",
            )

    # ------------------------------------------------------------------
    # Interactive review helpers – Task 10 implementations
    # ------------------------------------------------------------------
    def _display_proposed_skill(self, skill: Dict[str, Any]) -> str:
        """Return a human‑readable string representation of a proposed skill.

        Parameters
        ----------
        skill:
            The dictionary returned by :meth:`_analyze_request` or the
            helper generation methods.  It is expected to contain at least the
            keys ``type``, ``name``, ``description``, ``parameters``, ``requires``
            and ``returns``.

        Returns
        -------
        str
            A multi‑line string that lists each field in a user‑friendly
            format.  The exact layout is intentionally simple and deterministic
            to make it easy to test.
        """

        lines: List[str] = []
        lines.append(f"Skill type: {skill.get('type', 'unknown')}")
        lines.append(f"Name: {skill.get('name', '')}")
        lines.append(f"Description: {skill.get('description', '')}")
        params = skill.get("parameters", {})
        if params:
            lines.append("Parameters:")
            for name, p in params.items():
                p_type = p.get("type", "unknown")
                default = p.get("default")
                default_str = f" (default={default})" if default is not None else ""
                lines.append(f"  - {name}: {p_type}{default_str}")
        else:
            lines.append("Parameters: None")
        requires = skill.get("requires", {})
        if requires:
            lines.append("Requires:")
            for key, val in requires.items():
                lines.append(f"  - {key}: {val}")
        else:
            lines.append("Requires: None")
        returns = skill.get("returns", {})
        if returns:
            lines.append("Returns:")
            for key, val in returns.items():
                lines.append(f"  - {key}: {val}")
        else:
            lines.append("Returns: None")
        return "\n".join(lines)

    def _ask_confirmation(self) -> Union[bool, str]:
        """Prompt the user to confirm, edit, or cancel.

        Returns
        -------
        bool
            ``True`` if the user confirms, ``False`` if the user cancels.
        str
            ``"edit"`` if the user chooses to edit the proposal.
        """

        prompt = (
            "Confirm proposed skill? (y=Yes, n=No, e=Edit, c=Cancel) [y]: "
        )
        try:
            choice = input(prompt).strip().lower()
        except EOFError:
            # In non‑interactive contexts treat as cancel
            return False
        if not choice:
            return True
        if choice in {"y", "yes"}:
            return True
        if choice in {"n", "no", "c", "cancel"}:
            return False
        if choice == "e" or choice == "edit":
            return "edit"
        # Unrecognised input – ask again recursively
        print("Unrecognised option, please choose again.")
        return self._ask_confirmation()

    def _review_skill(self, skill: Dict[str, Any]) -> Optional[Union[Dict[str, Any], str]]:
        """Display the skill and ask the user to confirm, edit, or cancel.

        Parameters
        ----------
        skill: dict
            The proposed skill structure.

        Returns
        -------
        dict
            The original skill dictionary if the user confirms.
        str
            ``"edit"`` if the user opts to edit.
        None
            ``None`` if the user cancels.
        """

        print(self._display_proposed_skill(skill))
        decision = self._ask_confirmation()
        if decision is True:
            return skill
        if decision is False:
            return None
        # decision == "edit"
        return "edit"

