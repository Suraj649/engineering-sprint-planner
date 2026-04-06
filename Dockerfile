FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app:/app/adk_agents

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY adk_agents/ ./adk_agents/
COPY sprint_mcp/ ./sprint_mcp/
COPY sprint_api/ ./sprint_api/
COPY scripts/ ./scripts/

EXPOSE 8080

CMD ["uvicorn", "sprint_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
