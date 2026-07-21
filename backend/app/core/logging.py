"""
Logging configuration.

Why this exists:
- One place to configure log format/level for the whole API process.
- Request middleware and services share the same logger hierarchy.
"""

import logging
import sys

from app.core.config import get_settings


def configure_logging() -> None:
    """Configure root logging once at application startup."""
    settings = get_settings()
    level = logging.DEBUG if settings.debug else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        stream=sys.stdout,
        force=True,
    )

    # Keep third-party noise down in development.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
