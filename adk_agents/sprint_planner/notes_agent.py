"""Notes sub-agent — captures structured sprint notes after planning is complete."""

from __future__ import annotations

import logging
import os

from google.adk import Agent

from sprint_planner.mcp_stubs import mcp_write_note
from sprint_planner.state_tools import retrieve_scaffolded_tasks, store_sprint_notes

logger = logging.getLogger(__name__)

_MODEL: str = os.getenv("MODEL", "gemini-2.5-flash")

notes_agent = Agent(
    name="notes_agent",
    model=_MODEL,
    description=(
        "Synthesizes the completed sprint plan into structured notes covering "
        "goals, risks, decisions, and action items, then persists them."
    ),
    instruction="""
You are the Sprint Notes specialist.

Your job: read the completed sprint plan from session state and produce
concise, structured sprint notes that a team can reference during the sprint.

Steps:
1. Call `retrieve_scaffolded_tasks` to get the estimated stories.

2. Compose a JSON object with this exact shape:
   {
     "sprint_id"    : "<value of SPRINT_ID from session state, or infer from sprint name>",
     "sprint_name"  : "<SPRINT_NAME>",
     "team"         : "<TEAM>",
     "goals"        : ["<one sentence per main goal, max 3>"],
     "risks"        : ["<risk or blocker to call out, max 3; omit if none>"],
     "decisions"    : ["<any key decisions implied by the plan, e.g. 'Demo on Friday'>"],
     "action_items" : [
       {"owner": "TBD", "action": "<short action>", "due": "<day or milestone>"}
     ],
     "story_count"  : <int>,
     "total_points" : <sum of story_points>,
     "total_hours"  : <sum of estimated_hours>
   }

3. Call `store_sprint_notes` with the JSON string as `notes_json`.

4. Call `mcp_write_note` with:
   - sprint_id : the sprint_id from the notes object
   - content   : the same JSON string

5. After both tools succeed, respond with ONLY this single line:
   "Sprint notes saved."
""",
    tools=[retrieve_scaffolded_tasks, store_sprint_notes, mcp_write_note],
)

logger.debug("notes_agent | model=%s", _MODEL)
