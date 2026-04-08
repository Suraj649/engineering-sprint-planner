# Engineering Sprint Planner

> **Python 3.10+ required.** All dependencies (`google-adk`, `mcp`, etc.) require Python ≥ 3.10. The Dockerfile uses Python 3.12.

**Branch:** this repo’s default branch is `feat/sprint_planner` (there is no separate `main`). After `git clone`, run `git checkout feat/sprint_planner && git pull` so you have the latest code.

**Phase 2** (REST API + optional Postgres) lives in: `sprint_api/`, `sprint_mcp/db.py`, `Dockerfile`, `scripts/run_api.sh`. If those folders are missing locally, your clone is stale — `git pull origin feat/sprint_planner`.

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
  sprint_api/              ← Phase 2 FastAPI (`main.py`)
  sprint_mcp/
    db.py                  ← Phase 2 Postgres (optional DATABASE_URL)
  Dockerfile
  scripts/run_api.sh
```

## Run locally

```bash
cd engineering-sprint-planner
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# PYTHONPATH must include the project root so sprint_mcp is importable from agent tools
PYTHONPATH=. adk web adk_agents
```

In the UI, choose the **`sprint_planner`** app (not `tools` — that layout no longer exists).

## Example input

> Sprint starts Monday, we need to finish auth module, fix 3 bugs, write tests, and do a demo Friday

## Environment

| Variable | Required | Purpose |
|----------|----------|---------|
| `GOOGLE_API_KEY` or `GEMINI_API_KEY` | **Yes** | Gemini API key (get from [aistudio.google.com](https://aistudio.google.com)) |
| `MODEL` | No | Gemini model id (default `gemini-2.5-flash`) |
| `SPRINT_WEEK_START` | No | ISO Monday for calendar hints (default `2026-04-07`) |
| `LOG_LEVEL` | No | Logging verbosity (`debug`/`info`/`warning`) |
| `AZURE_DEVOPS_PAT` | No | Personal Access Token — enables real Azure DevOps push (stub otherwise) |
| `AZURE_DEVOPS_ORG` | No | Azure DevOps organisation slug |
| `AZURE_DEVOPS_PROJECT` | No | Azure DevOps project name |
| `DATABASE_URL` | No | Postgres connection string — enables plan persistence |

## Phase 2 — REST API + optional Postgres

```bash
export PYTHONPATH=.:adk_agents
./scripts/run_api.sh
# or: uvicorn sprint_api.main:app --host 0.0.0.0 --port 8080
```

- `GET /health` — liveness + active database backend  
- `POST /v1/plan` — body `{"message":"...","user_id":"..."}` — runs the full agent pipeline; returns `text`, `session_id`, `sprint_id`, `persisted`  
- `GET /v1/history/{session_id}` — retrieve a saved plan by session ID (requires `DATABASE_URL`)  
- `GET /v1/sprints/{sprint_id}/notes` — sprint notes (DB if `DATABASE_URL`, else in-memory)  
- MCP tools mounted at `/mcp` (streamable HTTP)

**Database (choose one):**

- **AlloyDB** (same approach as `omnexis-repo/backend/db.py`): set `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `ALLOYDB_CLUSTER`, `ALLOYDB_INSTANCE`, `ALLOYDB_USER`, `ALLOYDB_PASSWORD`, `ALLOYDB_DATABASE`. Uses `google-cloud-alloydb-connector` + `asyncpg`. Requires Application Default Credentials with access to the cluster.

- **Postgres URL:** set `DATABASE_URL=postgresql+pg8000://...` (e.g. Cloud SQL via proxy). If AlloyDB env vars are fully set, AlloyDB wins over `DATABASE_URL`.

Tables `sprints` and `sprint_notes` are created on API startup.

## Wire real integrations

Edit `adk_agents/sprint_planner/mcp_stubs.py` and keep the same function signatures. For Calendar, see `omnexis-repo/omniwork_mcp/google_clients/calendar.py`.
