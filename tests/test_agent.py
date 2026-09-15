#!/usr/bin/env python3
"""
Tests for MainAgent intent routing, offline fallback, and git logging.
"""


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
