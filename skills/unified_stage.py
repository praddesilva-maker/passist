import importlib.util
from typing import Any, Dict

class UnifiedSkillStage:
    """Wrapper to load and run skills via the registry.

    The registry stores the path to the skill implementation file.
    This stage imports the module dynamically and invokes its main callable.
    """

    def __init__(self, registry):
        self.registry = registry

    def _load_module(self, name: str):
        meta = self.registry.get_skill(name)
        if not meta:
            raise ValueError(f"Skill '{name}' not found in registry")
        path = meta["code_path"]
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load skill {name} from {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def run(self, name: str, **kwargs) -> Any:
        module = self._load_module(name)
        # Prefer run() then main() then any callable
        if hasattr(module, "run"):
            func = module.run
        elif hasattr(module, "main"):
            func = module.main
        else:
            # Find first public callable
            funcs = [getattr(module, attr) for attr in dir(module)
                     if callable(getattr(module, attr)) and not attr.startswith("_")]
            if not funcs:
                raise AttributeError(f"No callable found in skill '{name}'")
            func = funcs[0]
        return func(**kwargs)
