from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


@router.get("/settings")
async def get_settings(request: Request) -> dict:
    config = request.app.state.config
    return {
        "llm": {
            "provider": config.llm.provider,
            "model": config.llm.model,
            "temperature": config.llm.temperature,
        },
        "tcm": {"provider": config.tcm.provider},
        "gap_analysis": {
            "top_gaps_default": config.gap_analysis.top_gaps_default,
            "match_threshold": config.gap_analysis.match_threshold,
        },
    }


class SettingsUpdate(BaseModel):
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    temperature: Optional[float] = None


@router.put("/settings")
async def update_settings(body: SettingsUpdate, request: Request) -> dict:
    config_path = Path.cwd() / "testweavex.config.yaml"
    if config_path.exists():
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    else:
        raw = {}
    if "llm" not in raw:
        raw["llm"] = {}
    if body.llm_provider:
        raw["llm"]["provider"] = body.llm_provider
    if body.llm_model:
        raw["llm"]["model"] = body.llm_model
    if body.temperature is not None:
        raw["llm"]["temperature"] = body.temperature
    config_path.write_text(yaml.dump(raw), encoding="utf-8")
    return {"status": "updated"}
