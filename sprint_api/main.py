"""
Phase 2 API — Engineering Sprint Planner

Cloud Shell:
  export PYTHONPATH=.:adk_agents
  source .venv/bin/activate
  ./scripts/run_api.sh
  # or: uvicorn sprint_api.main:app --host 0.0.0.0 --port 8080

Endpoints:
  GET  /health
  GET  /docs                 (Swagger — FastAPI default)
  POST /v1/plan              run full multi-agent pipeline; persists to DB
  GET  /v1/history/{id}      retrieve saved plan (mirrors omnexis /history/{session_id})
  GET  /v1/sprints/{id}/notes
  MCP tools at /mcp          (streamable HTTP — same as omnexis /mcp mount)
"""

from __future__ import annotations

import json
import logging
import os
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_adk = os.path.join(_ROOT, "adk_agents")
if _adk not in sys.path:
    sys.path.insert(0, _adk)

logger = logging.getLogger(__name__)

from sprint_mcp.mcp_connector import mcp_app


@asynccontextmanager
async def lifespan(app: FastAPI):
    from sprint_mcp.db import init_db_startup, shutdown_db

    await init_db_startup()

    # MCP session manager must be running for streamable HTTP transport
    # (same pattern as omnexis-repo backend/main.py)
    if not mcp_app.session_manager._has_started:
        async with mcp_app.session_manager.run():
            yield
    else:
        yield

    await shutdown_db()


app = FastAPI(
    title="Engineering Sprint Planner API",
    version="2.0",
    description=(
        "Multi-agent sprint planning: story breakdown → estimation → calendar → notes. "
        "MCP tools mounted at /mcp. History at /v1/history/{session_id}."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/mcp", mcp_app.streamable_http_app())


class PlanRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Sprint brain-dump text")
    user_id: str = Field(default="api_user")


class PlanResponse(BaseModel):
    text: str
    session_id: str
    sprint_id: str = ""
    persisted: bool = False


@app.get("/health", tags=["ops"])
def health() -> dict:
    from sprint_mcp.db import database_backend, is_configured

    return {
        "status": "ok",
        "database": database_backend() if is_configured() else "off",
    }


@app.post("/v1/plan", response_model=PlanResponse, tags=["planner"])
async def plan(body: PlanRequest) -> PlanResponse:
    """
    Run the full multi-agent sprint planning pipeline.

    Saves stories, calendar events, and notes to the database (when configured).
    Returns the agent's plain-text response plus a session_id for /v1/history.
    """
    from google.adk.runners import InMemoryRunner
    from google.genai.types import Content, Part
    from sprint_mcp.db import is_configured, save_plan_session
    from sprint_planner.agent import root_agent

    runner = InMemoryRunner(agent=root_agent, app_name="sprint_planner_api")
    adk_session = await runner.session_service.create_session(
        app_name="sprint_planner_api",
        user_id=body.user_id,
    )

    user_message = Content(role="user", parts=[Part(text=body.message)])
    texts: list[str] = []

    async for event in runner.run_async(
        user_id=body.user_id,
        session_id=adk_session.id,
        new_message=user_message,
    ):
        if event.is_final_response():
            for part in event.content.parts or []:
                if part.text:
                    texts.append(part.text)

    response_text = "\n\n".join(texts) if texts else ""

    # Read structured state that sub-agents stored in session
    state: dict = {}
    try:
        state = await runner.session_service.get_session(
            app_name="sprint_planner_api",
            user_id=body.user_id,
            session_id=adk_session.id,
        )
        state = state.state if state else {}
    except Exception:
        logger.exception("Could not read ADK session state")

    sprint_id: str = state.get("SPRINT_ID", "")
    sprint_name: str = state.get("SPRINT_NAME", "")
    team: str = state.get("TEAM", "")

    tasks: list[dict] = []
    events: list[dict] = []
    try:
        raw_tasks = state.get("SCAFFOLDED_TASKS", "[]")
        tasks = json.loads(raw_tasks) if isinstance(raw_tasks, str) else raw_tasks
        raw_events = state.get("SCHEDULE", "[]")
        events = json.loads(raw_events) if isinstance(raw_events, str) else raw_events
    except Exception:
        logger.exception("Could not parse state JSON for persistence")

    persisted = False
    if is_configured() and sprint_id:
        try:
            save_plan_session(
                session_id=adk_session.id,
                user_input=body.message,
                sprint_id=sprint_id,
                sprint_name=sprint_name,
                team=team,
                summary_text=response_text[:2000],
                tasks=tasks,
                events=events,
            )
            persisted = True
        except Exception:
            logger.exception("save_plan_session failed — response still returned")

    return PlanResponse(
        text=response_text,
        session_id=adk_session.id,
        sprint_id=sprint_id,
        persisted=persisted,
    )


@app.get("/v1/history/{session_id}", tags=["planner"])
def history(session_id: str) -> dict:
    """
    Retrieve a saved sprint plan by session_id.
    Mirrors omnexis-repo GET /history/{session_id}.
    """
    from sprint_mcp.db import get_plan_session, is_configured

    if not is_configured():
        raise HTTPException(status_code=503, detail="Database not configured — no history available.")

    result = get_plan_session(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id!r} not found.")
    return result


@app.get("/v1/sprints/{sprint_id}/notes", tags=["planner"])
def sprint_notes(sprint_id: str) -> dict:
    from sprint_mcp.notes_store import get_notes

    return {"sprint_id": sprint_id, "notes": get_notes(sprint_id)}
