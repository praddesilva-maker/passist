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
delivers intent analysis only; the creation flow itself (structure and
code generation, interactive review, testing and registration) is added in
Tasks 8-11, and wiring into :class:`agent.main_agent.MainAgent` in Task 22.
"""

import re
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Intent vocabulary (stable; documented in PERSONAL_ASSISTANT_GUIDE.md §1.8.8)
# ---------------------------------------------------------------------------

INTENT_CREATE_SKILL = "create_skill"
INTENT_USE_SKILL = "use_skill"
INTENT_GENERAL = "general"

ALL_INTENTS = (INTENT_CREATE_SKILL, INTENT_USE_SKILL, INTENT_GENERAL)

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


class NewSkillPipeline:
    """Intent-analysis stage of the New Skill Development pipeline.

    * :meth:`detect_intent` — public classifier (counts requests in
      ``self.stats``), backed by the guide-named :meth:`_detect_intent`.
    * :meth:`handle_request` — stable routing envelope used by
      demonstrations and by the main-agent wiring (Task 22).

    Construction takes only what intent analysis needs (an optional LLM);
    Tasks 8-11 will extend the pipeline with the rest of the creation flow.
    """

    def __init__(self, llm: Any = None) -> None:
        self.llm = llm
        self.stats = {
            "requests": 0,
            INTENT_CREATE_SKILL: 0,
            INTENT_USE_SKILL: 0,
            INTENT_GENERAL: 0,
        }

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

