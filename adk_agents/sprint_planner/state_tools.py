"""Session state tools (omnexis pattern; no `tools/` subpackage — ADK lists subdirs as apps)."""

from __future__ import annotations

import logging
from typing import Any

from google.adk.tools.tool_context import ToolContext

logger = logging.getLogger(__name__)


def store_sprint_context(
    tool_context: ToolContext,
    sprint_name: str,
    team: str,
    raw_message: str,
) -> dict[str, Any]:
    tool_context.state["SPRINT_NAME"] = sprint_name
    tool_context.state["TEAM"] = team
    tool_context.state["RAW_MESSAGE"] = raw_message
    logger.info("Sprint context saved | sprint=%s team=%s", sprint_name, team)
    return {"status": "success", "sprint_name": sprint_name, "team": team}


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
