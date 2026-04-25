from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(request: Request) -> dict:
    repo = request.app.state.repo
    coverage = repo.get_coverage_percentage()
    runs = repo.list_runs(limit=1)
    all_cases = repo.get_all_test_cases()
    open_gaps = repo.get_gaps(limit=9999, status="open")
    return {
        "coverage_percentage": coverage,
        "total_test_cases": len(all_cases),
        "automated": sum(1 for tc in all_cases if tc.is_automated),
        "open_gaps": len(open_gaps),
        "last_run_id": runs[0].id if runs else None,
    }
