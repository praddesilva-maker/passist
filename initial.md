Read and follow the PERSONAL_ASSISTANT_GUIDE.md which documents the plan for Personal Assistant Agentic System.

I need you to implement a Personal Assistant Agentic System with the following specifications:

## Core Architecture
- Use Cline (VS Code extension) + GLM (Qwen 30B model)
- Implement two pipelines: New Skill Development and Existing Skill Usage
- Use LangChain as the agent framework
- Centralized skill registry with version control (SQLite + Git)
- Single unified skill stage for all skill types (function, agent, workflow)

## Project Requirements
- Python 3.10+
- LangChain for agent framework
- GLM integration (Qwen 30B)
- SQLite database with version history
- pytest for testing
- Git for version control

## Key Deliverables
1. Complete implementation plan with all Python files
2. Comprehensive test suite with 80%+ coverage
3. Documentation for usage and API
4. Git integration with automatic commits
5. Interactive CLI for skill building
6. Python API for Cline integration

## Development Phases
1. Core foundation (registry + skill stage) - Days 1-2
2. New skill pipeline - Days 3-5  
3. Existing skill pipeline - Days 6-7
4. Main agent implementation - Days 8-9
5. Testing and validation - Days 10-12

## Critical Requirements
- Skills ONLY accessible through central registry (no auto-discovery)
- All skills must be version-controlled with Git
- pytest framework for all skills
- Clean Python API for Cline
- Self-contained in VS Code project

## Testing
- Run all tests with pytest
- Ensure 100% pass rate
- Generate coverage reports
- Test all core functionality

## Documentation
- Provide README.md with usage examples
- Document API usage
- Create troubleshooting guide
- Add code comments

Please implement this complete system following the detailed specifications provided in the implementation guide document. Start with Phase 1 and work through each phase systematically.