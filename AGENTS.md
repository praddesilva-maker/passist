# passist - Local-first Agent Framework

## Project Purpose

A local-first agent framework that allows AI agents to safely and securely read and write to the Personal Assist API entirely from the local machine, without cloud services, admin rights, or MCP server requirements.

## Runtime Contract

### Pinned Runtime Table
- Python interpreter: `/home/praddesilva/ProjectTeams/personal-assistant/.venv/bin/python` (Python 3.12)
- Virtual Environment: `/home/praddesilva/ProjectTeams/personal-assistant/.venv`
- Tool paths:
  - CLI forwarder: `python -m passist.api.run`
  - In-process CLI: `python -m passist.api.cli`
  - Tools registry: `/home/praddesilva/ProjectTeams/personal-assistant/src/passist/api/registry.py`

### Skills Rule
This framework contains a skills system where:
1. Every subfolder of `skills/` containing a `SKILL.md` is a skill  
2. The agent must scan `skills/*/SKILL.md` and match the request to a skill's description
3. Follow that skill in full before improvising

### Tools Rule 
The source of truth for all available tools is:
- Primary source: `/home/praddesilva/ProjectTeams/personal-assistant/src/passist/api/TOOLS.md`
- The agent should read this file first and never discover tools from source code
- Call via: `echo '<json>' | python -m passist.api.run <tool>`
- Write operations require the `--confirm` flag

### Hard Rules
1. **Stdout only for results** - All output must be pure JSON on stdout, never mixed with logs
2. **Never fabricate** - If content can't be grounded in real API/data, use "To be confirmed"  
3. **Upsert not duplicate** - Search for existing objects before creating new ones
4. **No hard-coded config defaults** - All non-secret IDs/config should come from `config/default-values.txt`
5. **Dry-run default** - All write operations default to dry-run unless explicitly confirmed
6. **Confirm destructive writes** - Any state-changing operation requires explicit `--confirm` flag
7. **Temporary file handling** - All temporary working files created by skills must be written to the `/home/praddesilva/ProjectTeams/personal-assistant/temp` directory

### Documentation Policy
Every change to tools or skills must update:
- README.md (tools/skills tables)
- .claude/skills/<name>/SKILL.md stub  
- docs/project/skills.md + docs/prompts.md
- src/passist/api/TOOLS.md (regenerate via the generator)
- CHANGELOG.md (dated entry)
- docs/prompts.md — summary table and skill's launch-prompts section
- metrics/baselines.json + metrics/config.json + primary-volume logic

### Quality Gate Rule
Every new or changed skill must be run through `skill-reviewer` before it's considered done, and any Blocker/Major findings addressed. `skill-hygiene-check` is the mechanical backstop the doc policy leans on.