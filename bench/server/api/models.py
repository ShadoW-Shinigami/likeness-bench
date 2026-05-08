"""Available models API."""
from __future__ import annotations

from fastapi import APIRouter

from ...config import load_config, get_api_key

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("")
async def list_models() -> dict:
    cfg = load_config()
    out = []
    for key, m in cfg.models.items():
        pcfg = cfg.providers.get(m.provider)
        env_var = pcfg.api_key_env if pcfg else None
        configured = bool(get_api_key(env_var)) if env_var else (m.provider == "mock")
        out.append({
            "key": key,
            "model_id": m.model_id,
            "display": m.display,
            "family": m.family,
            "provider": m.provider,
            "price_per_1m_input": m.price_per_1m_input,
            "price_per_1m_output": m.price_per_1m_output,
            "configured": configured,
        })
    return {"models": out}
