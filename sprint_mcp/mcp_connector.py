"""
Sprint MCP — FastMCP server.

Exposes sprint planner tools over the MCP protocol (streamable HTTP).
Used by the FastAPI backend in Phase 2; agents call the underlying
functions directly rather than going through the MCP protocol layer.

Run standalone (for testing):
    uvicorn sprint_mcp.mcp_connector:mcp_app --port 8001

Mount inside FastAPI (Phase 2):
    app.mount("/mcp", mcp_app.streamable_http_app())
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from sprint_mcp.azure_clients.boards import push_stories
from sprint_mcp.notes_store import get_notes, write_note

mcp_app = FastMCP("SprintPlanner", stateless_http=True)


# ── Tracker ────────────────────────────────────────────────────────────────────

@mcp_app.tool()
def mcp_push_tracker(stories_json: str) -> dict:
    """
    Create Azure DevOps work items from an EstimatedStory[] JSON string.

    Args:
        stories_json: JSON array of EstimatedStory objects.
            Fields: id, title, description, issue_type, priority,
                    story_points, estimated_hours, due.
    """
    return push_stories(stories_json)


# ── Calendar (stub — wire to google_clients/calendar.py after credentials) ─────

@mcp_app.tool()
def mcp_block_calendar(slots_json: str) -> dict:
    """
    Block calendar slots from a CalendarSlot[] JSON string.

    Args:
        slots_json: JSON array of CalendarSlot objects.
            Fields: task_id, task_title, start (ISO 8601), end (ISO 8601), notes.

    Note: Wired to Google Calendar once GOOGLE_CLIENT_ID / GOOGLE_REFRESH_TOKEN
    are configured. Returns stub response until then.
    """
    try:
        count = len(json.loads(slots_json)) if slots_json else 0
    except Exception:
        count = 0
    return {
        "status": "stub",
        "slots_booked": count,
        "message": "Calendar stub — set GOOGLE_CLIENT_ID and GOOGLE_REFRESH_TOKEN to enable.",
    }


# ── GitHub (stub — wire to GitHub Issues API) ──────────────────────────────────

@mcp_app.tool()
def mcp_push_github(stories_json: str) -> dict:
    """
    Mirror sprint stories as GitHub Issues.

    Args:
        stories_json: JSON array of EstimatedStory objects.

    Note: Stub until GITHUB_TOKEN and GITHUB_REPO are configured.
    """
    try:
        count = len(json.loads(stories_json)) if stories_json else 0
    except Exception:
        count = 0
    return {
        "status": "stub",
        "issues_created": count,
        "message": "GitHub stub — set GITHUB_TOKEN and GITHUB_REPO to enable.",
    }


# ── Notes ──────────────────────────────────────────────────────────────────────

@mcp_app.tool()
def mcp_write_note(sprint_id: str, content: str) -> dict:
    """
    Persist a sprint note.

    Args:
        sprint_id: Identifier for the sprint (e.g. "sprint_auth_001").
        content:   Note content — plain text or markdown.
    """
    return write_note(sprint_id, content)


@mcp_app.tool()
def mcp_get_notes(sprint_id: str) -> list[dict]:
    """
    Retrieve all notes for a sprint.

    Args:
        sprint_id: Identifier for the sprint.
    """
    return get_notes(sprint_id)
