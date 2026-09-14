#!/usr/bin/env python3
import pytest
from agent.main_agent import PersonalAssistantAgent, IntentType
from agent.agent_config import AgentConfig

def test_agent_config_initialization():
    config = AgentConfig()
    assert config.name == "Personal Assistant"
    assert config.version == "1.0.0"
