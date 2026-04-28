from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from testweavex.core.exceptions import ConfigError, LLMOutputError, RecordNotFound
from testweavex.llm.base import get_llm_adapter

router = APIRouter()


@router.get("/gaps")
async def list_gaps(
    request: Request,
    limit: int = 50,
    status: str = "open",
    min_score: float = 0.0,
) -> list[dict]:
    repo = request.app.state.repo
    gaps = repo.get_gaps(limit=limit, status=status)
    filtered = [g for g in gaps if g.priority_score >= min_score]
    return [g.model_dump(mode="json") for g in filtered]


@router.post("/gaps/{gap_id}/generate")
async def generate_for_gap(gap_id: str, request: Request) -> dict:
    repo = request.app.state.repo
    config = request.app.state.config

    all_gaps = repo.get_gaps(limit=10000, status="open")
    gap = next((g for g in all_gaps if g.id == gap_id), None)
    if gap is None:
        raise HTTPException(status_code=404, detail=f"Gap '{gap_id}' not found")

    try:
        tc = repo.get_test_case(gap.test_case_id)
    except RecordNotFound:
        raise HTTPException(status_code=404, detail="Test case for gap not found")

    try:
        adapter = get_llm_adapter(config)
    except ConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    if not adapter.health_check():
        raise HTTPException(status_code=503, detail="LLM provider is not available")

    try:
        response = adapter.suggest_gap_automation(tc)
    except LLMOutputError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return response.model_dump(mode="json")
