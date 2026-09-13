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
- Folder management system for skill execution with dedicated temp and deliverables directories
- `src/passist/api/skill_folder_manager.py` module for handling temporary file operations
- Comprehensive documentation in `/docs/skill-folder-management-implementation.md`
- Project-level documentation in `/docs/project/folder-management.md`
- Enhanced error handling and logging for file system operations
- Context manager approach for automatic setup and cleanup

### Changed
- Updated AGENTS.md to include documentation of the new folder management system
- Standardized directory structure usage across skills execution

## [0.1.0] - 2026-09-12

### Added
- Initial framework implementation for passist agent
- Skills and tools infrastructure
- Basic execution flow with CLI support