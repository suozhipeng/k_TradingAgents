"""Import helpers for AStock tests that support module-to-package refactors."""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path


def load_astock_submodule(rel_name: str, pkg_parent: str, path_root: Path):
    """Load an AStock submodule from either a package directory or legacy file.
    
    Supports both flat modules (``fee_model``) and dotted subpackages 
    (``backtest.fee_model``, ``infrastructure.event_bus``).
    """
    full_name = f"{pkg_parent}.{rel_name}"
    rel_parts = rel_name.split(".")
    
    # Clean up sys.modules for parent packages
    for parent in ("tradingagents", "tradingagents.astock", pkg_parent):
        mod = sys.modules.get(parent)
        if mod is not None and hasattr(mod, "__path__") and not getattr(mod, "__path__", []):
            del sys.modules[parent]
        if parent not in sys.modules:
            try:
                importlib.import_module(parent)
            except ImportError:
                pass

    # Strategy 1: Try as a proper Python package (handles dotted names)
    # For "backtest.fee_model" → check if backtest/ is a package, then import full_name
    if len(rel_parts) >= 1:
        first_part_path = path_root / rel_parts[0]
        if first_part_path.is_dir() and (first_part_path / "__init__.py").exists():
            # It's a package — use importlib which respects __path__
            return importlib.import_module(full_name)

    # Strategy 2: Try as a flat .py file (legacy)
    flat_module_path = path_root / f"{rel_name}.py"
    if flat_module_path.exists():
        parent_mod = sys.modules.get(pkg_parent)
        saved_path = getattr(parent_mod, "__path__", None)
        try:
            if parent_mod:
                parent_mod.__path__ = [str(path_root)]
            spec = importlib.util.spec_from_file_location(full_name, str(flat_module_path))
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot create spec for {full_name}")
            mod = importlib.util.module_from_spec(spec)
            mod.__package__ = pkg_parent
            mod.__name__ = full_name
            sys.modules[full_name] = mod
            spec.loader.exec_module(mod)
            return mod
        finally:
            if saved_path is not None and parent_mod:
                parent_mod.__path__ = saved_path

    raise ImportError(f"Cannot load {full_name} from {path_root}")
