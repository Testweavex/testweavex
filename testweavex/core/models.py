from __future__ import annotations

import hashlib
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


def generate_stable_id(*parts: str) -> str:
    """Generate a deterministic SHA-256 hash from parts.

    Uses the full 64-character hexdigest (no truncation).
    """
    key = "|".join(parts).encode("utf-8")
    return hashlib.sha256(key).hexdigest()


class TestStatus(str, Enum):
    pending = "pending"
    passed = "passed"
    failed = "failed"
    skipped = "skipped"
    flaky = "flaky"


class TestType(str, Enum):
    smoke = "smoke"
    sanity = "sanity"
    happy_path = "happy_path"
    edge_cases = "edge_cases"
    data_driven = "data_driven"
    integration = "integration"
    system = "system"
    e2e = "e2e"
    accessibility = "accessibility"
    cross_browser = "cross_browser"


class GapStatus(str, Enum):
    open = "open"
    pending_review = "pending_review"
    closed = "closed"
    dismissed = "dismissed"


class TestCase(BaseModel):
    id: str
    title: str
    feature_id: str
    gherkin: str
    test_type: TestType
    skill: str
    status: TestStatus = TestStatus.pending
    is_automated: bool = False
    tcm_id: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    priority: int = 2
    source_file: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class Feature(BaseModel):
    id: str
    name: str
    description: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    test_case_ids: list[str] = Field(default_factory=list)
    source_file: Optional[str] = None


class TestRun(BaseModel):
    id: str
    suite: str
    environment: str = "local"
    browser: Optional[str] = None
    triggered_by: str = "tw"
    started_at: datetime
    completed_at: Optional[datetime] = None
    result_ids: list[str] = Field(default_factory=list)


class TestResult(BaseModel):
    id: str
    run_id: str
    test_case_id: str
    status: TestStatus
    duration_ms: int
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    retry_count: int = 0


class Gap(BaseModel):
    id: str
    test_case_id: str
    priority_score: float = 0.0
    gap_reason: str = ""
    suggested_gherkin: Optional[str] = None
    status: GapStatus = GapStatus.open
    detected_at: datetime
    closed_at: Optional[datetime] = None

    @field_validator("priority_score")
    @classmethod
    def score_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"priority_score must be 0.0–1.0, got {v}")
        return v


class ScoringSignals(BaseModel):
    test_priority: int
    test_type: TestType
    defect_count: int = 0
    executions_90d: int = 0
    days_since_run: int = 0


class RunSummary(BaseModel):
    run_id: str
    total: int
    passed: int
    failed: int
    skipped: int
    duration_ms: int
    coverage_percentage: float


class GenerationRequest(BaseModel):
    feature_description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    existing_scenarios: list[str] = Field(default_factory=list)
    skill_names: list[str]
    n_suggestions: int = 5


class Scenario(BaseModel):
    title: str
    gherkin: str
    confidence: float
    rationale: str
    suggested_tags: list[str] = Field(default_factory=list)
    skill_used: str

    @field_validator("confidence")
    @classmethod
    def confidence_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"confidence must be 0.0–1.0, got {v}")
        return v


class GenerationResponse(BaseModel):
    scenarios: list[Scenario]
    skill_used: str
    llm_model: str
    tokens_used: int
    generation_time_ms: int


class StepDefinition(BaseModel):
    step_text: str
    implementation: str
    requires_new_module: bool = False
    module_spec: str | None = None


class StepDefinitionResponse(BaseModel):
    new_steps: list[StepDefinition]
    reused_count: int
    llm_model: str
    tokens_used: int
