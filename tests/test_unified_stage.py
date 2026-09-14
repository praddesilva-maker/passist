import os
import tempfile
import pytest
from skills.registry import SkillRegistry
from skills.unified_stage import UnifiedSkillStage

# Helper to create a skill file with run function

def create_skill_file(tmpdir, name, code):
    path = os.path.join(tmpdir, f"{name}.py")
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    return path

@pytest.fixture
def registry(tmp_path):
    db_path = os.path.join(tmp_path, "skills.db")
    return SkillRegistry(db_path=db_path, git_repo_path=tmp_path)

@pytest.fixture
def skill_stage(registry):
    return UnifiedSkillStage(registry)

def test_run_function_skill(registry, skill_stage):
    skill_name = "hello"
    code = "def run():\n    return 'hello world'\n"
    path = create_skill_file(os.path.dirname(registry.db_path), skill_name, code)
    registry.add_skill(skill_name, "function", path)
    result = skill_stage.run(skill_name)
    assert result == 'hello world'

def test_run_main_skill(registry, skill_stage):
    skill_name = "mainskill"
    code = "def main():\n    return 'main executed'\n"
    path = create_skill_file(os.path.dirname(registry.db_path), skill_name, code)
    registry.add_skill(skill_name, "function", path)
    result = skill_stage.run(skill_name)
    assert result == 'main executed'

# Test that passing arguments works

def test_run_with_args(registry, skill_stage):
    skill_name = "adder"
    code = "def run(x, y):\n    return x + y\n"
    path = create_skill_file(os.path.dirname(registry.db_path), skill_name, code)
    registry.add_skill(skill_name, "function", path)
    result = skill_stage.run(skill_name, x=2, y=3)
    assert result == 5
