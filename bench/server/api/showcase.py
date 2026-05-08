"""Showcase generation API."""
from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from ...config import load_config

router = APIRouter(prefix="/api/showcase", tags=["showcase"])

_BUILD_LOCK = asyncio.Lock()
_LAST_BUILD: dict = {"status": "idle", "started_at": None, "finished_at": None,
                     "stdout": "", "rc": None}


@router.get("/status")
async def status() -> dict:
    cfg = load_config()
    html = cfg.repo_root / "showcase.html"
    return {
        "exists": html.exists(),
        "size_bytes": html.stat().st_size if html.exists() else 0,
        "modified_at": html.stat().st_mtime if html.exists() else None,
        **_LAST_BUILD,
    }


@router.post("/build")
async def build() -> dict:
    """Rebuild showcase.html. Idempotent + cached image uploads."""
    if _BUILD_LOCK.locked():
        return {"status": "already_running", **_LAST_BUILD}

    async def _run():
        from datetime import datetime, timezone
        async with _BUILD_LOCK:
            cfg = load_config()
            script = cfg.repo_root / "scripts" / "build_showcase.py"
            _LAST_BUILD["status"] = "running"
            _LAST_BUILD["started_at"] = datetime.now(timezone.utc).isoformat()
            _LAST_BUILD["stdout"] = ""
            _LAST_BUILD["rc"] = None

            proc = await asyncio.create_subprocess_exec(
                sys.executable, str(script),
                cwd=str(cfg.repo_root),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            )
            assert proc.stdout
            chunks = []
            async for line in proc.stdout:
                chunks.append(line.decode(errors="replace"))
                _LAST_BUILD["stdout"] = "".join(chunks)[-4000:]
            rc = await proc.wait()
            _LAST_BUILD["rc"] = rc
            _LAST_BUILD["status"] = "completed" if rc == 0 else "failed"
            _LAST_BUILD["finished_at"] = datetime.now(timezone.utc).isoformat()

    asyncio.create_task(_run())
    return {"status": "started"}


@router.get("/file")
async def get_html():
    cfg = load_config()
    p = cfg.repo_root / "showcase.html"
    if not p.exists():
        return JSONResponse({"detail": "showcase.html not built yet"}, status_code=404)
    return FileResponse(p, media_type="text/html")
