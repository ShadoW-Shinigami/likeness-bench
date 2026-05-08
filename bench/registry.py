"""Provider and task registries.

Decorators register classes at import time. The CLI/server just imports the
package modules and reads from the registry.
"""
from __future__ import annotations

from typing import Type

_PROVIDERS: dict[str, Type] = {}
_TASKS: dict[str, Type] = {}


def register_provider(cls: Type) -> Type:
    name = getattr(cls, "name", None)
    if not name:
        raise ValueError(f"Provider class {cls.__name__} must set 'name'")
    _PROVIDERS[name] = cls
    return cls


def register_task(cls: Type) -> Type:
    type_id = getattr(cls, "type_id", None)
    if not type_id:
        raise ValueError(f"Task class {cls.__name__} must set 'type_id'")
    _TASKS[type_id] = cls
    return cls


def get_provider_class(name: str) -> Type:
    if name not in _PROVIDERS:
        raise KeyError(f"Provider '{name}' not registered. Available: {list(_PROVIDERS)}")
    return _PROVIDERS[name]


def get_task_class(type_id: str) -> Type:
    if type_id not in _TASKS:
        raise KeyError(f"Task '{type_id}' not registered. Available: {list(_TASKS)}")
    return _TASKS[type_id]


def list_providers() -> list[str]:
    return sorted(_PROVIDERS)


def list_tasks() -> list[str]:
    return sorted(_TASKS)
