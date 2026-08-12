"""
Logging shim.

Imports from `logging_setup`, NOT `logging`. The implementation used to live in
a root-level `logging.py`, which shadowed the standard library for anything
running with the repository root on `sys.path` — which CI does, via PYTHONPATH.

That was not a theoretical hazard. `pip` itself could not start in CI:

    pip/_internal/utils/_log.py: import logging
      -> <repo>/logging.py: from app.core.config import settings
        -> config.py: from pydantic_settings import ...
          -> ModuleNotFoundError: No module named 'pydantic_settings'

Dependency installation died before a single test ran. Never name a top-level
module after a standard library one.
"""

try:
    from logging_setup import setup_logging  # noqa: F401
except ImportError:  # pragma: no cover - fallback for partial checkouts

    def setup_logging() -> None:
        import logging

        logging.basicConfig(level=logging.INFO)
