# Engineering Sprint Planner

Multi-agent sprint flow adapted from [omnexis-repo](../omnexis-repo): story breakdown → estimation → sprint calendar, plus stubs for Jira/Linear, GitHub, and Google Calendar.

## ADK layout (important)

Google ADK treats **every subdirectory** of the agents directory as a **separate app** and imports it by folder name (e.g. `tools`, `subagents`). That broke the old layout where code lived under `agents/tools/` — Python loaded `tools` as a top-level module and `from agents.tools...` failed with `No module named 'agents'`.

This project uses:

```
engineering-sprint-planner/
  adk_agents/              ← pass THIS dir to `adk web`
    sprint_planner/        ← single app; only `.py` files (no subfolders)
      agent.py             ← root_agent
      master_agent.py
      state_tools.py
      mcp_stubs.py
      ...
```

## Run locally

```bash
cd engineering-sprint-planner
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
adk web adk_agents
```

In the UI, choose the **`sprint_planner`** app (not `tools` — that layout no longer exists).

## Example input

> Sprint starts Monday, we need to finish auth module, fix 3 bugs, write tests, and do a demo Friday

## Environment

| Variable | Purpose |
|----------|---------|
| `MODEL` | Gemini model id (default `gemini-2.5-flash`) |
| `SPRINT_WEEK_START` | ISO Monday for calendar hints (default `2026-04-07`) |
| `LOG_LEVEL` | Logging verbosity |

## Phase 2 — REST API + optional Postgres

```bash
export PYTHONPATH=.:adk_agents
./scripts/phase2_run_api.sh
# or: uvicorn sprint_api.main:app --host 0.0.0.0 --port 8080
```

- `GET /health` — liveness + whether `DATABASE_URL` is set  
- `POST /v1/plan` — body `{"message":"..."}` runs the full agent pipeline  
- `GET /v1/sprints/{sprint_id}/notes` — notes (DB if `DATABASE_URL`, else in-memory)  
- MCP tools mounted at `/mcp`

Set `DATABASE_URL=postgresql+pg8000://...` for Cloud SQL / AlloyDB (tables created on startup).

## Wire real integrations

Edit `adk_agents/sprint_planner/mcp_stubs.py` and keep the same function signatures. For Calendar, see `omnexis-repo/omniwork_mcp/google_clients/calendar.py`.
