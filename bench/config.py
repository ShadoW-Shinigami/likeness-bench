"""Config loader: bench.toml + bench.local.toml + .env."""
from __future__ import annotations

import os
import tomllib
from functools import cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel


class ModelConfig(BaseModel):
    provider: str
    model_id: str
    display: str
    family: str
    price_per_1m_input: float = 0.0
    price_per_1m_output: float = 0.0
    extra: dict[str, Any] = {}


class ProviderConfig(BaseModel):
    api_key_env: str | None = None
    base_url: str | None = None
    max_concurrency: int = 4


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    web_dist: str = "web/dist"


class EngineConfig(BaseModel):
    output_dir: str = "results"
    runs_dir: str = "runs"
    default_benchmark: str = "likeness_v1"
    default_concurrency: int = 4
    log_level: str = "INFO"
    max_cost_usd_default: float = 50.0


class BenchConfig(BaseModel):
    repo_root: Path
    engine: EngineConfig
    server: ServerConfig
    providers: dict[str, ProviderConfig]
    models: dict[str, ModelConfig]
    scoring: dict[str, dict[str, float]]

    def model_config_for(self, model_key: str) -> ModelConfig:
        if model_key not in self.models:
            raise KeyError(
                f"Model '{model_key}' not in bench.toml. Available: {list(self.models)}"
            )
        return self.models[model_key]

    def runs_dir_path(self) -> Path:
        return self.repo_root / self.engine.runs_dir

    def results_dir_path(self) -> Path:
        return self.repo_root / self.engine.output_dir

    def benchmarks_dir(self) -> Path:
        return self.repo_root / "benchmarks"

    def dataset_dir(self) -> Path:
        return self.repo_root / "dataset"

    def web_dist_path(self) -> Path:
        return self.repo_root / self.server.web_dist


def find_repo_root(start: Path | None = None) -> Path:
    cur = (start or Path.cwd()).resolve()
    for parent in (cur, *cur.parents):
        if (parent / "bench.toml").exists() or (parent / "pyproject.toml").exists():
            if (parent / "bench.toml").exists():
                return parent
    raise FileNotFoundError("Could not find bench.toml in any parent directory")


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = dict(base)
    for k, v in overlay.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


@cache
def load_config(repo_root: Path | None = None) -> BenchConfig:
    root = repo_root or find_repo_root()
    load_dotenv(root / ".env", override=False)

    with (root / "bench.toml").open("rb") as f:
        data = tomllib.load(f)

    local = root / "bench.local.toml"
    if local.exists():
        with local.open("rb") as f:
            data = _deep_merge(data, tomllib.load(f))

    providers = {k: ProviderConfig(**v) for k, v in data.get("providers", {}).items()}

    models: dict[str, ModelConfig] = {}
    for key, m in data.get("models", {}).items():
        known = {"provider", "model_id", "display", "family",
                 "price_per_1m_input", "price_per_1m_output"}
        extra = {k: v for k, v in m.items() if k not in known}
        models[key] = ModelConfig(
            provider=m["provider"],
            model_id=m["model_id"],
            display=m["display"],
            family=m["family"],
            price_per_1m_input=m.get("price_per_1m_input", 0.0),
            price_per_1m_output=m.get("price_per_1m_output", 0.0),
            extra=extra,
        )

    return BenchConfig(
        repo_root=root,
        engine=EngineConfig(**data.get("engine", {})),
        server=ServerConfig(**data.get("server", {})),
        providers=providers,
        models=models,
        scoring=data.get("scoring", {}),
    )


def get_api_key(env_var: str | None) -> str | None:
    if not env_var:
        return None
    return os.environ.get(env_var)
