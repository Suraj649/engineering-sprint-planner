"""
Phase 2 API — Google Cloud Shell

  export PYTHONPATH=.:adk_agents
  cd ~/engineering-sprint-planner && source .venv/bin/activate
  # optional: export DATABASE_URL=postgresql+pg8000://...
  uvicorn sprint_api.main:app --host 0.0.0.0 --port 8080

Endpoints:
  GET  /health
  POST /v1/plan        JSON {"message":"...", "user_id":"optional"}
  GET  /v1/sprints/{sprint_id}/notes
  MCP  mounted at /mcp (streamable HTTP)
"""

from __future__ import annotations

import logging
import os
import sys
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel, Field

load_dotenv()

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_adk = os.path.join(_ROOT, "adk_agents")
if _adk not in sys.path:
    sys.path.insert(0, _adk)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from sprint_mcp.db import init_db_startup, shutdown_db

    await init_db_startup()
    yield
    await shutdown_db()


app = FastAPI(title="Engineering Sprint Planner API", version="2.0", lifespan=lifespan)

from sprint_mcp.mcp_connector import mcp_app

app.mount("/mcp", mcp_app.streamable_http_app())


class PlanRequest(BaseModel):
    message: str = Field(..., min_length=1)
    user_id: str = Field(default="api_user")


class PlanResponse(BaseModel):
    text: str
    session_id: str


@app.get("/health")
def health() -> dict:
    from sprint_mcp.db import database_backend, is_configured

    return {
        "status": "ok",
        "database": database_backend() if is_configured() else "off",
    }


@app.post("/v1/plan", response_model=PlanResponse)
async def plan(body: PlanRequest) -> PlanResponse:
    from google.adk.runners import InMemoryRunner
    from google.genai.types import Content, Part
    from sprint_planner.agent import root_agent

    runner = InMemoryRunner(agent=root_agent, app_name="sprint_planner_api")
    session = await runner.session_service.create_session(
        app_name="sprint_planner_api",
        user_id=body.user_id,
    )
    user_message = Content(role="user", parts=[Part(text=body.message)])

    texts: list[str] = []

    async for event in runner.run_async(
        user_id=body.user_id,
        session_id=session.id,
        new_message=user_message,
    ):
        if event.is_final_response():
            for part in event.content.parts or []:
                if part.text:
                    texts.append(part.text)

    return PlanResponse(text="\n\n".join(texts) if texts else "", session_id=session.id)


@app.get("/v1/sprints/{sprint_id}/notes")
def sprint_notes(sprint_id: str) -> dict:
    from sprint_mcp.notes_store import get_notes

    return {"sprint_id": sprint_id, "notes": get_notes(sprint_id)}
