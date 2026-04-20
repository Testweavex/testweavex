from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("/runs")
async def list_runs(request: Request, limit: int = 50) -> list[dict]:
    repo = request.app.state.repo
    runs = repo.list_runs(limit=limit)
    return [r.model_dump(mode="json") for r in runs]


@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request) -> dict:
    repo = request.app.state.repo
    try:
        run = repo.get_run(run_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Run not found")
    results = repo.get_results_for_run(run_id)
    data = run.model_dump(mode="json")
    data["results"] = [r.model_dump(mode="json") for r in results]
    return data
