#!/usr/bin/env python3
"""
Central Skill Registry - the single source of truth for all skills.

Design rules (from PERSONAL_ASSISTANT_GUIDE.md):
* Skills are ONLY accessible through this registry.  There is no
  auto-discovery: nothing is imported from the filesystem unless it has been
  registered here.
* The registry is backed by SQLite (tables: ``skills``, ``skill_versions``,
  ``skill_runs``, ``skill_fts``) and is Git-controlled: every mutation that
  writes a skill file also records the resulting commit hash.
* All skill types (function, agent, workflow) are handled uniformly.
"""

import hashlib
import json
import os
import re
import sqlite3
from typing import Any, Dict, List, Optional

from .models import utcnow_iso
from .git_manager import GitManager, GitManagerError

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "skills.db"
)


class RegistryError(Exception):
    """Base exception for registry errors."""


class SkillNotFoundError(RegistryError):
    """Raised when a skill is not found."""


class SkillAlreadyExistsError(RegistryError):
    """Raised when registering a skill name that already exists."""


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _loads_dict(value: Any) -> Dict[str, Any]:
    """Best-effort JSON-object decode; always returns a dict."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (ValueError, TypeError):
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


_SCHEMA = """
CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    type TEXT NOT NULL CHECK (type IN ('function', 'agent', 'workflow')),
    code TEXT NOT NULL DEFAULT '',
    parameters TEXT NOT NULL DEFAULT '{}',
    examples TEXT NOT NULL DEFAULT '[]',
    tags TEXT NOT NULL DEFAULT '[]',
    current_version INTEGER NOT NULL DEFAULT 1,
    code_path TEXT,
    git_commit TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skill_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT NOT NULL,
    version INTEGER NOT NULL,
    code TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    parameters TEXT NOT NULL DEFAULT '{}',
    code_path TEXT,
    code_hash TEXT,
    git_commit TEXT,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (skill_name) REFERENCES skills (name) ON DELETE CASCADE,
    UNIQUE (skill_name, version)
);

CREATE TABLE IF NOT EXISTS skill_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT NOT NULL,
    version INTEGER,
    input_data TEXT NOT NULL DEFAULT '{}',
    output TEXT,
    success INTEGER NOT NULL DEFAULT 1,
    error TEXT,
    duration_ms REAL NOT NULL DEFAULT 0,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (skill_name) REFERENCES skills (name) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_skills_name ON skills (name);
CREATE INDEX IF NOT EXISTS idx_skill_versions_name ON skill_versions (skill_name);
CREATE INDEX IF NOT EXISTS idx_skill_runs_name ON skill_runs (skill_name);
"""


class SkillRegistry:
    """SQLite-backed, Git-controlled central skill registry."""

    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        git_repo_path: Optional[str] = None,
        auto_commit: bool = True,
        versioned_skills_dir: Optional[str] = None,
    ) -> None:
        self.db_path = db_path
        self.git_repo_path = git_repo_path or os.path.dirname(os.path.abspath(db_path))
        self.auto_commit = auto_commit
        self._git: Optional[GitManager] = None
        # Single, consistent directory for versioned skill files.  Both
        # _persist_skill_file and _cleanup_old_versions operate on this path.
        self.versioned_skills_dir = versioned_skills_dir or os.path.join(
            os.path.dirname(os.path.abspath(db_path)), "versioned_skills"
        )
        self._fts_available = False
        self._closed = False
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)) or ".", exist_ok=True)
        self._init_db()

    @property
    def git(self) -> Optional[GitManager]:
        """Lazy-initialized GitManager (None if the repo path is not a repo)."""
        if self._git is None:
            try:
                self._git = GitManager(self.git_repo_path)
            except GitManagerError:
                self._git = None
        return self._git

    def close(self) -> None:
        """Release registry resources.

        Connections are opened per-operation and closed in ``finally`` blocks,
        so there is no long-lived handle to shut down.  This drops the cached
        :class:`GitManager` and marks the registry closed so callers (and test
        fixtures) have a deterministic teardown hook.  Idempotent.
        """
        self._git = None
        self._closed = True

    def __enter__(self) -> "SkillRegistry":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_db(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
            self._migrate(conn)
            self._fts_available = self._setup_fts(conn)
            conn.commit()
        finally:
            conn.close()

    # Columns added after the original schema shipped: {table: {column: ddl}}.
    _ADDED_COLUMNS = {
        "skills": {
            "tags": "TEXT NOT NULL DEFAULT '[]'",
        },
        "skill_versions": {
            "description": "TEXT NOT NULL DEFAULT ''",
            "parameters": "TEXT NOT NULL DEFAULT '{}'",
        },
    }

    @classmethod
    def _migrate(cls, conn: sqlite3.Connection) -> None:
        """Add columns missing from a database created by an older schema.

        ``CREATE TABLE IF NOT EXISTS`` is a no-op on an existing table, so a
        registry file written before these columns existed would otherwise
        raise ``no such column`` on the first query. Idempotent: each column
        is added only when ``PRAGMA table_info`` says it is absent.
        """
        for table, columns in cls._ADDED_COLUMNS.items():
            try:
                existing = {
                    row[1] for row in conn.execute(
                        f"PRAGMA table_info({table})"
                    ).fetchall()
                }
            except sqlite3.OperationalError:
                continue
            if not existing:          # table not created yet
                continue
            for column, ddl in columns.items():
                if column not in existing:
                    conn.execute(
                        f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"
                    )

    @staticmethod
    def _setup_fts(conn: sqlite3.Connection) -> bool:
        try:
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS skill_fts
                USING fts5(name, description, content='skills', content_rowid='id')
                """
            )
            # Triggers keep skill_fts in sync automatically for *any* write to
            # ``skills`` (including raw SQL outside this class), per the
            # guide's Task 1.4 requirement.  ``_sync_fts``'s rebuild-on-write
            # (called from the CRUD methods below) remains as a redundant,
            # harmless safety net on top of these triggers.
            conn.executescript(
                """
                CREATE TRIGGER IF NOT EXISTS skills_fts_ai AFTER INSERT ON skills BEGIN
                    INSERT INTO skill_fts(rowid, name, description)
                    VALUES (new.id, new.name, new.description);
                END;
                CREATE TRIGGER IF NOT EXISTS skills_fts_ad AFTER DELETE ON skills BEGIN
                    INSERT INTO skill_fts(skill_fts, rowid, name, description)
                    VALUES ('delete', old.id, old.name, old.description);
                END;
                CREATE TRIGGER IF NOT EXISTS skills_fts_au AFTER UPDATE ON skills BEGIN
                    INSERT INTO skill_fts(skill_fts, rowid, name, description)
                    VALUES ('delete', old.id, old.name, old.description);
                    INSERT INTO skill_fts(rowid, name, description)
                    VALUES (new.id, new.name, new.description);
                END;
                """
            )
            return True
        except sqlite3.OperationalError:
            return False

    def _sync_fts(self, conn: sqlite3.Connection) -> None:
        if not self._fts_available:
            return
        try:
            conn.execute("INSERT INTO skill_fts(skill_fts) VALUES('rebuild')")
        except sqlite3.OperationalError:
            pass

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def register_skill(
        self,
        name: str,
        skill_type: str = "function",
        description: str = "",
        code: str = "",
        parameters: Optional[Dict[str, Any]] = None,
        examples: Optional[List[Dict[str, Any]]] = None,
        note: str = "",
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Register a brand-new skill (v1).

        Raises SkillAlreadyExistsError if the name is already taken and
        RegistryError when the skill is invalid.
        """
        validation = self.validate_skill(
            {"name": name, "type": skill_type, "code": code}
        )
        if not validation["valid"]:
            raise RegistryError(
                f"Invalid skill: {'; '.join(validation['errors'])}"
            )
        now = utcnow_iso()
        conn = self._connect()
        try:
            exists = conn.execute(
                "SELECT 1 FROM skills WHERE name = ?", (name,)
            ).fetchone()
            if exists:
                raise SkillAlreadyExistsError(f"Skill '{name}' already exists")
            conn.execute(
                """
                INSERT INTO skills (name, description, type, code, parameters,
                                    examples, tags, current_version, code_path,
                                    git_commit, active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, NULL, NULL, 1, ?, ?)
                """,
                (
                    name,
                    description,
                    skill_type,
                    code,
                    json.dumps(parameters or {}),
                    json.dumps(examples or []),
                    json.dumps(sorted(set(tags or []))),
                    now,
                    now,
                ),
            )
            self._insert_version(
                conn, name, 1, code, note or "initial version",
                description=description, parameters=parameters or {},
            )
            self._sync_fts(conn)
            conn.commit()
        finally:
            conn.close()

        code_path = self._persist_skill_file(name, code, 1)
        git_commit = self._commit_skill_files(name, "initial version", code_path)
        self._store_file_and_commit(name, 1, code_path, git_commit)
        return self.get_skill(name)

    def update_skill(
        self,
        name: str,
        code: Optional[str] = None,
        description: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        examples: Optional[List[Dict[str, Any]]] = None,
        note: str = "",
    ) -> Dict[str, Any]:
        """Update an existing skill, bumping its version (new history row)."""
        existing = self.get_skill(name)
        if existing is None:
            raise SkillNotFoundError(f"Skill '{name}' not found")

        new_code = code if code is not None else existing.get("code", "")
        new_description = (
            description if description is not None else existing.get("description", "")
        )
        new_parameters = (
            parameters if parameters is not None else existing.get("parameters", {})
        )
        new_examples = (
            examples if examples is not None else existing.get("examples", [])
        )
        new_version = existing["current_version"] + 1

        conn = self._connect()
        try:
            now = utcnow_iso()
            conn.execute(
                """
                UPDATE skills
                SET description = ?, code = ?, parameters = ?, examples = ?,
                    current_version = ?, updated_at = ?
                WHERE name = ?
                """,
                (
                    new_description,
                    new_code,
                    json.dumps(new_parameters),
                    json.dumps(new_examples),
                    new_version,
                    now,
                    name,
                ),
            )
            self._insert_version(
                conn, name, new_version, new_code, note,
                description=new_description, parameters=new_parameters,
            )
            self._sync_fts(conn)
            conn.commit()
        finally:
            conn.close()

        code_path = self._persist_skill_file(name, new_code, new_version)
        git_commit = self._commit_skill_files(name, f"v{new_version}", code_path)
        self._store_file_and_commit(name, new_version, code_path, git_commit)
        return self.get_skill(name)

    def delete_skill(self, name: str) -> None:
        """Soft-delete: mark the skill inactive (history is preserved)."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT 1 FROM skills WHERE name = ?", (name,)
            ).fetchone()
            if row is None:
                raise SkillNotFoundError(f"Skill '{name}' not found")
            conn.execute(
                "UPDATE skills SET active = 0, updated_at = ? WHERE name = ?",
                (utcnow_iso(), name),
            )
            self._sync_fts(conn)
            conn.commit()
        finally:
            conn.close()

    def activate_skill(self, name: str) -> Dict[str, Any]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT 1 FROM skills WHERE name = ?", (name,)
            ).fetchone()
            if row is None:
                raise SkillNotFoundError(f"Skill '{name}' not found")
            conn.execute(
                "UPDATE skills SET active = 1, updated_at = ? WHERE name = ?",
                (utcnow_iso(), name),
            )
            self._sync_fts(conn)
            conn.commit()
        finally:
            conn.close()
        return self.get_skill(name)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    def get_skill(self, name: str) -> Optional[Dict[str, Any]]:
        """Return the active skill dict for ``name`` or None."""
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT id, name, description, type, code, parameters, examples,
                       tags, current_version, code_path, git_commit, active,
                       created_at, updated_at
                FROM skills WHERE name = ? AND active = 1
                """,
                (name,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return self._row_to_skill(row)

    def list_skills(
        self,
        include_inactive: bool = False,
        skill_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """List registered skills, newest filters optional (Task 2.3).

        ``skill_type`` restricts to one canonical type. ``tags`` keeps only
        skills carrying **every** listed tag. Both default to None, so the
        existing single-argument calls are unaffected.
        """
        clauses = [] if include_inactive else ["active = 1"]
        params: List[Any] = []
        if skill_type:
            clauses.append("type = ?")
            params.append(skill_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        conn = self._connect()
        try:
            rows = conn.execute(
                f"""
                SELECT id, name, description, type, code, parameters, examples,
                       tags, current_version, code_path, git_commit, active,
                       created_at, updated_at
                FROM skills {where} ORDER BY name
                """,
                tuple(params),
            ).fetchall()
        finally:
            conn.close()
        skills = [self._row_to_skill(r) for r in rows]
        if tags:
            wanted = set(tags)
            skills = [
                s for s in skills
                if wanted <= set(s.get("tags") or [])
            ]
        return skills

    def get_version(self, name: str, version: int) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT skill_name, version, code, description, parameters,
                       code_path, code_hash, git_commit, note, created_at
                FROM skill_versions
                WHERE skill_name = ? AND version = ?
                """,
                (name, version),
            ).fetchone()
        finally:
            conn.close()
        return dict(row) if row is not None else None

    def get_version_history(self, name: str) -> List[Dict[str, Any]]:
        """Full version history for a skill, newest first."""
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT skill_name, version, code, description, parameters,
                       code_path, code_hash, git_commit, note, created_at
                FROM skill_versions
                WHERE skill_name = ?
                ORDER BY version DESC
                """,
                (name,),
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) for r in rows]

    def rollback_to_version(self, name: str, version: int) -> Dict[str, Any]:
        """Restore an older version as a NEW version (history preserved)."""
        old = self.get_version(name, version)
        if old is None:
            raise SkillNotFoundError(
                f"Version {version} of skill '{name}' not found"
            )
        return self.update_skill(name, code=old["code"], note=f"rollback to v{version}")

    def diff_versions(self, name: str, v1: int, v2: int) -> Dict[str, Any]:
        """Compare two versions of a skill (Task 3.3).

        Reports three kinds of change, per the guide's requirement to
        "compare metadata... compare parameters... compare implementation
        code":

        * ``diff`` - a unified diff of the implementation code
        * ``metadata_changes`` - per-field ``{"v1":…, "v2":…}`` for the
          version metadata that differs (description, note, git_commit)
        * ``parameter_changes`` - ``added`` / ``removed`` / ``changed``
          parameter names between the two versions

        ``changed`` is True when anything at all differs, so a caller need
        not inspect all three.
        """
        import difflib

        row1 = self.get_version(name, v1)
        row2 = self.get_version(name, v2)
        if row1 is None or row2 is None:
            raise SkillNotFoundError(f"Version(s) {v1}/{v2} of '{name}' not found")

        diff = "".join(
            difflib.unified_diff(
                row1["code"].splitlines(keepends=True),
                row2["code"].splitlines(keepends=True),
                fromfile=f"{name} v{v1}",
                tofile=f"{name} v{v2}",
            )
        )

        metadata_changes: Dict[str, Any] = {}
        for field in ("description", "note", "git_commit"):
            before, after = row1.get(field), row2.get(field)
            if before != after:
                metadata_changes[field] = {"v1": before, "v2": after}

        params1 = _loads_dict(row1.get("parameters"))
        params2 = _loads_dict(row2.get("parameters"))
        parameter_changes = {
            "added": sorted(set(params2) - set(params1)),
            "removed": sorted(set(params1) - set(params2)),
            "changed": sorted(
                key for key in set(params1) & set(params2)
                if params1[key] != params2[key]
            ),
        }

        return {
            "v1": row1,
            "v2": row2,
            "diff": diff,
            "metadata_changes": metadata_changes,
            "parameter_changes": parameter_changes,
            "changed": bool(
                diff
                or metadata_changes
                or any(parameter_changes.values())
            ),
        }

    # -- spec-named aliases (guide Tasks 3.2 / 3.3) ---------------------
    # The guide names these get_skill_history() and compare_versions(); the
    # implementation and every caller use get_version_history()/
    # diff_versions(). Renaming would break those callers, so both names are
    # offered and the DoD's naming requirement is met without a rename.

    def get_skill_history(self, name: str) -> List[Dict[str, Any]]:
        """Alias for :meth:`get_version_history` (guide Task 3.2)."""
        return self.get_version_history(name)

    def compare_versions(self, name: str, v1: int, v2: int) -> Dict[str, Any]:
        """Alias for :meth:`diff_versions` (guide Task 3.3)."""
        return self.diff_versions(name, v1, v2)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_skills(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Full-text search with LIKE fallback."""
        query = (query or "").strip()
        if not query:
            return self.list_skills()
        conn = self._connect()
        try:
            if self._fts_available:
                try:
                    rows = conn.execute(
                        """
                        SELECT s.name, s.description, s.type, s.current_version
                        FROM skill_fts f
                        JOIN skills s ON s.id = f.rowid
                        WHERE skill_fts MATCH ? AND s.active = 1
                        ORDER BY rank
                        LIMIT ?
                        """,
                        (self._fts_query(query), limit),
                    ).fetchall()
                    if rows:
                        return [
                            {
                                "name": r["name"],
                                "description": r["description"],
                                "type": r["type"],
                                "current_version": r["current_version"],
                                "score": None,
                            }
                            for r in rows
                        ]
                except sqlite3.OperationalError:
                    pass
            like = f"%{query}%"
            rows = conn.execute(
                """
                SELECT name, description, type, current_version
                FROM skills
                WHERE active = 1 AND (name LIKE ? OR description LIKE ?)
                ORDER BY name
                LIMIT ?
                """,
                (like, like, limit),
            ).fetchall()
        finally:
            conn.close()
        return [dict(r) | {"score": None} for r in rows]

    @staticmethod
    def _fts_query(query: str) -> str:
        # Quote each token so FTS5 treats them as phrases (avoids syntax errors).
        return " OR ".join(
            '"' + tok.replace('"', '""') + '"' for tok in query.split() if tok
        )

    # ------------------------------------------------------------------
    # Run logging
    # ------------------------------------------------------------------

    def log_skill_run(
        self,
        name: str,
        input_data: Dict[str, Any],
        output: Any,
        success: bool = True,
        error: Optional[str] = None,
        duration_ms: float = 0.0,
        version: Optional[int] = None,
    ) -> int:
        """Log one execution of a skill; returns the run id."""
        if version is None:
            skill = self.get_skill(name)
            version = (skill or {}).get("current_version")
        conn = self._connect()
        try:
            cur = conn.execute(
                """
                INSERT INTO skill_runs (skill_name, version, input_data, output,
                                        success, error, duration_ms, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    version,
                    json.dumps(input_data, default=str),
                    json.dumps(output, default=str),
                    1 if success else 0,
                    error,
                    duration_ms,
                    utcnow_iso(),
                ),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Validation / export / import
    # ------------------------------------------------------------------

    @staticmethod
    def validate_skill(skill: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a skill dict; returns {"valid": bool, "errors": [...]}.

        A valid skill has: a non-empty name, a known type, and code that
        contains at least one top-level function definition.
        """
        errors: List[str] = []
        name = str(skill.get("name", "")).strip()
        if not name:
            errors.append("name is required")
        elif not re.match(r"^[A-Za-z0-9][A-Za-z0-9_-]*$", name):
            errors.append("name must be alphanumeric (with - or _)")
        skill_type = skill.get("type") or skill.get("skill_type")
        if skill_type not in ("function", "agent", "workflow"):
            errors.append(f"invalid type: {skill_type!r}")
        code = skill.get("code", "")
        if not code.strip():
            errors.append("code is empty")
        elif not re.search(r"^def\s+[A-Za-z_]\w*\s*\(", code, re.MULTILINE):
            errors.append("code contains no function definition")
        return {"valid": not errors, "errors": errors}

    def export_skill(self, name: str) -> Dict[str, Any]:
        """Export a skill as a portable payload (dict / JSON-serializable)."""
        skill = self.get_skill(name)
        if skill is None:
            raise SkillNotFoundError(f"Skill '{name}' not found")
        return {
            "name": skill["name"],
            "description": skill["description"],
            "type": skill["type"],
            "code": skill["code"],
            "parameters": skill["parameters"],
            "examples": skill["examples"],
            "version": skill["current_version"],
        }

    def import_skill(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Import a skill from an exported payload.

        If the name exists it is updated (new version); otherwise it is
        registered fresh.
        """
        payload = dict(payload)
        name = payload.pop("name", None)
        if not name:
            raise RegistryError("import payload requires a 'name'")
        skill_type = payload.pop("type", "function")
        code = payload.pop("code", "")
        description = payload.pop("description", "")
        parameters = payload.pop("parameters", {})
        examples = payload.pop("examples", [])
        payload.pop("version", None)
        if self.get_skill(name):
            return self.update_skill(
                name,
                code=code,
                description=description,
                parameters=parameters,
                examples=examples,
                note="imported",
            )
        return self.register_skill(
            name,
            skill_type=skill_type,
            description=description,
            code=code,
            parameters=parameters,
            examples=examples,
            note="imported",
        )

    # ------------------------------------------------------------------
    # Persistence / Git helpers
    # ------------------------------------------------------------------

    def _store_file_and_commit(
        self,
        name: str,
        version: int,
        code_path: Optional[str],
        git_commit: Optional[str],
    ) -> None:
        """Persist code_path + git commit hash into skills and skill_versions."""
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE skills SET code_path = ?, git_commit = ? WHERE name = ?",
                (code_path, git_commit, name),
            )
            conn.execute(
                """
                UPDATE skill_versions
                SET code_path = ?, git_commit = ?
                WHERE skill_name = ? AND version = ?
                """,
                (code_path, git_commit, name, version),
            )
            conn.commit()
        finally:
            conn.close()

    def _commit_skill_files(
        self, name: str, note: str, code_path: Optional[str]
    ) -> Optional[str]:
        """Stage + commit the skill file; returns the new commit hash."""
        if not self.auto_commit:
            return None
        manager = self.git
        if manager is None or not code_path:
            return None
        try:
            if manager.add([code_path]):
                if manager.commit(f"feat(skills): {name} {note}"):
                    log = manager.log(limit=1)
                    return log[0]["hash"] if log else None
        except GitManagerError:
            return None
        return None

    def get_skill_runs(self, name: str, limit: int = 20) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT id, skill_name, version, input_data, output, success,
                       error, duration_ms, timestamp
                FROM skill_runs
                WHERE skill_name = ?
                ORDER BY id DESC LIMIT ?
                """,
                (name, limit),
            ).fetchall()
        finally:
            conn.close()
        result = []
        for r in rows:
            d = dict(r)
            for key in ("input_data", "output"):
                if isinstance(d.get(key), str):
                    try:
                        d[key] = json.loads(d[key])
                    except (ValueError, TypeError):
                        pass
            d["success"] = bool(d["success"])
            result.append(d)
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_skill(row: sqlite3.Row) -> Dict[str, Any]:
        skill = {k: row[k] for k in row.keys()}
        for key in ("parameters", "examples", "tags"):
            if isinstance(skill.get(key), str):
                try:
                    skill[key] = json.loads(skill[key])
                except (ValueError, TypeError):
                    pass
        skill["skill_type"] = skill.get("type")
        skill["version"] = skill.get("current_version")
        skill["active"] = bool(skill.get("active"))
        return skill

    def _insert_version(
        self,
        conn: sqlite3.Connection,
        name: str,
        version: int,
        code: str,
        note: str,
        description: str = "",
        parameters: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Snapshot one version of a skill.

        ``description`` and ``parameters`` are captured alongside the code so
        that :meth:`compare_versions` can diff metadata and parameters, not
        just implementation - Task 3.3 requires all three, and a version row
        that stores only code makes a metadata-only change impossible to
        compare after the fact.
        """
        conn.execute(
            """
            INSERT INTO skill_versions (skill_name, version, code, description,
                                        parameters, code_path, code_hash,
                                        git_commit, note, created_at)
            VALUES (?, ?, ?, ?, ?, NULL, ?, NULL, ?, ?)
            """,
            (
                name, version, code, description or "",
                json.dumps(parameters or {}), _sha256(code), note,
                utcnow_iso(),
            ),
        )

    def _persist_skill_file(self, name: str, code: str, version: int) -> str:
        """Write the skill code into ``versioned_skills_dir``."""
        version_dir = self.versioned_skills_dir
        os.makedirs(version_dir, exist_ok=True)
        filepath = os.path.join(version_dir, f"{name}_v{version}.py")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)
        self._cleanup_old_versions(name)
        return filepath

    def _cleanup_old_versions(self, name: str, keep: int = 10) -> None:
        """Prune per-skill version files in ``versioned_skills_dir``, keeping
        only the latest ``keep``.

        Uses the exact same directory as :meth:`_persist_skill_file` so files
        are always created and pruned in the same location.
        """
        import glob

        version_dir = self.versioned_skills_dir
        if not os.path.isdir(version_dir):
            return

        def sort_key(path: str) -> int:
            match = re.search(r"v(\d+)\.py$", path)
            return int(match.group(1)) if match else 0

        files = sorted(
            glob.glob(os.path.join(version_dir, f"{name}_v*.py")),
            key=sort_key,
            reverse=True,
        )
        for old in files[keep:]:
            try:
                os.remove(old)
            except OSError:
                pass
