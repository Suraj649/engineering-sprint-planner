"""Pydantic contracts (adapted from omnexis-repo agents/schemas.py)."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class SprintStory(BaseModel):
    id: str = ""
    title: str
    description: str = ""
    issue_type: Literal["feature", "bug", "chore", "test", "spike", "demo", "other"] = "feature"
    priority: Literal["low", "medium", "high"] = "medium"


class EstimatedStory(BaseModel):
    id: str = ""
    title: str
    description: str = ""
    issue_type: Literal["feature", "bug", "chore", "test", "spike", "demo", "other"] = "feature"
    priority: Literal["low", "medium", "high"] = "medium"
    story_points: int = 3
    estimated_hours: float = 4.0
    due: Optional[str] = None


class CalendarSlot(BaseModel):
    task_id: str = ""
    task_title: str
    start: str
    end: str
    notes: str = ""


class SprintPlannerResponse(BaseModel):
    version: Literal["1.0"] = "1.0"
    status: Literal["complete", "partial", "failed"] = "complete"
    sprint_name: str
    team: str
    summary: str
    stories: list[EstimatedStory] = Field(default_factory=list)
    events: list[CalendarSlot] = Field(default_factory=list)
    mcp_actions: list[str] = Field(default_factory=list)
