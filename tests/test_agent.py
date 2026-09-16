#!/usr/bin/env python3
"""
Tests for MainAgent intent routing, offline fallback, and git logging.
"""

import json

import pytest


def test_unknown_intent_offline_response(temp_agent, isolated_env):
    response = temp_agent.handle_request("hello there")
    assert response["intent"] == "unknown"
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
    assert response["intent"] == "develop_skill"
    result = response["result"]
    assert result["success"] is True
    assert result["created"] is True
    assert result["skill"]["name"] == "adder"
    # Now usable through the unified stage.
    use = temp_agent.handle_request(
        "use skill adder",
        request_data={"name": "adder", "input": {"input_value": "x"}},
    )
    assert use["result"]["success"] is True


def test_develop_skill_rejects_invalid_name(temp_agent):
    response = temp_agent.handle_request(
        "develop a skill named @bad name!",
        request_data={"name": "@bad name!", "description": "bad"},
    )
    assert response["intent"] == "develop_skill"
    assert response["result"]["success"] is False
    assert response["result"]["error"]


def test_handle_request_empty_message_no_crash(temp_agent):
    response = temp_agent.handle_request("")
    assert response["intent"] == "unknown"
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

    rc = main.main(["use", "adder", "input_value=5"])
    used = _cli_json(capsys)
    assert rc == 0
    assert used["result"]["success"] is True
    assert used["result"]["output"]["input"] == 5


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
    assert payload["intent"] == "unknown"


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
