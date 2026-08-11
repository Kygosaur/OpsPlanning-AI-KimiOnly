FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY planning_agent/ ./planning_agent/
COPY scripts/ ./scripts/
COPY tests/ ./tests/

RUN mkdir -p /app/data /app/documents /app/outputs \
    && useradd --create-home --uid 10001 planner \
    && chown -R planner:planner /app

USER planner

ENTRYPOINT ["python", "-m", "planning_agent.cli"]
CMD ["--help"]
