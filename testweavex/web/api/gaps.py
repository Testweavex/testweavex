from __future__ import annotations

from fastapi import APIRouter, Request

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
    return {
        "message": "LLM generation for gaps available in Phase 5+",
        "gap_id": gap_id,
    }
