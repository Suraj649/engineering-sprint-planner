"""Session state tools (omnexis pattern; no `tools/` subpackage — ADK lists subdirs as apps)."""

from __future__ import annotations

import logging
import os
import re
from datetime import date, timedelta
from typing import Any

from google.adk.tools.tool_context import ToolContext

logger = logging.getLogger(__name__)


def _next_weekday(start: date, weekday: int) -> date:
    """Return the nearest future date (>=start) that falls on `weekday` (0=Mon)."""
    days_ahead = weekday - start.weekday()
    if days_ahead < 0:
        days_ahead += 7
    return start + timedelta(days=days_ahead)


def _infer_sprint_monday(raw_message: str) -> str:
    """
    Extract the sprint-start Monday from free text.

    Handles phrases like:
      - "sprint starts Monday"         → next Monday from today
      - "sprint starts next Monday"    → same
      - "starts 2026-04-14"            → that exact date (rounded to Monday)
      - "starts Apr 14"/ "April 14"   → parsed to date, rounded to Monday
    Falls back to env SPRINT_WEEK_START, then the coming Monday.
    """
    today = date.today()
    text = raw_message.lower()

    # Explicit ISO date: YYYY-MM-DD
    iso = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", raw_message)
    if iso:
        try:
            d = date.fromisoformat(iso.group(1))
            return _next_weekday(d, 0).isoformat()
        except ValueError:
            pass

    # Month-name day: "Apr 14", "April 14", "14 April"
    month_names = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    m = re.search(r"\b([a-z]{3,9})\s+(\d{1,2})\b|\b(\d{1,2})\s+([a-z]{3,9})\b", text)
    if m:
        month_str = (m.group(1) or m.group(4) or "")[:3]
        day_str = m.group(2) or m.group(3) or "0"
        month_num = month_names.get(month_str)
        if month_num:
            try:
                year = today.year if month_num >= today.month else today.year + 1
                d = date(year, month_num, int(day_str))
                return _next_weekday(d, 0).isoformat()
            except ValueError:
                pass

    # "next monday" / "this monday" / "starts monday"
    if "monday" in text or "next week" in text:
        return _next_weekday(today + timedelta(days=1), 0).isoformat()

    # Env fallback
    env_val = os.getenv("SPRINT_WEEK_START", "").strip()
    if env_val:
        try:
            d = date.fromisoformat(env_val)
            if d >= today:
                return d.isoformat()
        except ValueError:
            pass

    # Ultimate fallback: coming Monday
    return _next_weekday(today, 0).isoformat()


def store_sprint_context(
    tool_context: ToolContext,
    sprint_name: str,
    team: str,
    raw_message: str,
) -> dict[str, Any]:
    sprint_monday = _infer_sprint_monday(raw_message)
    tool_context.state["SPRINT_NAME"] = sprint_name
    tool_context.state["TEAM"] = team
    tool_context.state["RAW_MESSAGE"] = raw_message
    tool_context.state["SPRINT_WEEK_START"] = sprint_monday
    logger.info(
        "Sprint context saved | sprint=%s team=%s week_start=%s",
        sprint_name, team, sprint_monday,
    )
    return {
        "status": "success",
        "sprint_name": sprint_name,
        "team": team,
        "sprint_week_start": sprint_monday,
    }


def store_sprint_stories(
    tool_context: ToolContext,
    stories_json: str,
) -> dict[str, Any]:
    tool_context.state["SPRINT_STORIES"] = stories_json
    logger.info("SPRINT_STORIES saved | %d chars", len(stories_json))
    return {"status": "success", "message": "Stories saved to session state."}


def retrieve_sprint_stories(tool_context: ToolContext) -> dict[str, Any]:
    stories_json: str = tool_context.state.get("SPRINT_STORIES", "[]")
    logger.info("SPRINT_STORIES read | %d chars", len(stories_json))
    return {"status": "success", "stories_json": stories_json}


def store_scaffolded_tasks(
    tool_context: ToolContext,
    tasks_json: str,
) -> dict[str, Any]:
    tool_context.state["SCAFFOLDED_TASKS"] = tasks_json
    logger.info("SCAFFOLDED_TASKS saved | %d chars", len(tasks_json))
    return {"status": "success", "message": "Estimated stories saved to session state."}


def retrieve_scaffolded_tasks(tool_context: ToolContext) -> dict[str, Any]:
    tasks_json: str = tool_context.state.get("SCAFFOLDED_TASKS", "[]")
    logger.info("SCAFFOLDED_TASKS read | %d chars", len(tasks_json))
    return {"status": "success", "tasks_json": tasks_json}


def store_schedule(
    tool_context: ToolContext,
    schedule_json: str,
) -> dict[str, Any]:
    tool_context.state["SCHEDULE"] = schedule_json
    logger.info("SCHEDULE saved | %d chars", len(schedule_json))
    return {"status": "success", "message": "Schedule saved to session state."}


def retrieve_schedule(tool_context: ToolContext) -> dict[str, Any]:
    schedule_json: str = tool_context.state.get("SCHEDULE", "[]")
    logger.info("SCHEDULE read | %d chars", len(schedule_json))
    return {"status": "success", "schedule_json": schedule_json}


def store_sprint_notes(
    tool_context: ToolContext,
    notes_json: str,
) -> dict[str, Any]:
    tool_context.state["SPRINT_NOTES"] = notes_json
    logger.info("SPRINT_NOTES saved | %d chars", len(notes_json))
    return {"status": "success", "message": "Sprint notes saved to session state."}


def retrieve_sprint_notes(tool_context: ToolContext) -> dict[str, Any]:
    notes_json: str = tool_context.state.get("SPRINT_NOTES", "{}")
    logger.info("SPRINT_NOTES read | %d chars", len(notes_json))
    return {"status": "success", "notes_json": notes_json}
