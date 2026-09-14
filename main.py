#!/usr/bin/env python3
"""
Personal Assistant Agentic System - Main Entry Point
"""

import asyncio
from agent.main_agent import PersonalAssistantAgent, AgentConfig
from skills.registry import SkillRegistry


def main():
    """Main entry point for the Personal Assistant"""
    # Load configuration
    config = AgentConfig()
    config.load_from_env()
    
    # Initialize registry
    registry = SkillRegistry(db_path=config.database.db_path)
    
    # Initialize agent
    agent = PersonalAssistantAgent(config=config, registry=registry)
    
    print("Personal Assistant Agentic System")
    print(f"Version: {config.version}")
    print("Type 'help' for available commands")
    
    # Main loop
    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() == 'exit':
                print("Goodbye!")
                break
            
            result = asyncio.run(agent.process_input(user_input))
            print("Assistant: " + str(result.output))
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print("Error:", e)


if __name__ == "__main__":
    main()

