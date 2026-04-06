"""Sprint calendar sub-agent (omnexis calendar_agent pattern)."""

from __future__ import annotations

import logging
import os

from google.adk import Agent

from sprint_planner.state_tools import retrieve_scaffolded_tasks, store_schedule

logger = logging.getLogger(__name__)

_MODEL: str = os.getenv("MODEL", "gemini-2.5-flash")
_WEEK_START: str = os.getenv("SPRINT_WEEK_START", "2026-04-07")

sprint_calendar_agent = Agent(
    name="sprint_calendar_agent",
    model=_MODEL,
    description=(
        "Maps estimated sprint stories to concrete calendar slots across the sprint week."
    ),
    instruction=f"""
You are the Sprint Calendar planner.

Anchor Monday for this sprint week: **{_WEEK_START}** (ISO date).
Consecutive weekdays: Mon +0, Tue +1, Wed +2, Thu +3, Fri +4, then skip weekend.

Steps:
1. Call `retrieve_scaffolded_tasks` to get `tasks_json`.

2. Assign **exactly one** calendar slot per story in order (same count as tasks).
   - Use working-day blocks; prefer morning focus: e.g. 09:00–12:00 or 09:00–13:00
     scaled lightly by estimated_hours (longer stories get longer blocks, max ~09:00–18:00).
   - Higher priority stories get earlier days in the week.
   - Reserve **Friday afternoon** for demo-related stories when the brief mentions a demo.

3. Each slot object must match this shape (same field names as omnexis CalendarSlot):
   {{
     "task_id"    : "<id from story>",
     "task_title" : "<title>",
     "start"      : "YYYY-MM-DDTHH:MM:00",
     "end"        : "YYYY-MM-DDTHH:MM:00",
     "notes"      : "SP=<points>; est <h>h"
   }}

4. Call `store_schedule` with the JSON array string as `schedule_json`.

5. After the tool succeeds, respond with ONLY this single line:
   "Sprint calendar complete — time blocks saved."
""",
    tools=[retrieve_scaffolded_tasks, store_schedule],
)

logger.debug("sprint_calendar_agent | model=%s week_start=%s", _MODEL, _WEEK_START)
