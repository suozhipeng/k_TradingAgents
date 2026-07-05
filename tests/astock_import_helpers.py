"""Import helpers for AStock tests that support module-to-package refactors."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path


def load_astock_submodule(rel_name: str, pkg_parent: str, path_root: Path):
    """Load an AStock submodule from either a package directory or legacy file."""
    full_name = f"{pkg_parent}.{rel_name}"
    package_path = path_root / rel_name
    module_path = path_root / f"{rel_name}.py"

    for parent in ("tradingagents", "tradingagents.astock", pkg_parent):
        mod = sys.modules.get(parent)
        if mod is not None and hasattr(mod, "__path__") and not getattr(mod, "__path__", []):
            del sys.modules[parent]
        if parent not in sys.modules:
            try:
                importlib.import_module(parent)
            except ImportError:
                pass

    parent_mod = sys.modules.get(pkg_parent)
    if parent_mod:
        parent_mod.__path__ = [str(path_root)]

    if package_path.is_dir() and (package_path / "__init__.py").exists():
        return importlib.import_module(full_name)

    if not module_path.exists():
        raise ImportError(f"Cannot load {full_name} from {module_path}")

    spec = importlib.util.spec_from_file_location(full_name, str(module_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {full_name} from {module_path}")

    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = pkg_parent
    mod.__name__ = full_name
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod
