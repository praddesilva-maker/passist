#!/usr/bin/env python3
"""
Tests for skills/git_manager.py (GitManager).

Safety: every test here operates on a throwaway git repository created
fresh under pytest's ``tmp_path`` fixture. Nothing in this file ever runs a
git command against this project's own repository -- ``GitManager`` takes
an explicit ``repo_path`` constructor argument and never reads any
environment variable to locate a repo, so there is no way for these tests
to accidentally resolve to the real project directory.
"""

import os

import pytest

from skills.git_manager import GitManager, GitManagerError


@pytest.fixture
def git_identity(monkeypatch):
    """Force a deterministic git author/committer identity for subprocess
    git commands, independent of whatever (if anything) is configured on
    the host running the tests."""
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Test Author")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test-author@example.invalid")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Test Author")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test-author@example.invalid")


@pytest.fixture
def throwaway_repo(tmp_path, git_identity):
    """A fresh, real git repository under tmp_path (never the project repo)."""
    repo_dir = tmp_path / "throwaway_repo"
    repo_dir.mkdir()
    manager = GitManager(str(repo_dir))
    assert manager.init() is True
    assert manager.is_repo is True
    return repo_dir, manager


# ---------------------------------------------------------------------------
# Graceful degradation outside a repo
# ---------------------------------------------------------------------------


def test_non_repo_path_degrades_gracefully(tmp_path, capsys):
    plain_dir = tmp_path / "not_a_repo"
    plain_dir.mkdir()
    manager = GitManager(str(plain_dir))

    assert manager.is_repo is False
    assert manager.auto_commit is False
    # The "not a git repo" diagnostic must go to stderr, never stdout: a
    # caller (e.g. main.py's CLI) may be relying on stdout carrying only
    # structured JSON output.
    captured = capsys.readouterr()
    assert "not a git repo" in captured.err
    assert captured.out == ""


def test_missing_path_degrades_gracefully(tmp_path):
    missing = tmp_path / "does_not_exist"
    manager = GitManager(str(missing))
    assert manager.is_repo is False


def test_operations_are_safe_noops_outside_a_repo(tmp_path):
    plain_dir = tmp_path / "not_a_repo"
    plain_dir.mkdir()
    manager = GitManager(str(plain_dir))

    assert manager.add(["some_file.txt"]) is False
    assert manager.commit("message") is False
    assert manager.log() == []
    status = manager.status()
    assert status == {"repo": False, "clean": None, "changes": [], "untracked": []}


def test_add_with_no_paths_returns_false(throwaway_repo):
    _, manager = throwaway_repo
    assert manager.add([]) is False


# ---------------------------------------------------------------------------
# init()
# ---------------------------------------------------------------------------


def test_init_creates_repo_and_enables_auto_commit(tmp_path, git_identity):
    repo_dir = tmp_path / "fresh_repo"
    repo_dir.mkdir()
    manager = GitManager(str(repo_dir))
    assert manager.is_repo is False  # not yet a repo

    result = manager.init()

    assert result is True
    assert manager.is_repo is True
    assert manager.auto_commit is True
    assert (repo_dir / ".git").is_dir()


def test_init_is_idempotent(throwaway_repo):
    _, manager = throwaway_repo
    assert manager.init() is True
    assert manager.is_repo is True


# ---------------------------------------------------------------------------
# add() / commit() / status()
# ---------------------------------------------------------------------------


def test_status_reports_untracked_files(throwaway_repo):
    repo_dir, manager = throwaway_repo
    (repo_dir / "new_file.txt").write_text("hello\n")

    status = manager.status()

    assert status["repo"] is True
    assert status["clean"] is False
    assert "new_file.txt" in status["untracked"]
    assert status["changes"] == []


def test_add_and_commit_round_trip(throwaway_repo):
    repo_dir, manager = throwaway_repo
    file_path = repo_dir / "hello.txt"
    file_path.write_text("hello\n")

    assert manager.add([str(file_path)]) is True
    committed = manager.commit("feat: add hello.txt")
    assert committed is True

    status = manager.status()
    assert status["clean"] is True
    assert status["changes"] == []
    assert status["untracked"] == []


def test_commit_with_nothing_staged_returns_false(throwaway_repo):
    repo_dir, manager = throwaway_repo
    file_path = repo_dir / "hello.txt"
    file_path.write_text("hello\n")
    manager.add([str(file_path)])
    assert manager.commit("first commit") is True

    # Nothing changed since -- a second commit must be a no-op, not an error.
    assert manager.commit("nothing to commit") is False


def test_commit_outside_a_repo_returns_false(tmp_path):
    plain_dir = tmp_path / "not_a_repo"
    plain_dir.mkdir()
    manager = GitManager(str(plain_dir))
    assert manager.commit("anything") is False


# ---------------------------------------------------------------------------
# log()
# ---------------------------------------------------------------------------


def test_log_on_empty_repo_is_empty_list(throwaway_repo):
    _, manager = throwaway_repo
    assert manager.log() == []


def test_log_returns_commits_newest_first(throwaway_repo):
    repo_dir, manager = throwaway_repo

    for i in range(3):
        f = repo_dir / f"file{i}.txt"
        f.write_text(f"content {i}\n")
        manager.add([str(f)])
        assert manager.commit(f"commit {i}") is True

    commits = manager.log()

    assert len(commits) == 3
    # Newest first.
    assert commits[0]["message"] == "commit 2"
    assert commits[-1]["message"] == "commit 0"
    for entry in commits:
        assert set(entry) == {"hash", "short_hash", "author", "message"}
        assert entry["author"] == "Test Author"


def test_log_respects_limit(throwaway_repo):
    repo_dir, manager = throwaway_repo
    for i in range(5):
        f = repo_dir / f"file{i}.txt"
        f.write_text(str(i))
        manager.add([str(f)])
        manager.commit(f"commit {i}")

    commits = manager.log(limit=2)
    assert len(commits) == 2
    assert commits[0]["message"] == "commit 4"


def test_log_n_alias_is_equivalent_to_limit(throwaway_repo):
    repo_dir, manager = throwaway_repo
    for i in range(3):
        f = repo_dir / f"file{i}.txt"
        f.write_text(str(i))
        manager.add([str(f)])
        manager.commit(f"commit {i}")

    assert manager.log(n=1) == manager.log(limit=1)


# ---------------------------------------------------------------------------
# Constructor / error semantics sanity checks
# ---------------------------------------------------------------------------


def test_git_manager_error_is_an_exception_subclass():
    assert issubclass(GitManagerError, Exception)


def test_empty_repo_path_is_not_a_repo():
    manager = GitManager("")
    assert manager.is_repo is False
    assert manager.status()["repo"] is False


# ===========================================================================
# Task 18 is execution logging, not git (the runbook/status mapped it to
# git_manager.py on its title alone). These cover the real requirement:
# _log_skill_run - store each skill execution with its input, output and
# timestamp - plus history retrieval and data integrity (18.1 / 18.2).
# ===========================================================================

import pytest

from skills.unified_stage import UnifiedSkillStage

_ECHO = "def run(text: str = '') -> str:\n    return text[::-1]\n"
_BOOM = "def run(text: str = '') -> str:\n    raise ValueError('nope')\n"


@pytest.fixture
def logged(temp_registry):
    for name, code in (("echo", _ECHO), ("boom", _BOOM)):
        temp_registry.register_skill(
            name=name, skill_type="function", description=name, code=code,
            parameters={"text": {"description": "t", "type": "str"}},
        )
    return temp_registry, UnifiedSkillStage(temp_registry)


def test_successful_execution_is_logged_with_its_data(logged):
    registry, stage = logged
    stage.execute_skill("echo", {"text": "hello"})
    runs = registry.get_skill_runs("echo")
    assert len(runs) == 1
    run = runs[0]
    assert run["input_data"] == {"text": "hello"}
    assert run["output"] == "olleh"
    assert run["timestamp"]
    assert run["success"] is True or run["success"] == 1
    assert run["version"] == 1


def test_failed_execution_is_also_logged(logged):
    """A run history that omits failures cannot distinguish a skill that was
    never called from one that fails every time."""
    registry, stage = logged
    stage.execute_skill("boom", {"text": "x"})
    runs = registry.get_skill_runs("boom")
    assert len(runs) == 1
    assert not runs[0]["success"]
    assert "ValueError: nope" in runs[0]["error"]


def test_run_history_is_per_skill(logged):
    registry, stage = logged
    stage.execute_skill("echo", {"text": "a"})
    stage.execute_skill("echo", {"text": "b"})
    stage.execute_skill("boom", {"text": "c"})
    assert len(registry.get_skill_runs("echo")) == 2
    assert len(registry.get_skill_runs("boom")) == 1


def test_run_history_honours_its_limit(logged):
    registry, stage = logged
    for i in range(4):
        stage.execute_skill("echo", {"text": str(i)})
    assert len(registry.get_skill_runs("echo", limit=2)) == 2


def test_log_run_can_be_suppressed(logged):
    registry, stage = logged
    stage.execute_skill("echo", {"text": "quiet"}, log_run=False)
    assert registry.get_skill_runs("echo") == []


def test_logging_failure_never_breaks_execution(logged):
    """Logging is best-effort: a broken log must not fail a good run."""
    registry, stage = logged

    def _explode(*args, **kwargs):
        raise RuntimeError("log table gone")

    registry.log_skill_run = _explode
    result = stage.execute_skill("echo", {"text": "hi"})
    assert result["success"] is True
    assert result["output"] == "ih"


def test_soft_delete_preserves_run_history(logged):
    """delete_skill is a soft delete, so history deliberately survives."""
    registry, stage = logged
    stage.execute_skill("echo", {"text": "keep"})
    registry.delete_skill("echo")
    assert len(registry.get_skill_runs("echo")) == 1


# --- config isolation (found while verifying Task 0) ----------------------

def test_config_prefers_the_pa_prefixed_environment_names(monkeypatch, tmp_path):
    """The test suite redirects shared state with PA_-prefixed variables;
    config.py originally read only the unprefixed names, so anything
    building a Config() under test pointed at the real registry and repo."""
    import importlib

    import config as config_module

    monkeypatch.setenv("PA_DATABASE_PATH", str(tmp_path / "isolated.db"))
    monkeypatch.setenv("PA_GIT_REPO_PATH", str(tmp_path / "isolated_repo"))
    importlib.reload(config_module)
    built = config_module.Config()
    assert built.database.db_path == str(tmp_path / "isolated.db")
    assert built.git.repo_path == str(tmp_path / "isolated_repo")


def test_config_still_honours_the_unprefixed_names(monkeypatch, tmp_path):
    import importlib

    import config as config_module

    monkeypatch.delenv("PA_DATABASE_PATH", raising=False)
    monkeypatch.setenv("SKILLS_DB_PATH", str(tmp_path / "legacy.db"))
    importlib.reload(config_module)
    assert config_module.Config().database.db_path == str(tmp_path / "legacy.db")
