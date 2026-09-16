# Personal Assistant — Agentic Skill System

A self-extending assistant. It keeps a registry of *skills* — small Python
programs — and can both **run** the skills it has and **write new ones** on
request, versioning every change.

Everything works offline. With no `GLM_API_KEY` set, the LLM-backed paths fall
back to deterministic rules rather than failing, so the whole system is usable
and testable without an API key or a network connection.

---

## Contents

- [How it fits together](#how-it-fits-together)
- [Installation](#installation)
- [Quick start](#quick-start)
- [CLI reference](#cli-reference)
- [Usage examples](#usage-examples)
- [API reference](#api-reference)
- [Running the tests and QA suite](#running-the-tests-and-qa-suite)
- [Troubleshooting](#troubleshooting)

---

## How it fits together

```
                    ┌──────────────┐
   your request ───▶│  MainAgent   │  detects intent, routes
                    └──────┬───────┘
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
   ┌───────────────────┐       ┌──────────────────────┐
   │ NewSkillPipeline  │       │ ExistingSkillPipeline│
   │ "create a skill"  │       │ "use a skill"        │
   └─────────┬─────────┘       └──────────┬───────────┘
             │                            │
             ▼                            ▼
   ┌───────────────────┐       ┌──────────────────────┐
   │   SkillBuilder    │       │  UnifiedSkillStage   │
   │ build + validate  │       │ load + execute       │
   └─────────┬─────────┘       └──────────┬───────────┘
             └────────────┬───────────────┘
                          ▼
                 ┌──────────────────┐
                 │  SkillRegistry   │  SQLite: skills,
                 │  single source   │  versions, run log
                 └──────────────────┘
```

| Component | Module | Responsibility |
|---|---|---|
| **Registry** | `skills/registry.py` | The single source of truth. Skills, version history, and a log of every execution, in SQLite. |
| **Unified stage** | `skills/unified_stage.py` | Loads and executes any skill type uniformly. Owns module compilation, keyword resolution and run logging. |
| **Skill builder** | `skills/skill_builder.py` | Creates and interactively edits skills: selection, description/parameter/code editing, templates, export/import, rollback. |
| **New skill pipeline** | `pipelines/new_skill_pipeline.py` | Turns a request into a registered skill: analyse → structure → code → review → register → QA gate. |
| **Existing skill pipeline** | `pipelines/existing_skill_pipeline.py` | Turns a request into a skill run: search → parse parameters → validate → execute. |
| **Main agent** | `agent/main_agent.py` | Detects intent and routes to the right pipeline. Keeps conversation memory. |
| **QA suite** | `qa/qa_test_suite.py` | Exercises the assembled system end to end and reports what works. |
| **CLI** | `main.py` | Command-line entry point; emits JSON. |

There are exactly **three skill types**: `function`, `agent`, `workflow`.

---

## Installation

Requires **Python 3.10+** (developed on 3.14).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Optionally, to enable the LLM-backed paths:

```bash
export GLM_API_KEY="your-key"
```

Without it the system runs **offline**: intent detection, skill-structure
analysis and parameter parsing all fall back to deterministic rules. Nothing
breaks; the results are just less flexible.

### Configuration

Set via environment variables (see `config.py`):

| Variable | Default | Purpose |
|---|---|---|
| `GLM_API_KEY` | *(empty)* | LLM key. Empty means offline mode. |
| `GLM_MODEL` | `glm-4` | Model name. |
| `GLM_TEMPERATURE` | `0.7` | Sampling temperature. |
| `PA_DATABASE_PATH` *(or `SKILLS_DB_PATH`)* | `./skills/skills.db` | Registry database. |
| `PA_GIT_REPO_PATH` *(or `GIT_REPO_PATH`)* | project root | Repo for skill auto-commits. |
| `GIT_AUTO_COMMIT` | `true` | Commit skill changes to git. |

The `PA_`-prefixed names take precedence. The test suite sets them to redirect
all state into a temporary directory.

---

## Quick start

```bash
# 1. See what skills exist (empty to begin with)
.venv/bin/python main.py list

# 2. Create one
.venv/bin/python main.py create greeter --description "greets a person"

# 3. Run it
.venv/bin/python main.py use greeter input=world

# 4. Talk to the assistant and let it decide what to do
.venv/bin/python main.py chat "create a skill named word_counter that counts words"
```

Every command prints JSON to stdout and exits `0` on success, `1` on a handled
error, `2` on a usage error.

---

## CLI reference

| Command | Purpose |
|---|---|
| `list` | List registered skills. |
| `create NAME [--type] [--description] [--code]` | Register a new skill. Generates an implementation unless `--code` is given. |
| `use NAME [key=value ...]` | Execute a skill with arguments. |
| `chat MESSAGE...` | Send a request to the agent, which picks the pipeline. |
| `gitlog [LIMIT]` | Show recent registry git commits. |

`--type` is one of `function`, `agent`, `workflow` (default `function`).

---

## Usage examples

### Creating a skill

Let the pipeline write the implementation:

```bash
.venv/bin/python main.py create summarizer \
    --type function --description "summarizes a block of text"
```

Or supply your own — the pipeline registers what you wrote rather than
generating over it:

```bash
.venv/bin/python main.py create shouter \
    --code 'def run(text: str = "") -> str:
    return text.upper()'
```

In Python:

```python
from pipelines import NewSkillPipeline

pipeline = NewSkillPipeline()
result = pipeline.create_skill(
    "create a skill named shouter that upper-cases text",
    auto_confirm=True,          # skip the interactive review
)
print(result["status"])          # "completed"
print(result["qa"]["passed"])    # True - it was executed as a check
```

`status` is one of `completed`, `qa_failed`, `registration_failed`,
`already_exists`, `cancelled`, `edit_requested`, `error`.

> The QA gate runs **after** registration — both of its checks look the skill up
> in the registry — so `qa_failed` means *registered but did not pass its smoke
> test*, not "nothing happened".

### Using a skill

```bash
.venv/bin/python main.py use shouter text=hello
```

```python
from pipelines import ExistingSkillPipeline

pipeline = ExistingSkillPipeline()
result = pipeline.handle_request("shout text=hello")
print(result["status"])                 # "executed"
print(result["execution"]["output"])    # "HELLO" - for the --code version above
```

> A skill whose implementation was **generated** carries a placeholder body
> that returns an empty value until you fill it in (edit it with
> `SkillBuilder.edit_code`, which creates a new version). Only a skill you
> supplied code for does real work immediately.

If nothing matches, you get `not_found` plus suggestions rather than a dead end:

```python
result = pipeline.handle_request("launch a rocket to mars")
print(result["suggestions"]["message"])
```

### Version control

Every edit creates a new version; nothing is overwritten.

```python
from skills.skill_builder import SkillBuilder

builder = SkillBuilder()
builder.edit_description("shouter", "upper-cases text loudly")

print(builder.format_version_history("shouter"))
print(builder.format_version_diff("shouter", 1, 2))

builder.rollback("shouter", 1)     # restored as a NEW version
```

Comparison covers metadata, parameters *and* code — a description-only change
is still a detected change.

### Templates, export and import

```python
builder.available_templates()                    # ['agent', 'function', 'workflow']
builder.create_from_template("pipeline_job", skill_type="workflow")

payload = builder.export_skill("pipeline_job")["json"]   # portable JSON
builder.import_skill(payload)                            # validated before writing
```

### Talking to the agent

```python
from agent.main_agent import MainAgent

with MainAgent() as agent:
    print(agent.handle_request("create a skill named adder")["response"])
    print(agent.handle_request("use skill adder input=2")["response"])
    agent.run()      # interactive loop
```

---

## API reference

### `MainAgent` — `agent/main_agent.py`

| Method | Description |
|---|---|
| `detect_intent(request)` | Classify as `create_skill`, `use_skill` or `general`. |
| `process_input(request, request_data=None)` | Route to a pipeline. Returns `(intent, result)`. |
| `handle_request(request, request_data=None)` | `process_input` wrapped in the response envelope. |
| `run(reader=None, writer=None)` | Interactive loop; returns the number of requests handled. |
| `get_memory()` / `get_history(limit=None)` | Memory snapshot / conversation turns, oldest first. |
| `get_registry_status()` / `get_stats()` | Registry and session counters. |
| `cleanup()` | Close the registry. Idempotent; also a context manager. |

Response envelope: `intent`, `success`, `skill_name`, `result`, `response`,
`error`. Note `success` means *the request was handled*; whether the operation
itself worked is `result["success"]`.

### `NewSkillPipeline` — `pipelines/new_skill_pipeline.py`

| Method | Description |
|---|---|
| `detect_intent(request)` | `create_skill` / `use_skill` / `general`. |
| `analyze_request(request, request_data=None)` | Request → registry-compatible structure. |
| `generate_code(structure)` | Dispatch to the function/agent/workflow generator. |
| `create_skill(request, ..., auto_confirm=False, git=None)` | The complete creation flow. |

### `ExistingSkillPipeline` — `pipelines/existing_skill_pipeline.py`

| Method | Description |
|---|---|
| `find_skills(query, limit, skill_type, min_score)` | Ranked search. |
| `display_results(results)` / `suggest(query)` | Rendering and no-match suggestions. |
| `parse_input_to_params(text, skill)` | Natural language → parameters. |
| `validate_params(params, skill)` | Type coercion, required checks, defaults. |
| `execute_skill(name, input_data)` | Execute, dispatching on skill type. |
| `handle_request(request, skill_name=None, input_data=None)` | Search → parse → validate → execute. |

Statuses: `executed`, `not_found`, `ambiguous`, `invalid_params`,
`execution_failed`, `error`.

### `SkillRegistry` — `skills/registry.py`

| Method | Description |
|---|---|
| `register_skill(name, skill_type, description, code, parameters, examples, tags)` | Register at v1. |
| `get_skill(name)` | The active skill, or `None`. |
| `list_skills(include_inactive, skill_type, tags)` | List with optional filters. |
| `search_skills(query, limit)` | Full-text search with a LIKE fallback. |
| `update_skill(name, ...)` | Write a new version. |
| `delete_skill(name)` | **Soft** delete — marks inactive, keeps history. |
| `get_version_history(name)` *(alias `get_skill_history`)* | Versions, newest first. |
| `diff_versions(name, v1, v2)` *(alias `compare_versions`)* | Code diff plus metadata and parameter changes. |
| `rollback_to_version(name, version)` | Restore an old version as a new one. |
| `log_skill_run(...)` / `get_skill_runs(name, limit)` | Execution log — successes *and* failures. |
| `export_skill(name)` / `import_skill(payload)` | Portable payloads. |

### `UnifiedSkillStage` — `skills/unified_stage.py`

| Method | Description |
|---|---|
| `execute_skill(name, input_data, skill_type=None, log_run=True)` | Execute; always returns a result dict. |
| `load_skill(name, version=None)` | Load as a runnable (cached). |
| `run(name, **kwargs)` | Return raw output; raises on failure. |
| `cache_stats()` / `clear_cache()` | Cache hits, misses, size. |

### `SkillBuilder` — `skills/skill_builder.py`

Selection (`select_skill`, `describe_skill`, `format_skill_list`), editing
(`edit_description`, `add_parameter`, `update_parameter`, `remove_parameter`,
`edit_code`), versions (`version_history`, `compare_versions`, `rollback`,
`format_version_history`, `format_version_diff`), templates
(`available_templates`, `template_for`, `create_from_template`), portability
(`export_skill`, `import_skill`), and `run_interactive_session()`.

Every public method returns a structured dict with `success` and `error` —
validation failures come back as payloads, not exceptions.

---

## Running the tests and QA suite

```bash
.venv/bin/python -m pytest -q
```

The suite runs fully offline and never touches the real registry or repo.

The system-level QA suite exercises the assembled system:

```bash
.venv/bin/python -c "from qa import run_qa; print(run_qa()['report'])"
```

Select a scope:

```python
from qa import run_qa

run_qa(test_type="core",     pipeline="both")      # registry, loading, versions
run_qa(test_type="critical", pipeline="new")       # registration + execution paths
run_qa(test_type="full",     pipeline="both")      # everything, incl. integration
```

It builds a throwaway registry, so a QA run never writes fixtures into
`skills/skills.db`.

---

## Troubleshooting

### `"I could not determine what you want to do (running offline...)"`

The agent could not classify your request. Offline, intent detection is keyword
based. Phrase it explicitly — `use skill <name>` or `create a skill named
<name>` — or set `GLM_API_KEY` for a more flexible classifier.

### `missing required parameter(s): x`

The skill declares a parameter you did not supply. Check what it expects:

```python
from skills.registry import SkillRegistry
print(SkillRegistry().get_skill("your_skill")["parameters"])
```

Then pass it: `main.py use your_skill x=value`.

### `unknown parameter 'y'`

You passed a name the skill does not declare. This is deliberate — it catches
typos instead of silently dropping the argument. Use the declared name.

Note a skill registered with *no* `parameters` metadata accepts anything; the
unified stage resolves arguments against the real function signature.

### `Invalid skill: name must be alphanumeric (with - or _)`

Skill names allow letters, digits, `-` and `_`. When *you* state a name it is
validated rather than silently rewritten; when the pipeline infers one from
free text, it sanitizes it.

### `Skill 'x' already exists`

Creation is idempotent and will not overwrite. Edit it instead
(`SkillBuilder.edit_code`) — which creates a new version — or pick another name.

### A skill registered but reports `qa_failed`

It passed registration but failed its smoke test. The skill *is* registered.
Inspect the reason:

```python
result = pipeline.create_skill("...", auto_confirm=True)
print(result["qa"]["errors"])
```

### `OfflineModelUnavailableError` from `bind_tools`

Tool calling genuinely cannot work without a model. Set `GLM_API_KEY`. Note the
agent loader drops tools when offline rather than crashing.

### Everything returns `"[offline]"`

No `GLM_API_KEY` is set. Expected — set it to enable LLM paths.

### `no such column` from the registry

A database written by an older schema. The registry migrates itself on open
(adding `tags`, and per-version `description`/`parameters`), so opening it once
with the current code fixes it. If it persists, the file may be corrupt — move
it aside and let a fresh one be created.

### Tests write to the real registry

Make sure `PA_DATABASE_PATH` and `PA_GIT_REPO_PATH` are set (the `isolated_env`
fixture does this). `config.py` prefers those over the unprefixed names
precisely so tests cannot reach real state.

### Debugging tips

- Every public method returns a structured dict — inspect `error` and, on the
  pipelines, `status`, rather than relying on exceptions.
- `registry.get_skill_runs(name)` shows the execution history, failures
  included, with the input, output and error of each run.
- `stage.cache_stats()` reports cache hits and misses.
- `pipeline.stats` counts intents, parses and outcomes.
- The QA suite reports per-check failures with tracebacks:
  `run_qa()["summary"]["failures"]`.
