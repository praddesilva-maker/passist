# Changelog

## 2026-09-11 — Phase 0 Complete

Initial repository skeleton created with:
- Basic project structure following the architecture spec
- Configuration files (.env.example, default-values.txt)  
- Pyproject.toml with pinned Python 3.12 dependencies
- Base passist package with __init__.py
- Personal Assist API client wrapper (stub implementation)
- Default values loader
- Tool registry system 
- Example tools: getThing and updateThing
- CLI modules (run.py, cli.py) for forwarder and fallback
- Documentation generator and consistency guard
- AGENTS.md master instruction file

## [Unreleased]

### Added
- New quality gate skills: `skill-reviewer` (subjective expert critique) and `skill-hygiene-check` (mechanical conformance sweep)
- Documentation policy enforcement for quality gates
- Run Receipt registration capabilities for skills
- New runtime skill: `use-capability` - the runtime front door that routes user goals to existing tools/skills