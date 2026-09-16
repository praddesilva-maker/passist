#!/usr/bin/env python3
"""
Personal Assistant Agentic System - CLI entry point.

Registry-driven, offline-safe command line for the Personal Assistant.

Usage:
    python main.py list
    python main.py use <name> [key=value ...]
    python main.py create <name> [--code CODE] [--type function|agent|workflow]
                               [--description TEXT]
    python main.py gitlog [N]
    python main.py chat [message ...]
"""

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

from config import Config, get_config
from agent.llm import create_chat_model
from skills.registry import SkillRegistry
from skills.unified_stage import UnifiedSkillStage
from skills.git_manager import GitManager
from skills.skill_builder import SkillBuilder
from skills.qa_skill import SkillQA
from agent.main_agent import MainAgent


# ---------------------------------------------------------------------------
# Runtime wiring
# ---------------------------------------------------------------------------

def build_llm(config: Optional[Config] = None):
    """Create the chat model (ChatOpenAI online, OfflineChatModel otherwise)."""
    cfg = config or get_config()
    return create_chat_model(cfg.model)


def build_git_manager(config: Optional[Config] = None) -> Optional[GitManager]:
    """Create a defensive GitManager; None when no repo path is configured."""
    cfg = config or get_config()
    if not cfg.git.repo_path:
        return None
    try:
        return GitManager(cfg.git.repo_path)
    except Exception:  # noqa: BLE001 - git must never break the CLI
        return None


def build_runtime(config: Optional[Config] = None) -> Dict[str, Any]:
    """Wire config -> LLM -> registry -> git -> stage -> agent -> QA."""
    cfg = config or get_config()
    llm = build_llm(cfg)
    registry = SkillRegistry(
        db_path=cfg.database.db_path,
        git_repo_path=cfg.git.repo_path,
        auto_commit=cfg.git.auto_commit,
    )
    git_manager = build_git_manager(cfg)
    stage = UnifiedSkillStage(registry)
    agent = MainAgent(
        agent_name=cfg.agent.name,
        stage=stage,
        registry=registry,
        llm=llm,
        git_manager=git_manager,
        memory_backend="memory",
    )
    return {
        "config": cfg,
        "llm": llm,
        "registry": registry,
        "git_manager": git_manager,
        "stage": stage,
        "agent": agent,
        "skill_builder": SkillBuilder(registry),
        "qa": SkillQA(registry, llm=llm),
    }


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

def emit(payload: Any) -> None:
    """Print a structured payload as pretty JSON (always valid JSON)."""
    print(json.dumps(payload, indent=2, default=str, ensure_ascii=False))


def parse_use_args(pairs: List[str]) -> Dict[str, Any]:
    """Parse ``key=value`` CLI pairs into a dict (JSON values when possible)."""
    data: Dict[str, Any] = {}
    for pair in pairs or []:
        if "=" not in pair:
            continue
        key, _, raw = pair.partition("=")
        key = key.strip()
        if not key:
            continue
        value: Any = raw
        try:
            value = json.loads(raw)
        except (ValueError, TypeError):
            if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
                value = raw[1:-1]
        data[key] = value
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Personal Assistant CLI (registry-driven, offline-safe)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List registered skills")

    p_use = sub.add_parser("use", help="Use (execute) a registered skill")
    p_use.add_argument("name", help="Skill name")
    p_use.add_argument("args", nargs="*", help="key=value arguments")

    p_create = sub.add_parser("create", help="Create (register) a new skill")
    p_create.add_argument("name", help="Skill name")
    p_create.add_argument(
        "--code", default=None, help="Skill code (default: offline template)"
    )
    p_create.add_argument(
        "--type",
        dest="skill_type",
        default="function",
        choices=("function", "agent", "workflow"),
        help="Skill type",
    )
    p_create.add_argument("--description", default="", help="Skill description")

    p_gitlog = sub.add_parser("gitlog", help="Show recent registry git commits")
    p_gitlog.add_argument("limit", nargs="?", type=int, default=10, help="Max commits")

    p_chat = sub.add_parser("chat", help="Chat with the assistant")
    p_chat.add_argument("message", nargs="*", help="Chat message")

    return parser


# ---------------------------------------------------------------------------
# Command handlers (each returns a process exit code)
# ---------------------------------------------------------------------------

def handle_list(rt: Dict[str, Any], args: argparse.Namespace) -> int:
    skills = rt["registry"].list_skills()
    emit(
        {
            "success": True,
            "total_skills": len(skills),
            "skills": [
                {
                    "name": s.get("name"),
                    "type": s.get("type"),
                    "version": s.get("current_version"),
                    "description": s.get("description"),
                }
                for s in skills
            ],
            "error": None,
        }
    )
    return 0


def handle_use(rt: Dict[str, Any], args: argparse.Namespace) -> int:
    agent: MainAgent = rt["agent"]
    name = (args.name or "").strip()
    if not name:
        emit({"success": False, "error": "skill name is required"})
        return 2
    input_data = parse_use_args(args.args)
    response = agent.handle_request(
        f"use skill {name}",
        request_data={"name": name, "input": input_data},
    )
    emit(response)
    return 0 if response.get("result", {}).get("success") else 1


def handle_create(rt: Dict[str, Any], args: argparse.Namespace) -> int:
    agent: MainAgent = rt["agent"]
    name = (args.name or "").strip()
    if not name:
        emit({"success": False, "error": "skill name is required"})
        return 2
    request = f"develop a skill named {name}"
    if args.description:
        request += f" (description: {args.description})"
    request_data = {
        "name": name,
        "skill_type": args.skill_type,
        "description": args.description or name,
    }
    if args.code:
        request_data["code"] = args.code
    response = agent.handle_request(request, request_data=request_data)
    emit(response)
    return 0 if response.get("result", {}).get("success") else 1


def handle_gitlog(rt: Dict[str, Any], args: argparse.Namespace) -> int:
    agent: MainAgent = rt["agent"]
    commits = agent.get_git_log(limit=args.limit)
    emit(
        {
            "success": True,
            "commits": commits,
            "count": len(commits),
            "error": None,
        }
    )
    return 0


def handle_chat(rt: Dict[str, Any], args: argparse.Namespace) -> int:
    agent: MainAgent = rt["agent"]
    message = " ".join(args.message or []).strip()
    if not message:
        message = sys.stdin.read().strip()
    if not message:
        emit(
            {
                "success": False,
                "intent": "unknown",
                "error": "empty message; provide a chat message argument",
            }
        )
        return 2
    response = agent.handle_request(message)
    emit(response)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse already printed a usage message
        return int(exc.code) if exc.code else 0
    try:
        rt = build_runtime()
    except Exception as exc:  # noqa: BLE001 - structured failure, no traceback
        emit({"success": False, "error": f"runtime initialization failed: {exc}"})
        return 1
    handlers = {
        "list": handle_list,
        "use": handle_use,
        "create": handle_create,
        "gitlog": handle_gitlog,
        "chat": handle_chat,
    }
    try:
        return handlers[args.command](rt, args)
    except Exception as exc:  # noqa: BLE001 - CLI must never crash
        emit({"success": False, "error": f"{type(exc).__name__}: {exc}"})
        return 1


if __name__ == "__main__":
    sys.exit(main())

