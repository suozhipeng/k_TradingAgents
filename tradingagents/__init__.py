import sys
import os

# ── Pydantic isolation ──────────────────────────────────────────────────
# Prevent Hermes Agent venv's pydantic from polluting this project's imports.
# When running inside Hermes, the agent's venv may inject its own pydantic
# into sys.path, which leads to ModuleNotFoundError:
#   pydantic_core._pydantic_core (ABI mismatch between Python 3.11/3.12).
# Clear PYTHONPATH and remove any hermes-related entries from sys.path
# before any downstream import (e.g. pywencai → pydantic) can pick it up.
_hermes_paths = [p for p in sys.path if 'hermes' in p.lower()]
if _hermes_paths:
    sys.path = [p for p in sys.path if 'hermes' not in p.lower()]
    os.environ.setdefault("PYTHONPATH", "")

import warnings

# Load .env files at package import so DEFAULT_CONFIG's env-var overlay
# (and every llm_clients consumer) sees the user's keys regardless of
# python-dotenv: core dep, always available. find_dotenv(usecwd=True)
# walks from the CWD, so the installed `tradingagents` console script
# picks up the project's .env instead of stepping up from site-packages.
# load_dotenv defaults to override=False, so it never clobbers values
# the caller has already exported.
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True))
load_dotenv(find_dotenv(".env.enterprise", usecwd=True), override=False)

# langchain-core 1.3.3 calls surface_langchain_deprecation_warnings() in
# langchain-core: guaranteed transitive dep via langgraph. Import first so
# its deprecation-warning filters are installed before ours.
import langchain_core  # noqa: F401

# langgraph-checkpoint 4.0.3 calls Reviver() at module load without an
# explicit allowed_objects, which triggers a noisy pending-deprecation
# warning from langchain-core 1.3.3 on every interpreter start. The fix
# is already merged upstream (langchain-ai/langgraph#7743, 2026-05-08)
# and will arrive in the next langgraph-checkpoint release. Remove this
# block (and the langchain_core preload above) when we bump past it.
warnings.filterwarnings(
    "ignore",
    message=r"The default value of `allowed_objects`.*",
    category=PendingDeprecationWarning,
)

try:
    from importlib.metadata import version as _version

    __version__ = _version("tradingagents")
except Exception:
    __version__ = "0.3.0"
