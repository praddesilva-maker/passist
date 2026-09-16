#!/usr/bin/env python3
"""Git operations for skill file version control with graceful fallback.

:class:`GitManager` wraps ``git`` CLI operations.  It degrades gracefully:
if the target path is not a Git repository (or ``git`` is missing), all
operations simply report failure / empty state instead of raising, so the
rest of the system keeps working.  :class:`GitManagerError` is only raised
when a git command that *should* succeed fails on a real repository.
"""

import os
import subprocess
import sys
from typing import Any, Dict, List, Optional


class GitManagerError(Exception):
    """Raised when a git operation fails inside a real repository."""


def _run_git(repo_path: str, args: List[str]) -> bool:
    """Run ``git -C repo_path *args`` and return True on success."""
    if not repo_path or not os.path.isdir(repo_path):
        return False
    try:
        completed = subprocess.run(
            ["git", "-C", repo_path, *args],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False
    return completed.returncode == 0


class GitManager:
    """Thin, defensive wrapper around the git CLI for one repository path."""

    def __init__(self, repo_path: str) -> None:
        self.repo_path = repo_path
        self.is_repo = False
        self.auto_commit = False
        self._check_repo()

    # ------------------------------------------------------------------
    # Repo detection
    # ------------------------------------------------------------------

    def _check_repo(self) -> None:
        if not self.repo_path or not _run_git(self.repo_path, ["rev-parse", "--is-inside-work-tree"]):
            # Diagnostic only -- must not land on stdout: main.py's CLI (and
            # anything else) writes structured JSON to stdout, and this used
            # to print ahead of it on every non-repo path, corrupting that
            # output (see tests/test_agent.py's cli_env / _cli_json comments,
            # which had to work around it by scanning for the first '{').
            print(
                f"[git-manager] {self.repo_path!r} is not a git repo; auto-commit disabled",
                file=sys.stderr,
            )
            return
        self.is_repo = True
        self.auto_commit = True

    def _git(self, *args: str, allow_fail: bool = False) -> Optional[str]:
        """Run a git command; returns stdout or None. Raises GitManagerError on
        hard failures when allow_fail is False."""
        try:
            completed = subprocess.run(
                ["git", "-C", self.repo_path, *args],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except FileNotFoundError as exc:
            raise GitManagerError("git executable not found") from exc
        except subprocess.TimeoutExpired as exc:
            raise GitManagerError(f"git {' '.join(args)} timed out") from exc
        if completed.returncode != 0 and not allow_fail:
            raise GitManagerError(
                f"git {' '.join(args)} failed: {completed.stderr.strip()}"
            )
        return completed.stdout.strip()

    # ------------------------------------------------------------------
    # Operations (all no-ops outside a repo)
    # ------------------------------------------------------------------

    def add(self, paths: List[str]) -> bool:
        """Stage the given absolute paths (git resolves work-tree-relative)."""
        if not self.is_repo or not paths:
            return False
        try:
            self._git(*["add", "--", *paths])
            return True
        except GitManagerError:
            return False

    def commit(self, message: str) -> bool:
        """Commit staged changes. Returns False when there is nothing to commit."""
        if not self.is_repo:
            return False
        try:
            if not self.status()["changes"] and not self.status()["untracked"]:
                return False
            self._git("commit", "-m", message)
            return True
        except GitManagerError:
            return False

    def status(self) -> Dict[str, Any]:
        if not self.is_repo:
            return {"repo": False, "clean": None, "changes": [], "untracked": []}
        try:
            out = self._git("status", "--porcelain") or ""
        except GitManagerError:
            return {"repo": True, "clean": None, "changes": [], "untracked": []}
        changes: List[str] = []
        untracked: List[str] = []
        for line in out.splitlines():
            if not line.strip():
                continue
            if line.startswith("??"):
                untracked.append(line[3:].strip())
            else:
                changes.append(line[3:].strip())
        return {"repo": True, "clean": not changes and not untracked,
                "changes": changes, "untracked": untracked}

    def log(self, n: Optional[int] = None, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """Return the most recent commits (newest first) as dicts."""
        if not self.is_repo:
            return []
        count = limit if limit is not None else (n or 10)
        try:
            out = self._git("log", f"--max-count={count}",
                            "--format=%H|%h|%an|%s", allow_fail=True) or ""
        except GitManagerError:
            return []
        commits: List[Dict[str, str]] = []
        for line in out.splitlines():
            parts = line.split("|", 3)
            if len(parts) != 4:
                continue
            full_hash, short_hash, author, message = parts
            commits.append({"hash": full_hash, "short_hash": short_hash,
                            "author": author, "message": message})
        return commits

    def init(self, default_branch: Optional[str] = None) -> bool:
        """Initialize the path as a git repository (best effort)."""
        if self.is_repo:
            return True
        cmd = ["init"]
        if default_branch:
            cmd += ["-b", default_branch]
        try:
            _run_git(self.repo_path, cmd)
        except Exception:
            return False
        self._check_repo()
        return self.is_repo
