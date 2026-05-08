"""Storage abstraction for sample images.

The dataset build pipeline writes images locally. By default we keep them
local (the FastAPI server serves them via /api/samples/.../image/<file>, and
showcase.html references them by relative path).

If you want a CDN, plug in your own backend by implementing `Storage` and
setting `BENCH_STORAGE_BACKEND=<dotted.path.YourClass>` in your env. We ship
a `LocalStorage` stub here. See README for adapter examples.
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Optional, Protocol


class Storage(Protocol):
    def upload_file(
        self, *, local_path: str | Path,
        blob_name: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> str: ...

    def upload_bytes(
        self, *, data: bytes, blob_name: str,
        content_type: Optional[str] = None,
    ) -> str: ...


class LocalStorage:
    """Default backend: returns the absolute path. Nothing is uploaded."""

    def upload_file(self, *, local_path, blob_name=None, content_type=None) -> str:
        return f"file://{Path(local_path).resolve()}"

    def upload_bytes(self, *, data, blob_name, content_type=None) -> str:
        # for true byte uploads, write to a `data/uploads/<blob_name>` file
        out = Path("data/uploads") / blob_name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        return f"file://{out.resolve()}"


_INSTANCE: Storage | None = None


def get_storage() -> Storage:
    global _INSTANCE
    if _INSTANCE is not None:
        return _INSTANCE
    backend = os.environ.get("BENCH_STORAGE_BACKEND")
    if not backend:
        _INSTANCE = LocalStorage()
        return _INSTANCE
    # e.g. BENCH_STORAGE_BACKEND=mypkg.s3.S3Storage
    module_path, _, cls_name = backend.rpartition(".")
    cls = getattr(importlib.import_module(module_path), cls_name)
    _INSTANCE = cls()
    return _INSTANCE


# Convenience helpers used by the dataset orchestrator + showcase builder.
def upload_file_to_storage(*, local_path, blob_name=None, content_type=None) -> str:
    return get_storage().upload_file(
        local_path=local_path, blob_name=blob_name, content_type=content_type,
    )


def upload_bytes_to_storage(*, data, blob_name, content_type=None) -> str:
    return get_storage().upload_bytes(
        data=data, blob_name=blob_name, content_type=content_type,
    )
