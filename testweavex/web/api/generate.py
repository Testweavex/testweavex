# testweavex/web/api/generate.py
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from testweavex.core.exceptions import ConfigError, LLMOutputError
from testweavex.core.models import GenerationRequest
from testweavex.llm.base import get_llm_adapter

router = APIRouter()


class GenerateRequest(BaseModel):
    feature_description: str
    skill: str = "functional/smoke"
    n_suggestions: int = 5


@router.post("/generate")
async def generate_tests(body: GenerateRequest, request: Request) -> dict:
    config = request.app.state.config

    try:
        adapter = get_llm_adapter(config)
    except ConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    if not adapter.health_check():
        raise HTTPException(status_code=503, detail="LLM provider is not available")

    gen_request = GenerationRequest(
        feature_description=body.feature_description,
        skill_names=[body.skill],
        n_suggestions=body.n_suggestions,
    )

    try:
        response = adapter.generate_tests(gen_request)
    except LLMOutputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return response.model_dump(mode="json")
