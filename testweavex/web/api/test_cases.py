from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from testweavex.core.exceptions import RecordNotFound
from testweavex.core.models import (
    TestCase,
    TestStatus,
    TestType,
    generate_stable_id,
)

router = APIRouter()


@router.get("/test-cases")
async def list_test_cases(
    request: Request,
    test_type: Optional[str] = None,
    is_automated: Optional[bool] = None,
    search: Optional[str] = None,
) -> list[dict]:
    repo = request.app.state.repo
    cases = repo.get_all_test_cases()
    if test_type:
        cases = [tc for tc in cases if tc.test_type.value == test_type]
    if is_automated is not None:
        cases = [tc for tc in cases if tc.is_automated == is_automated]
    if search:
        q = search.lower()
        cases = [
            tc for tc in cases
            if q in tc.title.lower() or any(q in tag.lower() for tag in tc.tags)
        ]
    return [tc.model_dump(mode="json") for tc in cases]


@router.get("/test-cases/{tc_id}")
async def get_test_case(tc_id: str, request: Request) -> dict:
    repo = request.app.state.repo
    try:
        tc = repo.get_test_case(tc_id)
    except RecordNotFound:
        raise HTTPException(status_code=404, detail="Test case not found")
    recent_results = repo.get_results_for_test_case(tc_id, limit=10)
    data = tc.model_dump(mode="json")
    data["recent_results"] = [r.model_dump(mode="json") for r in recent_results]
    return data


class TestCaseCreate(BaseModel):
    title: str
    test_type: str = "smoke"
    skill: str = "builtin"
    priority: int = 2
    is_automated: bool = False
    tags: list[str] = []
    gherkin: str = ""


@router.post("/test-cases", status_code=201)
async def create_test_case(body: TestCaseCreate, request: Request) -> dict:
    repo = request.app.state.repo
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    try:
        tt = TestType(body.test_type)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid test_type: {body.test_type}")

    tc_id = generate_stable_id("manual", body.title, now.isoformat())
    gherkin = body.gherkin.strip() or f"Scenario: {body.title}\n  Given the test exists"

    tc = TestCase(
        id=tc_id,
        title=body.title,
        feature_id=generate_stable_id("manual", body.title),
        gherkin=gherkin,
        test_type=tt,
        skill=body.skill,
        status=TestStatus.pending,
        is_automated=body.is_automated,
        tags=body.tags,
        priority=max(1, min(3, body.priority)),
        created_at=now,
        updated_at=now,
    )
    repo.upsert_test_case(tc)
    return tc.model_dump(mode="json")


class TestCaseUpdate(BaseModel):
    title: Optional[str] = None
    test_type: Optional[str] = None
    priority: Optional[int] = None
    status: Optional[str] = None
    is_automated: Optional[bool] = None
    tags: Optional[list[str]] = None
    gherkin: Optional[str] = None


@router.patch("/test-cases/{tc_id}")
async def update_test_case(tc_id: str, body: TestCaseUpdate, request: Request) -> dict:
    repo = request.app.state.repo
    try:
        tc = repo.get_test_case(tc_id)
    except RecordNotFound:
        raise HTTPException(status_code=404, detail="Test case not found")

    updates: dict = {"updated_at": datetime.now(timezone.utc).replace(tzinfo=None)}

    if body.title is not None:
        updates["title"] = body.title
    if body.test_type is not None:
        try:
            updates["test_type"] = TestType(body.test_type)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid test_type: {body.test_type}")
    if body.priority is not None:
        updates["priority"] = max(1, min(3, body.priority))
    if body.status is not None:
        try:
            updates["status"] = TestStatus(body.status)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid status: {body.status}")
    if body.is_automated is not None:
        updates["is_automated"] = body.is_automated
    if body.tags is not None:
        updates["tags"] = body.tags
    if body.gherkin is not None:
        updates["gherkin"] = body.gherkin

    tc = tc.model_copy(update=updates)
    repo.upsert_test_case(tc)
    return tc.model_dump(mode="json")


@router.delete("/test-cases/{tc_id}", status_code=204)
async def delete_test_case(tc_id: str, request: Request) -> None:
    repo = request.app.state.repo
    try:
        repo.delete_test_case(tc_id)
    except RecordNotFound:
        raise HTTPException(status_code=404, detail="Test case not found")
