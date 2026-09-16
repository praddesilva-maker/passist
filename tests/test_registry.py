#!/usr/bin/env python3
"""
Tests for the central skill registry and unified stage.
"""

import sqlite3
import subprocess

import pytest

from skills.registry import (
    SkillRegistry,
    SkillAlreadyExistsError,
    SkillNotFoundError,
)


def test_registry_register_and_get(temp_registry):
    skill = temp_registry.register_skill(
        name="hello",
        skill_type="function",
        description="Says hello",
        code='def run(input_value: str = ""):\n    return {"hello": input_value}\n',
    )
    assert skill["name"] == "hello"
    assert skill["type"] == "function"
    assert skill["current_version"] == 1

    fetched = temp_registry.get_skill("hello")
    assert fetched["name"] == "hello"
    assert "def run(" in fetched["code"]


def test_registry_duplicate_rejected(temp_registry):
    temp_registry.register_skill(
        name="dup",
        skill_type="function",
        code="def run(input_value: str = ''): return input_value\n",
    )
    try:
        temp_registry.register_skill(
            name="dup",
            skill_type="function",
            code="def run(input_value: str = ''): return input_value\n",
        )
    except SkillAlreadyExistsError:
        return
    raise AssertionError("expected SkillAlreadyExistsError")


def test_registry_missing_skill(temp_registry):
    # get_skill is a lookup: it is declared -> Optional[Dict] and MainAgent
    # .handle_request relies on the None return, so a miss is not an error.
    assert temp_registry.get_skill("nope") is None

    # Mutating a skill that does not exist IS an error.
    for operation in (
        lambda: temp_registry.update_skill("nope", code="def run():\n    return 1\n"),
        lambda: temp_registry.delete_skill("nope"),
    ):
        try:
            operation()
        except SkillNotFoundError:
            continue
        raise AssertionError("expected SkillNotFoundError")


def test_registry_list_and_runs(temp_registry_with_skills):
    skills = temp_registry_with_skills.list_skills()
    assert any(s["name"] == "echo_skill" for s in skills)

    stage = _stage(temp_registry_with_skills)
    result = stage.execute_skill("echo_skill", {"input_value": "hi"})
    assert result["success"] is True
    assert result["output"] == {"echo": "hi"}

    runs = temp_registry_with_skills.get_skill_runs("echo_skill")
    assert len(runs) == 1
    assert runs[0]["success"] is True


def test_stage_unknown_skill_structured_error(temp_registry):
    from skills.unified_stage import UnifiedSkillStage

    stage = UnifiedSkillStage(temp_registry)
    result = stage.execute_skill("ghost", {"input_value": "x"})
    assert result["success"] is False
    assert result["error"]
    assert result["skill_name"] == "ghost"


def _stage(registry: SkillRegistry):
    from skills.unified_stage import UnifiedSkillStage

    return UnifiedSkillStage(registry)


# ----------------------------------------------------------------------
# Task 1 — Database schema verification
# ----------------------------------------------------------------------


def _raw_connect(registry: SkillRegistry) -> sqlite3.Connection:
    conn = sqlite3.connect(registry.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def test_schema_tables_and_columns_exist(temp_registry):
    conn = _raw_connect(temp_registry)
    try:
        names = {
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        for table in ("skills", "skill_versions", "skill_runs", "skill_fts"):
            assert table in names, f"missing table {table}"

        skills_cols = {r["name"] for r in conn.execute("PRAGMA table_info(skills)")}
        assert skills_cols >= {
            "id", "name", "description", "type", "code", "parameters",
            "examples", "current_version", "code_path", "git_commit",
            "active", "created_at", "updated_at",
        }

        versions_cols = {
            r["name"] for r in conn.execute("PRAGMA table_info(skill_versions)")
        }
        assert versions_cols >= {
            "id", "skill_name", "version", "code", "code_path", "code_hash",
            "git_commit", "note", "created_at",
        }

        runs_cols = {r["name"] for r in conn.execute("PRAGMA table_info(skill_runs)")}
        assert runs_cols >= {
            "id", "skill_name", "version", "input_data", "output", "success",
            "error", "duration_ms", "timestamp",
        }
    finally:
        conn.close()


def test_schema_primary_and_foreign_keys(temp_registry):
    conn = _raw_connect(temp_registry)
    try:
        # Primary keys.
        pk_cols = [
            r["name"] for r in conn.execute("PRAGMA table_info(skills)") if r["pk"]
        ]
        assert pk_cols == ["id"]

        # Foreign keys from skill_versions/skill_runs back to skills(name).
        fks = {
            r["table"]: (r["from"], r["to"])
            for r in conn.execute("PRAGMA foreign_key_list(skill_versions)")
        }
        assert fks.get("skills") == ("skill_name", "name")
        fks_runs = {
            r["table"]: (r["from"], r["to"])
            for r in conn.execute("PRAGMA foreign_key_list(skill_runs)")
        }
        assert fks_runs.get("skills") == ("skill_name", "name")

        # Foreign keys are actually enforced (not just declared) on this
        # connection style, matching what the registry itself uses.
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            conn.execute(
                "INSERT INTO skill_versions (skill_name, version, code, created_at) "
                "VALUES ('does-not-exist', 1, 'x', 'now')"
            )
            conn.commit()
            raise AssertionError("expected FK violation to be rejected")
        except sqlite3.IntegrityError:
            pass
    finally:
        conn.close()


def test_schema_not_null_and_check_constraints(temp_registry):
    conn = _raw_connect(temp_registry)
    try:
        # name is NOT NULL.
        try:
            conn.execute(
                "INSERT INTO skills (name, type, created_at, updated_at) "
                "VALUES (NULL, 'function', 'now', 'now')"
            )
            conn.commit()
            raise AssertionError("expected NOT NULL violation on name")
        except sqlite3.IntegrityError:
            pass

        # type is constrained to the three known skill types.
        try:
            conn.execute(
                "INSERT INTO skills (name, type, created_at, updated_at) "
                "VALUES ('badtype', 'not-a-type', 'now', 'now')"
            )
            conn.commit()
            raise AssertionError("expected CHECK violation on type")
        except sqlite3.IntegrityError:
            pass

        # name is UNIQUE.
        conn.execute(
            "INSERT INTO skills (name, type, created_at, updated_at) "
            "VALUES ('uniq', 'function', 'now', 'now')"
        )
        conn.commit()
        try:
            conn.execute(
                "INSERT INTO skills (name, type, created_at, updated_at) "
                "VALUES ('uniq', 'function', 'now', 'now')"
            )
            conn.commit()
            raise AssertionError("expected UNIQUE violation on name")
        except sqlite3.IntegrityError:
            pass
    finally:
        conn.close()


def test_schema_fts_and_autosync_triggers(temp_registry):
    """FTS5 table + auto-update triggers exist (guide Task 1.4), and the
    triggers keep skill_fts in sync even for writes that bypass the
    registry's Python-level ``_sync_fts`` rebuild (e.g. raw SQL)."""
    conn = _raw_connect(temp_registry)
    try:
        trigger_names = {
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger'"
            ).fetchall()
        }
        assert {"skills_fts_ai", "skills_fts_ad", "skills_fts_au"} <= trigger_names

        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            "INSERT INTO skills (name, description, type, created_at, updated_at) "
            "VALUES ('rawskill', 'a raw sql skill', 'function', 'now', 'now')"
        )
        conn.commit()

        hits = conn.execute(
            "SELECT s.name FROM skill_fts f JOIN skills s ON s.id = f.rowid "
            "WHERE skill_fts MATCH 'rawskill'"
        ).fetchall()
        assert [h["name"] for h in hits] == ["rawskill"]

        conn.execute("DELETE FROM skills WHERE name = 'rawskill'")
        conn.commit()
        hits_after_delete = conn.execute(
            "SELECT s.name FROM skill_fts f JOIN skills s ON s.id = f.rowid "
            "WHERE skill_fts MATCH 'rawskill'"
        ).fetchall()
        assert hits_after_delete == []
    finally:
        conn.close()


def test_schema_indexes_present(temp_registry):
    conn = _raw_connect(temp_registry)
    try:
        index_names = {
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            ).fetchall()
        }
        assert {
            "idx_skills_name", "idx_skill_versions_name", "idx_skill_runs_name",
        } <= index_names
    finally:
        conn.close()


# ----------------------------------------------------------------------
# Task 2 — additional basic-operations coverage
# ----------------------------------------------------------------------


def test_get_skill_and_list_skills_expose_id(temp_registry):
    """Task 2.1 requires register_skill() to 'generate a unique skill ID' and
    'return skill ID'. Skills are addressed by name everywhere in this
    codebase, but the underlying unique row id should still be exposed."""
    skill = temp_registry.register_skill(
        name="idcheck", skill_type="function", code="def run():\n    return 1\n"
    )
    assert isinstance(skill.get("id"), int) and skill["id"] > 0

    fetched = temp_registry.get_skill("idcheck")
    assert fetched["id"] == skill["id"]

    listed = {s["name"]: s["id"] for s in temp_registry.list_skills()}
    assert listed["idcheck"] == skill["id"]


def test_search_skills_like_fallback_is_sorted(temp_registry):
    """search_skills() must 'return sorted results' (Task 2.4) even when it
    falls back to LIKE because the FTS5 query matched nothing (e.g. the
    query text only appears as a substring inside a larger token)."""
    for name, description in (
        ("zeta", "wrapxyzsubstrwrap"),
        ("alpha", "xyzsubstrhead"),
        ("middle", "tailxyzsubstr"),
    ):
        temp_registry.register_skill(
            name=name, skill_type="function",
            code="def run():\n    return 1\n", description=description,
        )
    results = temp_registry.search_skills("xyzsubstr")
    assert [r["name"] for r in results] == ["alpha", "middle", "zeta"]


# ----------------------------------------------------------------------
# Task 3 — version control / git integration coverage
# ----------------------------------------------------------------------


def test_version_control_git_commit_roundtrip(tmp_path):
    """Task 3.1 and 3.4 both require 'Git commit working'. The default test
    fixture runs with auto_commit=False, so this exercises the real path
    against an actual git repository."""
    import shutil

    if shutil.which("git") is None:
        import pytest as _pytest

        _pytest.skip("git executable not available")

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], capture_output=True, check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@example.com"],
                    check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)

    registry = SkillRegistry(
        db_path=str(tmp_path / "registry.db"),
        git_repo_path=str(repo),
        auto_commit=True,
        versioned_skills_dir=str(repo / "versioned_skills"),
    )
    try:
        skill = registry.register_skill(
            name="gitskill", skill_type="function",
            code="def run():\n    return 1\n",
        )
        assert skill["git_commit"]

        updated = registry.update_skill(
            "gitskill", code="def run():\n    return 2\n"
        )
        assert updated["git_commit"]
        assert updated["git_commit"] != skill["git_commit"]

        rolled = registry.rollback_to_version("gitskill", 1)
        assert rolled["git_commit"]
        assert rolled["git_commit"] != updated["git_commit"]

        log = subprocess.run(
            ["git", "-C", str(repo), "log", "--oneline"],
            capture_output=True, text=True, check=True,
        )
        commit_lines = [l for l in log.stdout.splitlines() if l.strip()]
        assert len(commit_lines) == 3

        history = registry.get_version_history("gitskill")
        assert [h["version"] for h in history] == [3, 2, 1]
        assert all(h["git_commit"] for h in history)
    finally:
        registry.close()


# ===========================================================================
# Escalations resolved after the Task 1-3 verification pass (2026-09-17):
# list_skills type/tag filtering (Task 2.3), per-version metadata snapshots
# so compare_versions can diff metadata and parameters (Task 3.3), and the
# spec-named aliases get_skill_history / compare_versions (Tasks 3.2/3.3).
# ===========================================================================

@pytest.fixture
def tagged_registry(temp_registry):
    temp_registry.register_skill(
        name="alpha", skill_type="function", description="first skill",
        code="def run(x=1):\n    return x\n",
        parameters={"x": {"type": "int"}}, tags=["math", "core"],
    )
    temp_registry.register_skill(
        name="beta", skill_type="workflow", description="second skill",
        code="def run():\n    return 2\n", tags=["core"],
    )
    return temp_registry


def test_list_skills_filters_by_type(tagged_registry):
    assert [s["name"] for s in tagged_registry.list_skills(skill_type="workflow")] == ["beta"]


def test_list_skills_filters_by_tag(tagged_registry):
    assert [s["name"] for s in tagged_registry.list_skills(tags=["core"])] == ["alpha", "beta"]


def test_list_skills_tag_filter_requires_every_tag(tagged_registry):
    assert [s["name"] for s in tagged_registry.list_skills(tags=["math", "core"])] == ["alpha"]
    assert tagged_registry.list_skills(tags=["absent"]) == []


def test_list_skills_without_filters_is_unchanged(tagged_registry):
    """The new parameters are optional; existing single-argument calls work."""
    assert [s["name"] for s in tagged_registry.list_skills()] == ["alpha", "beta"]


def test_tags_round_trip_as_a_list(tagged_registry):
    assert tagged_registry.get_skill("alpha")["tags"] == ["core", "math"]
    assert tagged_registry.get_skill("beta")["tags"] == ["core"]


def test_compare_versions_detects_metadata_only_change(tagged_registry):
    """Was structurally impossible before: skill_versions stored only code,
    so a change to description or parameters left no trace to diff."""
    tagged_registry.update_skill(
        "alpha", description="renamed skill",
        parameters={"x": {"type": "str"}, "y": {"type": "int"}},
        note="metadata change",
    )
    result = tagged_registry.compare_versions("alpha", 1, 2)
    assert result["changed"] is True
    assert result["diff"] == ""                       # code itself unchanged
    assert result["metadata_changes"]["description"] == {
        "v1": "first skill", "v2": "renamed skill",
    }
    assert result["parameter_changes"]["added"] == ["y"]
    assert result["parameter_changes"]["changed"] == ["x"]
    assert result["parameter_changes"]["removed"] == []


def test_compare_versions_still_diffs_code(tagged_registry):
    tagged_registry.update_skill("alpha", code="def run(x=1):\n    return x * 2\n")
    result = tagged_registry.compare_versions("alpha", 1, 2)
    assert "return x * 2" in result["diff"]
    assert result["changed"] is True


def test_spec_named_aliases_match_their_implementations(tagged_registry):
    tagged_registry.update_skill("alpha", description="v2")
    assert (
        tagged_registry.get_skill_history("alpha")
        == tagged_registry.get_version_history("alpha")
    )
    assert (
        tagged_registry.compare_versions("alpha", 1, 2)
        == tagged_registry.diff_versions("alpha", 1, 2)
    )


def test_migration_adds_columns_to_a_pre_existing_database(tmp_path):
    """A registry file written before these columns existed must still open."""
    from skills.registry import SkillRegistry

    db_path = tmp_path / "old.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL DEFAULT '',
            type TEXT NOT NULL CHECK (type IN ('function','agent','workflow')),
            code TEXT NOT NULL DEFAULT '', parameters TEXT NOT NULL DEFAULT '{}',
            examples TEXT NOT NULL DEFAULT '[]',
            current_version INTEGER NOT NULL DEFAULT 1, code_path TEXT,
            git_commit TEXT, active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE skill_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, skill_name TEXT NOT NULL,
            version INTEGER NOT NULL, code TEXT NOT NULL DEFAULT '',
            code_path TEXT, code_hash TEXT, git_commit TEXT,
            note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
            UNIQUE (skill_name, version));
        INSERT INTO skills (name, description, type, code, created_at, updated_at)
        VALUES ('legacy', 'pre-existing', 'function',
                'def run():\n    return 0\n', '2020-01-01', '2020-01-01');
        """
    )
    conn.commit()
    conn.close()

    registry = SkillRegistry(
        db_path=str(db_path), git_repo_path=str(tmp_path), auto_commit=False
    )
    try:
        legacy = registry.get_skill("legacy")
        assert legacy is not None
        assert legacy["tags"] == []                 # defaulted by the migration
        assert [s["name"] for s in registry.list_skills()] == ["legacy"]
    finally:
        registry.close()


def test_migration_is_idempotent(tmp_path):
    from skills.registry import SkillRegistry

    db_path = str(tmp_path / "twice.db")
    for _ in range(3):
        registry = SkillRegistry(
            db_path=db_path, git_repo_path=str(tmp_path), auto_commit=False
        )
        registry.close()
    registry = SkillRegistry(
        db_path=db_path, git_repo_path=str(tmp_path), auto_commit=False
    )
    try:
        registry.register_skill(
            name="ok", skill_type="function", code="def run():\n    return 1\n",
            tags=["t"],
        )
        assert registry.get_skill("ok")["tags"] == ["t"]
    finally:
        registry.close()


def test_registry_default_path_follows_the_configured_environment(monkeypatch, tmp_path):
    """SkillRegistry() consulted a hardcoded path and ignored the project's
    own configuration, so library and script use wrote to skills/skills.db
    however the project was configured - and a test that forgets the
    isolation fixture reached real data.

    Note: no importlib.reload here. Reloading skills.registry rebinds its
    exception classes, so any other test holding the old SkillNotFoundError
    stops matching it in an except clause.
    """
    from skills.registry import SkillRegistry, _default_db_path

    monkeypatch.setenv("PA_DATABASE_PATH", str(tmp_path / "configured.db"))
    assert _default_db_path() == str(tmp_path / "configured.db")

    registry = SkillRegistry(git_repo_path=str(tmp_path))
    try:
        assert registry.db_path == str(tmp_path / "configured.db")
    finally:
        registry.close()


def test_registry_honours_the_unprefixed_name_too(monkeypatch, tmp_path):
    from skills.registry import _default_db_path

    monkeypatch.delenv("PA_DATABASE_PATH", raising=False)
    monkeypatch.setenv("SKILLS_DB_PATH", str(tmp_path / "legacy.db"))
    assert _default_db_path() == str(tmp_path / "legacy.db")


def test_registry_falls_back_to_the_bundled_path(monkeypatch):
    from skills.registry import _BUILTIN_DB_PATH, _default_db_path

    monkeypatch.delenv("PA_DATABASE_PATH", raising=False)
    monkeypatch.delenv("SKILLS_DB_PATH", raising=False)
    assert _default_db_path() == _BUILTIN_DB_PATH


def test_an_explicit_db_path_still_wins(monkeypatch, tmp_path):
    from skills.registry import SkillRegistry

    monkeypatch.setenv("PA_DATABASE_PATH", str(tmp_path / "ignored.db"))
    registry = SkillRegistry(
        db_path=str(tmp_path / "explicit.db"), git_repo_path=str(tmp_path)
    )
    try:
        assert registry.db_path == str(tmp_path / "explicit.db")
    finally:
        registry.close()
