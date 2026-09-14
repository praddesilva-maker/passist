#!/usr/bin/env python3
""""
Skill Registry Module - Core Foundation Implementation
""""

import sqlite3
import json
import os
import subprocess
import shutil
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

class RegistryError(Exception):
    """Base exception for registry errors"""

    pass
class SkillNotFoundError(RegistryError):
    """Raised when a skill is not found"""
    pass

class SkillAlreadyExistsError(RegistryError):
    """Raised when a skill already exists"""
    pass

class SkillRegistry:
    """
    Central registry for managing skills with version history tracking
    All skills MUST be accessed through this registry (no auto-discovery)
    """
    def __init__(self, db_path: str = "./skills/skills.db", git_repo_path: str = None):
        self.db_path = db_path
        self.git_repo_path = git_repo_path or os.path.dirname(db_path)
        self._create_tables()
        self._ensure_skills_dir()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
    def _create_tables(self):
        conn.commit()
        conn.close()
    def _ensure_skills_dir(self):
        if skills_dir and not os.path.exists(skills_dir):
        skills_dir = os.path.dirname(self.db_path)
            os.makedirs(skills_dir, exist_ok=True)

    def _calculate_file_hash(self, code: str) -> str:
        import hashlib
        return hashlib.md5(code.encode('utf-8')).hexdigest()
    
    def _get_skill_directory(self) -> str:
        return os.path.dirname(self.db_path) or os.getcwd()
    
    def _save_skill_file(self, skill_name: str, code: str, version: int = None) -> str:
        skills_dir = self._get_skill_directory()
        version_dir = os.path.join(skills_dir, "versioned_skills")
        os.makedirs(version_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{skill_name}_v{timestamp}.py"
        filepath = os.path.join(version_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)
        return filepath
    
    def _cleanup_old_versions(self, skill_name: str, keep_versions: int = 10):
        import glob
        skills_dir = self._get_skill_directory()
        version_dir = os.path.join(skills_dir, "versioned_skills")
        if not os.path.exists(version_dir):
            return
        pattern = os.path.join(version_dir, f"{skill_name}_v*.py")
        version_files = sorted(glob.glob(pattern), key=lambda x: x, reverse=True)
        for old_file in version_files[keep_versions:]:
            if os.path.exists(old_file):
                os.remove(old_file)

    def add_skill(self, skill_data: Dict[str, Any], save_to_git: bool = True) -> Dict[str, Any]:
        skill_name = skill_data.get('name')
        if not skill_name:
            raise RegistryError("Skill name is required")
        current_time = datetime.now().isoformat()
        existing = self.get_skill(skill_name)
        if existing:
            current_versions = json.loads(existing.get('versions', '[]'))
            new_version = len(current_versions) + 1 if current_versions else 1
        else:
            new_version = 1
            current_versions = []
        saved_file_path = None
        if save_to_git and skill_data.get('code'):
            saved_file_path = self._save_skill_file(skill_name, skill_data['code'], new_version)
            current_versions.append(saved_file_path)
        if save_to_git:
            self._cleanup_old_versions(skill_name)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO skills (name, description, type, code, parameters, examples, created_at, updated_at, versions, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (skill_name, skill_data.get('description', ''), skill_data.get('type', 'function'), skill_data.get('code', ''), json.dumps(skill_data.get('parameters', []), ensure_ascii=False), json.dumps(skill_data.get('examples', []), ensure_ascii=False), skill_data.get('created_at', current_time), current_time, json.dumps(current_versions, ensure_ascii=False), 1))
        conn.commit()
        conn.close()
        return self.get_skill(skill_name)

    def get_skill(self, name: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name, description, type, code, parameters, examples, created_at, updated_at, versions, is_active FROM skills WHERE name = ? AND is_active = 1", (name,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                'name': row[0], 'description': row[1], 'type': row[2],
                'code': row[3], 'parameters': json.loads(row[4] if row[4] else '[]'),
                'examples': json.loads(row[5] if row[5] else '[]'),
                'created_at': row[6], 'updated_at': row[7],
                'versions': json.loads(row[8] if row[8] else '[]'),
                'is_active': row[9]
            }
        return None

    def search_skills(self, query: str, skill_type: str = None, max_results: int = 10) -> List[Dict[str, Any]]:
        return self.list_skills(skill_type=skill_type, search_query=query, limit=max_results, offset=0, active_only=True)
    
    def get_skill_versions(self, name: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT skill_name, filename, created_at FROM versions WHERE skill_name = ? ORDER BY created_at DESC", (name,))
        rows = cursor.fetchall()
        conn.close()
        return [{'skill_name': row[0], 'filename': row[1], 'created_at': row[2]} for row in rows]
    
    def get_skill_history(self, name: str) -> List[Dict[str, Any]]:
        skill = self.get_skill(name)
        if not skill:
            return []
        versions = self.get_skill_versions(name)
        return {
            'name': name, 'versions': versions,
            'current_parameters': skill.get('parameters', []),
            'current_code': skill.get('code', ''),
            'created_at': skill.get('created_at'),
            'updated_at': skill.get('updated_at')
        }

    def update_skill(self, name: str, skill_data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.get_skill(name):
            raise SkillNotFoundError(f"Skill '{name}' not found")
        if skill_data.get('code'):
            saved_file_path = self._save_skill_file(name, skill_data['code'])
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO versions (skill_name, filename, created_at) VALUES (?, ?, ?)", (name, saved_file_path, datetime.now().isoformat()))
            conn.commit()
            conn.close()
        return self.add_skill(skill_data, save_to_git=True)
    
    def delete_skill(self, name: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM skills WHERE name = ?", (name,))
        cursor.execute("DELETE FROM skill_parameters WHERE skill_name = ?", (name,))
        cursor.execute("DELETE FROM skill_examples WHERE skill_name = ?", (name,))
        rows = cursor.rowcount
        conn.commit()
        conn.close()
        return rows > 0

    def restore_skill(self, name: str, version_path: str) -> bool:
        if not os.path.exists(version_path):
            return False
        with open(version_path, 'r', encoding='utf-8') as f:
            code = f.read()
        skill = self.get_skill(name)
        parameters = skill.get('parameters', []) if skill else []
        skill_data = {
            'name': name,
            'description': f"Restored from version: {os.path.basename(version_path)}",
            'type': 'function', 'code': code,
            'parameters': parameters,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        self.add_skill(skill_data, save_to_git=False)
        return True
    
    def validate_skill(self, skill_data: Dict[str, Any]) -> tuple:
        errors = []
        if not skill_data.get('name'):
            errors.append("Skill name is required")
        if not skill_data.get('code'):
            errors.append("Skill code is required")
        skill_type = skill_data.get('type', 'function')
        if skill_type not in ['function', 'agent', 'workflow']:
            errors.append(f"Invalid skill type: {skill_type}")
        if skill_data.get('parameters'):
            for i, param in enumerate(skill_data['parameters']):
                if not param.get('name'):
                    errors.append(f"Parameter at index {i} missing 'name' field")
                if 'type' not in param:
                    errors.append(f"Parameter '{param.get('name', 'unnamed')}' missing 'type' field")
        return len(errors) == 0, errors
    
    def count_skills(self, skill_type: str = None) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        if skill_type:
            cursor.execute("SELECT COUNT(*) FROM skills WHERE type = ? AND is_active = 1", (skill_type,))
        else:
            cursor.execute("SELECT COUNT(*) FROM skills WHERE is_active = 1")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_statistics(self) -> Dict[str, Any]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM skills WHERE is_active = 1")
        total_skills = cursor.fetchone()[0]
        cursor.execute("SELECT type, COUNT(*) FROM skills WHERE is_active = 1 GROUP BY type")
        skills_by_type = {row[0]: row[1] for row in cursor.fetchall()}
        cursor.execute("SELECT name, type, created_at FROM skills WHERE is_active = 1 ORDER BY created_at DESC LIMIT 5")
        latest_skills = [{'name': row[0], 'type': row[1], 'created_at': row[2]} for row in cursor.fetchall()]
        conn.close()
        return {
            'total_skills': total_skills, 'skills_by_type': skills_by_type,
            'latest_skills': latest_skills
        }
    
    def clear_all_skills(self) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM skills")
        cursor.execute("DELETE FROM skill_parameters")
        cursor.execute("DELETE FROM skill_examples")
        rows = cursor.rowcount
        conn.commit()
        conn.close()
        return rows
    
    def reset_registry(self) -> bool:
        try:
            if os.path.exists(self.db_path):
                backup_path = f"{self.db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(self.db_path, backup_path)
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
            self._create_tables()
            self._ensure_skills_dir()
            return True
        except Exception as e:
            raise RegistryError(f"Failed to reset registry: {e}")



def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'init':
        registry = SkillRegistry()
        return
    registry = SkillRegistry()
    print("Registry module loaded. Use SkillRegistry class directly.")

if __name__ == "__main__":
    import sys
    main()

class NewSkillRegistry:
    """Simplified registry used for tests and core functionality."""
    def __init__(self, db_path: str = "./skills/skills.db", git_repo_path: Optional[str] = None):
        self.db_path = os.path.abspath(db_path)
        self.git_repo_path = os.path.abspath(git_repo_path or os.path.dirname(self.db_path))
        self._ensure_skills_dir()
        self._create_tables()

    def _ensure_skills_dir(self) -> None:
        skills_dir = os.path.dirname(self.db_path)
        os.makedirs(skills_dir, exist_ok=True)
        git_dir = os.path.join(self.git_repo_path, ".git")
        if not os.path.isdir(git_dir):
            subprocess.run(["git", "init", self.git_repo_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _create_tables(self) -> None:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                code_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            );
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS skill_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_name TEXT NOT NULL,
                version TEXT NOT NULL,
                code_path TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        conn.commit()
        conn.close()

    def _git_commit(self, file_path: str, message: str) -> None:
        rel_path = os.path.relpath(file_path, self.git_repo_path)
        try:
            subprocess.run(["git", "add", rel_path], cwd=self.git_repo_path, check=True)
            subprocess.run(["git", "commit", "-m", message], cwd=self.git_repo_path, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            # Git may not be available or commit may fail; ignore
            pass

    def _add_version(self, skill_name: str, version: str, code_path: str) -> None:
        now = datetime.utcnow().isoformat()
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT INTO skill_versions (skill_name, version, code_path, created_at) VALUES (?,?,?,?)", (skill_name, version, code_path, now))
        conn.commit()
        conn.close()

    def add_skill(self, name: str, skill_type: str, code_path: str, version: Optional[str] = None) -> Dict[str, Any]:
        if self.get_skill(name):
            raise RegistryError(f"Skill '{name}' already exists")
        now = datetime.utcnow().isoformat()
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT INTO skills (name, type, code_path, created_at, updated_at, active) VALUES (?,?,?,?,?,1)", (name, skill_type, code_path, now, now))
        conn.commit()
        conn.close()
        if version is None:
            version = "1.0"
        self._add_version(name, version, code_path)
        self._git_commit(code_path, f"Add skill {name} version {version}")
        return self.get_skill(name)

    def get_skill(self, name: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT name, type, code_path, created_at, updated_at, active FROM skills WHERE name=? AND active=1", (name,))
        row = c.fetchone()
        conn.close()
        if row:
            return {
                "name": row[0],
                "type": row[1],
                "code_path": row[2],
                "created_at": row[3],
                "updated_at": row[4],
                "active": bool(row[5]),
            }
        return None

    def list_skills(self) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT name, type, code_path FROM skills WHERE active=1")
        rows = c.fetchall()
        conn.close()
        return [{"name": r[0], "type": r[1], "code_path": r[2]} for r in rows]

    def update_skill(self, name: str, new_code_path: str, version: Optional[str] = None) -> Dict[str, Any]:
        skill = self.get_skill(name)
        if not skill:
            raise RegistryError(f"Skill '{name}' not found")
        now = datetime.utcnow().isoformat()
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("UPDATE skills SET code_path=?, updated_at=? WHERE name=?", (new_code_path, now, name))
        conn.commit()
        conn.close()
        if version is None:
            version = "1.0"
        self._add_version(name, version, new_code_path)
        self._git_commit(new_code_path, f"Update skill {name} version {version}")
        return self.get_skill(name)

    def delete_skill(self, name: str) -> None:
        if not self.get_skill(name):
            raise RegistryError(f"Skill '{name}' not found")
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("DELETE FROM skills WHERE name=?", (name,))
        conn.commit()
        conn.close()

    def get_versions(self, name: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("SELECT version, code_path, created_at FROM skill_versions WHERE skill_name=? ORDER BY created_at DESC", (name,))
        rows = c.fetchall()
        conn.close()
        return [{"version": r[0], "code_path": r[1], "created_at": r[2]} for r in rows]

# Alias to maintain backward compatibility
SkillRegistry = NewSkillRegistry

