"""Run control coordination via on-disk JSON state.

The pipeline reads runs/<run_id>/control.json between every sample to decide
whether to keep going, pause, or kill. The CLI and FastAPI both edit the same
file. This is the single source of truth — no in-process queues — so a runner
in one process can be controlled from another (e.g., the bench server).
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ..models import RunControlState

ControlAction = Literal["none", "pause", "resume", "kill"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def control_path(runs_dir: Path, run_id: str) -> Path:
    return runs_dir / run_id / "control.json"


def write_state(runs_dir: Path, state: RunControlState) -> None:
    path = control_path(runs_dir, state.run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    state.updated_at = _now()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(state.model_dump_json(indent=2))
    tmp.replace(path)


def read_state(runs_dir: Path, run_id: str) -> RunControlState | None:
    path = control_path(runs_dir, run_id)
    if not path.exists():
        return None
    return RunControlState.model_validate_json(path.read_text())


def update_state(runs_dir: Path, run_id: str, **kwargs: Any) -> RunControlState | None:
    s = read_state(runs_dir, run_id)
    if s is None:
        return None
    for k, v in kwargs.items():
        setattr(s, k, v)
    write_state(runs_dir, s)
    return s


def list_states(runs_dir: Path) -> list[RunControlState]:
    if not runs_dir.exists():
        return []
    out: list[RunControlState] = []
    for sub in sorted(runs_dir.iterdir(), reverse=True):
        if not sub.is_dir():
            continue
        cp = sub / "control.json"
        if cp.exists():
            try:
                out.append(RunControlState.model_validate_json(cp.read_text()))
            except Exception:
                continue
    return out


def request_action(runs_dir: Path, run_id: str, action: ControlAction) -> RunControlState | None:
    return update_state(runs_dir, run_id, requested_action=action)


def init_state(
    runs_dir: Path,
    run_id: str,
    *,
    n_samples: int,
    model_id: str,
    benchmark_id: str,
) -> RunControlState:
    state = RunControlState(
        run_id=run_id,
        status="queued",
        n_samples=n_samples,
        completed=0,
        started_at=_now(),
        updated_at=_now(),
        model_id=model_id,
        benchmark_id=benchmark_id,
        pid=os.getpid(),
    )
    write_state(runs_dir, state)
    return state


def wait_if_paused(
    runs_dir: Path,
    run_id: str,
    poll_seconds: float = 0.5,
) -> Literal["continue", "kill"]:
    """Block while paused. Return 'kill' if a kill was requested, else 'continue'."""
    while True:
        s = read_state(runs_dir, run_id)
        if s is None:
            return "continue"
        if s.requested_action == "kill":
            update_state(runs_dir, run_id, status="killed", requested_action="none")
            return "kill"
        if s.requested_action == "pause":
            update_state(runs_dir, run_id, status="paused", requested_action="none")
        if s.status == "paused":
            ns = read_state(runs_dir, run_id)
            if ns and ns.requested_action == "resume":
                update_state(runs_dir, run_id, status="running", requested_action="none")
                return "continue"
            if ns and ns.requested_action == "kill":
                update_state(runs_dir, run_id, status="killed", requested_action="none")
                return "kill"
            time.sleep(poll_seconds)
            continue
        return "continue"
