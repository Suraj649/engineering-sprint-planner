"""
ADK tool wrappers for the sprint planner MCP layer.

Each function here is an ADK tool (accepts ToolContext) that delegates to
sprint_mcp/ for the actual business logic. This keeps ToolContext out of
the pure-Python MCP layer.

  mcp_push_tracker   → sprint_mcp/azure_clients/boards.py  (real Azure DevOps)
  mcp_push_github    → stub (wire to GitHub Issues API when ready)
  mcp_block_calendar → sprint_mcp/mcp_connector.py stub (real after Google creds)
  mcp_write_note     → sprint_mcp/notes_store.py (Postgres if DATABASE_URL)
  db_create_sprint   → sprint_mcp/db.py (AlloyDB or DATABASE_URL) else session-only id
"""

from __future__ import annotations

import json
import logging
from typing import Any

from google.adk.tools.tool_context import ToolContext

logger = logging.getLogger(__name__)

_AUDIT_KEY = "MCP_AUDIT_LOG"


# ── Private helpers ────────────────────────────────────────────────────────────

def _audit(tool_context: ToolContext, action: str) -> None:
    log: list[str] = tool_context.state.get(_AUDIT_KEY, [])
    log.append(action)
    tool_context.state[_AUDIT_KEY] = log


def _parse_count(json_str: str) -> int:
    try:
        parsed = json.loads(json_str)
        return len(parsed) if isinstance(parsed, list) else 1
    except (json.JSONDecodeError, TypeError):
        return 0


# ── DB sprint (Postgres when DATABASE_URL set) ─────────────────────────────────

def db_create_sprint(
    tool_context: ToolContext,
    sprint_name: str,
    team: str,
) -> dict[str, Any]:
    from sprint_mcp import db as sprint_db

    sprint_id = f"sprint_{sprint_name[:12].lower().replace(' ', '_')}_001"
    tool_context.state["SPRINT_ID"] = sprint_id
    if sprint_db.is_configured():
        sprint_db.insert_sprint(sprint_id, sprint_name, team)
        _audit(tool_context, f"db_create_sprint({sprint_name!r}, {team!r}) [postgres]")
        logger.info("db_create_sprint | id=%s persisted", sprint_id)
    else:
        _audit(tool_context, f"db_create_sprint({sprint_name!r}, {team!r}) [memory]")
        logger.info("db_create_sprint | id=%s (no DATABASE_URL)", sprint_id)
    return {
        "status": "created",
        "sprint_id": sprint_id,
        "sprint_name": sprint_name,
        "team": team,
    }


# ── Azure DevOps Boards ────────────────────────────────────────────────────────

def mcp_push_tracker(
    tool_context: ToolContext,
    stories_json: str,
) -> dict[str, Any]:
    """Create one Azure DevOps work item per estimated story."""
    from sprint_mcp.azure_clients.boards import push_stories
    result = push_stories(stories_json)
    _audit(tool_context, f"mcp_push_tracker({result.get('issues_created', 0)} items, status={result.get('status')})")
    return result


# ── GitHub stub ────────────────────────────────────────────────────────────────

def mcp_push_github(
    tool_context: ToolContext,
    stories_json: str,
) -> dict[str, Any]:
    """[STUB → GitHub Issues API] Wire GITHUB_TOKEN + GITHUB_REPO when ready."""
    count = _parse_count(stories_json)
    _audit(tool_context, f"mcp_push_github({count} issues) [STUB]")
    logger.info("mcp_push_github | count=%d", count)
    return {"status": "stub", "issues_created": count}


# ── Google Calendar (stub until Google credentials are configured) ─────────────

def mcp_block_calendar(
    tool_context: ToolContext,
    slots_json: str,
) -> dict[str, Any]:
    """[STUB → Google Calendar API] Set GOOGLE_CLIENT_ID + GOOGLE_REFRESH_TOKEN to enable."""
    from sprint_mcp.mcp_connector import mcp_block_calendar as _mcp_block_calendar
    result = _mcp_block_calendar(slots_json)
    _audit(tool_context, f"mcp_block_calendar({_parse_count(slots_json)} slots)")
    logger.info("mcp_block_calendar | slots=%d status=%s", _parse_count(slots_json), result.get("status"))
    return result


# ── Notes ──────────────────────────────────────────────────────────────────────

def mcp_write_note(
    tool_context: ToolContext,
    sprint_id: str,
    content: str,
) -> dict[str, Any]:
    """Persist a sprint note (Postgres if DATABASE_URL; else in-memory)."""
    from sprint_mcp.notes_store import write_note
    result = write_note(sprint_id, content)
    _audit(tool_context, f"mcp_write_note({sprint_id!r})")
    logger.info("mcp_write_note | sprint=%s", sprint_id)
    return result
