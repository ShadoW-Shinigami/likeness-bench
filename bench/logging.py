"""Structlog configuration."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import structlog


def configure_logging(level: str = "INFO", log_file: Path | None = None) -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stderr, level=level.upper())

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if sys.stderr.isatty():
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper())),
        cache_logger_on_first_use=True,
    )

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file)
        fh.setFormatter(logging.Formatter("%(message)s"))
        logging.getLogger().addHandler(fh)


def get_logger(*args, **kwargs):
    return structlog.get_logger(*args, **kwargs)
