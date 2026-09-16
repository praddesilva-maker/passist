#!/usr/bin/env python3
"""
Existing Skill Pipeline (PERSONAL_ASSISTANT_GUIDE.md §1.8.16-§1.8.18).

The execution flow: given a natural-language request, find the skill that
serves it, turn the request text into that skill's parameters, and run it.

* Task 15 — skill search: :meth:`ExistingSkillPipeline.find_skills`,
  relevance ranking, result display, and suggestions when nothing matches.
* Task 16 — skill execution: per-type execution
  (:meth:`_execute_function_skill`, :meth:`_execute_agent_skill`,
  :meth:`_execute_workflow_skill`) and the :meth:`execute_skill` dispatcher.
* Task 17 — natural-language parsing: :meth:`_parse_input_to_params` with
  an LLM-first path and a deterministic offline fallback, plus parameter
  validation.

Layering note: execution is delegated to
:class:`~skills.unified_stage.UnifiedSkillStage`, which owns module loading,
keyword resolution and run logging (guide §1.5 makes the unified stage the
single execution point). The per-type methods here shape the input and
post-process the result; they deliberately do not re-implement loading.

Everything works offline: with no LLM, or an offline one, every path falls
back to deterministic rules.
"""

import re
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

SKILL_TYPE_FUNCTION = "function"
SKILL_TYPE_AGENT = "agent"
SKILL_TYPE_WORKFLOW = "workflow"

CANONICAL_SKILL_TYPES = (
    SKILL_TYPE_FUNCTION,
    SKILL_TYPE_AGENT,
    SKILL_TYPE_WORKFLOW,
)

# Terminal statuses for the execution flow.
STATUS_EXECUTED = "executed"
STATUS_NOT_FOUND = "not_found"
STATUS_AMBIGUOUS = "ambiguous"
STATUS_INVALID_PARAMS = "invalid_params"
STATUS_EXECUTION_FAILED = "execution_failed"
STATUS_ERROR = "error"

ALL_STATUSES = (
    STATUS_EXECUTED,
    STATUS_NOT_FOUND,
    STATUS_AMBIGUOUS,
    STATUS_INVALID_PARAMS,
    STATUS_EXECUTION_FAILED,
    STATUS_ERROR,
)

# Default number of search results surfaced to the user.
DEFAULT_SEARCH_LIMIT = 5

# A match at or below this score is too weak to act on without confirmation.
WEAK_MATCH_SCORE = 0.15

# Words carrying no signal for relevance ranking.
_STOPWORDS = frozenset(
    """a an the and or of to for with using use run execute call please
    my me i want need can you it this that on in at by from is are be
    do does skill""".split()
)

# Coercers for validating/normalizing a parsed parameter against its type.
_TYPE_COERCERS: Dict[str, Any] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
}

_TRUE_WORDS = frozenset({"true", "yes", "y", "1", "on"})
_FALSE_WORDS = frozenset({"false", "no", "n", "0", "off"})

# A parameter key followed by "=" or ":" anywhere in the text.  The
# lookbehind keeps it from firing inside a dotted or hyphenated token.
_PAIR_KEY_RE = re.compile(r"(?<![\w.])([A-Za-z_]\w*)\s*[=:]\s*")


def _stem(token: str) -> str:
    """Strip common English inflections so related words compare equal.

    Ranking without this is close to useless in practice: the query
    "count words" shares no exact token with the skill ``word_counter``
    ("count" != "counter", "words" != "word"), so an obviously correct
    match scored below the weak-match floor and was reported as no match
    at all.
    """
    for suffix in ("ing", "ed", "er"):
        if len(token) > len(suffix) + 2 and token.endswith(suffix):
            return token[: -len(suffix)]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _tokenize(text: str) -> List[str]:
    """Lowercase, stopword-free, stemmed word tokens."""
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in text or "")
    return [
        _stem(tok) for tok in cleaned.split()
        if tok and tok not in _STOPWORDS
    ]


def _coerce_bool(value: Any) -> bool:
    """Coerce a parsed value to bool, honouring common word forms."""
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _TRUE_WORDS:
        return True
    if text in _FALSE_WORDS:
        return False
    raise ValueError(f"{value!r} is not a boolean")


def _coerce(value: Any, type_name: str) -> Any:
    """Coerce ``value`` to ``type_name``; raise ValueError if impossible."""
    if type_name == "bool":
        return _coerce_bool(value)
    coercer = _TYPE_COERCERS.get(type_name)
    if coercer is None:          # unknown declared type: accept as-is
        return value
    if isinstance(value, coercer) and not (
        # bool is a subclass of int - do not let True satisfy an int param
        type_name == "int" and isinstance(value, bool)
    ):
        return value
    if type_name in ("list", "dict"):
        raise ValueError(f"{value!r} is not a {type_name}")
    try:
        return coercer(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{value!r} is not a valid {type_name}") from exc


class ExistingSkillPipeline:
    """Search for a registered skill, parse an input for it, and run it."""

    def __init__(
        self,
        registry: Any = None,
        stage: Any = None,
        llm: Any = None,
    ) -> None:
        self._registry = registry
        self._stage = stage
        self.llm = llm
        self.stats: Dict[str, int] = {
            "searches": 0,
            "executions": 0,
            "parse_total": 0,
            "parse_llm_used": 0,
            "parse_fallback": 0,
        }
        for status in ALL_STATUSES:
            self.stats[status] = 0

    # ------------------------------------------------------------------
    # Lazily-built dependencies
    # ------------------------------------------------------------------

    def _get_registry(self) -> Any:
        if self._registry is None:
            from skills.registry import SkillRegistry

            self._registry = SkillRegistry()
        return self._registry

    def _get_stage(self) -> Any:
        if self._stage is None:
            from skills.unified_stage import UnifiedSkillStage

            self._stage = UnifiedSkillStage(self._get_registry())
        return self._stage

    @property
    def offline(self) -> bool:
        """True when no usable LLM is configured."""
        return self.llm is None or bool(getattr(self.llm, "is_offline", False))

    # ==================================================================
    # Task 15 — skill search
    # ==================================================================

    def _score_match(self, query: str, skill: Dict[str, Any]) -> float:
        """Relevance of ``skill`` to ``query`` in ``0.0``-``1.0``.

        A deterministic lexical score: overlap between the query's tokens
        and the skill's name and description, with the name weighted more
        heavily and an exact name match always scoring ``1.0``.

        The guide asks for vector embeddings "if available" (Task 15.2);
        no embedding model is available offline, and the project's hard
        requirement is that everything works with no API key, so ranking
        is lexical. :meth:`find_skills` is the seam an embedding-backed
        ranker would replace.
        """
        query_tokens = set(_tokenize(query))
        name = str(skill.get("name") or "")
        if not query_tokens:
            return 0.0
        if query.strip().lower() == name.lower():
            return 1.0

        name_tokens = set(_tokenize(name))
        desc_tokens = set(_tokenize(str(skill.get("description") or "")))

        name_hits = len(query_tokens & name_tokens)
        desc_hits = len(query_tokens & desc_tokens)
        if name_tokens and name_tokens <= query_tokens:
            # Every word of the skill's name appears in the query.
            return min(1.0, 0.9 + 0.1 * desc_hits)

        # Name matches are worth three times a description match.
        weighted = (3.0 * name_hits + desc_hits) / (3.0 * len(query_tokens))
        return min(1.0, weighted)

    def find_skills(
        self,
        query: str,
        limit: int = DEFAULT_SEARCH_LIMIT,
        skill_type: Optional[str] = None,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Find registered skills matching ``query``, best match first.

        Uses the registry's full-text search, then ranks the candidates by
        :meth:`_score_match` and filters them. The registry returns
        ``score: None``, so ranking is this pipeline's responsibility.

        ``skill_type`` restricts results to one canonical type;
        ``min_score`` drops weak matches; ``limit`` caps the result count.
        """
        self.stats["searches"] += 1
        registry = self._get_registry()
        text = (query or "").strip()
        try:
            # Over-fetch so ranking has candidates to work with, then trim.
            candidates = registry.search_skills(text, limit=max(limit * 4, 20))
        except Exception:  # noqa: BLE001 - a search failure is not a crash
            candidates = []

        if not candidates and text:
            # FTS can miss a substring the user clearly meant; fall back to
            # scoring the whole catalogue rather than reporting nothing.
            try:
                candidates = registry.list_skills()
            except Exception:  # noqa: BLE001
                candidates = []

        results: List[Dict[str, Any]] = []
        for candidate in candidates:
            if skill_type and candidate.get("type") != skill_type:
                continue
            scored = dict(candidate)
            scored["score"] = round(self._score_match(text, candidate), 4)
            if scored["score"] < min_score:
                continue
            results.append(scored)

        results.sort(key=lambda s: (-s["score"], str(s.get("name") or "")))
        return results[:limit]

    def display_results(self, results: List[Dict[str, Any]]) -> str:
        """Render search results as user-facing text (Task 15.3).

        Shows each skill's name, type, version, relevance score and
        description, and states plainly when there is nothing to show.
        """
        if not results:
            return "No matching skills found."
        lines = [f"Found {len(results)} matching skill(s):"]
        for index, skill in enumerate(results, start=1):
            name = skill.get("name", "<unnamed>")
            stype = skill.get("type", "unknown")
            version = skill.get("current_version")
            score = skill.get("score")
            version_str = f" v{version}" if version is not None else ""
            score_str = f" [relevance {score:.2f}]" if score is not None else ""
            lines.append(f"{index}. {name} ({stype}{version_str}){score_str}")
            description = str(skill.get("description") or "").strip()
            lines.append(f"     {description or '(no description)'}")
        return "\n".join(lines)

    def suggest(
        self, query: str, limit: int = DEFAULT_SEARCH_LIMIT
    ) -> Dict[str, Any]:
        """Suggest a way forward when a search finds nothing (Task 15.4).

        Returns the closest skills by relevance (ignoring the score floor)
        and always offers creating the skill instead, so a user whose
        request matches nothing is never left at a dead end.
        """
        similar = self.find_skills(query, limit=limit, min_score=0.0)
        similar = [s for s in similar if s.get("score", 0) > 0]
        if similar:
            message = (
                "No skill matched that closely. The nearest matches are:\n"
                + self.display_results(similar)
                + "\n\nYou can run one of these, rephrase your request, or "
                "ask me to create a new skill for it."
            )
        else:
            message = (
                f"No registered skill resembles {query.strip()!r}. "
                "Ask me to create a new skill for it, or run "
                "'list skills' to see what is available."
            )
        return {
            "query": query,
            "similar": similar,
            "can_create": True,
            "message": message,
        }

    # ==================================================================
    # Task 17 — natural-language parameter parsing
    # ==================================================================

    @staticmethod
    def _declared_parameters(skill: Dict[str, Any]) -> Dict[str, Any]:
        """The skill's declared parameters as a ``{name: info}`` mapping."""
        params = skill.get("parameters")
        if isinstance(params, dict):
            return params
        if isinstance(params, list):
            # Tolerate a list-of-dicts shape from an older registry payload.
            coerced = {}
            for entry in params:
                if isinstance(entry, dict) and entry.get("name"):
                    coerced[entry["name"]] = entry
            return coerced
        return {}

    @staticmethod
    def _extract_pairs(text: str) -> Dict[str, str]:
        """Pull ``key=value`` / ``key: value`` pairs out of free text.

        Each pair's value runs from its separator to the start of the next
        pair, or to the end of the string - so an unquoted multi-word value
        (``text=hello world``) survives intact, while several pairs in one
        line (``a=1, b=2``) still split correctly.

        Scanning for keys anywhere in the string, rather than splitting the
        text into lines first, is what lets a pair embedded in a sentence
        be found at all: ``"count the words in text=hello"`` has no line
        whose whole left-hand side is a bare key.
        """
        source = str(text or "")
        matches = list(_PAIR_KEY_RE.finditer(source))
        pairs: Dict[str, str] = {}
        for index, match in enumerate(matches):
            start = match.end()
            end = (
                matches[index + 1].start()
                if index + 1 < len(matches)
                else len(source)
            )
            value = source[start:end].strip().strip(",;").strip().strip("'\"")
            if value:
                pairs[match.group(1).lower()] = value
        return pairs

    def _parse_params_fallback(
        self, text: str, skill: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deterministic parameter extraction, used whenever no LLM answers.

        Handles, in order of precedence: explicit ``key=value`` pairs, then
        - for a single-parameter skill - the remaining text as that
        parameter's value. Anything it cannot determine is simply left out,
        so validation reports it as missing rather than inventing a value.
        """
        declared = self._declared_parameters(skill)
        if not declared:
            return {}

        pairs = self._extract_pairs(text)
        parsed: Dict[str, Any] = {}
        for name in declared:
            if name.lower() in pairs:
                parsed[name] = pairs[name.lower()]

        if not parsed and len(declared) == 1:
            # A conversational request for a one-parameter skill: the text
            # itself is the argument, minus any leading command phrasing.
            # Only for a textual parameter - handing arbitrary prose to an
            # int/bool/list parameter would manufacture a wrong value where
            # reporting it missing is the honest outcome.
            only = next(iter(declared))
            info = declared[only] if isinstance(declared[only], dict) else {}
            if str(info.get("type", "str")) not in ("str", ""):
                return parsed
            stripped = str(text or "").strip()
            for prefix in ("run ", "use ", "execute ", "call "):
                if stripped.lower().startswith(prefix):
                    stripped = stripped[len(prefix):].strip()
                    break
            name = str(skill.get("name") or "")
            if name and stripped.lower().startswith(name.lower()):
                stripped = stripped[len(name):].strip(" :,-")
            if stripped:
                parsed[only] = stripped
        return parsed

    def _parse_params_llm(
        self, text: str, skill: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Ask the LLM to map ``text`` onto the skill's parameters.

        Returns ``None`` on any failure - no LLM, an offline one, a raised
        exception, or an answer that is not a usable JSON object - so the
        caller falls back deterministically.
        """
        if self.offline:
            return None
        declared = self._declared_parameters(skill)
        if not declared:
            return {}
        spec = ", ".join(
            f"{name} ({info.get('type', 'str') if isinstance(info, dict) else 'str'})"
            for name, info in declared.items()
        )
        prompt = (
            "Extract the parameter values from the user's request.\n"
            f"Skill: {skill.get('name')}\n"
            f"Parameters: {spec}\n"
            f"Request: {text}\n"
            "Answer with a single JSON object mapping parameter names to "
            "values. Omit any parameter the request does not supply."
        )
        try:
            from pipelines.new_skill_pipeline import _extract_json_object

            reply = self.llm.invoke(prompt)
            content = getattr(reply, "content", reply)
            parsed = _extract_json_object(str(content))
        except Exception:  # noqa: BLE001 - any LLM failure falls back
            return None
        if not isinstance(parsed, dict):
            return None
        # Keep only declared parameters; the model may hallucinate extras.
        return {k: v for k, v in parsed.items() if k in declared}

    def _parse_input_to_params(
        self, text: str, skill: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Turn a natural-language request into the skill's parameters.

        LLM-first (Task 17.1 asks for GLM integration), with the
        deterministic fallback above whenever the LLM is absent, offline,
        failing, or unparseable. Counted in ``stats``.
        """
        self.stats["parse_total"] += 1
        parsed = self._parse_params_llm(text, skill)
        if parsed is None:
            parsed = self._parse_params_fallback(text, skill)
            self.stats["parse_fallback"] += 1
        else:
            self.stats["parse_llm_used"] += 1
        return parsed

    # Public alias - the guide names the method with a leading underscore,
    # but callers outside the pipeline (the main agent) need a public seam.
    def parse_input_to_params(
        self, text: str, skill: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Public wrapper for :meth:`_parse_input_to_params`."""
        return self._parse_input_to_params(text, skill)

    def validate_params(
        self, params: Dict[str, Any], skill: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Type-check and required-check parsed parameters (Task 17.3).

        A declared parameter is required unless its declaration carries a
        ``default``. Values are coerced to the declared type where that is
        unambiguous (``"5"`` to ``5`` for an ``int``), and reported as an
        error where it is not.

        Returns ``{"valid", "params", "errors", "missing"}`` - ``params``
        holds the coerced values, with declared defaults filled in.
        """
        declared = self._declared_parameters(skill)
        if not declared:
            # No declared schema, so there is nothing to validate against.
            # Registering `parameters` metadata is optional, and plenty of
            # skills omit it while their run() still takes arguments - the
            # unified stage resolves kwargs against the real signature.
            # Rejecting every argument as "unknown" here would make such a
            # skill impossible to call through the pipeline at all.
            return {
                "valid": True,
                "params": dict(params),
                "errors": [],
                "missing": [],
            }
        errors: List[str] = []
        missing: List[str] = []
        coerced: Dict[str, Any] = {}

        for name, info in declared.items():
            info = info if isinstance(info, dict) else {}
            declared_type = str(info.get("type", "str"))
            has_default = "default" in info
            if name not in params:
                if has_default:
                    coerced[name] = info["default"]
                else:
                    missing.append(name)
                continue
            try:
                coerced[name] = _coerce(params[name], declared_type)
            except ValueError as exc:
                errors.append(f"parameter '{name}': {exc}")

        for name in params:
            if name not in declared:
                errors.append(f"unknown parameter '{name}'")

        if missing:
            errors.append(
                "missing required parameter(s): " + ", ".join(sorted(missing))
            )
        return {
            "valid": not errors,
            "params": coerced,
            "errors": errors,
            "missing": missing,
        }

    # ==================================================================
    # Task 16 — skill execution
    # ==================================================================

    def _execute_via_stage(
        self,
        skill: Dict[str, Any],
        input_data: Dict[str, Any],
        skill_type: str,
    ) -> Dict[str, Any]:
        """Run one skill through the unified stage."""
        return self._get_stage().execute_skill(
            skill.get("name"), dict(input_data or {}), skill_type=skill_type
        )

    def _execute_function_skill(
        self, skill: Dict[str, Any], input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a function skill (Task 16.1).

        A function skill returns its value directly, so the stage result is
        passed through unchanged.
        """
        return self._execute_via_stage(skill, input_data, SKILL_TYPE_FUNCTION)

    def _execute_agent_skill(
        self, skill: Dict[str, Any], input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute an agent skill (Task 16.2).

        An agent's answer may arrive wrapped - as a message object with
        ``.content``, or as a dict under ``output``/``result``/``answer`` -
        so the payload is unwrapped into ``output`` while the original is
        preserved under ``raw_output``.
        """
        result = self._execute_via_stage(skill, input_data, SKILL_TYPE_AGENT)
        if not result.get("success"):
            return result
        raw = result.get("output")
        unwrapped = raw
        if hasattr(raw, "content"):
            unwrapped = raw.content
        elif isinstance(raw, dict):
            for key in ("output", "result", "answer"):
                if key in raw:
                    unwrapped = raw[key]
                    break
        if unwrapped is not raw:
            result = dict(result)
            result["raw_output"] = raw
            result["output"] = unwrapped
        return result

    def _execute_workflow_skill(
        self, skill: Dict[str, Any], input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a workflow skill (Task 16.3).

        A workflow may report per-step results; when the output is a list
        or carries a ``steps`` key, the step count is surfaced as
        ``steps_completed`` so a caller can report progress.
        """
        result = self._execute_via_stage(skill, input_data, SKILL_TYPE_WORKFLOW)
        if not result.get("success"):
            return result
        output = result.get("output")
        steps = None
        if isinstance(output, list):
            steps = len(output)
        elif isinstance(output, dict) and isinstance(output.get("steps"), list):
            steps = len(output["steps"])
        if steps is not None:
            result = dict(result)
            result["steps_completed"] = steps
        return result

    def execute_skill(
        self, name: str, input_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a registered skill, dispatching on its declared type.

        Always returns a result dict; a missing skill, an unknown type, or
        a failure inside the skill are all reported, never raised.
        """
        self.stats["executions"] += 1
        registry = self._get_registry()
        try:
            skill = registry.get_skill(name)
        except Exception as exc:  # noqa: BLE001
            return {
                "success": False, "skill_name": name, "skill_type": "unknown",
                "output": None, "error": f"{type(exc).__name__}: {exc}",
                "execution_time_ms": 0.0, "version": None,
            }
        if skill is None:
            return {
                "success": False, "skill_name": name, "skill_type": "unknown",
                "output": None,
                "error": f"Skill '{name}' not found in registry",
                "execution_time_ms": 0.0, "version": None,
            }

        skill_type = skill.get("type")
        payload = dict(input_data or {})
        if skill_type == SKILL_TYPE_AGENT:
            return self._execute_agent_skill(skill, payload)
        if skill_type == SKILL_TYPE_WORKFLOW:
            return self._execute_workflow_skill(skill, payload)
        if skill_type == SKILL_TYPE_FUNCTION:
            return self._execute_function_skill(skill, payload)
        return {
            "success": False, "skill_name": name,
            "skill_type": skill_type or "unknown", "output": None,
            "error": f"Unknown skill type: {skill_type!r}",
            "execution_time_ms": 0.0,
            "version": skill.get("current_version"),
        }

    # ==================================================================
    # End-to-end flow
    # ==================================================================

    def _result(
        self,
        status: str,
        *,
        response: str,
        skill_name: Optional[str] = None,
        matches: Optional[List[Dict[str, Any]]] = None,
        params: Optional[Dict[str, Any]] = None,
        execution: Optional[Dict[str, Any]] = None,
        errors: Optional[List[str]] = None,
        suggestions: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build the execution envelope and count the outcome."""
        if status in self.stats:
            self.stats[status] += 1
        return {
            "success": status == STATUS_EXECUTED,
            "status": status,
            "skill_name": skill_name,
            "matches": matches or [],
            "params": params or {},
            "execution": execution,
            "errors": list(errors or []),
            "suggestions": suggestions,
            "response": response,
        }

    def handle_request(
        self,
        request: str,
        skill_name: Optional[str] = None,
        input_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Search, parse and execute in one call.

        ``skill_name`` skips the search when the caller already knows which
        skill to run; ``input_data`` skips natural-language parsing when the
        caller already has structured parameters.
        """
        try:
            matches: List[Dict[str, Any]] = []
            if skill_name is None:
                matches = self.find_skills(request, min_score=WEAK_MATCH_SCORE)
                if not matches:
                    suggestions = self.suggest(request)
                    return self._result(
                        STATUS_NOT_FOUND,
                        matches=[],
                        suggestions=suggestions,
                        response=suggestions["message"],
                    )
                best, *rest = matches
                if rest and abs(rest[0]["score"] - best["score"]) < 1e-9:
                    tied = [best, rest[0]]
                    return self._result(
                        STATUS_AMBIGUOUS,
                        matches=matches,
                        response=(
                            "That request matches more than one skill equally "
                            "well; tell me which to run:\n"
                            + self.display_results(tied)
                        ),
                    )
                skill_name = best["name"]

            skill = self._get_registry().get_skill(skill_name)
            if skill is None:
                suggestions = self.suggest(request)
                return self._result(
                    STATUS_NOT_FOUND,
                    skill_name=skill_name,
                    suggestions=suggestions,
                    response=f"Skill '{skill_name}' is not registered.",
                )

            if input_data is None:
                parsed = self._parse_input_to_params(request, skill)
            else:
                parsed = dict(input_data)

            validation = self.validate_params(parsed, skill)
            if not validation["valid"]:
                return self._result(
                    STATUS_INVALID_PARAMS,
                    skill_name=skill_name,
                    matches=matches,
                    params=parsed,
                    errors=validation["errors"],
                    response=(
                        f"Could not run '{skill_name}': "
                        + "; ".join(validation["errors"])
                    ),
                )

            execution = self.execute_skill(skill_name, validation["params"])
            if not execution.get("success"):
                return self._result(
                    STATUS_EXECUTION_FAILED,
                    skill_name=skill_name,
                    matches=matches,
                    params=validation["params"],
                    execution=execution,
                    errors=[execution.get("error") or "execution failed"],
                    response=(
                        f"Skill '{skill_name}' failed: "
                        f"{execution.get('error') or 'unknown error'}"
                    ),
                )
            return self._result(
                STATUS_EXECUTED,
                skill_name=skill_name,
                matches=matches,
                params=validation["params"],
                execution=execution,
                response=(
                    f"Ran '{skill_name}' -> {execution.get('output')!r}"
                ),
            )
        except Exception as exc:  # noqa: BLE001 - the flow returns, never raises
            return self._result(
                STATUS_ERROR,
                skill_name=skill_name,
                errors=[f"{type(exc).__name__}: {exc}"],
                response=f"Request failed: {type(exc).__name__}: {exc}",
            )
