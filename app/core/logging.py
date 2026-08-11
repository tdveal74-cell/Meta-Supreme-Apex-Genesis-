"""Logging shim."""
try:
    from logging import setup_logging  # noqa: F401
except ImportError:

    def setup_logging() -> None:
        import logging

        logging.basicConfig(level=logging.INFO)
