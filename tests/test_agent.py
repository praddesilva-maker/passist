#!/usr/bin/env python3
"""
Tests for MainAgent intent routing, offline fallback, and git logging.
"""

import json

import pytest


def test_unknown_intent_offline_response(temp_agent, isolated_env):
    response = temp_agent.handle_request("hello there")
    assert response["intent"] == "general"
    assert response["success"] is True
    # Offline LLM -> deterministic fallback message, not a crash.
    assert "offline" in response["response"].lower()
    assert "error" not in response or not response.get("error")


def test_use_skill_intent_routes_to_stage(temp_agent):
    response = temp_agent.handle_request(
        "use skill echo_skill",
        request_data={"name": "echo_skill", "input": {"input_value": "hi"}},
    )
    assert response["intent"] == "use_skill"
    result = response["result"]
    assert result["success"] is True
    assert result["skill_name"] == "echo_skill"
    assert result["output"] == {"echo": "hi"}
    # Regression: _handle_use_skill's success payload used to have no
    # "message" key, so handle_request()'s human-readable "response" (and,
    # since Task 23, the per-turn text recorded by get_history()) was ""
    # for every successful skill run.
    assert response["response"]
    assert "echo_skill" in response["response"]


def test_use_skill_unknown_skill_structured_error(temp_agent):
    response = temp_agent.handle_request(
        "use skill ghost", request_data={"name": "ghost", "input": {}}
    )
    assert response["intent"] == "use_skill"
    assert response["result"]["success"] is False
    assert response["result"]["error"]


def test_develop_skill_intent_creates_offline_template(temp_agent):
    response = temp_agent.handle_request(
        "develop a skill named adder (description: Adds numbers)",
        request_data={
            "name": "adder",
            "skill_type": "function",
            "description": "Adds numbers",
        },
    )
    assert response["intent"] == "create_skill"
    result = response["result"]
    assert result["success"] is True
    assert result["created"] is True
    assert result["skill"]["name"] == "adder"
    # Now usable through the unified stage.
    use = temp_agent.handle_request(
        "use skill adder",
        # The pipeline-generated skill declares an `input` parameter (the
        # old offline template took `input_value`); passing an undeclared
        # name is now correctly rejected rather than silently ignored.
        request_data={"name": "adder", "input": {"input": "x"}},
    )
    assert use["result"]["success"] is True


def test_develop_skill_rejects_invalid_name(temp_agent):
    response = temp_agent.handle_request(
        "develop a skill named @bad name!",
        request_data={"name": "@bad name!", "description": "bad"},
    )
    assert response["intent"] == "create_skill"
    assert response["result"]["success"] is False
    assert response["result"]["error"]


def test_handle_request_empty_message_no_crash(temp_agent):
    response = temp_agent.handle_request("")
    assert response["intent"] == "general"
    assert response["success"] is True


def test_git_log_never_raises(temp_agent):
    commits = temp_agent.get_git_log(limit=5)
    assert isinstance(commits, list)


# ---------------------------------------------------------------------------
# Task 23: Main Agent - Memory Management.
#
# Before this pass, _remember_action() only recorded {intent, skill, at} --
# no request/response text -- and there was no retrieval method at all
# beyond get_memory()'s raw key/value snapshot. That met "memory size
# management" (RECENT_ACTIONS_LIMIT) but not "history storage" or "history
# retrieval" (guide Task 23.2/23.3): there was no actual conversation to
# retrieve. get_history() and the request/response fields on
# _remember_action close that gap; see main_agent.py's Memory section.
# ---------------------------------------------------------------------------


def test_history_records_request_and_response_text(temp_agent):
    temp_agent.handle_request(
        "use skill echo_skill",
        request_data={"name": "echo_skill", "input": {"input_value": "hi"}},
    )
    history = temp_agent.get_history()
    assert len(history) == 1
    turn = history[0]
    assert turn["intent"] == "use_skill"
    assert turn["skill"] == "echo_skill"
    assert turn["request"] == "use skill echo_skill"
    assert isinstance(turn["response"], str)
    assert "at" in turn


def test_history_is_size_bounded_and_ordered_oldest_first(temp_agent):
    for i in range(temp_agent.RECENT_ACTIONS_LIMIT + 5):
        temp_agent.handle_request(f"hello number {i}")
    history = temp_agent.get_history()
    assert len(history) == temp_agent.RECENT_ACTIONS_LIMIT
    # Oldest-first: the last request made is the last entry.
    assert history[-1]["request"] == f"hello number {temp_agent.RECENT_ACTIONS_LIMIT + 4}"


def test_history_limit_returns_most_recent_n(temp_agent):
    temp_agent.handle_request("first")
    temp_agent.handle_request("second")
    temp_agent.handle_request("third")
    last_two = temp_agent.get_history(limit=2)
    assert [t["request"] for t in last_two] == ["second", "third"]


def test_get_memory_snapshot_includes_history_key(temp_agent):
    temp_agent.handle_request("use skill echo_skill", request_data={"name": "echo_skill"})
    snapshot = temp_agent.get_memory()
    key = temp_agent.MEMORY_KEY_RECENT_ACTIONS
    assert key in snapshot
    assert isinstance(snapshot[key], list)


def test_create_chat_model_offline_without_key(isolated_env):
    from agent.llm import OfflineChatModel, create_chat_model

    model = create_chat_model(model_name="glm-4-flash")
    assert isinstance(model, OfflineChatModel)
    assert model.is_offline is True


def test_offline_model_invocation_is_structured(isolated_env):
    from agent.llm import create_chat_model

    model = create_chat_model()
    reply = model.invoke("hello")
    # LangChain-style AIMessage with a string content.
    assert "offline" in str(getattr(reply, "content", "")).lower()


def test_agent_config_defaults_and_validation(isolated_env):
    """agent/agent_config.py: 'Configuration correct' (Task 20 DoD).

    AgentConfig is exported from agent/__init__.py but nothing in the
    codebase constructs one from wiring (agent.main_agent.MainAgent takes
    plain kwargs, and main.py's build_runtime() builds its own
    config.Config/config.AgentConfig dataclass instead) -- see the
    verification report's Task 20 escalation. This test at least locks
    down that the pydantic model's own field defaults and bounds behave as
    documented, since nothing else exercised it.
    """
    from pydantic import ValidationError

    from agent.agent_config import AgentConfig

    cfg = AgentConfig()
    assert cfg.glm_model == "glm-4"
    assert cfg.glm_temperature == 0.7
    assert cfg.glm_max_tokens == 2048

    # Field bounds (ge/le) are enforced.
    with pytest.raises(ValidationError):
        AgentConfig(glm_temperature=5.0)
    with pytest.raises(ValidationError):
        AgentConfig(glm_max_tokens=0)


def test_create_chat_model_online_when_credentials_present(isolated_env):
    """Task 20: create_chat_model() also has an online branch (ChatOpenAI)

    that no test previously exercised (isolated_env forces GLM_API_KEY="",
    and every other test relies on that). Constructing ChatOpenAI does not
    itself touch the network -- only .invoke()/.agenerate() would -- so this
    stays fully offline-safe while still verifying the online branch wires
    the config through instead of silently falling back to OfflineChatModel.
    """
    from langchain_openai import ChatOpenAI

    from agent.llm import create_chat_model
    from config import ModelConfig

    cfg = ModelConfig(api_key="fake-key-for-construction-only", use_offline=False)
    model = create_chat_model(cfg, model_name="glm-4-plus", temperature=0.2, max_tokens=512)
    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "glm-4-plus"
    assert model.temperature == 0.2
    assert model.max_tokens == 512


def test_extract_text_handles_str_dict_and_none():
    from agent.llm import extract_text

    assert extract_text(None) == ""
    assert extract_text("plain string") == "plain string"
    assert extract_text({"content": "from a dict"}) == "from a dict"

    class _Msg:
        content = "from an object"

    assert extract_text(_Msg()) == "from an object"


# ---------------------------------------------------------------------------
# Task 24: Main Agent - Entry Point (main.py CLI).
#
# main.py had ZERO test coverage before this verification pass, so its
# "REVIEW" -> "passing" status in status.md reflected only that the rest of
# the suite happened not to import it -- not that the CLI worked.  A real
# defect was found and fixed here: handle_list(rt) was missing the `args`
# parameter that main()'s dispatcher always passes
# (`handlers[args.command](rt, args)`), so `python main.py list` raised
# TypeError on every invocation and main()'s outer except turned that into
# an exit-code-1 JSON error instead of a skill listing. See main.py
# handle_list (fixed to accept `args`).
# ---------------------------------------------------------------------------


@pytest.fixture
def cli_env(tmp_path, monkeypatch):
    """Isolate main.py's runtime (config.py), independent of conftest.

    conftest.py's autouse `isolated_env` fixture sets GLM_API_KEY="" (which
    main.py's runtime honors) but also sets PA_MEMORY_DIR / PA_SKILLS_DIR /
    PA_DATABASE_PATH / PA_GIT_REPO_PATH -- names config.py never reads (it
    reads SKILLS_DB_PATH / GIT_REPO_PATH). Left alone, any test that calls
    main.main() would default to config.py's real project-relative paths
    (./skills/skills.db, this repo as the git dir). Set the names config.py
    actually reads, pointed at tmp_path, so CLI tests can't touch real
    project state. GIT_AUTO_COMMIT=0 and a non-repo tmp_path both keep
    GitManager a no-op (see skills/git_manager.py's graceful degrade).
    """
    monkeypatch.setenv("GLM_API_KEY", "")
    monkeypatch.setenv("USE_OFFLINE_MODEL", "1")
    monkeypatch.setenv("SKILLS_DB_PATH", str(tmp_path / "skills.db"))
    monkeypatch.setenv("GIT_REPO_PATH", str(tmp_path))
    monkeypatch.setenv("GIT_AUTO_COMMIT", "0")
    return tmp_path


def _cli_json(capsys):
    """Parse the JSON payload main.py's emit() printed.

    skills/git_manager.py (out of this task's scope; see report escalation)
    prints a plain-text "not a git repo" diagnostic to stdout on every
    build_runtime() call when GIT_REPO_PATH isn't a real repo, ahead of
    emit()'s JSON -- so parse from the first '{' rather than the whole
    captured stream.
    """
    out = capsys.readouterr().out
    return json.loads(out[out.index("{") :])


def test_cli_list_empty_registry(cli_env, capsys):
    import main

    rc = main.main(["list"])
    payload = _cli_json(capsys)
    assert rc == 0
    assert payload["success"] is True
    assert payload["total_skills"] == 0
    assert payload["skills"] == []


def test_cli_create_list_use_roundtrip(cli_env, capsys):
    import main

    rc = main.main(["create", "adder", "--description", "adds numbers"])
    created = _cli_json(capsys)
    assert rc == 0
    assert created["result"]["success"] is True
    assert created["result"]["skill_name"] == "adder"

    rc = main.main(["list"])
    listed = _cli_json(capsys)
    assert rc == 0
    assert listed["total_skills"] == 1
    assert listed["skills"][0]["name"] == "adder"

    # `input` is the parameter the pipeline-generated skill declares; an
    # undeclared name is now rejected instead of being silently dropped.
    rc = main.main(["use", "adder", "input=5"])
    used = _cli_json(capsys)
    assert rc == 0
    assert used["result"]["success"] is True
    # Creation now goes through the New Skill Pipeline, so a generated skill
    # carries the pipeline's placeholder body (Task 9's generator) rather than
    # SkillBuilder.offline_template's echo dict. What matters here is that the
    # CLI round trip executes the skill it just created.
    assert isinstance(used["result"]["output"], str)


def test_cli_use_unknown_skill_nonzero_exit(cli_env, capsys):
    import main

    rc = main.main(["use", "ghost"])
    payload = _cli_json(capsys)
    assert rc == 1
    assert payload["result"]["success"] is False
    assert payload["result"]["error"]


def test_cli_create_rejects_invalid_name(cli_env, capsys):
    import main

    rc = main.main(["create", "@bad name!"])
    payload = _cli_json(capsys)
    assert rc == 1
    assert payload["result"]["success"] is False


def test_cli_chat_routes_through_agent(cli_env, capsys):
    import main

    rc = main.main(["chat", "hello", "there"])
    payload = _cli_json(capsys)
    assert rc == 0
    assert payload["intent"] == "general"


def test_cli_gitlog_never_raises(cli_env, capsys):
    import main

    rc = main.main(["gitlog"])
    payload = _cli_json(capsys)
    assert rc == 0
    assert payload["commits"] == []


def test_cli_unknown_command_exit_code(cli_env, capsys):
    import main

    rc = main.main(["bogus-command"])
    assert rc == 2


def test_cli_missing_required_arg_exit_code(cli_env, capsys):
    import main

    rc = main.main(["use"])
    assert rc == 2


def test_cli_chat_empty_message_and_stdin_errors_cleanly(cli_env, capsys, monkeypatch):
    import io
    import sys

    import main

    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    rc = main.main(["chat"])
    payload = _cli_json(capsys)
    assert rc == 2
    assert payload["success"] is False


# ===========================================================================
# Task 22 (guide §1.8.23): pipeline integration — the agent routes through
# pipelines/ instead of re-implementing creation and execution, the intent
# vocabulary is unified with the guide, and process_input()/run() exist.
# ===========================================================================

from agent.main_agent import (  # noqa: E402
    ALL_INTENTS,
    INTENT_CREATE_SKILL,
    INTENT_DEVELOP_SKILL,
    INTENT_GENERAL,
    INTENT_UNKNOWN,
    INTENT_USE_SKILL,
)


def test_intent_vocabulary_matches_the_guide():
    assert ALL_INTENTS == ("use_skill", "create_skill", "general")


def test_deprecated_intent_aliases_still_resolve():
    """External callers using the pre-Task-22 names keep working."""
    assert INTENT_DEVELOP_SKILL == INTENT_CREATE_SKILL == "create_skill"
    assert INTENT_UNKNOWN == INTENT_GENERAL == "general"


def test_agent_holds_both_pipelines(temp_agent):
    from pipelines.existing_skill_pipeline import ExistingSkillPipeline
    from pipelines.new_skill_pipeline import NewSkillPipeline

    assert isinstance(temp_agent.new_pipeline, NewSkillPipeline)
    assert isinstance(temp_agent.existing_pipeline, ExistingSkillPipeline)


def test_pipelines_are_injectable(temp_registry):
    from agent.main_agent import MainAgent

    sentinel_new, sentinel_existing = object(), object()
    with MainAgent(
        registry=temp_registry,
        new_pipeline=sentinel_new,
        existing_pipeline=sentinel_existing,
    ) as agent:
        assert agent.new_pipeline is sentinel_new
        assert agent.existing_pipeline is sentinel_existing


# --- routing through process_input() (22.3) -------------------------------

def test_process_input_routes_creation_to_the_new_pipeline(temp_agent):
    calls = []

    class _Spy:
        def create_skill(self, request, request_data=None, auto_confirm=False, **kw):
            calls.append((request, auto_confirm))
            return {
                "status": "completed", "skill_name": "spied",
                "skill": {"name": "spied", "current_version": 1},
                "errors": [], "qa": None, "response": "",
            }

    temp_agent.new_pipeline = _Spy()
    intent, result = temp_agent.process_input(
        "develop a skill named spied", {"name": "spied"}
    )
    assert intent == INTENT_CREATE_SKILL
    assert result["success"] is True
    assert calls and calls[0][1] is True        # agent runs non-interactively


def test_process_input_routes_execution_to_the_existing_pipeline(temp_agent):
    calls = []

    class _Spy:
        def handle_request(self, request, skill_name=None, input_data=None):
            calls.append(skill_name)
            return {
                "status": "executed", "errors": [], "response": "ok",
                "execution": {
                    "success": True, "output": "spied-output", "error": None,
                    "skill_type": "function", "version": 1,
                    "execution_time_ms": 0.1,
                },
            }

    temp_agent.existing_pipeline = _Spy()
    intent, result = temp_agent.process_input(
        "use skill echo_skill", {"name": "echo_skill", "input": {}}
    )
    assert intent == INTENT_USE_SKILL
    assert result["success"] is True
    assert result["output"] == "spied-output"
    assert calls == ["echo_skill"]


def test_process_input_routes_anything_else_to_the_general_handler(temp_agent):
    intent, result = temp_agent.process_input("what is the weather?")
    assert intent == INTENT_GENERAL
    assert result["success"] is False
    assert "could not determine" in result["message"]


def test_handle_request_still_wraps_process_input(temp_agent):
    response = temp_agent.handle_request("what is the weather?")
    assert response["intent"] == INTENT_GENERAL
    assert response["success"] is True          # handled, though not actioned
    assert response["response"]


# --- creation semantics preserved through the pipeline --------------------

def test_creation_goes_through_the_pipeline_end_to_end(temp_agent):
    response = temp_agent.handle_request(
        "develop a skill named routed_skill",
        request_data={"name": "routed_skill", "description": "routed"},
    )
    assert response["result"]["success"] is True
    assert temp_agent.registry.get_skill("routed_skill") is not None
    assert response["result"]["qa"]["passed"] is True   # QA gate ran


def test_caller_supplied_code_is_not_overwritten_by_generation(temp_agent):
    """The CLI's --code path: if the caller wrote the implementation, the
    pipeline must not silently replace it with a generated placeholder."""
    code = "def run(input: str = '') -> str:\n    return 'mine:' + input\n"
    temp_agent.handle_request(
        "develop a skill named handwritten",
        request_data={"name": "handwritten", "code": code},
    )
    stored = temp_agent.registry.get_skill("handwritten")
    assert "mine:" in stored["code"]


def test_an_explicitly_named_bad_skill_is_rejected_not_renamed(temp_agent):
    """The pipeline sanitizes inferred names, which is right; but a name the
    caller states must be rejected rather than silently changed."""
    response = temp_agent.handle_request(
        "develop a skill", request_data={"name": "@bad name!"}
    )
    assert response["result"]["success"] is False
    assert "Invalid skill" in response["result"]["error"]
    assert temp_agent.registry.get_skill("bad_name") is None


def test_duplicate_creation_reports_already_exists(temp_agent):
    data = {"name": "dup_skill", "description": "d"}
    temp_agent.handle_request("develop a skill named dup_skill", request_data=data)
    second = temp_agent.handle_request("develop a skill named dup_skill", request_data=data)
    assert second["result"]["success"] is False
    assert "already exists" in second["result"]["error"]
    assert "use skill dup_skill" in second["result"]["suggestion"]


# --- run() loop (Task 24.2) ----------------------------------------------

def test_run_loop_handles_requests_until_exit(temp_agent):
    lines = iter(["use skill echo_skill", "exit"])
    written = []
    handled = temp_agent.run(reader=lambda _: next(lines), writer=written.append)
    assert handled == 1
    assert any("ready" in line for line in written)
    assert any("stopped after 1" in line for line in written)


def test_run_loop_skips_blank_lines(temp_agent):
    lines = iter(["", "   ", "exit"])
    handled = temp_agent.run(reader=lambda _: next(lines), writer=lambda _: None)
    assert handled == 0


def test_run_loop_treats_eof_as_exit(temp_agent):
    def _eof(_):
        raise EOFError

    assert temp_agent.run(reader=_eof, writer=lambda _: None) == 0


@pytest.mark.parametrize("word", ["exit", "quit", ":q", "EXIT"])
def test_run_loop_quit_words(temp_agent, word):
    lines = iter([word])
    assert temp_agent.run(reader=lambda _: next(lines), writer=lambda _: None) == 0
