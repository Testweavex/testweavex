from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/test-cases")
async def list_test_cases(
    request: Request,
    test_type: Optional[str] = None,
    is_automated: Optional[bool] = None,
) -> list[dict]:
    repo = request.app.state.repo
    cases = repo.get_all_test_cases()
    if test_type:
        cases = [tc for tc in cases if tc.test_type.value == test_type]
    if is_automated is not None:
        cases = [tc for tc in cases if tc.is_automated == is_automated]
    return [tc.model_dump(mode="json") for tc in cases]
