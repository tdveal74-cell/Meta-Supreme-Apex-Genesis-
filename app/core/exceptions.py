"""Re-export exception helpers when available at repo root."""
try:
    from exceptions import register_exception_handlers  # noqa: F401
except ImportError:

    def register_exception_handlers(app):  # type: ignore[no-untyped-def]
        return None
