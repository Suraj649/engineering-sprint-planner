"""
Sprint notes — Postgres when DATABASE_URL is set, else in-memory dict.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sprint_mcp import db as sprint_db

logger = logging.getLogger(__name__)

_store: dict[str, list[dict[str, Any]]] = {}


def write_note(sprint_id: str, content: str) -> dict[str, Any]:
    if sprint_db.is_configured():
        result = sprint_db.write_note_db(sprint_id, content)
        logger.info("write_note | db sprint=%s notes_count=%s", sprint_id, result.get("notes_count"))
        return result

    entry = {
        "sprint_id": sprint_id,
        "content": content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _store.setdefault(sprint_id, []).append(entry)
    logger.info("write_note | memory sprint=%s notes_count=%d", sprint_id, len(_store[sprint_id]))
    return {"status": "saved", "sprint_id": sprint_id, "notes_count": len(_store[sprint_id])}


def get_notes(sprint_id: str) -> list[dict[str, Any]]:
    if sprint_db.is_configured():
        notes = sprint_db.get_notes_db(sprint_id)
        logger.info("get_notes | db sprint=%s count=%d", sprint_id, len(notes))
        return notes

    notes = _store.get(sprint_id, [])
    logger.info("get_notes | memory sprint=%s count=%d", sprint_id, len(notes))
    return notes


def list_sprints() -> list[str]:
    if sprint_db.is_configured():
        return sprint_db.list_sprint_ids()
    return list(_store.keys())
