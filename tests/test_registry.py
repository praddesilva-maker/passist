import os
import tempfile
import shutil
import pytest
from skills.registry import SkillRegistry, RegistryError

# Helper to create a simple skill file

def create_skill_file(tmpdir, name, content="def run():\n    return 'hello'\n"):
    path = os.path.join(tmpdir, f"{name}.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path

@pytest.fixture
def registry(tmp_path):
    db_path = os.path.join(tmp_path, "skills.db")
    # Ensure skills directory exists
    skills_dir = os.path.join(tmp_path, "skills")
    os.makedirs(skills_dir, exist_ok=True)
    return SkillRegistry(db_path=db_path, git_repo_path=tmp_path)

def test_add_and_get_skill(registry):
    skill_name = "dummy"
    skill_type = "function"
    code_path = create_skill_file(os.path.dirname(registry.db_path), skill_name)
    registry.add_skill(skill_name, skill_type, code_path)
    skill = registry.get_skill(skill_name)
    assert skill is not None
    assert skill["name"] == skill_name
    assert skill["type"] == skill_type
    assert skill["code_path"] == code_path

def test_list_skills(registry):
    names = ["skill1", "skill2"]
    for n in names:
        path = create_skill_file(os.path.dirname(registry.db_path), n)
        registry.add_skill(n, "function", path)
    listed = registry.list_skills()
    listed_names = {s["name"] for s in listed}
    assert set(names) == listed_names

def test_update_skill(registry):
    name = "updatable"
    path1 = create_skill_file(os.path.dirname(registry.db_path), name, "def run():\n    return 'v1'\n")
    registry.add_skill(name, "function", path1)
    # Update with new code
    path2 = create_skill_file(os.path.dirname(registry.db_path), name, "def run():\n    return 'v2'\n")
    registry.update_skill(name, path2, version="2.0")
    skill = registry.get_skill(name)
    assert skill["code_path"] == path2
    versions = registry.get_versions(name)
    assert any(v["version"] == "2.0" for v in versions)

def test_delete_skill(registry):
    name = "tobedeleted"
    path = create_skill_file(os.path.dirname(registry.db_path), name)
    registry.add_skill(name, "function", path)
    registry.delete_skill(name)
    assert registry.get_skill(name) is None

def test_duplicate_skill_error(registry):
    name = "dup"
    path = create_skill_file(os.path.dirname(registry.db_path), name)
    registry.add_skill(name, "function", path)
    with pytest.raises(RegistryError):
        registry.add_skill(name, "function", path)
