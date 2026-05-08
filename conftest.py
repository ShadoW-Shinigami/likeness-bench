"""Pytest top-level: ensure providers + tasks are registered before tests run."""
from bench import providers as _providers  # noqa: F401
from bench import tasks as _tasks  # noqa: F401
